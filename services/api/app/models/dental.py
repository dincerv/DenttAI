"""SQLAlchemy models: tooth_records (odontogram) + treatments (plan)."""
from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Numeric, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ToothStatus(str, enum.Enum):
    HEALTHY = "healthy"
    CARIES = "caries"
    FILLED = "filled"
    RCT = "rct"
    CROWN = "crown"
    MISSING = "missing"
    IMPLANT = "implant"
    BRIDGE = "bridge"
    PLANNED = "planned"


class ProcedureType(str, enum.Enum):
    MUAYENE = "muayene"
    DOLGU = "dolgu"
    KANAL = "kanal"
    CEKIM = "cekim"
    KRON = "kron"
    KOPRU = "kopru"
    IMPLANT = "implant"
    PROTEZ = "protez"
    VENEER = "veneer"
    ORTODONTI = "ortodonti"
    TEMIZLIK = "temizlik"
    DIGER = "diger"


class TreatmentStatus(str, enum.Enum):
    PLANNED = "planned"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ToothRecord(Base):
    __tablename__ = "tooth_records"
    __table_args__ = (
        UniqueConstraint("clinic_id", "patient_id", "tooth_fdi", name="uq_tooth_records_patient"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    patient_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    tooth_fdi: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ToothStatus.HEALTHY.value)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Treatment(Base):
    __tablename__ = "treatments"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    patient_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    tooth_fdi: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    procedure: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TreatmentStatus.PLANNED.value)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    appointment_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True
    )
    payment_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("payments.id", ondelete="SET NULL"), nullable=True
    )
    doctor_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
