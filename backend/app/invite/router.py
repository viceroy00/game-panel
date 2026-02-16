"""
초대 코드 시스템
- 관리자: 코드 생성/목록/비활성화
- 지인: 코드로 가입 (공개 엔드포인트)
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_db
from app.db.models import User, InviteCode
from app.auth.deps import require_admin
from app.auth.service import hash_password, create_temp_token
from app.invite.schemas import InviteCodeCreate, InviteCodeResponse, InviteRegisterRequest
from app.discord.notify import notify_user_registered

settings = get_settings()
router = APIRouter(prefix="/api/invite", tags=["초대 코드"])


# ═══════════════════════════════════════════
# 관리자: 초대 코드 관리
# ═══════════════════════════════════════════

@router.post("/codes", response_model=InviteCodeResponse)
async def create_invite_code(
    req: InviteCodeCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """초대 코드 생성 (관리자)"""
    expires_at = None
    if req.expires_hours:
        expires_at = datetime.utcnow() + timedelta(hours=req.expires_hours)

    code = InviteCode(
        created_by=admin.id,
        max_uses=req.max_uses,
        note=req.note,
        expires_at=expires_at,
    )
    db.add(code)
    await db.commit()
    await db.refresh(code)

    return InviteCodeResponse(
        id=code.id, code=code.code, max_uses=code.max_uses,
        use_count=code.use_count, is_active=code.is_active,
        note=code.note,
        expires_at=code.expires_at.isoformat() if code.expires_at else None,
        created_at=code.created_at.isoformat(),
    )


@router.get("/codes", response_model=list[InviteCodeResponse])
async def list_invite_codes(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """초대 코드 목록 (관리자)"""
    result = await db.execute(select(InviteCode).order_by(InviteCode.created_at.desc()))
    codes = result.scalars().all()
    return [
        InviteCodeResponse(
            id=c.id, code=c.code, max_uses=c.max_uses,
            use_count=c.use_count, is_active=c.is_active,
            note=c.note,
            expires_at=c.expires_at.isoformat() if c.expires_at else None,
            created_at=c.created_at.isoformat(),
        )
        for c in codes
    ]


@router.delete("/codes/{code_id}")
async def deactivate_invite_code(
    code_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(InviteCode).where(InviteCode.id == code_id))
    code = result.scalar_one_or_none()
    if not code:
        raise HTTPException(status_code=404, detail="초대 코드를 찾을 수 없습니다")
    code.is_active = False
    await db.commit()
    return {"message": "초대 코드가 비활성화되었습니다"}


# ═══════════════════════════════════════════
# 공개: 초대 코드로 가입
# ═══════════════════════════════════════════

@router.post("/register")
async def register_with_invite(
    req: InviteRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """초대 코드로 가입 (공개)"""
    if not settings.invite_code_enabled:
        raise HTTPException(status_code=404, detail="초대 코드 가입이 비활성화되어 있습니다")

    # 코드 검증
    result = await db.execute(
        select(InviteCode).where(InviteCode.code == req.invite_code.upper())
    )
    code = result.scalar_one_or_none()

    if not code or not code.is_active:
        raise HTTPException(status_code=400, detail="유효하지 않은 초대 코드입니다")

    if code.use_count >= code.max_uses:
        raise HTTPException(status_code=400, detail="초대 코드 사용 횟수가 초과되었습니다")

    if code.expires_at and code.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="만료된 초대 코드입니다")

    # 유저명 중복 체크
    existing = await db.execute(select(User).where(User.username == req.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="이미 존재하는 사용자명입니다")

    # 계정 생성
    user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        display_name=req.display_name,
        email=req.email,
        is_admin=False,
        totp_setup_required=True,
        registered_via="invite",
    )
    db.add(user)

    # 코드 사용 처리
    code.use_count += 1
    code.used_by = user.id
    if code.use_count >= code.max_uses:
        code.is_active = False

    await db.commit()
    await db.refresh(user)

    # 2FA 설정으로 진행
    temp_token = create_temp_token(user.id, purpose="2fa_setup")

    try:
        await notify_user_registered(req.username, "invite")
    except Exception:
        pass

    return {
        "status": "2fa_setup_required",
        "temp_token": temp_token,
        "message": f"가입 완료! 2차 인증을 설정해주세요",
    }


@router.get("/verify/{code}")
async def verify_invite_code(code: str, db: AsyncSession = Depends(get_db)):
    """초대 코드 유효성 확인 (프론트엔드에서 입력 전 검증)"""
    result = await db.execute(
        select(InviteCode).where(InviteCode.code == code.upper())
    )
    invite = result.scalar_one_or_none()

    if not invite or not invite.is_active:
        return {"valid": False, "reason": "유효하지 않은 코드입니다"}

    if invite.use_count >= invite.max_uses:
        return {"valid": False, "reason": "사용 횟수가 초과되었습니다"}

    if invite.expires_at and invite.expires_at < datetime.utcnow():
        return {"valid": False, "reason": "만료된 코드입니다"}

    return {"valid": True}
