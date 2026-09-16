# DentAI Flow — Backend Eksiksiz Tamamlama Planı

> Amaç: Monolith API (`services/api`) **üretimde eksiksiz** olsun.  
> Bu dosya denetim sonucudur; adım adım uygulanır, her adımda test edilir.  
> İlişkili: `PAGE_AND_DB_COMPLETION_PLAN.md` (sayfa/UI tarafı)

**Denetim tarihi:** 2026-09-16  
**Canlı API:** `https://denttai-production.up.railway.app`  
**Branch:** `refactor/monolith-migration`

---

## 0. Verdict (tek cümle)

Çekirdek CRUD (auth, randevu, stok, analytics, PMS config) **çalışır**.  
WhatsApp / post-op / Celery stub / kolon drift / güvenlik middleware **eksik veya kırık** → backend henüz “eksiksiz” değil.

---

## 1. Denetim özeti

### 1.1 Ne tamam?

| Domain | Durum |
|--------|--------|
| Auth (login/refresh/me/users/admin) | ✅ |
| Tenants | ✅ |
| Appointments + patients/doctors (list/CRUD) | ✅ |
| Waitlist CRUD | ✅ |
| Inventory + QR + cycle | ✅ |
| Analytics endpoints | ✅ |
| PMS config / sync / test-connection | ✅ (adapter kırılganlığı ayrı) |
| `/health`, `/api/health`, `/api/auth/health` | ✅ |
| DB migration seti `002`–`017` | ✅ özellik tabloları mevcut |
| Neon temel seed (login kanıtı) | ✅ |

### 1.2 Ne kritik eksik / kırık?

| # | Sorun | Etki | Öncelik |
|---|--------|------|---------|
| C1 | `celery_app.py` → `.delay = lambda: None` | Post-op reachout UI 202 alır, **iş çalışmaz** | P0 |
| C2 | `process_incoming_whatsapp_message` **yok** | Gelen WhatsApp mesajı düşer | P0 |
| C3 | WhatsApp Graph URL = `graph.instagram.com` | Mesaj gönderimi production’da fail | P0 |
| C4 | `appointment_tasks` / `whatsapp_tasks` kırık import (`celery_app`, `metrics`) | Hatırlatma / iptal yolları ölü | P0 |
| C5 | `patients.phone_number` (doğrusu `phone`) | Task SQL patlar | P0 |
| H1 | Broker: `appointment.completed` / waitlist match eksik | Otomasyon yok | P1 |
| H2 | Çift webhook path kafa karışıklığı | Meta webhook yanlış URL riski | P1 |
| H3 | CSRF + RateLimit middleware kapalı | Production hardening eksik | P1 |
| H4 | ORM eksik tablolar (Patient, Doctor, …) | Tip güvenliği / drift | P2 |
| M1 | Enum/VARCHAR, nullability drift | Orta risk | P2 |
| M2 | Legacy `*_legacy.py` + stub Celery | Bakım karmaşası | P2 |

---

## 2. DB katmanı — tablo matrisi

| Tablo | SQL | ORM | Not |
|-------|-----|-----|-----|
| clinics, users, refresh_tokens | ✅ | ✅ | |
| appointments, waitlist | ✅ | ✅ | Bazı kolonlar ORM’de eksik |
| inventory_*, cycle_materials | ✅ | ✅ | |
| clinic_settings, doctor_settings, … (WhatsApp 007/015) | ✅ | ✅ | |
| doctors, patients | ✅ | ❌ | raw SQL only |
| sent_messages, patient_notes, clinic_integrations, ai_usage_events | ✅ | ❌ | raw SQL only |

**Kolon drift (acil):**

| Yanlış | Doğru | Dosya |
|--------|-------|--------|
| `p.phone_number` | `p.phone` | `appointment_tasks.py` (~94, ~404) + `_legacy` |
| `patient.phone_number` (attr) | `phone` / dict key | `post_op_tasks.py` (~401) |

**ORM’ye eklenmeli (sonra):**

- `Appointment.treatment_type`, `Appointment.is_auto_filled_by_ai`
- `Waitlist.preferred_doctor_ids`
- `Patient`, `Doctor`, `PatientNote`, `ClinicIntegration`, `AiUsageEvent`, `SentMessage`

### 2.1 Neon doğrulama SQL (Adım B0)

```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema='public' AND table_name IN (
  'clinics','users','refresh_tokens','doctors','patients',
  'appointments','waitlist','inventory_items','inventory_adjustments',
  'cycle_materials','sent_messages','clinic_settings','doctor_settings',
  'appointment_extended','clinic_faq','patient_feedback',
  'whatsapp_message_log','ai_usage_events','patient_notes','clinic_integrations'
) ORDER BY 1;

SELECT column_name FROM information_schema.columns
WHERE table_name='patients' AND column_name IN ('phone','phone_number');

SELECT column_name FROM information_schema.columns
WHERE table_name='waitlist'
  AND column_name IN ('preferred_doctor_ids','doctor_id','preferred_days','notes');
```

Eksik tablo/kolon varsa:
```powershell
$env:DATABASE_URL = "<NEON_DIRECT_URL>"
python scripts/apply_neon_schema.py --schema-only
```

---

## 3. Endpoint envanteri (özet)

Mount: `main.py` → her router `prefix="/api"`.

| Domain | Base | Not |
|--------|------|-----|
| Auth | `/api/auth/*` | health, login, refresh, logout, me, register |
| Users | `/api/auth/users/*` | |
| Admin | `/api/auth/admin/*` | clinics, impersonate, stats |
| Tenants | `/api/tenants/me` | |
| Appointments | `/api/appointments/*` | + doctors, patients |
| Waitlist | `/api/waitlist/*` | |
| Patient notes | `/api/patient-notes/*` | |
| Inventory | `/api/inventory/*` | items, qr, cycle |
| Analytics | `/api/analytics/*` | |
| PMS | `/api/integration/*` | config, sync, post-op |
| WhatsApp settings | `/api/integration/whatsapp/*` | clinic/doctor settings, FAQ, feedback |
| Webhook | `/api/integration/webhook/webhook` **ve** `/api/whatsapp/webhook` | tek contract’a indir |

### UI ↔ API kritik uyumsuzluk

| UI çağrısı | Backend gerçek | Düzeltme |
|------------|----------------|----------|
| `GET/PUT /clinic-settings` | `/integration/whatsapp/clinic-settings` | UI path düzelt (sayfa planı Adım 2) |
| `fetch('/api/patients')` | `/appointments/patients` | WaitlistForm apiClient |
| `GET /api/patients/{id}` | **endpoint yok** | İsteğe bağlı `GET /appointments/patients/{id}` ekle |

---

## 4. Adım adım uygulama (backend)

Her adım: kod → deploy → checklist test → bu tabloda işaretle.

### B0 — Neon şema doğrula
- [ ] 19 tablo var
- [ ] `patients.phone` var, `phone_number` yok (veya kullanılmıyor)
- [ ] waitlist kolonları var  
**Test:** SQL sorguları yeşil

### B1 — Hotfix: `phone_number` → `phone`
Dosyalar: `appointment_tasks.py`, `*_legacy.py`, `post_op_tasks.py` log satırı  
**Test:** İlgili SQL’i lokal/Neon’da dry-run veya log’da kolon hatası yok

### B2 — WhatsApp Graph URL düzelt
`providers/whatsapp_provider.py`: `graph.facebook.com`  
**Test:** `/api/integration/whatsapp/health/whatsapp` anlamlı yanıt; mock mode’da hata yok

### B3 — Celery stub’ı işlevsel hale getir
`.delay()` no-op yerine:
- ya `asyncio.create_task` / BackgroundTasks
- ya APScheduler job

Özellikle: `send_postop_followup_for_appointment`  
**Test:** UI “post-op reachout” → log’da gerçek çalıştırma; 202 sonrası sessizlik yok

### B4 — Gelen WhatsApp handler
`process_incoming_whatsapp_message` implement et veya webhook’u mevcut async pipeline’a bağla  
**Test:** Webhook verify GET; POST örnek payload → 200 + log

### B5 — Tek webhook contract
Meta için tek path seç (öneri: `/api/whatsapp/webhook`)  
Diğerini redirect/alias veya docs’ta netleştir  
**Test:** Verify token challenge OK

### B6 — `appointment_tasks` / `whatsapp_tasks` import düzelt veya kaldır
- `from app.celery_app import celery_app` → var olan export
- `app.core.metrics` → shim veya metrik çağrılarını kaldır
**Test:** `python -c "from app.tasks import appointment_tasks"` import OK

### B7 — Broker otomasyonu
- `appointment.confirmed` → reminder (varsa doğrula)
- `appointment.completed` → post-op schedule
- waitlist match → WhatsApp (veya bilerek defer + dokümante)
**Test:** Randevu completed → scheduler job görünür / log

### B8 — CSRF + RateLimit middleware aç
- Gerçek CSRF token (`/auth/health` artık `disabled` değil)
- UI interceptor ile uyum testi
**Test:** Login, randevu create, waitlist add, inventory adjust

### B9 — ORM tamamlaması
Patient, Doctor + eksik Appointment/Waitlist kolonları  
**Test:** Mevcut endpoint regressiyon; unit yoksa smoke

### B10 — Legacy temizlik
`*_legacy.py` birleştir veya sil; Celery stub dokümantasyonu  
**Test:** Import smoke; Railway health OK

### B11 — İsteğe bağlı API tamamlayıcılar
- `GET /appointments/patients/{id}`
- patient_id ile feedback listesi  
**Test:** İlgili UI bileşeni bağlanınca

---

## 5. Test matrisi (backend smoke)

| # | İstek | Beklenen |
|---|--------|----------|
| 1 | `GET /health` | 200 ok |
| 2 | `POST /api/auth/login` (superadmin) | token |
| 3 | `POST /api/auth/login` (owner + code) | token |
| 4 | `GET /api/appointments` | 200 liste |
| 5 | `GET /api/waitlist` | 200 |
| 6 | `GET /api/inventory/items` | 200 |
| 7 | `GET /api/analytics/appointments/stats` | 200 |
| 8 | `GET /api/integration/whatsapp/clinic-settings` | 200 |
| 9 | `PUT` clinic-settings (küçük değişiklik) | 200 persist |
| 10 | `POST` post-op-reachout | 202 **ve** gerçek task/log |
| 11 | `GET` whatsapp health | 200 |
| 12 | Webhook verify | challenge echo |

Auth header: Bearer access_token (4–12).

---

## 6. Env checklist (Railway API)

Zorunlu:
- `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `ENVIRONMENT=production`
- `CORS_ALLOWED_ORIGINS=https://dentai-ui-production.up.railway.app`

WhatsApp (gönderim için):
- `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_BUSINESS_ACCOUNT_ID`
- `WHATSAPP_WEBHOOK_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET`

AI (opsiyonel):
- `GEMINI_API_KEY` / `OPENAI_API_KEY`

---

## 7. Öncelik sırası (backend-first)

```
B0  Neon doğrula
B1  phone drift hotfix
B2  Graph URL
B3  .delay gerçek çalıştırma (post-op)
B4  Gelen WhatsApp handler
B5  Tek webhook
B6  Task import düzelt
B7  Broker otomasyon
B8  CSRF/RateLimit
B9  ORM
B10 Legacy temizlik
B11 Opsiyonel endpoints
```

**Paralel (UI planı):** Integrations path + Waitlist form — backend B2/B8 ile birlikte test edilir.

---

## 8. İlerleme kaydı

| Adım | Durum | Tarih | Not |
|------|--------|-------|-----|
| B0 Neon | ⬜ | | Canlı login ile dolaylı OK; SQL checklist sonraki |
| B1 phone | ✅ | 2026-09-16 | `p.phone AS phone_number` |
| B2 Graph URL | ✅ | 2026-09-16 | `graph.facebook.com` |
| B3 Celery→async | ✅ | 2026-09-16 | ThreadPoolExecutor `.delay` |
| B4 Ingest handler | ✅ | 2026-09-16 | `process_incoming_whatsapp_message` |
| B5 Webhook tek | ✅ | 2026-09-16 | Alias → whatsapp_ingest |
| B6 Task imports | ✅ | 2026-09-16 | `celery_app` + `metrics` shim |
| B7 Broker | ✅ | 2026-09-16 | completed→post-op; waitlist WhatsApp |
| B8 CSRF/RL | ✅ | 2026-09-16 | Middleware açık; webhook + login muaf; CORS expose |
| B9 ORM | ⬜ | | |
| B10 Legacy | ⬜ | | |
| B11 Opsiyonel API | ⬜ | | |

### Canlı UI smoke (2026-09-16, owner demo)
| Endpoint (browser) | Sonuç |
|--------------------|--------|
| POST patients + appointments | 201 |
| POST inventory/items | 201 |
| GET/PUT whatsapp/clinic-settings | 200 |
| GET auth/users + tenants/me | 200 |

---

## 9. “Backend eksiksiz” tanımı (Definition of Done)

Backend tamam sayılır ancak:

1. Yukarıdaki smoke matrisi (1–12) yeşil  
2. Post-op reachout gerçekten çalışıyor (stub değil)  
3. WhatsApp gönderim yolu tek + doğru Graph host  
4. Gelen webhook en azından mesajı log’luyor / işliyor  
5. `phone_number` drift yok  
6. CSRF + RateLimit production’da açık ve login bozmuyor  
7. Kritik task modülleri import edilebiliyor  
8. Neon 19 tablo doğrulanmış  

---

## Şimdi

**Sonraki aksiyon:** B0 (Neon SQL) → hemen ardından **B1+B2+B3** kod (en kritik üçlü).  
Onaylarsan B1’den kodlamaya başlarım.
