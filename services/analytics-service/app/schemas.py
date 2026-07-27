"""
Pydantic şemaları — Analytics Service.
Tüm response modelleri buradadır; router'lar buradan import eder.
"""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Ortak ──────────────────────────────────────────────────────────────────

class DateRangeParams(BaseModel):
    start_date: date
    end_date: date


# ── Recovered Revenue ──────────────────────────────────────────────────────

class RecoveredAppointment(BaseModel):
    message_id: UUID
    sent_at: datetime
    original_appointment_id: UUID
    specialty: str | None
    patient_name: str
    fee: float = Field(..., description="Bu branş için uygulanan seans ücreti (TRY)")


class RecoveredRevenueResponse(BaseModel):
    period_start: date
    period_end: date
    total_recovered_appointments: int
    total_recovered_revenue: float = Field(..., description="Toplam kurtarılan ciro (TRY)")
    by_specialty: list[dict] = Field(
        ...,
        description="Branş bazlı {'specialty': str, 'count': int, 'revenue': float}",
    )
    appointments: list[RecoveredAppointment]
    cached: bool = False


# ── Appointment Stats ──────────────────────────────────────────────────────

class SpecialtyStats(BaseModel):
    specialty: str | None
    total: int
    cancelled: int
    no_show: int
    completed: int
    cancel_rate_pct: float | None = None
    no_show_rate_pct: float | None = None


class AppointmentStatsResponse(BaseModel):
    period_start: date
    period_end: date
    total: int
    cancelled: int
    no_show: int
    completed: int
    upcoming: int
    cancel_rate_pct: float | None = None
    no_show_rate_pct: float | None = None
    completion_rate_pct: float | None = None
    by_specialty: list[SpecialtyStats]
    cached: bool = False


class PatientTypePeriodOverview(BaseModel):
    new_count: int
    old_count: int


class NewPatientsOverviewResponse(BaseModel):
    day: PatientTypePeriodOverview
    week: PatientTypePeriodOverview
    month: PatientTypePeriodOverview
    year: PatientTypePeriodOverview
    generated_at: datetime


# ── Inventory Waste Report ─────────────────────────────────────────────────

class HighWasteMaterial(BaseModel):
    id: UUID
    qr_id: str
    name: str
    category: str | None
    start_date: date | None
    end_date: date | None
    expected_lifespan: int | None
    actual_lifespan: int | None
    end_reason: str | None
    waste_note: str | None


class WasteCategorySummary(BaseModel):
    category: str
    total_cycles: int
    high_waste_count: int
    waste_rate_pct: float | None
    avg_actual_lifespan: float | None
    avg_expected_lifespan: float | None


class WasteReportResponse(BaseModel):
    total_high_waste: int
    by_category: list[WasteCategorySummary]
    materials: list[HighWasteMaterial]
    cached: bool = False


# ── Expiring Cycles ────────────────────────────────────────────────────────


class ExpiringCycle(BaseModel):
    id: UUID
    qr_id: str
    shelf_code: str | None
    name: str
    category: str | None
    start_date: date | None
    expected_lifespan: int | None
    actual_lifespan: int | None
    lifespan_used_pct: float | None


class ExpiringCyclesResponse(BaseModel):
    items: list[ExpiringCycle]
    cached: bool = False


# ── Doctor Performance ─────────────────────────────────────────────────────

class DoctorScorecard(BaseModel):
    doctor_id: UUID
    doctor_name: str
    specialty: str | None
    total: int
    completed: int
    cancelled: int
    no_show: int
    cancel_rate_pct: float | None
    completion_rate_pct: float | None
    loyal_patient_count: int


class DoctorPerformanceResponse(BaseModel):
    period_start: date
    period_end: date
    doctors: list[DoctorScorecard]
    cached: bool = False


# ── Treatment Counts (Tedavi Sayaçları) ───────────────────────────────────


class TreatmentPeriod(BaseModel):
    """Tek bir dönem (gün/hafta/ay/yıl) için tedavi sayıları."""
    period: date
    total_completed: int
    dolgu: int = 0
    kanal: int = 0
    implant: int = 0
    kron: int = 0
    cekim: int = 0
    protez: int = 0
    ortodonti: int = 0
    temizlik: int = 0
    beyazlatma: int = 0


class TreatmentTotals(BaseModel):
    """Dönem kümülatif toplamları — dashboard kart sayaçları."""
    total_completed: int
    dolgu: int = 0
    kanal: int = 0
    implant: int = 0
    kron: int = 0
    cekim: int = 0
    protez: int = 0
    ortodonti: int = 0
    temizlik: int = 0


class TreatmentCountsResponse(BaseModel):
    period_start: date
    period_end: date
    group_by: str  # day | week | month | year
    doctor_id: UUID | None = None
    doctor_name: str | None = None
    totals: TreatmentTotals
    trend: list[TreatmentPeriod]
    cached: bool = False


# ── Treatments By Doctor (Sahip görünümü) ─────────────────────────────────

class DoctorTreatmentRow(BaseModel):
    """Tek bir hekimin dönem içindeki tedavi özeti."""
    doctor_id: UUID
    doctor_name: str
    specialty: str | None = None
    total_completed: int = 0
    dolgu: int = 0
    kanal: int = 0
    implant: int = 0
    kron: int = 0
    cekim: int = 0
    protez: int = 0
    ortodonti: int = 0
    temizlik: int = 0


class TreatmentsByDoctorResponse(BaseModel):
    period_start: date
    period_end: date
    doctors: list[DoctorTreatmentRow]
    cached: bool = False


# ── AI Clinic Chat ─────────────────────────────────────────────────────────

class AIChatRequest(BaseModel):
    message: str = Field(..., min_length=3, max_length=3000)


class AIChatResponse(BaseModel):
    answer: str
    model: str
    fallback_used: bool = False


# ── Inventory Item Snapshot ───────────────────────────────────────────────

class InventoryItemSnapshot(BaseModel):
    """Tek bir malzemenin anlık stok durumu."""
    id: UUID
    name: str
    category: str | None = None
    quantity: float
    unit: str | None = None
    min_stock_level: float
    cost_per_unit: float | None = None
    shelf_code: str | None = None
    expiry_date: date | None = None
    batch_number: str | None = None
    is_low_stock: bool


class CategoryStockSummary(BaseModel):
    """Kategori bazında stok özeti."""
    category: str
    item_count: int
    low_stock_count: int
    total_value: float
    total_quantity: float


class StockOverviewResponse(BaseModel):
    items: list[InventoryItemSnapshot]
    categories: list[CategoryStockSummary]
    total_items: int
    low_stock_count: int
    total_value: float
    cached: bool = False


# ── Inventory Consumption ─────────────────────────────────────────────────

class ConsumptionRow(BaseModel):
    """Tek bir dönem + kalem kombinasyonu için hareket özeti."""
    period: date
    item_name: str
    category: str
    unit: str | None = None
    total_in: float = 0.0
    total_out: float = 0.0
    net_delta: float = 0.0
    in_count: int = 0
    out_count: int = 0


class ItemConsumptionTotal(BaseModel):
    """Dönem toplamı — kalem bazında."""
    item_name: str
    category: str
    unit: str | None = None
    total_in: float = 0.0
    total_out: float = 0.0
    net_delta: float = 0.0
    in_count: int = 0
    out_count: int = 0


class ConsumptionResponse(BaseModel):
    period_start: date
    period_end: date
    group_by: str
    rows: list[ConsumptionRow]
    totals: list[ItemConsumptionTotal]
    cached: bool = False


# ── Expiring Cycles ───────────────────────────────────────────────────────
