"""
Async SQLAlchemy engine ve session fabrikası.
Her isteğe özel oturum açılır; bağlantı havuzu (pool) paylaşılır.
RLS multi-tenancy: her session'da SET LOCAL app.current_clinic_id çalışır.
"""
from collections.abc import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.ENVIRONMENT == "development",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Tüm SQLAlchemy modelleri bu sınıftan türer. Tek Base — tek metadata."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency injection için session üreteci.

    Kullanım:
        @router.get("/")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def set_rls_context(session: AsyncSession, clinic_id: str | None) -> None:
    """
    PostgreSQL RLS için clinic_id context'ini ayarlar.
    Her DB işleminden önce çağrılmalı.
    """
    if clinic_id:
        await session.execute(
            text("SELECT set_config('app.current_clinic_id', :cid, true)").bindparams(cid=str(clinic_id))
        )
    else:
        await session.execute(
            text("SELECT set_config('app.current_clinic_id', '', true)")
        )
