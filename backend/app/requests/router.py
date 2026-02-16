import os
import shutil
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.db.session import get_db
from app.db.models import User, GameRequest, REQUEST_STAGES, REQUEST_STAGE_LABELS
from app.auth.deps import get_current_user, require_admin, require_discord_role
from app.requests.schemas import GameRequestResponse, GameRequestReview
from app.mail.service import send_game_request_notification, send_stage_notification
from app.discord.notify import notify_game_request, notify_request_stage_change

router = APIRouter(prefix="/api/game-requests", tags=["게임 신청"])

CONFIG_UPLOAD_DIR = "/app/data/uploads/configs"
os.makedirs(CONFIG_UPLOAD_DIR, exist_ok=True)


def _build_response(game_req: GameRequest, user: User = None) -> GameRequestResponse:
    name = ""
    email = None
    if user:
        name = user.display_name or user.username
        email = user.email
    else:
        # v0.4.0 이전 레거시: DB에 requester_name/email 컬럼 잔류
        name = getattr(game_req, 'requester_name', None) or "(알 수 없음)"
        email = getattr(game_req, 'requester_email', None)
    return GameRequestResponse(
        id=game_req.id,
        requester_id=game_req.requester_id or "",
        requester_name=name,
        requester_email=email,
        game_name=game_req.game_name,
        player_count=game_req.player_count,
        preferred_time=game_req.preferred_time,
        notes=game_req.notes,
        config_file_path=game_req.config_file_path,
        status=game_req.status,
        status_label=REQUEST_STAGE_LABELS.get(game_req.status, game_req.status),
        admin_notes=game_req.admin_notes,
        server_address=game_req.server_address,
        server_port=game_req.server_port,
        server_password=game_req.server_password,
        config_path=game_req.config_path,
        created_at=game_req.created_at.isoformat(),
    )


async def _get_user(db: AsyncSession, user_id: str) -> User | None:
    if not user_id:
        return None
    r = await db.execute(select(User).where(User.id == user_id))
    return r.scalar_one_or_none()


# ─── 게임 서버 신청 (파일 업로드 포함) ───

@router.post("/", response_model=GameRequestResponse)
async def submit_game_request(
    game_name: str = Form(...),
    player_count: int = Form(1),
    preferred_time: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    config_file: Optional[UploadFile] = File(None),
    user: User = Depends(require_discord_role),
    db: AsyncSession = Depends(get_db),
):
    config_file_path = None
    if config_file and config_file.filename:
        if not config_file.filename.endswith((".xlsx", ".xls")):
            raise HTTPException(400, "엑셀 파일만 업로드 가능합니다")
        import uuid
        file_id = str(uuid.uuid4())[:8]
        save_name = f"{file_id}_{config_file.filename}"
        save_path = os.path.join(CONFIG_UPLOAD_DIR, save_name)
        with open(save_path, "wb") as f:
            shutil.copyfileobj(config_file.file, f)
        config_file_path = save_name

    game_req = GameRequest(
        requester_id=user.id,
        game_name=game_name,
        player_count=player_count,
        preferred_time=preferred_time,
        notes=notes,
        config_file_path=config_file_path,
    )
    db.add(game_req)
    await db.commit()
    await db.refresh(game_req)

    requester_name = user.display_name or user.username

    try:
        await send_game_request_notification(
            requester_name=requester_name,
            requester_email=user.email or "",
            game_name=game_name,
            player_count=player_count,
            preferred_time=preferred_time or "",
            notes=notes or "",
        )
    except Exception as e:
        print(f"[MAIL ERROR] 게임 신청 알림 발송 실패: {e}")

    try:
        await notify_game_request(
            requester_name=requester_name,
            game_name=game_name,
            player_count=player_count,
            notes=notes,
        )
    except Exception:
        pass

    return _build_response(game_req, user)


# ─── 내 신청 내역 조회 ───

@router.get("/my", response_model=list[GameRequestResponse])
async def my_game_requests(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GameRequest)
        .where(GameRequest.requester_id == user.id)
        .order_by(GameRequest.created_at.desc())
    )
    return [_build_response(r, user) for r in result.scalars().all()]


# ─── 신청 목록 조회 (관리자) ───

@router.get("/", response_model=list[GameRequestResponse])
async def list_game_requests(
    status_filter: str = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(GameRequest).order_by(GameRequest.created_at.desc())
    if status_filter:
        query = query.where(GameRequest.status == status_filter)

    result = await db.execute(query)
    requests = result.scalars().all()

    responses = []
    user_cache = {}
    for r in requests:
        if r.requester_id not in user_cache:
            user_cache[r.requester_id] = await _get_user(db, r.requester_id)
        responses.append(_build_response(r, user_cache[r.requester_id]))
    return responses


# ─── 신청 상태 변경 (관리자 — 단계별 워크플로우) ───

@router.patch("/{request_id}", response_model=GameRequestResponse)
async def review_game_request(
    request_id: str,
    review: GameRequestReview,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if review.status not in REQUEST_STAGES:
        raise HTTPException(400, f"유효하지 않은 상태: {review.status}")

    result = await db.execute(select(GameRequest).where(GameRequest.id == request_id))
    game_req = result.scalar_one_or_none()
    if game_req is None:
        raise HTTPException(404, "신청을 찾을 수 없습니다")

    old_status = game_req.status
    game_req.status = review.status
    if review.admin_notes is not None:
        game_req.admin_notes = review.admin_notes
    if review.server_address is not None:
        game_req.server_address = review.server_address
    if review.server_port is not None:
        game_req.server_port = review.server_port
    if review.server_password is not None:
        game_req.server_password = review.server_password
    if review.config_path is not None:
        game_req.config_path = review.config_path
    game_req.reviewed_by = admin.id
    game_req.reviewed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(game_req)

    # 신청자 정보
    requester = await _get_user(db, game_req.requester_id)
    if requester and requester.email and old_status != review.status:
        try:
            await send_stage_notification(
                to=requester.email,
                username=requester.display_name or requester.username,
                game_name=game_req.game_name,
                new_status=review.status,
                server_address=game_req.server_address,
                server_port=game_req.server_port,
                server_password=game_req.server_password,
                config_path=game_req.config_path,
                admin_notes=game_req.admin_notes,
            )
        except Exception as e:
            print(f"[MAIL ERROR] 단계 알림 실패: {e}")

        try:
            await notify_request_stage_change(
                requester_name=requester.display_name or requester.username,
                game_name=game_req.game_name,
                old_status=old_status,
                new_status=review.status,
            )
        except Exception:
            pass

    return _build_response(game_req, requester)


# ─── 사용자 업로드 설정 파일 다운로드 (관리자) ───

@router.get("/{request_id}/config-download")
async def download_request_config(
    request_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(GameRequest).where(GameRequest.id == request_id))
    game_req = result.scalar_one_or_none()
    if not game_req or not game_req.config_file_path:
        raise HTTPException(404, "설정 파일이 없습니다")

    file_path = os.path.join(CONFIG_UPLOAD_DIR, game_req.config_file_path)
    if not os.path.exists(file_path):
        raise HTTPException(404, "파일이 존재하지 않습니다")

    original_name = game_req.config_file_path.split("_", 1)[1] if "_" in game_req.config_file_path else game_req.config_file_path
    return FileResponse(file_path, filename=original_name, media_type="application/octet-stream")


# ─── 상태 목록 (프론트엔드용) ───

@router.get("/stages/list")
async def get_stages():
    return {"stages": REQUEST_STAGES, "labels": REQUEST_STAGE_LABELS}
