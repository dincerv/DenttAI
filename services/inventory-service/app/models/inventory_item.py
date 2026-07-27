"""
SQLAlchemy modeli: InventoryItem — sarf malzeme stok takibi (Batch / Parti yönetimli).
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    __table_args__ = (
        UniqueConstraint(
            "clinic_id", "name", "expiry_date", "batch_number",
            name="uq_inventory_batch",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    clinic_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0"), nullable=False
    )
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    min_stock_level: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0"), nullable=False
    )
    cost_per_unit: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    shelf_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    batch_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    @property
    def is_low_stock(self) -> bool:
        """Stok minimum düzeyin altındaysa True döner."""
        return self.quantity <= self.min_stock_level
