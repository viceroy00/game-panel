from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import User
from app.auth.service import decode_token
from app.config import get_settings

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """JWT 검증 → 유저 반환 (2FA 검증 완료 토큰만 허용)"""
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 토큰입니다")

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 토큰 유형입니다")

    if not payload.get("2fa_verified", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="2차 인증이 필요합니다")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="비활성 계정입니다")

    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """관리자 권한 필수"""
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한이 필요합니다")
    return user


async def require_discord_role(user: User = Depends(get_current_user)) -> User:
    """
    Discord 역할 체크 — 허용된 역할 중 하나라도 보유해야 접근 가능
    관리자는 역할 제한 무시. allowed_role_ids가 비어있으면 제한 없음.
    """
    if user.is_admin:
        return user

    settings = get_settings()
    allowed = settings.allowed_role_ids
    if not allowed:
        return user  # 역할 제한 미설정 → 모든 로그인 사용자 허용

    user_roles = user.discord_roles or []
    if not set(user_roles) & set(allowed):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="필요한 Discord 역할이 없습니다. 관리자에게 문의하세요"
        )
    return user
