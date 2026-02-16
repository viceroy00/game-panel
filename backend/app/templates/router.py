import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import User, GameConfigTemplate
from app.auth.deps import require_admin, get_current_user

router = APIRouter(prefix="/api/templates", tags=["설정 양식"])

UPLOAD_DIR = "/app/data/uploads/templates"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("/")
async def list_templates(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GameConfigTemplate).order_by(GameConfigTemplate.game_name)
    )
    templates = result.scalars().all()
    return [
        {
            "id": t.id,
            "game_name": t.game_name,
            "filename": t.filename,
            "created_at": t.created_at.isoformat(),
        }
        for t in templates
    ]


@router.post("/")
async def upload_template(
    game_name: str = Form(...),
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "엑셀 파일(.xlsx, .xls)만 업로드 가능합니다")

    existing = await db.execute(
        select(GameConfigTemplate).where(GameConfigTemplate.game_name == game_name)
    )
    old = existing.scalar_one_or_none()
    if old:
        old_path = os.path.join(UPLOAD_DIR, f"{old.id}_{old.filename}")
        if os.path.exists(old_path):
            os.remove(old_path)
        await db.delete(old)

    template = GameConfigTemplate(
        game_name=game_name,
        filename=file.filename,
        uploaded_by=admin.id,
    )
    db.add(template)
    await db.flush()

    save_path = os.path.join(UPLOAD_DIR, f"{template.id}_{file.filename}")
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    await db.commit()
    return {"message": f"'{game_name}' 설정 양식 업로드 완료", "id": template.id}


@router.get("/{template_id}/download")
async def download_template(
    template_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GameConfigTemplate).where(GameConfigTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(404, "양식을 찾을 수 없습니다")

    file_path = os.path.join(UPLOAD_DIR, f"{template.id}_{template.filename}")
    if not os.path.exists(file_path):
        raise HTTPException(404, "파일이 존재하지 않습니다")

    return FileResponse(file_path, filename=template.filename, media_type="application/octet-stream")


@router.get("/by-game/{game_name}")
async def get_template_by_game(
    game_name: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GameConfigTemplate).where(GameConfigTemplate.game_name == game_name)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(404, "해당 게임의 설정 양식이 없습니다")
    return {
        "id": template.id,
        "game_name": template.game_name,
        "filename": template.filename,
    }


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GameConfigTemplate).where(GameConfigTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(404, "양식을 찾을 수 없습니다")

    file_path = os.path.join(UPLOAD_DIR, f"{template.id}_{template.filename}")
    if os.path.exists(file_path):
        os.remove(file_path)

    await db.delete(template)
    await db.commit()
    return {"message": f"'{template.game_name}' 설정 양식 삭제 완료"}
