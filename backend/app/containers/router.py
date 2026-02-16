from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from docker.errors import NotFound, APIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, Permission
from app.db.session import get_db
from app.auth.deps import require_discord_role
from app.rbac.deps import RequirePermission
from app.containers.schemas import ContainerInfo, ContainerAction, ContainerLogs
from app.containers.service import list_game_containers, container_action, get_container_logs, get_container, get_container_stats
from app.discord.notify import notify_server_up

router = APIRouter(prefix="/api/containers", tags=["컨테이너 관리"])


# ─── 목록 조회 (권한 있는 컨테이너만) ───

@router.get("/", response_model=list[ContainerInfo])
async def get_containers(
    user: User = Depends(require_discord_role),
    db: AsyncSession = Depends(get_db),
):
    try:
        containers = list_game_containers()

        # 관리자는 전체 조회
        if user.is_admin:
            return [ContainerInfo(**c) for c in containers]

        # 일반 사용자는 권한 있는 컨테이너만
        result = await db.execute(
            select(Permission.container_name).where(Permission.user_id == user.id)
        )
        allowed = {row[0] for row in result.fetchall()}
        return [ContainerInfo(**c) for c in containers if c["name"] in allowed]
    except APIError as e:
        raise HTTPException(status_code=500, detail=f"Docker 오류: {e}")


# ─── 단일 컨테이너 정보 ───

@router.get("/{container_name}", response_model=ContainerInfo)
async def get_container_info(
    container_name: str,
    user: User = Depends(RequirePermission("logs")),
):
    try:
        containers = list_game_containers()
        for c in containers:
            if c["name"] == container_name:
                return ContainerInfo(**c)
        raise HTTPException(status_code=404, detail="컨테이너를 찾을 수 없습니다")
    except NotFound:
        raise HTTPException(status_code=404, detail="컨테이너를 찾을 수 없습니다")


# ─── 리소스 사용량 (CPU/메모리) ───

@router.get("/{container_name}/stats")
async def get_stats(
    container_name: str,
    user: User = Depends(RequirePermission("logs")),
):
    try:
        return get_container_stats(container_name)
    except NotFound:
        raise HTTPException(status_code=404, detail="컨테이너를 찾을 수 없습니다")


# ─── 시작 ───

@router.post("/{container_name}/start")
async def start_container(
    container_name: str,
    user: User = Depends(RequirePermission("start")),
):
    try:
        msg = container_action(container_name, "start")
        # Discord 알림
        try:
            c = get_container(container_name)
            game = c.labels.get("game-panel.game", container_name)
            await notify_server_up(container_name, game)
        except Exception:
            pass
        return {"message": msg}
    except NotFound:
        raise HTTPException(status_code=404, detail="컨테이너를 찾을 수 없습니다")
    except APIError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── 정지 ───

@router.post("/{container_name}/stop")
async def stop_container(
    container_name: str,
    user: User = Depends(RequirePermission("stop")),
):
    try:
        msg = container_action(container_name, "stop")
        return {"message": msg}
    except NotFound:
        raise HTTPException(status_code=404, detail="컨테이너를 찾을 수 없습니다")
    except APIError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── 재시작 ───

@router.post("/{container_name}/restart")
async def restart_container(
    container_name: str,
    user: User = Depends(RequirePermission("restart")),
):
    try:
        msg = container_action(container_name, "restart")
        return {"message": msg}
    except NotFound:
        raise HTTPException(status_code=404, detail="컨테이너를 찾을 수 없습니다")
    except APIError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── 로그 조회 ───

@router.get("/{container_name}/logs", response_model=ContainerLogs)
async def get_logs(
    container_name: str,
    tail: int = 100,
    user: User = Depends(RequirePermission("logs")),
):
    try:
        logs = get_container_logs(container_name, tail=tail)
        return ContainerLogs(container_name=container_name, logs=logs, lines=tail)
    except NotFound:
        raise HTTPException(status_code=404, detail="컨테이너를 찾을 수 없습니다")


# ─── 실시간 로그 WebSocket ───

@router.websocket("/{container_name}/logs/stream")
async def stream_logs(websocket: WebSocket, container_name: str):
    await websocket.accept()

    # WebSocket에서는 JWT를 쿼리 파라미터로 받아 검증
    # ws://host/api/containers/mc/logs/stream?token=xxx
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="인증 필요")
        return

    from app.auth.service import decode_token
    payload = decode_token(token)
    if not payload or not payload.get("2fa_verified"):
        await websocket.close(code=4001, reason="인증 실패")
        return

    try:
        container = get_container(container_name)
        for log_line in container.logs(stream=True, follow=True, tail=50, timestamps=True):
            await websocket.send_text(log_line.decode("utf-8", errors="replace"))
    except NotFound:
        await websocket.close(code=4004, reason="컨테이너 없음")
    except WebSocketDisconnect:
        pass
    except Exception:
        await websocket.close(code=4500, reason="내부 오류")
