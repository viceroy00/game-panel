from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import get_settings
from app.db.models import Base

settings = get_settings()

# SQLite async 엔진
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """테이블 생성 + 자동 마이그레이션 + 초기 관리자 계정 생성"""
    # 1) 새 테이블 생성 (모델 기반)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2) 기존 DB 마이그레이션 (스키마 변경분 자동 적용)
    from app.db.migrate import run_migrations
    run_migrations()

    # 3) 초기 관리자 계정 생성
    from app.auth.service import create_initial_admin
    await create_initial_admin()


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
