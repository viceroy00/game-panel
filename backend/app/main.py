import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.session import init_db
from app.auth.router import router as auth_router
from app.discord.router import router as discord_router
from app.invite.router import router as invite_router
from app.containers.router import router as containers_router
from app.files.router import router as files_router
from app.rbac.router import router as rbac_router
from app.requests.router import router as requests_router
from app.templates.router import router as templates_router

settings = get_settings()
_scheduler_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler_task

    # DB 초기화 + 관리자 계정
    await init_db()

    # game-servers 네트워크
    try:
        from app.containers.service import ensure_game_network
        ensure_game_network()
    except Exception as e:
        print(f"[STARTUP] 네트워크 초기화 경고: {e}")

    # 헬스체크 스케줄러
    from app.scheduler.healthcheck import run_healthcheck
    _scheduler_task = asyncio.create_task(run_healthcheck())

    print(f"[STARTUP] {settings.app_name} 시작됨")
    print(f"[STARTUP] Docker: {settings.docker_base_url}")
    print(f"[STARTUP] Discord OAuth2: {'활성' if settings.discord_enabled else '비활성'}")
    print(f"[STARTUP] 초대 코드: {'활성' if settings.invite_code_enabled else '비활성'}")

    yield

    if _scheduler_task:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title=settings.app_name,
    description="비공개 게임 서버 관리 시스템",
    version="0.5.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.app_url, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(auth_router)
app.include_router(discord_router)
app.include_router(invite_router)
app.include_router(containers_router)
app.include_router(files_router)
app.include_router(rbac_router)
app.include_router(requests_router)
app.include_router(templates_router)


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": "0.5.0",
        "discord": settings.discord_enabled,
        "invite": settings.invite_code_enabled,
    }
