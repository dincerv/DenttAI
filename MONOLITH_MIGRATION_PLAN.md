# DentAI Flow — Mikroservis → Monolith Geçiş Planı

> **Amaç:** 7 Python mikroservisi + 1 Node.js servisi + Nginx gateway + RabbitMQ'yu,  
> Railway'de 2 servis olarak çalışacak şekilde birleştirmek:
> - **`api`** → tek Python/FastAPI monolith (tüm domain'ler + scheduler)
> - **`ui`** → mevcut Next.js 14 frontend (değişmez)
> - **`postgres`** → Railway PostgreSQL add-on
> - **`redis`** → Railway Redis add-on (session cache, APScheduler lock)
>
> RabbitMQ ve Nginx gateway **kaldırılır**.  
> Veritabanı şeması **değişmez** — migration yazmak gerekmez.

---

## Hedef Mimari

```
Browser
  │
  ▼
Next.js (ui) — NEXT_PUBLIC_API_URL=https://api.railway.app
  │
  ▼ HTTPS
FastAPI Monolith (api) — /auth/, /appointments/, /inventory/,
                          /analytics/, /integration/, /notifications/
  │
  ├──► PostgreSQL (Railway add-on)
  └──► Redis       (Railway add-on)
```

İki servis arasındaki eski RabbitMQ event akışı, monolith içinde **doğrudan Python async fonksiyon çağrısına** dönüşür.  
Node.js notification-service içindeki BullMQ scheduler, Python'da **APScheduler** ile yeniden yazılır.

---

## Geçişte Değişmeyen Şeyler

| Bileşen | Durum |
|---|---|
| Veritabanı şeması (`shared/db/`) | **Değişmez** |
| RLS & multi-tenancy mantığı | **Değişmez** |
| Frontend kodları (`ui/`) | **Değişmez** |
| JWT / RBAC mantığı | Aynı kalır, sadece tek app içine taşınır |
| API path'leri (`/api/auth/`, `/api/appointments/`, …) | **Değişmez** — sadece gateway ortadan kalkar |

---

## Adım Listesi

### ADIM 0 — Hazırlık

- [ ] `git checkout -b refactor/monolith` (yeni branch)
- [ ] `docker compose up` ile mevcut durumun çalıştığını doğrula
- [ ] `shared/db/` migration'larının tamamını çalıştır, DB'nin güncel olduğunu kontrol et
- [ ] `railway.toml` dosyalarının var olduğunu not et (sonra güncellenecek)

---

### ADIM 1 — Monolith Dizin Yapısını Oluştur

Yeni servis: `services/api/`

```
services/api/
├── Dockerfile
├── requirements.txt
├── main.py                  ← FastAPI app, tüm router'ları include eder
├── app/
│   ├── core/
│   │   ├── config.py        ← TEK config (tüm env var'lar burada)
│   │   ├── database.py      ← TEK async engine
│   │   ├── security.py      ← JWT / bcrypt (auth-service'den taşı)
│   │   ├── dependencies.py  ← get_current_user, get_db, clinic_context
│   │   └── scheduler.py     ← APScheduler (notification-service yerine)
│   ├── routers/
│   │   ├── auth.py          ← auth-service/app/routers/auth.py + users.py + tenants.py + admin.py
│   │   ├── appointments.py  ← appointment-service routers
│   │   ├── waitlist.py
│   │   ├── patient_notes.py
│   │   ├── inventory.py     ← inventory-service routers
│   │   ├── analytics.py     ← analytics-service/app/routers.py
│   │   ├── integration.py   ← integration-service routers
│   │   ├── whatsapp.py      ← whatsapp-ingestion-service + integration whatsapp router
│   │   └── notifications.py ← notification-service HTTP endpoint'leri (varsa)
│   ├── services/            ← tüm servislerden taşınan business logic
│   ├── models/              ← tüm ORM modelleri (tek metadata)
│   ├── schemas/             ← tüm Pydantic şemalar
│   ├── tasks/               ← eski Celery task'lar → asyncio background task
│   └── providers/           ← WhatsApp, LLM, PMS adapter'lar
```

**Bu adımda yapılacak:**
1. `services/api/` dizinini oluştur
2. Boş `main.py` ve `app/` iskeletini yaz
3. `requirements.txt` — tüm servislerden bağımlılıkları birleştir

---

### ADIM 2 — `core/` Katmanını Birleştir

**2a. `config.py`**
- `auth-service/app/core/config.py` temel alınır
- Tüm diğer servislerden env var'lar eklenir:
  - `RABBITMQ_URL` → **kaldırılır**
  - `CELERY_BROKER_URL` → **kaldırılır**
  - `WHATSAPP_*`, `OPENAI_*`, `GEMINI_*`, `PMS_*` buraya taşınır

**2b. `database.py`**
- Tek async SQLAlchemy engine
- RLS middleware: her request'te `SET LOCAL app.current_clinic_id`
- `shared/auth_middleware.py` buraya entegre edilir

**2c. `security.py`**
- `auth-service/app/core/security.py` olduğu gibi kopyalanır

**2d. `dependencies.py`**
- `get_current_user`, `require_role`, `get_db` fonksiyonları tek yerden

---

### ADIM 3 — Modelleri ve Şemaları Birleştir

**3a. `models/`**
- Her servisten `app/models/*.py` dosyaları `services/api/app/models/` altına taşınır
- `Base = declarative_base()` **tek bir yerde** tanımlanır (tüm modeller bunu import eder)
- Tablolar aynı isimde kalır — migration gerekmez

**3b. `schemas/`**
- Her servisten Pydantic şemalar taşınır
- İsim çakışması varsa (örn. iki servis de `HealthResponse` tanımlıyorsa) birleştirilir

---

### ADIM 4 — Router'ları Taşı

Her mikroservis router'ı sırayla taşınır. Sıra önemli (bağımlılık sırası):

| Sıra | Kaynak | Hedef `services/api/app/routers/` |
|---|---|---|
| 1 | `auth-service/app/routers/auth.py` | `auth.py` |
| 2 | `auth-service/app/routers/users.py` | `auth.py` içine veya ayrı `users.py` |
| 3 | `auth-service/app/routers/tenants.py` | `tenants.py` |
| 4 | `auth-service/app/routers/admin.py` | `admin.py` |
| 5 | `appointment-service/app/routers/appointments.py` | `appointments.py` |
| 6 | `appointment-service/app/routers/waitlist.py` | `waitlist.py` |
| 7 | `appointment-service/app/routers/patient_notes.py` | `patient_notes.py` |
| 8 | `inventory-service/app/routers/*.py` | `inventory.py` |
| 9 | `analytics-service/app/routers.py` | `analytics.py` |
| 10 | `integration-service/app/routers/*.py` | `integration.py`, `whatsapp.py` |
| 11 | `whatsapp-ingestion-service/app/routers/webhook.py` | `whatsapp.py` içine ekle |

**`main.py`'da prefix'ler:**
```python
app.include_router(auth_router,         prefix="/auth")
app.include_router(appointments_router, prefix="/appointments")
app.include_router(waitlist_router,     prefix="/waitlist")
app.include_router(patient_notes_router,prefix="/patient-notes")
app.include_router(inventory_router,    prefix="/inventory")
app.include_router(analytics_router,    prefix="/analytics")
app.include_router(integration_router,  prefix="/integration")
app.include_router(whatsapp_router,     prefix="/whatsapp")
```

Frontend `apiClient` zaten `/api/...` prefix'i ekliyor → Nginx kaldırıldıktan sonra  
Railway'de `NEXT_PUBLIC_API_URL=https://api.railway.app` olacak ve frontend  
`https://api.railway.app/auth/login` gibi çağıracak. Bu uyumlu.

> **ÖNEMLİ:** Gateway şu an `/api/auth/` → auth-service:8001 `/auth/` dönüşümü yapıyor.  
> Monolith'te gateway yok, `apiClient` base URL değişecek. Frontend kodu değişmeyecek,  
> sadece `NEXT_PUBLIC_API_URL` env var güncellenecek.

---

### ADIM 5 — RabbitMQ'yu Kaldır (Event Akışını Değiştir)

Mevcut akış:
```
appointment-service --[RabbitMQ]--> notification-service --> WhatsApp
```

Yeni akış (monolith içi):
```
appointments router
  └── appointment_service.create_appointment()
        └── await notification_service.schedule_whatsapp_reminder(appointment)
```

**Değiştirilecek noktalar:**

| Eski | Yeni |
|---|---|
| `appointment-service/app/core/broker.py` → RabbitMQ publish | `services/notification_service.py` fonksiyon çağrısı |
| `notification-service/src/consumers/*.ts` → RabbitMQ consumer | Kaldırılır, doğrudan Python çağrısı |
| `notification-service/src/scheduler/confirmationScheduler.ts` | `app/core/scheduler.py` → APScheduler |

**APScheduler kurulumu:**
```python
# app/core/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def start_scheduler():
    scheduler.start()

@app.on_event("shutdown")
async def stop_scheduler():
    scheduler.shutdown()
```

Randevu oluşturulduğunda → `scheduler.add_job(send_whatsapp_reminder, 'date', run_date=reminder_time, ...)`

---

### ADIM 6 — Celery Task'ları Kaldır

`integration-service` Celery kullanıyor. Monolith'te Celery yerine:

| Eski (Celery) | Yeni |
|---|---|
| `whatsapp_tasks.send_message` | `async def send_message()` — FastAPI background task veya APScheduler job |
| `post_op_tasks.send_post_op` | APScheduler job |
| `appointment_tasks.*` | APScheduler job veya doğrudan async çağrı |

```python
# Router içinde background task örneği
from fastapi import BackgroundTasks

@router.post("/whatsapp/send")
async def send(data: MessageData, bg: BackgroundTasks):
    bg.add_task(whatsapp_service.send_message, data)
    return {"status": "queued"}
```

---

### ADIM 7 — Notification Service'i Python'a Taşı (Node.js → Python)

`services/notification-service/` (Node.js/TypeScript) artık gerekmiyor.

Node.js'te yapılan şeyler ve Python karşılıkları:

| Node.js | Python karşılığı |
|---|---|
| BullMQ job queue | APScheduler `AsyncIOScheduler` |
| `whatsapp.provider.ts` → Meta Cloud API | `app/providers/whatsapp_provider.py` (zaten var, integration-service'den) |
| `confirmationScheduler.ts` | APScheduler scheduled job |
| RabbitMQ consumers (`matchFound`, `confirmed`, `completed`, `cancelled`) | Kaldırılır — doğrudan fonksiyon çağrısı |

---

### ADIM 8 — `shared/` Modüllerini Entegre Et

`shared/` dizinindeki modüller tek bir yer yerine monolith'in içine taşınır:

| Shared modül | Nereye gider |
|---|---|
| `auth_middleware.py` | `app/core/dependencies.py` içine entegre et |
| `csrf_protection.py` | `main.py`'da middleware olarak ekle |
| `rate_limiter.py` | `main.py`'da middleware olarak ekle |
| `security_headers.py` | `main.py`'da middleware olarak ekle |
| `exception_handler.py` | `main.py`'da global handler olarak ekle |
| `config_validator.py` | `app/core/config.py`'ya entegre et |
| `db/init/` + `db/migrations/` | Deploy sırasında manuel çalıştırılır (değişmez) |

---

### ADIM 9 — `main.py` Nihai Hali

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine, Base
from app.core.scheduler import start_scheduler, stop_scheduler
# Middleware'ler (shared'dan taşınan)
from app.middleware.csrf import CSRFMiddleware
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
# Router'lar
from app.routers import (
    auth, users, tenants, admin,
    appointments, waitlist, patient_notes,
    inventory, analytics, integration, whatsapp
)

app = FastAPI(title="DentAI Flow API", version="2.0.0")

# Middleware
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, ...)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(RateLimiterMiddleware)

# Router'lar
app.include_router(auth.router,          prefix="/auth",         tags=["auth"])
app.include_router(users.router,         prefix="/users",        tags=["users"])
app.include_router(tenants.router,       prefix="/tenants",      tags=["tenants"])
app.include_router(admin.router,         prefix="/admin",        tags=["admin"])
app.include_router(appointments.router,  prefix="/appointments", tags=["appointments"])
app.include_router(waitlist.router,      prefix="/waitlist",     tags=["waitlist"])
app.include_router(patient_notes.router, prefix="/patient-notes",tags=["patient-notes"])
app.include_router(inventory.router,     prefix="/inventory",    tags=["inventory"])
app.include_router(analytics.router,     prefix="/analytics",    tags=["analytics"])
app.include_router(integration.router,   prefix="/integration",  tags=["integration"])
app.include_router(whatsapp.router,      prefix="/whatsapp",     tags=["whatsapp"])

@app.on_event("startup")
async def startup():
    await start_scheduler()

@app.on_event("shutdown")
async def shutdown():
    await stop_scheduler()

@app.get("/health")
async def health():
    return {"status": "ok", "service": "dentai-api"}
```

---

### ADIM 10 — Dockerfile Yaz

```dockerfile
# services/api/Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# shared modülleri artık app/middleware/ altında — external copy gerekmez
COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

---

### ADIM 11 — `docker-compose.yml`'ı Güncelle

**Kaldırılacak servisler:**
- `auth-service`
- `appointment-service`
- `inventory-service`
- `analytics-service`
- `integration-service`
- `whatsapp-ingestion-service`
- `notification-service`
- `rabbitmq`
- `gateway`

**Kalacaklar / eklenecekler:**

```yaml
version: "3.9"
services:
  postgres:
    image: postgres:16-alpine
    # ... aynı

  redis:
    image: redis:7-alpine
    # ... aynı

  api:
    build: ./services/api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://...
      - REDIS_URL=redis://redis:6379/0
      - JWT_SECRET=${JWT_SECRET}
      # diğer env var'lar
    depends_on:
      - postgres
      - redis

  ui:
    build: ./ui
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://api:8000
    depends_on:
      - api
```

---

### ADIM 12 — Frontend `apiClient`'ı Güncelle

`ui/src/lib/api-client.ts` dosyasında `baseURL`:

**Şu an:**
```
NEXT_PUBLIC_API_URL=http://localhost:8081   (gateway)
baseURL: process.env.NEXT_PUBLIC_API_URL + "/api"
→ http://localhost:8081/api/auth/login
```

**Sonra (geliştirme):**
```
NEXT_PUBLIC_API_URL=http://localhost:8000
baseURL: process.env.NEXT_PUBLIC_API_URL
→ http://localhost:8000/auth/login
```

**Railway (production):**
```
NEXT_PUBLIC_API_URL=https://dentai-api.up.railway.app
→ https://dentai-api.up.railway.app/auth/login
```

> **Dikkat:** Gateway `/api/auth/` → `/auth/` rewrite yapıyordu.  
> Monolith'te rewrite yok. `apiClient`'ta `/api` prefix'i **kaldırılmalı**  
> VEYA monolith router prefix'lerine `/api` eklenmeli. İkincisi daha az değişiklik.

**Önerilen (az değişiklik):** `main.py`'da tüm router'ları `/api` prefix'li mount et:
```python
app.include_router(auth.router, prefix="/api/auth")
app.include_router(appointments.router, prefix="/api/appointments")
# ...
```
Böylece frontend kodu hiç değişmez.

---

### ADIM 13 — Railway Konfigürasyonu

**`services/api/railway.toml`:**
```toml
[build]
builder = "dockerfile"
dockerfilePath = "Dockerfile"

[deploy]
startCommand = "uvicorn main:app --host 0.0.0.0 --port $PORT --workers 2"
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "on_failure"
```

**`ui/railway.toml`:**
```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "node .next/standalone/server.js"
healthcheckPath = "/"
```

**Railway'de eklenecek environment variable'lar (api servisi):**
```
DATABASE_URL=postgresql+asyncpg://...  (Railway PostgreSQL URL'si)
REDIS_URL=redis://...                  (Railway Redis URL'si)
JWT_SECRET=<güçlü random>
JWT_REFRESH_SECRET=<güçlü random>
WHATSAPP_API_TOKEN=...
WHATSAPP_PHONE_NUMBER_ID=...
OPENAI_API_KEY=...  (veya GEMINI_API_KEY)
ENVIRONMENT=production
ALLOWED_ORIGINS=https://ui-url.railway.app
```

---

### ADIM 14 — Test & Doğrulama

- [ ] `docker compose up --build` ile local çalışıyor mu?
- [ ] `/health` endpoint'i 200 dönüyor mu?
- [ ] Login çalışıyor mu? (`/api/auth/login`)
- [ ] Randevu oluşturma çalışıyor mu?
- [ ] WhatsApp scheduler job tetikleniyor mu? (log'dan kontrol)
- [ ] Multi-tenancy: farklı `clinic_id`'ler birbirinin verisini görmüyor mu?
- [ ] Frontend build hatasız mı? (`npm run build`)
- [ ] Railway deploy → health check geçiyor mu?

---

### ADIM 15 — Temizlik (Eski Dosyaları Sil)

Tüm testler geçtikten sonra:
- [ ] `services/auth-service/` → sil
- [ ] `services/appointment-service/` → sil
- [ ] `services/inventory-service/` → sil
- [ ] `services/analytics-service/` → sil
- [ ] `services/integration-service/` → sil
- [ ] `services/whatsapp-ingestion-service/` → sil
- [ ] `services/notification-service/` → sil
- [ ] `gateway/` → sil (railway.toml hariç)
- [ ] `backend/` → sil (zaten duplicate'di)
- [ ] `docker-compose.cloud.yml`, `docker-compose.prod.yml` → yeni yapıya göre güncelle veya sil
- [ ] `azure-pipelines-*.yml` → Railway CI'a göre güncelle

---

## Bağımlılık Çakışması Riski

| Risk | Önlem |
|---|---|
| İki servis aynı tablo adını farklı model sınıfıyla tanımlamış olabilir | `Base.metadata` tek olacak, çakışmalar gözden geçirilmeli |
| Pydantic v1 vs v2 uyumsuzluğu | Tüm servisler aynı Pydantic versiyonunda mı kontrol et |
| `asyncio` event loop çakışması (Celery + uvicorn) | Celery kaldırıldığı için sorun kalmaz |
| APScheduler job persistence (restart'ta kaybolur) | Redis job store eklenebilir (opsiyonel) |

---

## İş Önceliği (Hangi Sırayla Başlanır)

```
ADIM 0 (hazırlık)
  ↓
ADIM 1 (dizin yapısı)
  ↓
ADIM 2 + 3 (core + modeller)
  ↓
ADIM 4 (router'lar — en uzun adım, servis servis)
  ↓
ADIM 5 + 6 (RabbitMQ + Celery kaldır)
  ↓
ADIM 7 (notification → Python)
  ↓
ADIM 8 (shared entegre)
  ↓
ADIM 9 + 10 (main.py + Dockerfile)
  ↓
ADIM 11 + 12 (docker-compose + frontend)
  ↓
ADIM 13 (Railway config)
  ↓
ADIM 14 (test)
  ↓
ADIM 15 (temizlik)
```

**Tahmini süre:** Router taşıma en çok zaman alır (~2-4 saat).  
Core/config/models birleşimi ~1 saat.  
RabbitMQ/Celery'nin kaldırılması ~1 saat.  
Toplam: **4–6 saat** dikkatli çalışmayla.
