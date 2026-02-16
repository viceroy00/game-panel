"""
게임 서버 헬스체크 스케줄러
- 주기적으로 관리 대상 컨테이너 상태 확인
- 다운 시 관련 사용자에게 메일 알림
- 7일 이상 종료 상태 → 삭제 예고 알림 → 자동 삭제
"""

import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import async_session
from app.db.models import ContainerState, Permission, User
from app.containers.service import list_game_containers, remove_container, get_docker_client
from app.mail.service import send_container_down_alert, send_container_delete_warning, send_container_deleted_notice
from app.discord.notify import (
    notify_server_down, notify_server_up, notify_delete_warning, notify_server_deleted,
)

settings = get_settings()


async def run_healthcheck():
    """메인 헬스체크 루프"""
    print(f"[HEALTHCHECK] 스케줄러 시작 (간격: {settings.healthcheck_interval_minutes}분)")

    while True:
        try:
            await _check_all_containers()
        except Exception as e:
            print(f"[HEALTHCHECK ERROR] {e}")

        await asyncio.sleep(settings.healthcheck_interval_minutes * 60)


async def _check_all_containers():
    """모든 관리 대상 컨테이너 상태 확인"""
    now = datetime.utcnow()

    try:
        containers = list_game_containers()
    except Exception as e:
        print(f"[HEALTHCHECK] Docker 연결 실패: {e}")
        return

    container_names = {c["name"] for c in containers}

    async with async_session() as db:
        # DB에 등록된 모든 컨테이너 상태 조회
        result = await db.execute(select(ContainerState))
        tracked = {cs.container_name: cs for cs in result.scalars().all()}

        # ── 현재 존재하는 컨테이너 상태 업데이트 ──
        for c in containers:
            name = c["name"]
            state = tracked.get(name)

            if state is None:
                # 새 컨테이너 발견 → 추적 시작
                state = ContainerState(
                    container_name=name,
                    container_id=c["id"],
                    game_name=c.get("labels", {}).get("game-panel.game", "Unknown"),
                    last_status=c["status"],
                    last_checked_at=now,
                )
                if c["status"] != "running":
                    state.stopped_since = now
                db.add(state)
            else:
                prev_status = state.last_status
                state.last_status = c["status"]
                state.last_checked_at = now
                state.container_id = c["id"]

                if c["status"] == "running":
                    # 살아남 → 종료 추적 초기화
                    if prev_status != "running" and prev_status != "unknown":
                        # 복구됨 → Discord 알림
                        try:
                            await notify_server_up(name, c.get("labels", {}).get("game-panel.game", name))
                        except Exception:
                            pass
                    state.stopped_since = None
                    state.down_alert_sent = False
                    state.delete_warning_sent = False

                elif c["status"] != "running" and prev_status == "running":
                    # 방금 꺼짐
                    state.stopped_since = now
                    state.down_alert_sent = False
                    state.delete_warning_sent = False

            # ── 다운 알림 ──
            if (
                c["status"] != "running"
                and not state.down_alert_sent
                and settings.healthcheck_notify
            ):
                await _send_down_alert(db, name, c.get("labels", {}).get("game-panel.game", name))
                state.down_alert_sent = True
                # Discord 채널 알림
                try:
                    await notify_server_down(name, c.get("labels", {}).get("game-panel.game", name))
                except Exception:
                    pass

            # ── 7일 자동 삭제 체크 ──
            if state.stopped_since:
                days_stopped = (now - state.stopped_since).days

                # 5일 경과 → 삭제 예고 (2일 전 경고)
                if days_stopped >= 5 and not state.delete_warning_sent:
                    await _send_delete_warning(db, name, state.stopped_since)
                    state.delete_warning_sent = True
                    try:
                        await notify_delete_warning(name, settings.auto_delete_days - days_stopped)
                    except Exception:
                        pass

                # 7일 경과 → 자동 삭제
                if days_stopped >= settings.auto_delete_days:
                    await _auto_delete_container(db, name, state)

        # ── 사라진 컨테이너 처리 (Docker에서 수동 삭제된 경우) ──
        for name, state in tracked.items():
            if name not in container_names:
                state.last_status = "removed"
                state.last_checked_at = now

        await db.commit()


async def _send_down_alert(db: AsyncSession, container_name: str, game_name: str):
    """컨테이너 다운 → 관련 사용자에게 메일 알림"""
    users = await _get_related_users(db, container_name)

    for user in users:
        if user.email:
            try:
                await send_container_down_alert(
                    to=user.email,
                    username=user.display_name or user.username,
                    container_name=container_name,
                    game_name=game_name,
                )
                print(f"[HEALTHCHECK] 다운 알림 발송: {container_name} → {user.email}")
            except Exception as e:
                print(f"[HEALTHCHECK] 메일 발송 실패 ({user.email}): {e}")

    # 관리자에게도 발송
    try:
        await send_container_down_alert(
            to=settings.admin_email,
            username="관리자",
            container_name=container_name,
            game_name=game_name,
        )
    except Exception as e:
        print(f"[HEALTHCHECK] 관리자 알림 실패: {e}")


async def _send_delete_warning(db: AsyncSession, container_name: str, stopped_since: datetime):
    """삭제 예고 알림 (7일 중 5일 경과)"""
    users = await _get_related_users(db, container_name)
    remaining_days = settings.auto_delete_days - (datetime.utcnow() - stopped_since).days

    for user in users:
        if user.email:
            try:
                await send_container_delete_warning(
                    to=user.email,
                    username=user.display_name or user.username,
                    container_name=container_name,
                    remaining_days=remaining_days,
                )
            except Exception as e:
                print(f"[HEALTHCHECK] 삭제 예고 메일 실패 ({user.email}): {e}")

    try:
        await send_container_delete_warning(
            to=settings.admin_email,
            username="관리자",
            container_name=container_name,
            remaining_days=remaining_days,
        )
    except Exception as e:
        print(f"[HEALTHCHECK] 관리자 삭제 예고 실패: {e}")


async def _auto_delete_container(db: AsyncSession, container_name: str, state: ContainerState):
    """7일 이상 종료 → 자동 삭제"""
    try:
        msg = remove_container(container_name, force=True)
        print(f"[HEALTHCHECK] 자동 삭제 완료: {msg}")

        # 관련 사용자에게 삭제 완료 알림
        users = await _get_related_users(db, container_name)
        for user in users:
            if user.email:
                try:
                    await send_container_deleted_notice(
                        to=user.email,
                        username=user.display_name or user.username,
                        container_name=container_name,
                        stopped_days=settings.auto_delete_days,
                    )
                except Exception:
                    pass

        await send_container_deleted_notice(
            to=settings.admin_email,
            username="관리자",
            container_name=container_name,
            stopped_days=settings.auto_delete_days,
        )

        # Discord 채널 알림
        try:
            await notify_server_deleted(container_name, settings.auto_delete_days)
        except Exception:
            pass

        # DB에서 상태 제거
        state.last_status = "auto_deleted"

    except Exception as e:
        print(f"[HEALTHCHECK] 자동 삭제 실패 ({container_name}): {e}")


async def _get_related_users(db: AsyncSession, container_name: str) -> list[User]:
    """컨테이너에 권한이 있는 사용자 목록"""
    result = await db.execute(
        select(User)
        .join(Permission, Permission.user_id == User.id)
        .where(Permission.container_name == container_name)
        .where(User.is_active == True)
    )
    return list(result.scalars().all())
