"""
DentAI Flow Monolith — Tüm ORM modelleri.
Tek Base, tek metadata — Alembic ve SQLAlchemy autogenerate için.
"""
# ── Auth / Tenant ──────────────────────────────────────────
from app.models.clinic import Clinic
from app.models.user import User, UserRole, RefreshToken

# ── Randevu ───────────────────────────────────────────────
from app.models.appointment import Appointment, AppointmentStatus

# ── Yedek Liste ───────────────────────────────────────────
from app.models.waitlist import Waitlist

# ── Stok ──────────────────────────────────────────────────
from app.models.inventory_item import InventoryItem
from app.models.inventory_adjustment import InventoryAdjustment
from app.models.cycle_material import CycleMaterial

# ── WhatsApp / AI Entegrasyonu ────────────────────────────
from app.models.whatsapp import (
    ClinicSettings,
    DoctorSettings,
    AppointmentExtended,
    ClinicFaqStatus,
    ClinicFaq,
    PatientFeedbackType,
    PatientFeedbackSeverity,
    PatientFeedback,
    WhatsappMessageStatus,
    WhatsappMessageLog,
)

__all__ = [
    # Auth
    "Clinic",
    "User",
    "UserRole",
    "RefreshToken",
    # Appointment
    "Appointment",
    "AppointmentStatus",
    # Waitlist
    "Waitlist",
    # Inventory
    "InventoryItem",
    "InventoryAdjustment",
    "CycleMaterial",
    # WhatsApp / Integration
    "ClinicSettings",
    "DoctorSettings",
    "AppointmentExtended",
    "ClinicFaqStatus",
    "ClinicFaq",
    "PatientFeedbackType",
    "PatientFeedbackSeverity",
    "PatientFeedback",
    "WhatsappMessageStatus",
    "WhatsappMessageLog",
]
