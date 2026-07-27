# Auth Service — app package
# Prompt-2 implement edildi:
#   app/core/       — config, database (async SQLAlchemy), security (JWT+bcrypt), dependencies
#   app/models/     — Clinic, User, RefreshToken SQLAlchemy modelleri
#   app/schemas/    — Pydantic request/response şemaları (auth + tenant)
#   app/routers/    — /auth ve /tenants endpoint'leri
#   app/services/   — auth_service, tenant_service iş mantığı
