# DentAI Flow — Teknik Gereksinimler ve Mimari Kararlar

> Bu doküman projenin teknik yol haritasını, teknoloji seçim gerekçelerini ve yazılım gereksinimlerini tanımlar.  
> Son güncelleme: 2026-07-27

---

## 1. Teknoloji Yığını Değerlendirmesi

### 1.1 Mevcut Durum

| Katman | Teknoloji | Değerlendirme |
|--------|-----------|---------------|
| Frontend | Next.js 14 + React 18 + TypeScript | Uygun — App Router, SSR potansiyeli |
| Backend | Python FastAPI (7 mikroservis) | Uygun — async, hızlı, OpenAPI otomatik |
| Bildirim | Node.js (1 servis) | Kabul edilebilir — BullMQ ekosistemi |
| Veritabanı | PostgreSQL 16 + RLS | Mükemmel — multi-tenant için ideal |
| Kuyruk | RabbitMQ 3.13 | Uygun — event-driven mimari |
| Önbellek | Redis 7 | Uygun — Celery broker + cache |
| Gateway | Nginx 1.27 | Uygun — production-ready reverse proxy |
| Container | Docker Compose | Uygun — geliştirme/staging için yeterli |
| UI | Tailwind CSS 3.4 | Uygun — utility-first, tutarlı |

### 1.2 Python Gerekli mi?

**EVET — Python kalmalı.** Gerekçeler:

1. **FastAPI ekosistemi olgun** — async, Pydantic validation, otomatik OpenAPI dokümantasyonu.
2. **AI/LLM entegrasyonu** — Gemini ve OpenAI SDK'ları Python-first. RAG motoru, NLP sınıflandırma, prompt engineering Python'da çok daha doğal.
3. **Celery** — zamanlanmış görevler (post-op follow-up, hatırlatıcı, webhook işleme) için endüstri standardı.
4. **PMS adaptörleri** — DentSoft/Dr.Dentes session scraping, veri parse, Excel import — Python kütüphaneleri (pandas, openpyxl) üstün.
5. **SQLAlchemy async** — PostgreSQL RLS ile tam uyumlu, güçlü query builder.
6. **7 servis yazılmış ve çalışıyor** — yeniden yazmak maliyet/risk açısından mantıksız.

**Tek Node.js servisi (notification-service)** BullMQ scheduler için tutulabilir. Yeni servisler Python ile yazılmalı.

### 1.3 Neler Değişmeli?

| Alan | Mevcut | Hedef | Neden |
|------|--------|-------|-------|
| Next.js | 14.2.3 | **14.2.x (son patch)** | Güvenlik yamaları |
| React | 18.3.1 | 18.3.x (kalabilir) | 19'a geçiş gerekli değil |
| Form yönetimi | Manuel useState | **React Hook Form + Zod** | Büyük formlar, validation |
| Veri çekme | Custom hooks + Axios | **TanStack Query + Axios** | Cache, invalidation, loading |
| UI primitifler | 3 bileşen (Button, Badge, Skeleton) | **Shadcn/UI tam kurulum** | Tutarlı tasarım sistemi |
| Linting | eslint-config-next (minimal) | **ESLint + Prettier** | Tutarlı kod formatı |
| Test | Hiç yok | **Vitest + React Testing Library** | Kritik akışlar |
| Monitoring | Prometheus (temel) | Prometheus + **Sentry** | Frontend hata izleme |

### 1.4 Turladur ile Karşılaştırma

| Özellik | Turladur | DentAI Flow | Yorum |
|---------|----------|-------------|-------|
| Mimari | Monolitik (Next.js full-stack) | Mikroservis (Next.js + FastAPI) | DentAI daha ölçeklenebilir |
| ORM | Prisma | SQLAlchemy + Raw SQL | İkisi de geçerli; DentAI RLS avantajlı |
| Auth | NextAuth | Özel JWT + FastAPI | DentAI daha esnek (multi-tenant) |
| UI | MUI + Tailwind + Radix + Headless (karışık) | Tailwind + Radix (minimal) | DentAI daha tutarlı potansiyelde |
| Dosya yapısı | Karışık (`app/`, `components/`, `src/` duplicate) | Mikroservis bazlı (temiz ayrım) | DentAI daha iyi organize |
| Rules | 1 dosya (iş tanımı) | 7 dosya (teknik kurallar) | DentAI çok daha kapsamlı |

**Sonuç:** Turladur'un monolitik yaklaşımı küçük projeler için hızlı başlangıç sağlar ama DentAI'ın mikroservis mimarisi SaaS ölçeğinde daha doğru seçim. Turladur'dan alınacak iyi pratikler: middleware.ts ile route koruması, Prisma seed yapısı, React Hook Form + Zod.

---

## 2. Yazılım Gereksinimleri

### 2.1 Fonksiyonel Gereksinimler

#### Modül: Kimlik Doğrulama ve Yetkilendirme
| # | Gereksinim | Öncelik | Durum |
|---|-----------|---------|-------|
| AUTH-01 | Klinik kodu + e-posta + şifre ile giriş | P0 | Tamamlandı |
| AUTH-02 | JWT access token (60 dk) + refresh token (30 gün, httpOnly cookie) | P0 | Tamamlandı |
| AUTH-03 | 4 rol: super_admin, owner, doctor, assistant | P0 | Tamamlandı |
| AUTH-04 | Sayfa bazlı yetkilendirme (allowed_pages) | P0 | Tamamlandı |
| AUTH-05 | Super admin klinik impersonation (15 dk token) | P1 | Tamamlandı |
| AUTH-06 | Next.js middleware.ts ile sunucu tarafı rota koruması | P0 | **EKSİK** |
| AUTH-07 | Kayıt endpoint'ini invite-only yapma | P0 | **EKSİK** |
| AUTH-08 | Şifre sıfırlama (e-posta ile) | P1 | **EKSİK** |
| AUTH-09 | İki faktörlü doğrulama (2FA) | P2 | Planlanıyor |

#### Modül: Randevu Yönetimi
| # | Gereksinim | Öncelik | Durum |
|---|-----------|---------|-------|
| APPT-01 | Randevu CRUD (oluştur, listele, güncelle, iptal) | P0 | Tamamlandı |
| APPT-02 | Doktor ve tarih bazlı çakışma kontrolü (advisory lock) | P0 | Tamamlandı |
| APPT-03 | Durum geçişleri: scheduled → confirmed → completed/cancelled/no_show | P0 | Tamamlandı |
| APPT-04 | Bekleme listesi (WaitlistEngine) — iptal → otomatik eşleştirme | P0 | Tamamlandı |
| APPT-05 | RabbitMQ event yayını (appointment.cancelled, confirmed, completed) | P0 | Tamamlandı |
| APPT-06 | Randevu süresi (duration_minutes) desteği | P1 | Tamamlandı |
| APPT-07 | AI tarafından otomatik doldurma flag'i (is_auto_filled_by_ai) | P1 | Tamamlandı |
| APPT-08 | Tedavi sonrası takip flag'i (treatment_follow_up_enabled) | P1 | Tamamlandı |
| APPT-09 | **Google Calendar senkronizasyonu** | P1 | **PLANLI** |
| APPT-10 | Tekrarlayan randevu desteği | P2 | Planlanıyor |

#### Modül: WhatsApp Otomasyonu
| # | Gereksinim | Öncelik | Durum |
|---|-----------|---------|-------|
| WA-01 | Meta Cloud API ile mesaj gönderimi (şablon + serbest metin) | P0 | Tamamlandı (mock aktif) |
| WA-02 | Webhook ingest (gelen mesaj alma + imza doğrulama) | P0 | Tamamlandı |
| WA-03 | Randevu teyit hatırlatıcısı (zamanlanmış) | P0 | Tamamlandı |
| WA-04 | İptal bildirimi + waitlist eşleşme bildirimi | P0 | Tamamlandı |
| WA-05 | Post-op follow-up (tedavi sonrası otomatik mesaj) | P1 | Tamamlandı |
| WA-06 | Gelen mesaj NLP sınıflandırma (RAG + LLM) | P1 | Tamamlandı |
| WA-07 | Doktor acil alert (ciddi hasta şikayeti) | P1 | Tamamlandı |
| WA-08 | WhatsApp Business Account yönetimi (klinik bazlı) | P1 | Tamamlandı (UI) |
| WA-09 | Mesaj şablonları yönetimi (CRUD) | P2 | **PLANLI** |
| WA-10 | Toplu mesaj gönderimi (kampanya) | P2 | Planlanıyor |

#### Modül: Envanter ve Stok Yönetimi
| # | Gereksinim | Öncelik | Durum |
|---|-----------|---------|-------|
| INV-01 | Malzeme CRUD (ad, miktar, birim, son kullanma, batch) | P0 | Tamamlandı |
| INV-02 | FEFO (First Expiry First Out) sıralama | P0 | Tamamlandı |
| INV-03 | QR kod oluşturma ve takip (döngüsel malzeme) | P1 | Tamamlandı |
| INV-04 | Düşük stok uyarısı | P1 | Tamamlandı |
| INV-05 | Stok ayarlama geçmişi (adjustment log) | P1 | Tamamlandı |
| INV-06 | Anomali tespiti (anormal tüketim) | P2 | Kısmi |
| INV-07 | Tedarikçi yönetimi | P2 | **PLANLI** |

#### Modül: Dashboard ve Analitik
| # | Gereksinim | Öncelik | Durum |
|---|-----------|---------|-------|
| DASH-01 | Patron dashboard (günlük randevu, gelir, doluluk) | P0 | Tamamlandı |
| DASH-02 | Doktor performans tablosu | P0 | Tamamlandı |
| DASH-03 | Kurtarılan Gelir (Recovered Revenue) metriği | P0 | Tamamlandı |
| DASH-04 | AI chat (doğal dil ile klinik sorgulama) | P1 | Tamamlandı |
| DASH-05 | Sezonsal trend analizi | P2 | Planlanıyor |
| DASH-06 | PDF rapor çıktısı | P2 | **PLANLI** |

#### Modül: Hasta Yönetimi
| # | Gereksinim | Öncelik | Durum |
|---|-----------|---------|-------|
| PAT-01 | Hasta CRUD (ad, telefon, e-posta) | P0 | Tamamlandı |
| PAT-02 | Excel/CSV ile toplu hasta import | P0 | Tamamlandı |
| PAT-03 | PMS senkronizasyonu (DentSoft, Dr.Dentes) | P1 | Tamamlandı |
| PAT-04 | Hasta notları ve tedavi geçmişi | P1 | Kısmi (şema drift) |
| PAT-05 | Hasta feedback timeline | P1 | Tamamlandı |
| PAT-06 | Hasta profil sayfası (detaylı görünüm) | P1 | Tamamlandı |

#### Modül: Takvim (YENİ)
| # | Gereksinim | Öncelik | Durum |
|---|-----------|---------|-------|
| CAL-01 | Haftalık/günlük/aylık takvim görünümü | P1 | Kısmi (SmartCalendar) |
| CAL-02 | Sürükle-bırak ile randevu taşıma | P2 | **PLANLI** |
| CAL-03 | Google Calendar iki yönlü sync | P1 | **PLANLI** |
| CAL-04 | Doktor müsaitlik takvimi | P1 | **PLANLI** |

### 2.2 Fonksiyonel Olmayan Gereksinimler

| # | Gereksinim | Hedef |
|---|-----------|-------|
| NFR-01 | Sayfa yüklenme süresi (LCP) | < 2 saniye |
| NFR-02 | API yanıt süresi (p95) | < 500ms |
| NFR-03 | Eşzamanlı kullanıcı desteği | 500+ (per klinik 50) |
| NFR-04 | Uptime | %99.5 |
| NFR-05 | Veri yedekleme | Günlük otomatik (pg_dump) |
| NFR-06 | KVKK uyumu | Kişisel veri şifreleme, silme hakkı |
| NFR-07 | WCAG AA erişilebilirlik | Temel form/buton uyumu |
| NFR-08 | Mobil uyumluluk (responsive) | Tüm dashboard sayfaları |
| NFR-09 | Çoklu dil desteği | Türkçe (v1), İngilizce (v2) |

---

## 3. Geliştirme Ortamı Gereksinimleri

### 3.1 Zorunlu Araçlar

| Araç | Minimum Sürüm | Amaç |
|------|---------------|------|
| Docker Desktop | 24+ | Tüm servisleri çalıştırma |
| Docker Compose | v2 | Multi-container orchestration |
| Node.js | 20 LTS | Frontend geliştirme |
| Python | 3.11+ | Backend geliştirme |
| Git | 2.40+ | Versiyon kontrolü |
| VS Code / Cursor | Son sürüm | IDE |

### 3.2 Önerilen VS Code / Cursor Eklentileri

- ESLint
- Prettier
- Tailwind CSS IntelliSense
- Python (ms-python)
- Prisma (eğer eklenirse)
- Docker
- GitLens
- Thunder Client veya REST Client

### 3.3 Çalıştırma

```bash
# 1. Repo klonla
git clone <repo-url> dentai-flow && cd dentai-flow

# 2. Ortam değişkenlerini hazırla
cp .env.example .env
# .env dosyasını düzenle — tüm secret'ları doldur

# 3. Tüm servisleri başlat
docker compose up --build -d

# 4. Veritabanı migration'larını uygula
docker compose exec postgres psql -U dentai -d dentai_db -f /docker-entrypoint-initdb.d/01_init.sql

# 5. Demo veri yükle (isteğe bağlı)
python reseed.py

# 6. Frontend geliştirme (hot reload)
cd ui && npm install && npm run dev
```

---

## 4. Refactoring Yol Haritası (Öncelik Sırasıyla)

### Faz 1: Güvenlik ve Stabilite (1-2 hafta)

> **Detaylı adım adım rehber:** [`PHASE_1_ROADMAP.md`](./PHASE_1_ROADMAP.md)  
> Bu tablo özet; uygulama sırasında yol haritası dosyasındaki checklist kullanılmalı.

| # | Görev | Dosyalar |
|---|-------|----------|
| R-05 | `.env.local` ve `HESAPLAR.md`'yi gitignore'a ekle | ✅ Tamamlandı |
| R-02 | Hardcoded secret default'larını kaldır | ✅ Tamamlandı |
| R-03 | `/auth/register`'ı invite-only yap | ✅ Tamamlandı |
| R-01 | `middleware.ts` ekle (sunucu tarafı auth guard) | ✅ Tamamlandı |
| R-04 | `PermissionContext` default deny | ✅ Tamamlandı |
| R-06 | Şema drift tamiri (migration yazımı) | ✅ Tamamlandı (`016`) |
| R-07 | Eksik FK'ları (ON DELETE) tamamla | ✅ Tamamlandı (`016`) |

### Faz 2: Frontend İyileştirme (2-3 hafta)

| # | Görev | Dosyalar |
|---|-------|----------|
| R-08 | Kırık API çağrılarını düzelt (4 bileşen) | `SettingsPanel`, `WaitlistForm`, `SmartCalendar`, `PatientDetailCard` |
| R-09 | Gateway eksik route'larını ekle | `gateway/routes.conf` |
| R-10 | `frontend/` + `backend/` duplicate klasörleri sil | Kök dizin |
| R-11 | Monolitik sayfaları parçala (appointments, inventory, dashboard) | `ui/src/app/dashboard/` |
| R-12 | Shadcn/UI kurulumunu tamamla (Input, Select, Modal, Card) | `ui/src/components/ui/` |
| R-13 | `error.tsx` + `loading.tsx` ekle | `ui/src/app/dashboard/` |
| R-14 | Kullanılmayan Radix + jose paketlerini kaldır | `ui/package.json` |

### Faz 3: Yeni Özellikler (Onay sonrası)

| # | Görev |
|---|-------|
| F-01 | WhatsApp live mode aktivasyonu + test |
| F-02 | Google Calendar iki yönlü sync |
| F-03 | Doktor müsaitlik takvimi |
| F-04 | E-posta bildirim servisi (Resend veya Nodemailer) |
| F-05 | React Hook Form + Zod geçişi |
| F-06 | TanStack Query geçişi |
| F-07 | Sentry frontend hata izleme |

---

## 5. Dosya ve Klasör İsimlendirme Standartları

### Frontend (Next.js / TypeScript)

```
ui/src/
├── app/                          → kebab-case route klasörleri
│   ├── dashboard/
│   │   ├── appointments/
│   │   │   └── page.tsx          → Route sayfası
│   │   └── layout.tsx
│   └── login/
│       └── page.tsx
├── components/
│   ├── ui/                       → PascalCase.tsx
│   │   ├── Button.tsx
│   │   └── Input.tsx
│   ├── layout/                   → PascalCase.tsx
│   │   └── Sidebar.tsx
│   └── appointments/             → kebab-case klasör, PascalCase.tsx dosya
│       ├── AppointmentForm.tsx
│       └── AppointmentList.tsx
├── hooks/                        → camelCase (use prefix)
│   └── useAppointments.ts
├── context/                      → PascalCase + Context suffix
│   └── AuthContext.tsx
├── lib/                          → camelCase
│   ├── api-client.ts
│   └── utils.ts
├── services/                     → camelCase + Api suffix
│   └── appointmentApi.ts
└── types/                        → camelCase veya index
    └── index.ts
```

### Backend (Python)

```
services/<servis-adı>/
├── app/
│   ├── core/                     → snake_case
│   │   ├── config.py
│   │   └── database.py
│   ├── models/                   → snake_case (tekil tablo adı)
│   │   ├── appointment.py
│   │   └── patient.py
│   ├── routers/                  → snake_case
│   │   ├── appointments.py
│   │   └── schemas/              → snake_case
│   │       └── appointment.py
│   ├── services/                 → snake_case + _service suffix
│   │   └── appointment_service.py
│   ├── tasks/                    → snake_case + _tasks suffix
│   │   └── appointment_tasks.py
│   └── providers/                → snake_case + _provider suffix
│       └── whatsapp_provider.py
├── requirements.txt
└── Dockerfile
```

### Veritabanı

```
shared/db/
├── init/
│   └── 01_init.sql               → NNN_açıklama.sql
└── migrations/
    ├── 002_production_hardening.sql
    ├── 003_batch_indexes.sql
    └── ...
```

### Docker

```
docker-compose.yml                → Geliştirme
docker-compose.prod.yml           → Production
docker-compose.monitoring.yml     → Monitoring stack
```

---

## 6. Ortam Değişkenleri Referansı

| Değişken | Zorunlu | Açıklama |
|----------|---------|----------|
| `POSTGRES_USER` | Evet | PostgreSQL kullanıcı adı |
| `POSTGRES_PASSWORD` | Evet | PostgreSQL şifresi |
| `POSTGRES_DB` | Evet | Veritabanı adı |
| `REDIS_PASSWORD` | Evet | Redis şifresi |
| `RABBITMQ_USER` | Evet | RabbitMQ kullanıcı adı |
| `RABBITMQ_PASS` | Evet | RabbitMQ şifresi |
| `JWT_SECRET` | Evet | JWT imzalama anahtarı (≥32 karakter) |
| `JWT_ALGORITHM` | Hayır | Varsayılan: HS256 |
| `JWT_EXPIRE_MINUTES` | Hayır | Varsayılan: 60 |
| `NEXT_PUBLIC_API_URL` | Evet | Frontend → Gateway URL |
| `WHATSAPP_PROVIDER` | Hayır | `mock` (varsayılan) veya `meta` |
| `WHATSAPP_PHONE_NUMBER_ID` | Meta mod | Meta Business Phone ID |
| `WHATSAPP_API_KEY` | Meta mod | Meta erişim token'ı |
| `WHATSAPP_WEBHOOK_VERIFY_TOKEN` | Meta mod | Webhook doğrulama token'ı |
| `GEMINI_API_KEY` | Hayır | Google Gemini LLM |
| `OPENAI_API_KEY` | Hayır | OpenAI alternatiifi |
