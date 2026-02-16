"""
범용 파일 탐색기 라우터
- 컨테이너 내부 파일 시스템을 웹에서 탐색/편집/업로드/다운로드
- RBAC: "files" 액션 권한 필요
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import io

from app.auth.deps import get_current_user
from app.rbac.deps import RequirePermission
from app.db.models import User
from app.files.service import (
    list_files, read_file, write_file, upload_file,
    download_file, delete_path, create_directory, rename_path,
)

router = APIRouter(prefix="/api/containers/{container_name}/files", tags=["파일 관리"])


class WriteFileRequest(BaseModel):
    path: str
    content: str


class CreateDirRequest(BaseModel):
    path: str


class RenameRequest(BaseModel):
    old_path: str
    new_name: str


class DeleteRequest(BaseModel):
    path: str


# ─── 파일 목록 ───

@router.get("")
async def api_list_files(
    container_name: str,
    path: str = Query(default="/", description="조회할 경로"),
    user: User = Depends(RequirePermission("files")),
):
    """디렉토리 내용 조회"""
    try:
        files = list_files(container_name, path)
        return {"path": path, "files": files, "count": len(files)}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── 파일 읽기 (텍스트 편집) ───

@router.get("/read")
async def api_read_file(
    container_name: str,
    path: str = Query(...),
    user: User = Depends(RequirePermission("files")),
):
    """텍스트 파일 내용 읽기 (웹 에디터용)"""
    try:
        return read_file(container_name, path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── 파일 저장 ───

@router.put("/write")
async def api_write_file(
    container_name: str,
    req: WriteFileRequest,
    user: User = Depends(RequirePermission("files")),
):
    """텍스트 파일 저장"""
    try:
        write_file(container_name, req.path, req.content)
        return {"message": "파일이 저장되었습니다", "path": req.path}
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── 파일 업로드 ───

@router.post("/upload")
async def api_upload_file(
    container_name: str,
    dest_dir: str = Query(default="/", description="업로드 대상 디렉토리"),
    file: UploadFile = File(...),
    user: User = Depends(RequirePermission("files")),
):
    """파일 업로드 (드래그앤드롭)"""
    try:
        file_data = await file.read()
        result = upload_file(container_name, dest_dir, file.filename or "upload", file_data)
        return {"message": "업로드 완료", **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── 파일 다운로드 ───

@router.get("/download")
async def api_download_file(
    container_name: str,
    path: str = Query(...),
    user: User = Depends(RequirePermission("files")),
):
    """파일 다운로드"""
    try:
        data, filename = download_file(container_name, path)
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── 디렉토리 생성 ───

@router.post("/mkdir")
async def api_create_dir(
    container_name: str,
    req: CreateDirRequest,
    user: User = Depends(RequirePermission("files")),
):
    """디렉토리 생성"""
    try:
        create_directory(container_name, req.path)
        return {"message": "디렉토리가 생성되었습니다", "path": req.path}
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── 이름 변경 ───

@router.put("/rename")
async def api_rename(
    container_name: str,
    req: RenameRequest,
    user: User = Depends(RequirePermission("files")),
):
    """파일/디렉토리 이름 변경"""
    try:
        new_path = rename_path(container_name, req.old_path, req.new_name)
        return {"message": "이름이 변경되었습니다", "new_path": new_path}
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── 삭제 ───

@router.delete("/delete")
async def api_delete(
    container_name: str,
    path: str = Query(...),
    user: User = Depends(RequirePermission("files")),
):
    """파일/디렉토리 삭제"""
    try:
        delete_path(container_name, path)
        return {"message": "삭제되었습니다", "path": path}
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
