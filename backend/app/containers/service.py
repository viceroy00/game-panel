import docker
from docker.errors import NotFound, APIError
from typing import Optional
from app.config import get_settings

settings = get_settings()

_client: Optional[docker.DockerClient] = None


def get_docker_client() -> docker.DockerClient:
    """Docker 클라이언트 — Windows/Linux 자동 감지"""
    global _client
    if _client is None:
        _client = docker.DockerClient(base_url=settings.docker_base_url)
        # 연결 테스트
        _client.ping()
    return _client


def _is_managed_container(container) -> bool:
    """관리 대상 컨테이너인지 확인 (이중 검증)"""
    labels = container.labels or {}

    # 조건 1: game-panel.managed=true 라벨
    if labels.get("game-panel.managed") != "true":
        return False

    # 조건 2: game-servers 네트워크에 연결되어 있는지
    networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
    if settings.game_network not in networks:
        return False

    return True


def list_game_containers() -> list[dict]:
    """
    game-panel.managed=true 라벨 + game-servers 네트워크에 속한 컨테이너만 조회
    기존 서비스 컨테이너는 절대 포함되지 않음
    """
    client = get_docker_client()

    # 라벨 필터로 1차 필터링
    containers = client.containers.list(
        all=True,
        filters={"label": "game-panel.managed=true"}
    )

    result = []
    for c in containers:
        # 네트워크 필터로 2차 필터링 (기존 서비스 격리 보장)
        if not _is_managed_container(c):
            continue

        info = {
            "name": c.name,
            "id": c.short_id,
            "image": c.image.tags[0] if c.image.tags else c.image.short_id,
            "status": c.status,
            "state": c.attrs["State"]["Status"],
            "created": c.attrs["Created"],
            "ports": c.ports or {},
            "labels": c.labels or {},
        }

        result.append(info)

    return result


def get_container_stats(name: str) -> dict:
    """개별 컨테이너 리소스 사용량 조회 (CPU/메모리)"""
    container = get_container(name)
    info = {}

    if container.status == "running":
        try:
            stats = container.stats(stream=False)
            cpu_delta = (
                stats["cpu_stats"]["cpu_usage"]["total_usage"]
                - stats["precpu_stats"]["cpu_usage"]["total_usage"]
            )
            system_delta = (
                stats["cpu_stats"]["system_cpu_usage"]
                - stats["precpu_stats"]["system_cpu_usage"]
            )
            cpu_count = stats["cpu_stats"].get("online_cpus", 1)
            if system_delta > 0:
                info["cpu_percent"] = round((cpu_delta / system_delta) * cpu_count * 100, 2)

            mem_usage = stats["memory_stats"].get("usage", 0)
            mem_limit = stats["memory_stats"].get("limit", 0)
            info["memory_usage"] = f"{mem_usage / 1024 / 1024:.1f}MB"
            info["memory_limit"] = f"{mem_limit / 1024 / 1024:.1f}MB"
        except (KeyError, APIError):
            pass

    return info


def get_container(name: str):
    """관리 대상 컨테이너만 반환 — 기존 서비스 접근 차단"""
    client = get_docker_client()
    try:
        container = client.containers.get(name)
        if not _is_managed_container(container):
            raise NotFound(f"'{name}'은(는) 관리 대상이 아니거나 격리 네트워크에 없습니다")
        return container
    except NotFound:
        raise


def container_action(name: str, action: str) -> str:
    """컨테이너 액션 수행 (관리 대상만)"""
    container = get_container(name)

    if action == "start":
        container.start()
        return f"{name} 시작됨"
    elif action == "stop":
        container.stop(timeout=30)
        return f"{name} 정지됨"
    elif action == "restart":
        container.restart(timeout=30)
        return f"{name} 재시작됨"
    elif action == "kill":
        container.kill()
        return f"{name} 강제 종료됨"
    else:
        raise ValueError(f"알 수 없는 액션: {action}")


def remove_container(name: str, force: bool = False) -> str:
    """컨테이너 삭제 (관리 대상만)"""
    container = get_container(name)
    container.remove(force=force, v=False)  # 볼륨은 보존
    return f"{name} 삭제됨 (볼륨 보존)"


def get_container_logs(name: str, tail: int = 100) -> str:
    """컨테이너 로그 조회"""
    container = get_container(name)
    return container.logs(tail=tail, timestamps=True).decode("utf-8", errors="replace")


def ensure_game_network():
    """game-servers 네트워크가 없으면 생성"""
    client = get_docker_client()
    try:
        client.networks.get(settings.game_network)
    except NotFound:
        client.networks.create(
            settings.game_network,
            driver="bridge",
            labels={"game-panel.network": "true"},
            ipam=docker.types.IPAMConfig(
                pool_configs=[docker.types.IPAMPool(subnet="172.30.0.0/16")]
            ),
        )
        print(f"[INIT] '{settings.game_network}' 네트워크 생성됨")
