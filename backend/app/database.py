from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.app_env == "development",
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=20,
    pool_timeout=15,
    # Соединения, "убитые" на середине COMMIT из-за asyncio.wait_for
    # cancellation, зависают в состоянии idle/ClientRead на стороне
    # Postgres на часы, съедая слоты пула (pool_size+max_overflow=40).
    # pool_recycle заставляет SQLAlchemy принудительно закрывать и
    # пересоздавать любое соединение старше 300с — даже "работающее" —
    # так зомби физически не могут копиться дольше 5 минут.
    pool_recycle=300,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
