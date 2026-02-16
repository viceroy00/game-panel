"""
Discord OAuth2 라우터
플로우:
  1) GET  /api/auth/discord/login    → Discord 인가 페이지로 리다이렉트
  2) GET  /api/auth/discord/callback → 코드 교환 → 서버 멤버 검증 → 계정 생성/연동
  3) 프론트에서 temp_token으로 2FA 설정/검증 진행 (기존 플로우와 동일)
"""

import secrets
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_db
from app.db.models import User
from app.auth.service import (
    hash_password, create_temp_token, create_access_token, create_refresh_token,
)
from app.discord.service import exchange_code, get_discord_user, check_guild_member, get_avatar_url, check_has_allowed_role
from app.discord.notify import notify_user_registered

settings = get_settings()
router = APIRouter(prefix="/api/auth/discord", tags=["Discord 인증"])


@router.get("/login")
async def discord_login():
    """Discord OAuth2 인가 페이지로 리다이렉트"""
    if not settings.discord_enabled:
        raise HTTPException(status_code=404, detail="Discord 로그인이 비활성화되어 있습니다")

    if not settings.discord_client_id:
        raise HTTPException(status_code=500, detail="Discord Client ID가 설정되지 않았습니다")

    return RedirectResponse(url=settings.discord_auth_url)


@router.get("/callback")
async def discord_callback(
    code: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Discord 인가 코드 콜백
    1) 코드 → 토큰 교환
    2) 유저 정보 조회
    3) 비공개 서버 멤버인지 확인
    4) 기존 계정 연동 또는 신규 생성
    5) 프론트엔드로 temp_token 전달 (2FA 플로우 진입)
    """
    # ── 1. 코드 → 토큰 ──
    token_data = await exchange_code(code)
    if not token_data:
        return _redirect_error("Discord 인증에 실패했습니다")

    access_token = token_data.get("access_token")
    if not access_token:
        return _redirect_error("Discord 토큰을 받지 못했습니다")

    # ── 2. 유저 정보 ──
    discord_user = await get_discord_user(access_token)
    if not discord_user:
        return _redirect_error("Discord 사용자 정보를 가져올 수 없습니다")

    discord_id = discord_user["id"]
    discord_name = discord_user.get("global_name") or discord_user.get("username", "Unknown")

    # ── 3. 서버 멤버 + 역할 검증 ──
    member_data = await check_guild_member(discord_id)
    if member_data is None:
        return _redirect_error("비공개 서버 멤버만 가입할 수 있습니다. 서버에 먼저 참가해주세요")

    member_roles = member_data.get("roles", [])
    if not check_has_allowed_role(member_roles):
        return _redirect_error("필요한 Discord 역할이 없습니다. 관리자에게 문의하세요")

    # ── 4. 기존 계정 확인 또는 신규 생성 ──
    result = await db.execute(select(User).where(User.discord_id == discord_id))
    user = result.scalar_one_or_none()

    if user is None:
        # 신규 계정 자동 생성
        username = _sanitize_username(discord_name)
        # 중복 체크
        existing = await db.execute(select(User).where(User.username == username))
        if existing.scalar_one_or_none():
            username = f"{username}_{discord_id[-4:]}"

        user = User(
            username=username,
            password_hash=hash_password(secrets.token_urlsafe(32)),  # 랜덤 PW (Discord 전용)
            display_name=discord_name,
            discord_id=discord_id,
            discord_username=discord_user.get("username"),
            discord_avatar=get_avatar_url(discord_user),
            discord_roles=member_roles,
            is_admin=False,
            totp_setup_required=True,
            registered_via="discord",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        print(f"[DISCORD] 신규 계정 생성: {username} (Discord: {discord_name}, roles: {member_roles})")
        try:
            await notify_user_registered(username, "discord")
        except Exception:
            pass
    else:
        # 기존 계정 — 프로필 + 역할 업데이트
        user.discord_username = discord_user.get("username")
        user.discord_avatar = get_avatar_url(discord_user)
        user.discord_roles = member_roles
        user.last_login_at = datetime.utcnow()
        await db.commit()

    if not user.is_active:
        return _redirect_error("계정이 비활성화되었습니다. 관리자에게 문의하세요")

    # ── 5. 프론트엔드로 토큰 전달 ──
    if user.totp_setup_required and not user.totp_enabled:
        # 최초 → 2FA 설정 필요
        temp_token = create_temp_token(user.id, purpose="2fa_setup")
        return RedirectResponse(
            url=f"{settings.app_url}/login?discord=1&status=2fa_setup_required&token={temp_token}"
        )
    elif user.totp_enabled:
        # 기존 → 2FA 검증 필요
        temp_token = create_temp_token(user.id, purpose="2fa")
        return RedirectResponse(
            url=f"{settings.app_url}/login?discord=1&status=2fa_required&token={temp_token}"
        )
    else:
        # 2FA 없이 (이론상 도달 안 함)
        access = create_access_token(user.id, user.is_admin)
        refresh = create_refresh_token(user.id)
        return RedirectResponse(
            url=f"{settings.app_url}/login?discord=1&status=authenticated&access={access}&refresh={refresh}"
        )


def _redirect_error(message: str) -> RedirectResponse:
    """에러 시 프론트엔드 로그인 페이지로 에러 메시지 전달"""
    from urllib.parse import quote
    return RedirectResponse(url=f"{settings.app_url}/login?discord_error={quote(message)}")


def _sanitize_username(name: str) -> str:
    """Discord 이름 → 유효한 username"""
    import re
    sanitized = re.sub(r'[^a-zA-Z0-9_\-가-힣]', '', name)
    if not sanitized:
        sanitized = "user"
    return sanitized[:50]
