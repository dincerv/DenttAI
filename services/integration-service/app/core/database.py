from __future__ import annotations
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=10,       # base pool (FastAPI + Celery worker tasks)
    max_overflow=20,    # extra connections under burst load
    pool_pre_ping=True, # validate connection before use (catches stale conns)
    pool_recycle=3600,  # recycle after 1 hour to avoid server-side timeouts
    pool_timeout=30,    # raise after 30 s instead of hanging forever
)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
        finally:
            await session.close()
