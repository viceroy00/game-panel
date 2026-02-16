"""
Discord OAuth2 서비스
- Authorization Code Grant 플로우
- 비공개 디스코드 서버 멤버 검증
"""

import httpx
from typing import Optional
from app.config import get_settings

settings = get_settings()

DISCORD_API = "https://discord.com/api/v10"


async def exchange_code(code: str) -> Optional[dict]:
    """인가 코드 → 액세스 토큰 교환"""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{DISCORD_API}/oauth2/token",
            data={
                "client_id": settings.discord_client_id,
                "client_secret": settings.discord_client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.discord_redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code != 200:
            print(f"[DISCORD] 토큰 교환 실패: {resp.status_code} {resp.text}")
            return None
        return resp.json()


async def get_discord_user(access_token: str) -> Optional[dict]:
    """Discord 사용자 정보 조회"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DISCORD_API}/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp.status_code != 200:
            return None
        return resp.json()


async def check_guild_member(discord_user_id: str) -> dict | None:
    """
    봇 토큰으로 해당 유저가 디스코드 서버 멤버인지 확인
    성공 시 멤버 정보(roles 포함) 반환, 실패 시 None
    """
    if not settings.discord_guild_id or not settings.discord_bot_token:
        print("[DISCORD] guild_id 또는 bot_token 미설정 — 멤버 검증 건너뜀")
        return {"roles": []}

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DISCORD_API}/guilds/{settings.discord_guild_id}/members/{discord_user_id}",
            headers={"Authorization": f"Bot {settings.discord_bot_token}"},
        )
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 404:
            return None
        else:
            print(f"[DISCORD] 멤버 확인 실패: {resp.status_code} {resp.text}")
            return None


def check_has_allowed_role(member_roles: list[str]) -> bool:
    """
    허용된 역할 중 하나라도 보유하고 있는지 확인
    allowed_role_ids가 비어있으면 멤버만 확인 (역할 제한 없음)
    """
    allowed = settings.allowed_role_ids
    if not allowed:
        return True  # 역할 제한 없음 — 멤버면 OK
    return bool(set(member_roles) & set(allowed))


def get_avatar_url(user_data: dict) -> Optional[str]:
    """Discord 아바타 URL"""
    avatar = user_data.get("avatar")
    user_id = user_data.get("id")
    if avatar:
        ext = "gif" if avatar.startswith("a_") else "png"
        return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}.{ext}"
    return None
