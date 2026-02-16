"""
Discord 채널 알림 서비스
- 봇 토큰으로 지정 채널에 Embed 메시지 전송
- 서버 다운/삭제 예고/게임 신청 등 이벤트 알림
"""

import httpx
from datetime import datetime
from typing import Optional
from app.config import get_settings

settings = get_settings()

DISCORD_API = "https://discord.com/api/v10"


async def _send_embed(channel_id: str, embed: dict):
    """Discord 채널에 Embed 메시지 전송"""
    if not settings.discord_bot_token or not channel_id:
        return

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{DISCORD_API}/channels/{channel_id}/messages",
            headers={
                "Authorization": f"Bot {settings.discord_bot_token}",
                "Content-Type": "application/json",
            },
            json={"embeds": [embed]},
        )
        if resp.status_code not in (200, 201):
            print(f"[DISCORD NOTIFY] 전송 실패: {resp.status_code} {resp.text}")


def _notify_channel() -> str:
    return settings.discord_notify_channel_id


def _request_channel() -> str:
    return settings.discord_request_channel_id or settings.discord_notify_channel_id


# ═══════════════════════════════════════════
# 서버 상태 알림
# ═══════════════════════════════════════════

async def notify_server_down(container_name: str, game_name: str):
    """게임 서버 다운 알림"""
    if not settings.discord_notify_enabled:
        return
    await _send_embed(_notify_channel(), {
        "title": "⚠️ 게임 서버 다운",
        "description": f"**{container_name}** ({game_name}) 서버가 중지되었습니다.",
        "color": 0xEF5350,  # 빨강
        "fields": [
            {"name": "서버", "value": container_name, "inline": True},
            {"name": "게임", "value": game_name, "inline": True},
            {"name": "조치", "value": f"[패널에서 확인]({settings.app_url}/servers)", "inline": False},
        ],
        "footer": {"text": "7일 이상 종료 시 자동 삭제됩니다"},
        "timestamp": datetime.utcnow().isoformat(),
    })


async def notify_server_up(container_name: str, game_name: str):
    """게임 서버 시작 알림"""
    if not settings.discord_notify_enabled:
        return
    await _send_embed(_notify_channel(), {
        "title": "✅ 게임 서버 시작",
        "description": f"**{container_name}** ({game_name}) 서버가 시작되었습니다!",
        "color": 0x66BB6A,  # 초록
        "fields": [
            {"name": "서버", "value": container_name, "inline": True},
            {"name": "게임", "value": game_name, "inline": True},
        ],
        "timestamp": datetime.utcnow().isoformat(),
    })


async def notify_delete_warning(container_name: str, remaining_days: int):
    """삭제 예고 알림"""
    if not settings.discord_notify_enabled:
        return
    await _send_embed(_notify_channel(), {
        "title": "🗑️ 서버 삭제 예고",
        "description": (
            f"**{container_name}** 서버가 **{remaining_days}일 후** 자동 삭제됩니다.\n"
            f"서버를 유지하려면 [패널]({settings.app_url}/servers)에서 다시 시작하세요."
        ),
        "color": 0xFFA726,  # 주황
        "timestamp": datetime.utcnow().isoformat(),
    })


async def notify_server_deleted(container_name: str, stopped_days: int):
    """서버 자동 삭제 완료"""
    if not settings.discord_notify_enabled:
        return
    await _send_embed(_notify_channel(), {
        "title": "❌ 서버 자동 삭제됨",
        "description": (
            f"**{container_name}** 서버가 {stopped_days}일 이상 종료 상태여서 삭제되었습니다.\n"
            f"볼륨 데이터는 보존됩니다. 필요 시 관리자에게 문의하세요."
        ),
        "color": 0xE53935,  # 진한 빨강
        "timestamp": datetime.utcnow().isoformat(),
    })


# ═══════════════════════════════════════════
# 게임 신청 알림
# ═══════════════════════════════════════════

# ═══════════════════════════════════════════
# 게임 신청 알림
# ═══════════════════════════════════════════

async def notify_game_request(
    requester_name: str, game_name: str,
    player_count: int, notes: Optional[str] = None,
):
    """새 게임 서버 신청"""
    if not settings.discord_notify_enabled:
        return
    fields = [
        {"name": "신청자", "value": requester_name, "inline": True},
        {"name": "게임", "value": game_name, "inline": True},
        {"name": "인원", "value": f"{player_count}명", "inline": True},
    ]
    if notes:
        fields.append({"name": "비고", "value": notes, "inline": False})
    fields.append({
        "name": "관리", "value": f"[신청 목록 확인]({settings.app_url}/admin/requests)", "inline": False,
    })

    await _send_embed(_request_channel(), {
        "title": "🎮 새 게임 서버 신청",
        "color": 0x42A5F5,
        "fields": fields,
        "timestamp": datetime.utcnow().isoformat(),
    })


STAGE_DISCORD = {
    "approved": ("✅ 신청 승인", 0x66BB6A),
    "building": ("🔨 서버 생성중", 0x42A5F5),
    "ready": ("🖥️ 서버 생성 완료", 0x26C6DA),
    "permission_granted": ("🔑 권한 부여 완료", 0x26A69A),
    "firewall_done": ("🛡️ 방화벽 설정 완료", 0x7E57C2),
    "onboarded": ("🎉 온보딩 완료", 0x66BB6A),
    "rejected": ("❌ 신청 거절", 0xEF5350),
}


async def notify_request_stage_change(
    requester_name: str, game_name: str,
    old_status: str, new_status: str,
):
    """신청 단계 변경 알림"""
    if not settings.discord_notify_enabled:
        return
    cfg = STAGE_DISCORD.get(new_status)
    if not cfg:
        return
    title, color = cfg
    from app.db.models import REQUEST_STAGE_LABELS
    old_label = REQUEST_STAGE_LABELS.get(old_status, old_status)
    new_label = REQUEST_STAGE_LABELS.get(new_status, new_status)

    await _send_embed(_request_channel(), {
        "title": title,
        "description": f"**{requester_name}**님의 **{game_name}** 신청",
        "color": color,
        "fields": [
            {"name": "이전", "value": old_label, "inline": True},
            {"name": "→", "value": new_label, "inline": True},
        ],
        "timestamp": datetime.utcnow().isoformat(),
    })


# ═══════════════════════════════════════════
# 사용자 활동 알림
# ═══════════════════════════════════════════

async def notify_user_registered(username: str, via: str):
    """새 사용자 가입"""
    if not settings.discord_notify_enabled:
        return
    via_text = {"discord": "Discord", "invite": "초대 코드", "admin": "관리자 생성"}.get(via, via)
    await _send_embed(_notify_channel(), {
        "title": "👤 새 사용자 가입",
        "description": f"**{username}** 님이 가입했습니다. ({via_text})",
        "color": 0xAB47BC,  # 보라
        "timestamp": datetime.utcnow().isoformat(),
    })


# ═══════════════════════════════════════════
# 권한 부여 / 서버 배정 알림
# ═══════════════════════════════════════════

async def notify_permission_granted(
    username: str, container_name: str, actions: list[str], is_new: bool = True,
):
    """권한 부여/변경 알림"""
    if not settings.discord_notify_enabled:
        return
    title = "🔑 서버 권한 부여" if is_new else "🔑 서버 권한 변경"
    action_str = ", ".join(f"`{a}`" for a in actions)
    await _send_embed(_notify_channel(), {
        "title": title,
        "description": f"**{username}** 님에게 **{container_name}** 서버 권한이 {'부여' if is_new else '변경'}되었습니다.",
        "color": 0x26A69A,  # 청록
        "fields": [
            {"name": "사용자", "value": username, "inline": True},
            {"name": "서버", "value": container_name, "inline": True},
            {"name": "허용 액션", "value": action_str, "inline": False},
        ],
        "timestamp": datetime.utcnow().isoformat(),
    })
