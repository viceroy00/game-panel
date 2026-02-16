"""
범용 파일 탐색기 서비스
- Docker exec으로 컨테이너 내부 파일 조회/편집
- Docker SDK의 put_archive/get_archive로 업로드/다운로드
- 게임을 몰라도 동작하는 범용 파일 관리
"""

import io
import tarfile
import posixpath
from docker.errors import NotFound
from app.containers.service import get_container
from app.config import get_settings

settings = get_settings()

FORBIDDEN_PATHS = ["/proc", "/sys", "/dev", "/run", "/boot", "/sbin", "/usr/sbin"]


def _validate_path(path: str) -> str:
    path = posixpath.normpath(path)
    if not path.startswith("/"):
        path = "/" + path
    if ".." in path.split("/"):
        raise ValueError("잘못된 경로입니다")
    for forbidden in FORBIDDEN_PATHS:
        if path == forbidden or path.startswith(forbidden + "/"):
            raise ValueError(f"접근이 차단된 경로입니다: {forbidden}")
    return path


def _format_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f}{unit}" if unit != "B" else f"{size}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def _sanitize_filename(name: str) -> str:
    name = name.replace("/", "_").replace("\\", "_").replace("..", "_")
    name = "".join(c for c in name if c.isalnum() or c in "._- ()")
    return name or "unnamed"


# ─── 파일 목록 ───

def list_files(container_name: str, path: str = "/") -> list[dict]:
    path = _validate_path(path)
    container = get_container(container_name)

    # GNU ls 시도 → 실패 시 BusyBox ls 폴백
    exit_code, output = container.exec_run(
        ["ls", "-la", "--time-style=+%Y-%m-%d %H:%M:%S", path],
        demux=True,
    )
    gnu_mode = True
    if exit_code != 0:
        stderr = output[1].decode("utf-8", errors="replace") if output[1] else ""
        if "unrecognized option" in stderr or "invalid option" in stderr:
            # BusyBox 폴백
            exit_code, output = container.exec_run(
                ["ls", "-la", path],
                demux=True,
            )
            gnu_mode = False
            if exit_code != 0:
                stderr2 = output[1].decode("utf-8", errors="replace") if output[1] else ""
                raise FileNotFoundError(stderr2 or f"경로를 찾을 수 없습니다: {path}")
        else:
            raise FileNotFoundError(stderr or f"경로를 찾을 수 없습니다: {path}")

    stdout = output[0].decode("utf-8", errors="replace") if output[0] else ""

    files = []
    for line in stdout.strip().split("\n"):
        if not line or line.startswith("total"):
            continue

        if gnu_mode:
            # GNU ls: perms links owner group size date time name
            parts = line.split(None, 7)
            if len(parts) < 8:
                continue
            perms, _, owner, group, size, date, time_str, name = parts
            modified = f"{date} {time_str}"
        else:
            # BusyBox ls: perms links owner group size Mon DD HH:MM name
            # 또는:       perms links owner group size Mon DD  YYYY name
            parts = line.split(None, 8)
            if len(parts) < 9:
                continue
            perms, _, owner, group, size, mon, dd, time_or_year, name = parts
            modified = f"{mon} {dd} {time_or_year}"

        if name in (".", ".."):
            continue

        real_name = name.split(" -> ")[0] if " -> " in name else name
        is_dir = perms.startswith("d")

        try:
            size_int = int(size)
        except ValueError:
            size_int = 0

        files.append({
            "name": real_name,
            "path": posixpath.join(path, real_name),
            "is_dir": is_dir,
            "is_link": perms.startswith("l"),
            "size": size_int if not is_dir else 0,
            "size_display": _format_size(size_int) if not is_dir else "-",
            "permissions": perms,
            "owner": owner,
            "modified": modified,
        })

    files.sort(key=lambda f: (not f["is_dir"], f["name"].lower()))
    return files


# ─── 파일 읽기 (텍스트 편집) ───

def read_file(container_name: str, path: str, max_size: int = 1024 * 1024) -> dict:
    path = _validate_path(path)
    container = get_container(container_name)

    exit_code, output = container.exec_run(["stat", "-c", "%s", path], demux=True)
    if exit_code != 0:
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

    file_size = int(output[0].decode().strip())
    if file_size > max_size:
        raise ValueError(f"파일이 너무 큽니다 ({_format_size(file_size)}). 최대 {_format_size(max_size)}")

    exit_code, output = container.exec_run(["cat", path], demux=True)
    if exit_code != 0:
        stderr = output[1].decode("utf-8", errors="replace") if output[1] else ""
        raise FileNotFoundError(stderr)

    content = output[0].decode("utf-8", errors="replace") if output[0] else ""
    return {"path": path, "content": content, "size": file_size}


# ─── 파일 저장 ───

def write_file(container_name: str, path: str, content: str):
    path = _validate_path(path)
    container = get_container(container_name)
    dir_path = posixpath.dirname(path)
    file_name = posixpath.basename(path)

    data = content.encode("utf-8")
    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode="w") as tar:
        info = tarfile.TarInfo(name=file_name)
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    tar_stream.seek(0)
    container.put_archive(dir_path, tar_stream)


# ─── 파일 업로드 ───

def upload_file(container_name: str, dest_dir: str, filename: str, file_data: bytes) -> dict:
    dest_dir = _validate_path(dest_dir)
    container = get_container(container_name)

    max_bytes = settings.max_mod_upload_size_mb * 1024 * 1024
    if len(file_data) > max_bytes:
        raise ValueError(f"파일이 너무 큽니다. 최대 {settings.max_mod_upload_size_mb}MB")

    safe_name = _sanitize_filename(filename)

    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode="w") as tar:
        info = tarfile.TarInfo(name=safe_name)
        info.size = len(file_data)
        tar.addfile(info, io.BytesIO(file_data))
    tar_stream.seek(0)
    container.put_archive(dest_dir, tar_stream)

    return {
        "filename": safe_name,
        "path": posixpath.join(dest_dir, safe_name),
        "size": len(file_data),
    }


# ─── 파일 다운로드 ───

def download_file(container_name: str, path: str) -> tuple[bytes, str]:
    path = _validate_path(path)
    container = get_container(container_name)

    try:
        bits, stat = container.get_archive(path)
    except NotFound:
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

    tar_stream = io.BytesIO()
    for chunk in bits:
        tar_stream.write(chunk)
    tar_stream.seek(0)

    with tarfile.open(fileobj=tar_stream, mode="r") as tar:
        member = tar.getmembers()[0]
        f = tar.extractfile(member)
        if f is None:
            raise ValueError("디렉토리는 다운로드할 수 없습니다")
        data = f.read()

    return data, posixpath.basename(path)


# ─── 삭제 ───

def delete_path(container_name: str, path: str):
    path = _validate_path(path)
    if path in ("/", "/data", "/home"):
        raise ValueError("루트 경로는 삭제할 수 없습니다")
    container = get_container(container_name)
    exit_code, output = container.exec_run(["rm", "-rf", path], demux=True)
    if exit_code != 0:
        stderr = output[1].decode("utf-8", errors="replace") if output[1] else ""
        raise RuntimeError(f"삭제 실패: {stderr}")


# ─── 디렉토리 생성 ───

def create_directory(container_name: str, path: str):
    path = _validate_path(path)
    container = get_container(container_name)
    exit_code, output = container.exec_run(["mkdir", "-p", path], demux=True)
    if exit_code != 0:
        stderr = output[1].decode("utf-8", errors="replace") if output[1] else ""
        raise RuntimeError(f"디렉토리 생성 실패: {stderr}")


# ─── 이름 변경 ───

def rename_path(container_name: str, old_path: str, new_name: str) -> str:
    old_path = _validate_path(old_path)
    new_name = _sanitize_filename(new_name)
    new_path = posixpath.join(posixpath.dirname(old_path), new_name)
    container = get_container(container_name)
    exit_code, output = container.exec_run(["mv", old_path, new_path], demux=True)
    if exit_code != 0:
        stderr = output[1].decode("utf-8", errors="replace") if output[1] else ""
        raise RuntimeError(f"이름 변경 실패: {stderr}")
    return new_path
