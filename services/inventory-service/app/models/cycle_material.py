"""
SQLAlchemy modeli: CycleMaterial — QR kodlu döngüsel malzeme ömür takibi.
actual_lifespan PostgreSQL'de GENERATED ALWAYS AS ile hesaplanır;
Python'dan okunur ama yazılmaz.
"""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.schema import FetchedValue
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CycleMaterial(Base):
    __tablename__ = "cycle_materials"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    clinic_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    qr_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    shelf_code: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expected_lifespan: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Computed column — DB'de GENERATED ALWAYS AS; sadece okunur, hiçbir zaman yazılmaz
    actual_lifespan: Mapped[int | None] = mapped_column(Integer, FetchedValue(), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_high_waste: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    end_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    waste_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
