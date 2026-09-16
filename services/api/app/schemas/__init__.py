"""
DentAI Flow Monolith — Tüm Pydantic şemaları tek noktadan export.

Analytics router'ı `from app.schemas import (...)` şeklinde import eder,
bu __init__.py o çağrıyı karşılar.
"""
# ── Auth schemas ───────────────────────────────────────────
from app.schemas.auth import (
    ClinicRegisterRequest,
    ClinicRegisterResponse,
    LoginRequest,
    TokenResponse,
    CurrentUserResponse,
    RefreshRequest,
)
from app.schemas.tenant import *

# ── Appointment schemas ────────────────────────────────────
from app.schemas.appointment import *
from app.schemas.waitlist import *

# ── Inventory schemas ──────────────────────────────────────
from app.schemas.items import *
from app.schemas.qr import *
from app.schemas.cycle import *

# ── Analytics schemas (flat file — analytics.py'den) ──────
from app.schemas.analytics import *

# ── Integration / Import schemas ──────────────────────────
from app.schemas.integration import *

# ── WhatsApp / Integration schemas ────────────────────────
from app.schemas.whatsapp import *
