"""
DentAI Flow Monolith — Tüm servis (business logic) fonksiyonları tek noktadan export.

Analytics router `from app.services import (...)` kullanıyor,
diğer router'lar doğrudan `from app.services.xxx_service import ...` kullanıyor.
"""
# ── Auth ──────────────────────────────────────────────────
from app.services.auth_service import login, logout, refresh_access_token, register_clinic
from app.services.tenant_service import *

# ── Appointment ───────────────────────────────────────────
from app.services.appointment_service import *
from app.services.waitlist_engine import *

# ── Inventory ─────────────────────────────────────────────
from app.services.items_service import *
from app.services.qr_service import *
from app.services.fefo_service import *
from app.services.cycle_service import *

# ── Analytics ─────────────────────────────────────────────
from app.services.revenue_service import get_recovered_revenue
from app.services.appointment_stats_service import get_appointment_stats
from app.services.inventory_stats_service import get_waste_report, get_expiring_cycles
from app.services.doctor_stats_service import get_doctor_performance
from app.services.treatment_service import get_treatment_counts, get_treatments_by_doctor
from app.services.ai_chat_service import answer_clinic_question

# ── Integration / WhatsApp ────────────────────────────────
from app.services.whatsapp_service import *
from app.services.import_service import *

__all__ = [
    # Auth
    "login", "logout", "refresh_access_token", "register_clinic",
    # Analytics
    "get_recovered_revenue",
    "get_appointment_stats",
    "get_waste_report",
    "get_expiring_cycles",
    "get_doctor_performance",
    "get_treatment_counts",
    "get_treatments_by_doctor",
    "answer_clinic_question",
]
