# Appointment Service — app package
# Modüller Prompt-3'te implement edilecek:
#   app/core/       — config, database, message broker bağlantısı
#   app/models/     — Appointment, Waitlist, DoctorSlot SQLAlchemy modelleri
#   app/schemas/    — Pydantic request/response şemaları
#   app/routers/    — appointments, waitlist, slots endpoint'leri
#   app/services/   — WaitlistEngine: iptal → uygun hasta atama mantığı
