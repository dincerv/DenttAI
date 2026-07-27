# MD-1 — DentAI Flow: Teknik Dokümantasyon

> **Kapsam:** Prompt 1–7 — Monorepo İskeleti → Auth → Appointment → Notification → Inventory → Analytics → Frontend
> **Tarih:** 22 Nisan 2026  
> **Durum:** Prompt 1 ✓ | Prompt 2 ✓ | Prompt 3 ✓ | Prompt 4 ✓ | Prompt 5 ✓ | Prompt 6 ✓ | Prompt 7 ✓

---

## İçindekiler

### Prompt 1 — Monorepo İskeleti
1. [Proje Özeti](#1-proje-özeti)
2. [Mimari Kararlar](#2-mimari-kararlar)
3. [Klasör Yapısı](#3-klasör-yapısı)
4. [Oluşturulan Dosyalar — Detaylı Açıklamalar](#4-oluşturulan-dosyalar--detaylı-açıklamalar)
   - [Kök Dizin Dosyaları](#41-kök-dizin-dosyaları)
   - [docker-compose.yml](#42-docker-composeyml)
   - [Auth Service (iskelet)](#43-auth-service)
   - [Appointment Service](#44-appointment-service)
   - [Notification Service](#45-notification-service)
   - [Inventory Service](#46-inventory-service)
   - [Analytics Service](#47-analytics-service)
   - [API Gateway](#48-api-gateway)
   - [Frontend](#49-frontend)
   - [Shared Katmanı](#410-shared-katmanı)
5. [Veritabanı Şeması](#5-veritabanı-şeması)
6. [Servisler Arası İletişim](#6-servisler-arası-i̇letişim)
7. [Güvenlik Mimarisi](#7-güvenlik-mimarisi)
8. [Hızlı Başlangıç](#8-hızlı-başlangıç)

### Prompt 2 — Auth & Multi-Tenancy
9. [Prompt 2 Kapsamı ve Kararlar](#9-prompt-2-kapsamı-ve-kararlar)
10. [PostgreSQL RLS Güncellemeleri](#10-postgresql-rls-güncellemeleri)
11. [Auth Service — Detaylı Implementasyon](#11-auth-service--detaylı-implementasyon)
    - [Klasör Yapısı](#111-klasör-yapısı)
    - [core/ Katmanı](#112-core-katmanı)
    - [models/ — SQLAlchemy](#113-models--sqlalchemy)
    - [schemas/ — Pydantic](#114-schemas--pydantic)
    - [services/ — İş Mantığı](#115-services--i̇ş-mantığı)
    - [routers/ — Endpoint'ler](#116-routers--endpointler)
12. [Shared Auth Middleware](#12-shared-auth-middleware)
13. [JWT Akışı ve Token Stratejisi](#13-jwt-akışı-ve-token-stratejisi)
14. [RLS Çalışma Mekanizması](#14-rls-çalışma-mekanizması)

### Prompt 3 — Appointment & WaitlistEngine
15. [Prompt 3 Kapsamı ve Kararlar](#15-prompt-3-kapsamı-ve-kararlar)
16. [Appointment Service — Klasör Yapısı](#16-appointment-service--klasör-yapısı)
17. [core/ Katmanı — Broker Dahil](#17-core-katmanı--broker-dahil)
18. [models/ — SQLAlchemy](#18-models--sqlalchemy)
19. [schemas/ — Pydantic](#19-schemas--pydantic)
20. [WaitlistEngine — İptal → Eşleşme → Event Zinciri](#20-waitlistengine--i̇ptal--eşleşme--event-zinciri)
21. [RabbitMQ Event Kataloğu](#21-rabbitmq-event-kataloğu)
22. [routers/ — Endpoint'ler](#22-routers--endpointler)

### Prompt 4 — Notification & Scheduler
23. [Prompt 4 Kapsamı ve Kararlar](#23-prompt-4-kapsamı-ve-kararlar)
24. [Notification Service — Klasör Yapısı](#24-notification-service--klasör-yapısı)
25. [RabbitMQ Consumer Mimarisi](#25-rabbitmq-consumer-mimarisi)
26. [Dinamik Zamanlayıcı — BullMQ](#26-dinamik-zamanlayıcı--bullmq)
27. [WhatsApp Entegrasyon Katmanı](#27-whatsapp-entegrasyon-katmanı)
28. [Tüm Bildirim Akışı — Uçtan Uca](#28-tüm-bildirim-akışı--uçtan-uca)
29. [sent\_messages Tablosu](#29-sent_messages-tablosu)
30. [Appointment Service Güncellemeleri](#30-appointment-service-güncellemeleri)
31. [Sonraki Adımlar](#31-sonraki-adımlar)

### Prompt 5 — Inventory & QR
32. [Prompt 5 Genel Bakış](#32-prompt-5--inventory-service-genel-bakış)
33. [SQL Şeması Güncellemeleri](#33-prompt-5--sql-şeması-güncellemeleri)
34. [Dosya Yapısı](#34-prompt-5--dosya-yapısı)
35. [API Endpoint'leri](#35-prompt-5--api-endpointleri)
36. [QR Yaşam Döngüsü](#36-prompt-5--qr-yaşam-döngüsü)
37. [Anomali Tespiti](#37-prompt-5--anomali-tespiti-algoritması)
38. [RLS Entegrasyonu](#38-prompt-5--rls-entegrasyonu)

### Prompt 6 — Analytics & Recovered Revenue
40. [Prompt 6 Kapsamı ve Kararlar](#40-prompt-6-kapsamı-ve-kararlar)
41. [Analytics Service — Dosya Yapısı](#41-analytics-service--dosya-yapısı)
42. [Redis Caching Mimarisi](#42-redis-caching-mimarisi)
43. [Recovered Revenue Motoru](#43-recovered-revenue-motoru)
44. [Randevu İstatistikleri (pandas)](#44-randevu-i̇statistikleri-pandas)
45. [Envanter İsraf Raporu](#45-envanter-i̇sraf-raporu)
46. [Hekim Performans Karnesi](#46-hekim-performans-karnesi)
47. [API Endpoint'leri](#47-analytics-api-endpointleri)
48. [SQL Şeması Güncellemesi](#48-sql-şeması-güncellemesi)
49. [Sonraki Adımlar (Prompt 6 Sonu)](#49-sonraki-adımlar)

### Prompt 7 — Frontend (Next.js 14)
50. [Prompt 7 Kapsamı ve Kararlar](#50-prompt-7-kapsamı-ve-kararlar)
51. [Frontend — Dosya Yapısı](#51-frontend--dosya-yapısı)
52. [API Client — Bearer Token Otomasyonu](#52-api-client--bearer-token-otomasyonu)
53. [Auth Katmanı — Token + Claims](#53-auth-katmanı--token--claims)
54. [Dashboard Sayfası ve Bileşenler](#54-dashboard-sayfası-ve-bileşenler)
55. [Diğer Sayfalar](#55-randevu-yedek-liste-envanter-sayfaları)
56. [Sonraki Adımlar](#56-sonraki-adımlar)

---

## 1. Proje Özeti

**DentAI Flow**, diş kliniklerine yönelik çok kiracılı (multi-tenant) bir mikroservis ekosistemidir. Temel hedefler:

- Randevu kaçaklarını önlemek (akıllı yedek liste motoru)
- Sarf malzeme ve döngüsel malzeme ömrünü QR koduyla takip etmek
- Yapay zeka destekli **Recovered Revenue** (Kurtarılan Ciro) raporlaması sunmak
- Her klinisyenin yalnızca kendi klinik verisine erişmesini garanti etmek (PostgreSQL RLS)

Bu ilk prompt adımında **kod yazılmadı**; yalnızca mimari iskelet, Docker konfigürasyonları ve veritabanı şeması kuruldu.

---

## 2. Mimari Kararlar

| Karar | Seçilen Yaklaşım | Gerekçe |
|---|---|---|
| Repo yapısı | **Monorepo** | Tüm servisler tek repoda; ortak `shared/` katmanı paylaşabilir |
| Container yönetimi | **Docker + docker-compose** | Tek komutla (`make up`) tüm sistem ayağa kalkar |
| Python servisleri | **FastAPI (async)** | Yüksek performanslı async I/O, otomatik OpenAPI dokümantasyonu |
| Notification servisi | **Node.js / TypeScript** | Olay güdümlü (event-driven) mimari için uygun; RabbitMQ consumer |
| Frontend | **Next.js 14 (App Router)** | SSR + SSG desteği, modern React ekosistemi |
| API yönlendirme | **Nginx (gateway/)** | Hafif, production-grade reverse proxy; rate limiting dahil |
| Veritabanı | **PostgreSQL 16 + RLS** | Multi-tenancy için Row Level Security; her klinik izole |
| Cache / Session | **Redis 7** | JWT blacklist, randevu kilitleme, geçici veri |
| Mesaj kuyruğu | **RabbitMQ 3.13** | Servisler arası asenkron iletişim (bildirimler, iptal olayları) |

---

## 3. Klasör Yapısı

```
daf/
│
├── docker-compose.yml              ← Tüm sistemi tek komutla başlatır
├── .env.example                    ← Ortam değişkeni şablonu
├── .gitignore                      ← .env ve build çıktıları git dışı
├── Makefile                        ← Kısayol komutları
├── README.md                       ← Proje hızlı başlangıç kılavuzu
├── MD-1.md                         ← Bu dokümantasyon dosyası
│
├── services/
│   ├── auth-service/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── main.py
│   │   └── app/
│   │       └── __init__.py
│   │
│   ├── appointment-service/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── main.py
│   │   └── app/
│   │       └── __init__.py
│   │
│   ├── notification-service/
│   │   ├── Dockerfile
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   └── src/
│   │       └── index.ts
│   │
│   ├── inventory-service/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── main.py
│   │   └── app/
│   │       └── __init__.py
│   │
│   └── analytics-service/
│       ├── Dockerfile
│       ├── requirements.txt
│       ├── main.py
│       └── app/
│           └── __init__.py
│
├── gateway/
│   ├── Dockerfile                  ← Nginx 1.27-alpine
│   └── nginx.conf                  ← Reverse proxy + rate limiting
│
├── frontend/
│   ├── Dockerfile                  ← Next.js 14 multi-stage build
│   └── .dockerignore
│
└── shared/
    ├── db/
    │   └── init/
    │       └── 01_init.sql         ← Postgres şema (RLS aktif)
    ├── types/
    │   └── __init__.py             ← Ortak Pydantic modelleri (placeholder)
    └── events/
        └── README.md               ← RabbitMQ event sözleşmeleri
```

---

## 4. Oluşturulan Dosyalar — Detaylı Açıklamalar

### 4.1 Kök Dizin Dosyaları

#### `.env.example`
Tüm servisler için gerekli ortam değişkenlerini içeren şablon dosyası.
```
cp .env.example .env
```
komutuyla `.env` oluşturulur ve şifreler düzenlenir. `.env` dosyası **asla Git'e commit edilmez** (`.gitignore` ile korunur).

İçerdiği değişken grupları:
- `POSTGRES_*` — Veritabanı kullanıcı adı, şifre, DB adı
- `REDIS_PASSWORD` — Redis kimlik doğrulaması
- `RABBITMQ_*` — Mesaj kuyruğu kimlik bilgileri
- `JWT_SECRET` / `JWT_ALGORITHM` / `JWT_EXPIRE_MINUTES` — Token güvenliği
- `WHATSAPP_API_URL` / `WHATSAPP_API_KEY` — Bildirim entegrasyonu
- `NEXT_PUBLIC_API_URL` — Frontend'in API'ye bağlanma adresi

#### `.gitignore`
Kritik dışlama kuralları:
- `.env` — Gizli bilgiler
- `__pycache__/`, `*.pyc` — Python önbellek
- `node_modules/`, `.next/`, `dist/` — Build çıktıları

#### `Makefile`
Sık kullanılan Docker komutlarını kısaltır:

| Komut | Açıklama |
|---|---|
| `make up` | Tüm servisleri arka planda başlat |
| `make down` | Tüm servisleri durdur |
| `make build` | Image'ları önbelleksiz yeniden oluştur |
| `make logs` | Canlı log akışını izle |
| `make ps` | Çalışan container'ları listele |
| `make clean` | Container + volume'ları tamamen sil |
| `make db` | Postgres CLI'a doğrudan bağlan |

---

### 4.2 `docker-compose.yml`

Tüm sistemi tek dosyada tanımlayan ana orkestrasyon dosyası. **3 katmana** ayrılmıştır:

#### Altyapı Servisleri

| Servis | Image | Port | Amaç |
|---|---|---|---|
| `postgres` | `postgres:16-alpine` | 5432 | Ana veritabanı |
| `redis` | `redis:7-alpine` | 6379 | Cache ve session |
| `rabbitmq` | `rabbitmq:3.13-management-alpine` | 5672 / 15672 | Mesaj kuyruğu |

Her altyapı servisi için **healthcheck** tanımlanmıştır. Uygulama servisleri, sağlık kontrolü geçene kadar (`condition: service_healthy`) başlamaz.

#### Mikroservisler

Her mikroservis için:
- `build.context` kendi dizinine işaret eder
- `expose` ile sadece iç ağa port açılır (dışarıya değil)
- Environment variables `.env` dosyasından okunur
- `depends_on` ile bağımlı servislerin hazır olması beklenir
- Hepsi `dentai-network` bridge ağında izole çalışır

#### Gateway ve Frontend

- **gateway** → 80 ve 443 portunu dışarıya açar; tüm servis istekleri buradan geçer
- **frontend** → Yalnızca 3000 portunu açar; gateway üzerinden servis edilir

#### Volume ve Network

```yaml
volumes:
  postgres_data:          # Veritabanı verisini container yeniden başlatmada korur

networks:
  dentai-network:         # Tüm servisler arası izole iletişim ağı (bridge)
```

---

### 4.3 Auth Service

**Dil / Framework:** Python 3.12 / FastAPI  
**Port:** 8001  
**Sorumluluk:** Multi-tenant JWT yetkilendirme, klinik izolasyonu

#### `Dockerfile`
- `python:3.12-slim` baz image
- `gcc` ve `libpq-dev` kurulumu (PostgreSQL driver için)
- `requirements.txt` önce kopyalanır → Docker layer cache optimizasyonu
- `uvicorn --reload` geliştirme modunda başlar

#### `requirements.txt` — Temel Bağımlılıklar

| Paket | Amaç |
|---|---|
| `fastapi` | Web framework |
| `uvicorn[standard]` | ASGI sunucu |
| `python-jose[cryptography]` | JWT üretimi ve doğrulaması |
| `passlib[bcrypt]` | Şifre hash'leme |
| `asyncpg` + `sqlalchemy[asyncio]` | Async PostgreSQL bağlantısı |
| `alembic` | Veritabanı migrasyon yönetimi |
| `redis[asyncio]` | JWT blacklist, session |
| `pydantic-settings` | `.env` okuması |

#### `main.py`
- FastAPI uygulaması oluşturulur
- CORS middleware eklenir
- `/health` endpoint'i hazır (gateway health check için)
- Prompt-2'de eklenecek router'lar `TODO` olarak işaretli

#### `app/__init__.py`
Prompt-2'de doldurulacak modül yapısı belgelenmiş:
- `app/core/` — config, security, database
- `app/models/` — Clinic, Doctor, User SQLAlchemy modelleri
- `app/schemas/` — Pydantic request/response şemaları
- `app/routers/` — auth, tenants, users endpoint'leri
- `app/services/` — JWT, bcrypt, tenant izolasyon mantığı

---

### 4.4 Appointment Service

**Dil / Framework:** Python 3.12 / FastAPI  
**Port:** 8002  
**Sorumluluk:** Branş bazlı akıllı randevu ve yedek liste yönetimi

Auth Service'e ek olarak şu bağımlılıklar eklendi:
- `aio-pika` — Async RabbitMQ client (iptal olaylarını kuyruğa gönderir)

`app/__init__.py`'de Prompt-3 için planlanan modüller:
- `app/services/` altında `WaitlistEngine` — iptal olduğunda uygun hastayı atan algoritma

---

### 4.5 Notification Service

**Dil / Framework:** Node.js 20 / TypeScript  
**Port:** 3001  
**Sorumluluk:** Dinamik WhatsApp bildirimleri, Post-Op mesaj planlaması

Bu servis diğerlerinden farklı olarak **Node.js** ile yazılmaktadır çünkü:
- Olay güdümlü (event-driven) mimari için Node.js event loop uygundur
- RabbitMQ mesajlarını tüketmek için reaktif yaklaşım gerekir

#### `package.json` — Temel Bağımlılıklar

| Paket | Amaç |
|---|---|
| `amqplib` | RabbitMQ bağlantısı ve consumer |
| `axios` | WhatsApp API HTTP çağrıları |
| `ioredis` | Zamanlayıcı durumu için Redis |
| `winston` | Yapılandırılmış loglama (JSON format) |

#### `tsconfig.json`
- `target: ES2022` — Modern JavaScript özellikleri
- `strict: true` — Tip güvenliği maksimum
- `outDir: ./dist` — Build çıktısı

#### `src/index.ts`
- `winston` logger ile yapılandırılmış JSON loglama
- `bootstrap()` fonksiyonu ile async başlatma akışı
- Prompt-4'te eklenecek `connectRabbitMQ` ve consumer'lar `TODO` olarak işaretli

#### `Dockerfile` — Multi-Stage Build
1. **builder** aşaması: TypeScript'i JavaScript'e derler
2. **runner** aşaması: Yalnızca production bağımlılıkları + `dist/` klasörü → küçük image

---

### 4.6 Inventory Service

**Dil / Framework:** Python 3.12 / FastAPI  
**Port:** 8003  
**Sorumluluk:** QR kodlu sarf malzeme takibi, döngüsel malzeme ömür yönetimi

Auth Service bağımlılıklarına ek:
- `qrcode[pil]` — QR kod üretimi (Prompt-5'te aktif kullanılacak)

`app/__init__.py`'de Prompt-5 için planlanan servisler:
- `QRGenerator` — Malzeme başına benzersiz QR kod üretir
- `LifespanTracker` — `expected_lifespan` vs gerçek kullanım süresi hesaplar
- `AnomalyDetector` — Beklenenden erken biten malzemeleri işaretler

---

### 4.7 Analytics Service

**Dil / Framework:** Python 3.12 / FastAPI  
**Port:** 8004  
**Sorumluluk:** Patron Dashboard, Recovered Revenue raporlama

Diğer servislerden farklı ek bağımlılık:
- `pandas` — Zaman serisi iptal analizi ve gelir hesaplama

`app/__init__.py`'de Prompt-6 için planlanan servisler:
- `RevenueCalculator` — İptal edilen randevu × randevu ücreti → kurtarılan ciro
- `CancellationAnalyzer` — Doktor/branş/zaman bazlı iptal deseni analizi

---

### 4.8 API Gateway

**Teknoloji:** Nginx 1.27-alpine  
**Port:** 80 (HTTP), 443 (HTTPS hazır)

#### `nginx.conf` — Tasarım Kararları

**Upstream tanımları:** Her mikroservis için ayrı upstream bloğu, servis adı ile Docker internal DNS üzerinden çözülür.

**Rate Limiting:**
```nginx
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=30r/s;
```
- IP bazlı sınırlama (DDoS ve brute-force koruması)
- Auth endpoint'leri: burst=20
- Analytics/Notification: burst=10 (daha kısıtlayıcı)

**Yönlendirme tablosu:**

| Dış URL yolu | İç servis |
|---|---|
| `/api/auth/*` | `auth-service:8001` |
| `/api/appointments/*` | `appointment-service:8002` |
| `/api/notifications/*` | `notification-service:3001` |
| `/api/inventory/*` | `inventory-service:8003` |
| `/api/analytics/*` | `analytics-service:8004` |
| `/health` | Nginx kendisi yanıtlar |

**Güvenlik başlıkları** her yanıta eklenir:
- `X-Frame-Options: SAMEORIGIN`
- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection: 1; mode=block`

---

### 4.9 Frontend

**Teknoloji:** Next.js 14 (App Router)  
**Port:** 3000

#### `Dockerfile` — 3 Aşamalı Build

```
deps    → npm ci ile bağımlılıkları indir
builder → next build ile uygulamayı derle
runner  → Sadece .next/standalone + static dosyalar → minimal image
```

Güvenlik için:
- `nextjs` adında sistem kullanıcısı oluşturulur (root olarak çalışmaz)
- `USER nextjs` ile container root yetkisiz çalışır

`.dockerignore`:
- `node_modules/` ve `.next/` build context'ten hariç tutulur → hızlı build

---

### 4.10 Shared Katmanı

#### `shared/db/init/01_init.sql`

PostgreSQL container ilk başladığında `/docker-entrypoint-initdb.d/` klasöründeki SQL dosyaları **otomatik** çalışır. Bu dosya:

- 7 temel tablo oluşturur
- `user_role` ve `appointment_status` enum tipleri tanımlar
- Tüm tablolarda **Row Level Security (RLS)** aktif eder
- Performans için kritik **indeksler** oluşturur

#### `shared/types/__init__.py`
Prompt-2 ve sonrasında ortak Pydantic temel modellerini içerecek.  
Her servisin kendi `app/schemas/` klasörü bu modelleri extend eder.

#### `shared/events/README.md`
RabbitMQ **event sözleşmelerini** belgeler — hangi servisin ne tür olaylar yayınladığını ve dinlediğini tanımlar. Exchange adı: `dentai.events` (topic type).

---

## 5. Veritabanı Şeması

```
clinics
  id (PK, UUID)
  name, slug (UNIQUE), settings (JSONB), is_active

doctors
  id (PK, UUID)
  clinic_id (FK → clinics) ← RLS anahtarı
  full_name, specialty
  notification_offset (INT) ← "X saat önce bildir" değeri

patients
  id (PK, UUID)
  clinic_id (FK → clinics) ← RLS anahtarı
  full_name, phone, email

appointments
  id (PK, UUID)
  clinic_id (FK → clinics) ← RLS anahtarı
  patient_id (FK → patients)
  doctor_id  (FK → doctors)
  scheduled_at (TIMESTAMPTZ)
  status: scheduled | confirmed | cancelled | completed | no_show
  type, notes

waitlist
  id (PK, UUID)
  clinic_id (FK → clinics) ← RLS anahtarı
  patient_id (FK → patients)
  specialty, priority (INT), is_active

inventory_items
  id (PK, UUID)
  clinic_id (FK → clinics) ← RLS anahtarı
  name, quantity, unit

cycle_materials
  id (PK, UUID)
  clinic_id  (FK → clinics) ← RLS anahtarı
  qr_id (UNIQUE) ← QR kod değeri
  start_date, end_date
  expected_lifespan (INT, gün cinsinden)
  is_active
```

**RLS Stratejisi:** Auth Service, her istek için `SET app.current_clinic_id = '<uuid>'` çalıştırır. PostgreSQL politikaları bu değeri okuyarak yalnızca ilgili klinik satırlarını döner (Prompt-2'de implement edilecek).

---

## 6. Servisler Arası İletişim

```
                    ┌─────────────────────────────────┐
                    │         Nginx Gateway            │
                    │    /api/<slug> → upstream        │
                    └──────────────┬──────────────────┘
                                   │ HTTP
          ┌────────────────────────┼───────────────────────┐
          │                        │                       │
   ┌──────▼──────┐        ┌────────▼──────┐      ┌────────▼──────┐
   │Auth Service │        │  Appointment  │      │  Inventory    │
   │   :8001     │        │  Service:8002 │      │  Service:8003 │
   └──────┬──────┘        └────────┬──────┘      └───────────────┘
          │                        │
          │ JWT Validation         │ appointment.cancelled
          │ (HTTP)                 │ (RabbitMQ → topic exchange)
          │                        ▼
          │                ┌───────────────┐
          │                │   RabbitMQ    │
          │                │   Exchange    │
          │                └───────┬───────┘
          │                        │
          │                        ▼
          │                ┌───────────────┐
          │                │  Notification │
          │                │  Service:3001 │
          │                └───────────────┘
          │
          ▼
   ┌─────────────┐
   │ PostgreSQL  │◄── Analytics Service (read)
   │  (RLS ON)   │◄── Tüm servisler (write)
   └─────────────┘

   ┌─────────────┐
   │    Redis    │◄── JWT blacklist (Auth)
   │             │◄── Cache (tüm servisler)
   └─────────────┘
```

---

## 7. Güvenlik Mimarisi

| Katman | Mekanizma | Detay |
|---|---|---|
| Ağ | Docker bridge network | Servisler yalnızca iç ağdan birbirine erişir; dışarıya sadece gateway açıktır |
| API | Rate limiting (Nginx) | IP başına 30 req/s; burst koruması |
| Kimlik | JWT (HS256) | `python-jose` ile üretim; Redis blacklist ile geçersiz kılma |
| Yetkilendirme | Multi-tenancy (RLS) | PostgreSQL satır düzeyi güvenlik; klinik verisi sızdırmaz |
| Container | Non-root user | Frontend container `nextjs` kullanıcısıyla çalışır |
| Gizli bilgiler | `.env` + Docker secrets | `.env` Git'e commit edilmez; `.env.example` şablon |
| HTTP güvenlik başlıkları | Nginx | X-Frame-Options, X-Content-Type-Options, X-XSS-Protection |

---

## 8. Hızlı Başlangıç

```bash
# 1. Ortam değişkenlerini hazırla
cp .env.example .env
# .env dosyasında tüm şifreleri güven değerlerle değiştir

# 2. Tüm servisleri başlat
make up

# 3. Çalışan servisleri kontrol et
make ps

# 4. Logları izle
make logs

# 5. Belirli bir servisin loguna bak
docker compose logs -f auth-service

# 6. Postgres'e bağlan
make db

# 7. RabbitMQ yönetim paneline eriş
# http://localhost:15672  (kullanıcı: .env'deki RABBITMQ_USER)

# 8. Servisleri durdur
make down
```

---

---

## 9. Prompt 2 Kapsamı ve Kararlar

**Prompt 2 Hedefi:** Sistemin güvenlik beynini ve klinik izolasyon katmanını hayata geçirmek.

| Karar | Seçilen Yaklaşım | Gerekçe |
|---|---|---|
| Şifre hash | **bcrypt** (`passlib`) | Hesaplama maliyetli; brute-force'a karşı dirençli |
| Access Token | **JWT (HS256)** — 60 dk | `clinic_id` + `user_role` payload'a gömülü |
| Refresh Token | **Opaque random token** (SHA-256 hash'i DB'de) | JWT refresh token'ların revoke edilememesi sorununu çözer; token rotation uygulanır |
| RLS Aktivasyonu | `SET LOCAL app.current_clinic_id` — her DB session'ında | Her sorgu otomatik olarak tenant bazlı filtrelenir |
| Shared Middleware | `shared/auth_middleware.py` — tüm servisler import eder | Yetkilendirme mantığı tek noktada; kopya kod yok |
| Rol sistemi | `owner` / `doctor` / `assistant` / `receptionist` | DB enum; genişletilebilir |

---

## 10. PostgreSQL RLS Güncellemeleri

`shared/db/init/01_init.sql` dosyasına aşağıdakiler eklendi:

#### Yeni `users` Tablosu
```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id       UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    email           VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    role            user_role DEFAULT 'receptionist',
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

#### `refresh_tokens` Tablosu
```sql
CREATE TABLE refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(64) UNIQUE NOT NULL,  -- SHA-256 hex
    expires_at  TIMESTAMPTZ NOT NULL,
    is_revoked  BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

#### RLS Politikaları
Her tabloya `clinic_id` filtrelemesi için politika eklendi:
```sql
-- Örnek (doctors tablosu için)
CREATE POLICY clinic_isolation ON doctors
    USING (clinic_id = current_setting('app.current_clinic_id')::UUID);
```
`users`, `patients`, `appointments`, `waitlist`, `inventory_items`, `cycle_materials` tablolarının her biri için aynı politika uygulandı.

---

## 11. Auth Service — Detaylı Implementasyon

### 11.1 Klasör Yapısı

```
services/auth-service/
├── Dockerfile
├── requirements.txt
├── main.py                        ← lifespan + router kaydı
└── app/
    ├── __init__.py
    ├── core/
    │   ├── config.py              ← pydantic-settings (.env okur)
    │   ├── database.py            ← async engine + session factory
    │   ├── security.py            ← JWT üretimi, bcrypt, refresh token hash
    │   ├── dependencies.py        ← get_current_user, require_role FastAPI dep.
    │   └── __init__.py
    ├── models/
    │   ├── clinic.py              ← Clinic SQLAlchemy modeli
    │   ├── user.py                ← User + RefreshToken SQLAlchemy modelleri
    │   └── __init__.py
    ├── schemas/
    │   ├── auth.py                ← Register/Login/Token Pydantic şemaları
    │   ├── tenant.py              ← ClinicResponse/ClinicUpdateRequest
    │   └── __init__.py
    ├── services/
    │   ├── auth_service.py        ← register_clinic, login, refresh, logout
    │   ├── tenant_service.py      ← get_clinic, update_clinic
    │   └── __init__.py
    └── routers/
        ├── auth.py                ← /auth/* endpoint'leri
        ├── tenants.py             ← /tenants/* endpoint'leri
        └── __init__.py
```

### 11.2 `core/` Katmanı

#### `config.py`
`pydantic-settings` ile `.env` dosyasını type-safe okur.

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `DATABASE_URL` | asyncpg bağlantısı | Async PostgreSQL URL |
| `REDIS_URL` | redis://... | JWT blacklist (ileriki adımlar) |
| `JWT_SECRET` | — | En az 32 karakter olmalı |
| `JWT_ACCESS_EXPIRE_MINUTES` | 60 | Access token ömrü |
| `JWT_REFRESH_EXPIRE_DAYS` | 30 | Refresh token ömrü |

#### `database.py`
- `create_async_engine` ile `asyncpg` bağlantı havuzu (pool_size=10, max_overflow=20)
- `async_sessionmaker` fabrikası
- `get_db()` dependency: her istekte yeni session, commit/rollback otomatik
- `Base` — tüm SQLAlchemy modelleri bu sınıftan türer

#### `security.py`

| Fonksiyon | Açıklama |
|---|---|
| `hash_password(plain)` | bcrypt hash üretir |
| `verify_password(plain, hashed)` | Hash karşılaştırması |
| `create_access_token(clinic_id, user_id, role)` | JWT payload: `sub`, `clinic_id`, `role`, `type=access`, `exp`, `iat` |
| `create_refresh_token(user_id)` | `(raw_token, sha256_hash)` tuple döner — raw istemciye, hash DB'ye |
| `decode_access_token(token)` | JWTError fırlatır; `type=access` zorunlu |
| `hash_refresh_token(raw)` | SHA-256 hex döner |

#### `dependencies.py`
- `get_current_user` — Bearer token doğrular, claims dict döner
- `require_role(*roles)` — belirli rolleri zorunlu kılan FastAPI Depends factory

### 11.3 `models/` — SQLAlchemy

**`clinic.py` — Clinic modeli:**
```python
class Clinic(Base):
    id: UUID          # PK
    name: str
    slug: str         # UNIQUE
    settings: dict    # JSONB
    is_active: bool
    created_at: datetime
    # İlişkiler: users →
```

**`user.py` — User + RefreshToken modelleri:**
```python
class User(Base):
    id: UUID
    clinic_id: UUID   # FK → Clinic (RLS anahtarı)
    email: str        # UNIQUE
    hashed_password: str
    full_name: str
    role: UserRole    # owner / doctor / assistant / receptionist
    is_active: bool

class RefreshToken(Base):
    id: UUID
    user_id: UUID     # FK → User
    token_hash: str   # SHA-256; UNIQUE
    expires_at: datetime
    is_revoked: bool
```

### 11.4 `schemas/` — Pydantic

**`auth.py`:**

| Schema | Kullanım | Kritik Alanlar |
|---|---|---|
| `ClinicRegisterRequest` | POST /auth/register | `clinic_name`, `slug`, `admin_email`, `password` |
| `ClinicRegisterResponse` | kayıt yanıtı | `clinic_id`, `user_id`, `access_token`, `refresh_token` |
| `LoginRequest` | POST /auth/login | `email`, `password` |
| `TokenResponse` | login/refresh yanıtı | `access_token`, `refresh_token`, `token_type=bearer` |
| `RefreshRequest` | POST /auth/refresh & /auth/logout | `refresh_token` |
| `CurrentUserResponse` | GET /auth/me | `id`, `email`, `full_name`, `role`, `clinic_id` |

**`tenant.py`:**

| Schema | Kullanım |
|---|---|
| `ClinicResponse` | GET /tenants/me yanıtı |
| `ClinicUpdateRequest` | PATCH /tenants/me — `name`, `settings` (opsiyonel) |

### 11.5 `services/` — İş Mantığı

**`auth_service.py`:**

| Fonksiyon | Açıklama |
|---|---|
| `register_clinic(data, db)` | Klinik + owner user atomik olarak oluşturur; access + refresh token döner |
| `login(data, db)` | Email/şifre doğrular; eski refresh token'ları temizler; yeni çift döner |
| `refresh_access_token(raw_token, db)` | DB'deki hash ile eşleştirir; token rotation — eski revoke, yeni çift oluşturur |
| `logout(raw_token, db)` | Token'ı `is_revoked=True` yapar |

**`tenant_service.py`:**

| Fonksiyon | Açıklama |
|---|---|
| `get_clinic(clinic_id, db)` | UUID ile klinik getirir; 404 fırlatır |
| `update_clinic(clinic_id, data, db)` | `name` veya `settings` JSONB kısmi güncelleme |

### 11.6 `routers/` — Endpoint'ler

**`/auth` router:**

| Method | Path | Yetki | Açıklama |
|---|---|---|---|
| POST | `/auth/register` | Herkese açık | Yeni klinik + admin kurar |
| POST | `/auth/login` | Herkese açık | Email/şifre → token çifti |
| POST | `/auth/refresh` | Herkese açık | Refresh token → yeni çift |
| POST | `/auth/logout` | Herkese açık | Refresh token'ı iptal et |
| GET | `/auth/me` | Bearer Token | Giriş yapan kullanıcı bilgisi |

**`/tenants` router:**

| Method | Path | Yetki | Açıklama |
|---|---|---|---|
| GET | `/tenants/me` | Bearer Token | Klinik bilgilerini getir |
| PATCH | `/tenants/me` | `owner` rolü | Klinik adı/ayarları güncelle |

---

## 12. Shared Auth Middleware

**Dosya:** `shared/auth_middleware.py`

Tüm diğer mikroservisler (Appointment, Inventory, Analytics) bu dosyayı import ederek:
1. Bearer token doğrulama
2. Claim extraction (`clinic_id`, `user_id`, `role`)
3. PostgreSQL RLS context ayarlama
4. Rol bazlı erişim kontrolü

için **aynı kodu** kullanır — kopya olmadan.

#### Sağlanan Depencies/Fonksiyonlar

| İsim | Tür | Açıklama |
|---|---|---|
| `get_verified_claims` | FastAPI Depends | Bearer token'ı doğrular; `{sub, clinic_id, role}` dict döner |
| `set_rls_context(db, clinic_id)` | async fonksiyon | `SET LOCAL app.current_clinic_id = '...'` SQL çalıştırır |
| `require_role(*roles)` | Depends factory | Belirli rolleri `Depends` ile zorunlu kılar |
| `get_clinic_id(claims)` | Yardımcı | Claims'den `UUID` çıkarır |

#### Diğer Servislerde Kullanım Örneği
```python
# appointment-service içinde
from shared.auth_middleware import get_verified_claims, set_rls_context

@router.get("/appointments")
async def list_appointments(
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    # Bu noktadan itibaren tüm DB sorguları yalnızca
    # ilgili kliniğin verilerini döner (RLS devrede)
    ...
```

---

## 13. JWT Akışı ve Token Stratejisi

```
[Register / Login]
    │
    ├─▶ Access Token (JWT, 60 dk)
    │       payload: { sub, clinic_id, role, type:"access", exp, iat }
    │       → Authorization: Bearer <token>
    │
    └─▶ Refresh Token (opaque, 30 gün)
            raw_token  → istemciye gönderilir
            SHA-256    → refresh_tokens tablosuna kaydedilir

[Token Refresh — Rotation]
    1. İstemci raw refresh token gönderir
    2. SHA-256 hesaplanır; DB'de eşleşme aranır
    3. Eski token revoke edilir
    4. Yeni access + refresh token çifti üretilir
    5. İstemciye yeni çift döner

[Logout]
    1. Raw refresh token gönderilir
    2. DB'de is_revoked = TRUE yapılır
    3. Access token: TTL dolana kadar geçerli
       (Redis blacklist Prompt-6'da eklenecek)

[Diğer Servisler]
    Authorization: Bearer <access_token>
    │
    └─▶ shared/auth_middleware.py → decode → clinic_id extract
        → SET LOCAL app.current_clinic_id → RLS devreye girer
```

---

## 14. RLS Çalışma Mekanizması

PostgreSQL Row Level Security, her DB session'ında şu şekilde çalışır:

```sql
-- 1. Her DB isteği başında (middleware tarafından)
SET LOCAL app.current_clinic_id = 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx';

-- 2. RLS policy (doctors tablosu örneği)
CREATE POLICY clinic_isolation ON doctors
    USING (clinic_id = current_setting('app.current_clinic_id')::UUID);

-- 3. Bu sorgu artık yalnızca ilgili kliniğin doktorlarını döner
SELECT * FROM doctors;  -- WHERE clinic_id = '<aktif-klinik-id>' otomatik eklenir
```

**`SET LOCAL`** kullanılmasının önemi: Transaction bittiğinde context otomatik temizlenir → bir isteğin context'i bir sonraki isteğe sızmaz.

---

---

## 15. Prompt 3 Kapsamı ve Kararlar

**Prompt 3 Hedefi:** Randevu yönetimini, akıllı yedek liste motorunu ve otonom event zincirini hayata geçirmek.

| Karar | Seçilen Yaklaşım | Gerekçe |
|---|---|---|
| Event yayınlama | **aio-pika (RabbitMQ topic exchange)** | Async, durable mesaj; notification-service bağımsız dinleyebilir |
| WaitlistEngine tetikleme | **Randevu PATCH içinde** (status→CANCELLED tespitinde) | Ekstra endpoint gerekmez; atomik akış |
| Öncelik sistemi | **priority: INT (1=en yüksek)** | Esnek; asistan istediği sırayı verebilir |
| Soft delete (waitlist) | `is_active=False` | Silinen kayıtlar analiz için korunur |
| Tenant izolasyonu | `shared/auth_middleware.py` + `set_rls_context` | Her endpoint'te RLS otomatik devreye girer |
| Bağlantı havuzu | `connect_robust` (aio-pika) | Reconnect logic dahili; servis yeniden başlasa da mesajlar kaybolmaz |

---

## 16. Appointment Service — Klasör Yapısı

```
services/appointment-service/
├── Dockerfile
├── requirements.txt
├── main.py                         ← lifespan: broker bağlantısı + router kaydı
└── app/
    ├── __init__.py
    ├── core/
    │   ├── config.py               ← pydantic-settings (.env okur)
    │   ├── database.py             ← async engine + session factory
    │   ├── broker.py               ← aio-pika bağlantı + publish_event()
    │   └── __init__.py
    ├── models/
    │   ├── appointment.py          ← Appointment modeli + AppointmentStatus enum
    │   ├── waitlist.py             ← Waitlist modeli
    │   └── __init__.py
    ├── schemas/
    │   ├── appointment.py          ← Create/Update/Response + branş doğrulaması
    │   ├── waitlist.py             ← Add/Update/Response + WaitlistMatchResponse
    │   └── __init__.py
    ├── services/
    │   ├── appointment_service.py  ← CRUD + _handle_cancellation()
    │   ├── waitlist_engine.py      ← Yedek liste CRUD
    │   └── __init__.py
    └── routers/
        ├── appointments.py         ← /appointments endpoint'leri
        ├── waitlist.py             ← /waitlist endpoint'leri
        └── __init__.py
```

---

## 17. `core/` Katmanı — Broker Dahil

### `config.py`
Auth service config'ine ek olarak:

| Değişken | Açıklama |
|---|---|
| `RABBITMQ_URL` | `amqp://user:pass@rabbitmq:5672/` |
| `RABBITMQ_EXCHANGE` | `dentai.events` (topic) |

### `broker.py` — RabbitMQ Bağlantı Katmanı

| Fonksiyon | Açıklama |
|---|---|
| `connect_broker()` | Uygulama başlangıcında `connect_robust` ile durable bağlantı kurar; exchange declare eder |
| `close_broker()` | Uygulama kapanırken bağlantıyı temiz kapatır |
| `publish_event(routing_key, payload)` | Topic exchange'e JSON event yayınlar; `DeliveryMode.PERSISTENT` (mesaj kaybolmaz) |

`connect_robust` sayesinde RabbitMQ geçici olarak kapansa bile servis yeniden bağlanır.

---

## 18. `models/` — SQLAlchemy

### `Appointment`

| Alan | Tip | Açıklama |
|---|---|---|
| `id` | UUID | PK |
| `clinic_id` | UUID FK | RLS anahtarı |
| `patient_id` | UUID FK | Hasta referansı |
| `doctor_id` | UUID FK | Doktor referansı |
| `specialty` | String(100) | Branş — indexed |
| `scheduled_at` | TIMESTAMPTZ | Randevu zamanı — indexed |
| `status` | Enum | `scheduled\|confirmed\|cancelled\|completed\|no_show` — indexed |
| `type` | String | Tedavi tipi (opsiyonel) |
| `notes` | Text | Notlar |
| `updated_at` | TIMESTAMPTZ | `onupdate=func.now()` |

### `Waitlist`

| Alan | Tip | Açıklama |
|---|---|---|
| `id` | UUID | PK |
| `clinic_id` | UUID FK | RLS anahtarı |
| `patient_id` | UUID FK | Hasta referansı |
| `specialty` | String(100) | Branş — indexed |
| `priority` | INT | 1=en yüksek öncelik |
| `is_active` | Bool | `False` → soft deleted veya eşleşme sonrası |
| `preferred_days` | String | Opsiyonel tercih ("Pazartesi,Çarşamba") |

---

## 19. `schemas/` — Pydantic

### Appointment Schemas

| Schema | Kullanım | Kritik Özellik |
|---|---|---|
| `AppointmentCreateRequest` | POST /appointments | `specialty` alan doğrulaması — 8 geçerli branş |
| `AppointmentUpdateRequest` | PATCH /appointments/{id} | `status` değişimi WaitlistEngine'i tetikler |
| `AppointmentResponse` | Tüm yanıtlar | `from_attributes=True` |
| `AppointmentListResponse` | GET /appointments | `items[]` + `total` (pagination) |

### Waitlist Schemas

| Schema | Kullanım | Kritik Özellik |
|---|---|---|
| `WaitlistAddRequest` | POST /waitlist | `priority: int (1-100)` |
| `WaitlistUpdateRequest` | PATCH /waitlist/{id} | Kısmi güncelleme |
| `WaitlistResponse` | Tüm yanıtlar | Öncelik ve aktiflik bilgisi |
| `WaitlistMatchResponse` | İptal event bilgisi | `cancelled_appointment_id` + `matched_waitlist_entry_id` |

**Desteklenen branşlar (VALID_SPECIALTIES):**
Orodonti, Pedodonti, İmplant, Cerrahi, Endodonti, Periodontoloji, Protez, Genel Diş Hekimliği

---

## 20. WaitlistEngine — İptal → Eşleşme → Event Zinciri

```
[PATCH /appointments/{id}]  {status: "cancelled"}
    │
    ├─ Önceki status ≠ cancelled?  → _handle_cancellation() çağrılır
    │
    └─▶ DB sorgusu:
            SELECT * FROM waitlist
            WHERE clinic_id = :cid        ← RLS zaten filtreler
              AND specialty = :specialty  ← Branş eşleşmesi
              AND is_active = TRUE
            ORDER BY priority ASC         ← En yüksek öncelikli
            LIMIT 1
                │
                ├─ Eşleşme BULUNDU:
                │       waitlist.is_active = False  (slot rezerve)
                │       publish_event(
                │           routing_key = "waitlist.match_found",
                │           payload = {
                │               clinic_id, cancelled_appointment_id,
                │               patient_id, waitlist_id, specialty,
                │               original_slot, doctor_id, priority
                │           }
                │       )
                │
                └─ Eşleşme YOK:
                        publish_event(
                            routing_key = "appointment.cancelled",
                            payload = {
                                clinic_id, appointment_id,
                                patient_id, doctor_id,
                                specialty, scheduled_at
                            }
                        )
```

**Kritik tasarım kararı:** `_handle_cancellation()` aynı DB transaction içinde çalışır. Waitlist kaydını `is_active=False` yapıp ardından event yayınlar. Event yayınlanamazsa transaction'ın rol-back edilmesi gereken durumlar için outbox pattern ileriki aşamada eklenebilir.

---

## 21. RabbitMQ Event Kataloğu

**Exchange:** `dentai.events` (topic, durable)

| Routing Key | Yayıncı | Alıcı | Payload Alanları |
|---|---|---|---|
| `appointment.cancelled` | appointment-service | notification-service | `clinic_id`, `appointment_id`, `patient_id`, `doctor_id`, `specialty`, `scheduled_at` |
| `waitlist.match_found` | appointment-service | notification-service | `clinic_id`, `cancelled_appointment_id`, `patient_id`, `waitlist_id`, `specialty`, `original_slot`, `doctor_id`, `priority` |
| `appointment.confirmed` | appointment-service (ileriki) | notification-service | `clinic_id`, `appointment_id`, `patient_id`, `scheduled_at`, `notification_offset` |

---

## 22. `routers/` — Endpoint'ler

### `/appointments` Router

| Method | Path | Yetki | Açıklama |
|---|---|---|---|
| POST | `/appointments` | Bearer Token | Yeni randevu oluştur |
| GET | `/appointments` | Bearer Token | Listele (branş/durum filtresi, pagination) |
| GET | `/appointments/{id}` | Bearer Token | Randevu detayı |
| PATCH | `/appointments/{id}` | Bearer Token | Güncelle → iptal tetikler WaitlistEngine |
| DELETE | `/appointments/{id}` | `owner` veya `doctor` | Randevuyu sil |

### `/waitlist` Router

| Method | Path | Yetki | Açıklama |
|---|---|---|---|
| POST | `/waitlist` | Bearer Token | Yedek listeye hasta ekle |
| GET | `/waitlist` | Bearer Token | Listele (branş/aktiflik filtresi, öncelik sıralı) |
| PATCH | `/waitlist/{id}` | Bearer Token | Öncelik/aktiflik güncelle |
| DELETE | `/waitlist/{id}` | `owner\|doctor\|assistant` | Soft delete (is_active=False) |

**Her endpoint:** `await set_rls_context(db, claims["clinic_id"])` ile başlar → farklı klinik verisi sızamaz.

---

## 23. Prompt 4 Kapsamı ve Kararlar

**Prompt 4 Hedefi:** Sistemin hasta ile konuştuğu dili kurmak: dinamik WhatsApp bildirimleri, doktor bazlı zamanlayıcı ve post-op bakım mesajları.

| Karar | Seçilen Yaklaşım | Gerekçe |
|---|---|---|
| Scheduler | **BullMQ + Redis** | Redis zaten var; BullMQ durable job, retry, backoff sağlar |
| Consumer kütpühanesi | **amqplib** (zaten mevcut) | Düşük bağımlılık; manual ack/nack ile hata kontrolu |
| WhatsApp | **Mock mode** (`WHATSAPP_MOCK=true`) | API key olmadan `console.log + sent_messages` DB kaydı |
| DB erişimi | **pg Pool + withRls()** (TypeScript) | Python shared middleware'in Node.js eşdeğeri |
| Teyit zamanı | `scheduled_at - doctor.notification_offset * saat` | Her doktor farklı offset belirleyebilir |
| Post-op zamanı | `completed_at + POSTOP_DELAY_HOURS saat` (env) | Ağırlıklı 24 saat; env ile ayarlanabilir |
| Graceful shutdown | `SIGTERM` handler + `worker.close()` + `pool.end()` | Docker SIGTERM için temiz kapatılma |

---

## 24. Notification Service — Klasör Yapısı

```
services/notification-service/
├── Dockerfile          ← multi-stage: builder + runner
├── package.json         ← bullmq, pg eklendi
├── tsconfig.json
└── src/
    ├── index.ts            ← bootstrap: DB test + BullMQ + 4x consumer
    ├── config/
    │   └── config.ts          ← tüm ortam değişkenleri type-safe
    ├── utils/
    │   └── logger.ts          ← Winston JSON logger
    ├── types/
    │   └── events.ts          ← Tüm event + job veri tipleri
    ├── db/
    │   └── database.ts        ← pg Pool + withRls() + helper query'ler
    ├── providers/
    │   └── whatsapp.provider.ts  ← Mock + Real mod; mesaj şablonları
    ├── consumers/
    │   ├── matchFoundConsumer.ts   ← waitlist.match_found
    │   ├── cancelledConsumer.ts    ← appointment.cancelled
    │   ├── confirmedConsumer.ts    ← appointment.confirmed
    │   └── completedConsumer.ts    ← appointment.completed
    └── scheduler/
        └── confirmationScheduler.ts ← BullMQ Queue + Worker + zamanla
```

---

## 25. RabbitMQ Consumer Mimarisi

Her consumer:
1. `assertQueue` (durable) → mesajlar broker yeniden başlasa da kaybolmaz
2. `bindQueue` ilgili routing key'e bağlar
3. `prefetch(5)` → aynı anda en fazla 5 mesaj işler
4. Hata durumunda: ilk denemede `nack + requeue`, ikinci denemede `nack + dead-letter`

| Consumer Dosyası | Routing Key | Tetiklenen Aksiyon |
|---|---|---|
| `matchFoundConsumer.ts` | `waitlist.match_found` | Anlık "slot açıldı" WhatsApp + teyit zamanla |
| `cancelledConsumer.ts` | `appointment.cancelled` | Hastaya iptal bildirimi WhatsApp |
| `confirmedConsumer.ts` | `appointment.confirmed` | Doktor offset oku + teyit zamanla |
| `completedConsumer.ts` | `appointment.completed` | Post-op mesaj zamanla |

---

## 26. Dinamik Zamanlayıcı — BullMQ

### Kuyruk: `dentai-notification-jobs`

```
RabbitMQ Event Geldi
        │
        └─▶ Consumer Doctor offset'ini okur (PostgreSQL)
                │
                └─▶ scheduleConfirmation({ sendAt })
                            delay = sendAt - Date.now()
                                    │
                                    └─▶ BullMQ Queue (Redis'te durable)
                                                │
                                      delay ms sonra
                                                │
                                                └─▶ Worker tetiklenir
                                                            │
                                                            └─▶ sendWhatsApp()
                                                                    │
                                                                    └─ Mock: console.log +
                                                                         sent_messages DB kaydı
```

**Job tipleri:**

| Tip | Tetikleyen | Zaman Formulü |
|---|---|---|
| `confirmation` | `matchFoundConsumer` veya `confirmedConsumer` | `scheduled_at − doctor.notification_offset` saat |
| `postop` | `completedConsumer` | `completed_at + POSTOP_DELAY_HOURS` saat |

**Hata toleransı:**
- `attempts: 3` — 3 kez dener
- `backoff: exponential(10s)` — 10s, 20s, 40s aralarla
- Başarısız job'lar Redis'te saklanır; `removeOnFail: {count: 50}`

---

## 27. WhatsApp Entegrasyon Katmanı

### Mock Mod (varsayılan)
`WHATSAPP_API_KEY` yoksa veya `WHATSAPP_MOCK=true` ise aktif.

```
WhatsApp gönderim isteği
    │
    ├─ patients tablosundan telefon numarası okunur (withRls)
    │       └─ Numara yoksa: +90-MOCK-{patient_id[0:8]}
    │
    └─ console.log (Winston JSON formatında)
         sent_messages tablosuna kaydet (withRls)
```

### Mesaj Şablonları (`templates` objesi)

| Tip | İçerik Özeti |
|---|---|
| `matchFound` | "Branş X'te slot açıldı, gelmek ister misiniz?" |
| `confirmation` | "Yarın branş X randevunuz var, teyit edin." |
| `postOp` | "Geçmiş olsun, bakım talimatları için bizi arayın." |
| `cancelledNotice` | "Randevunuz iptal edildi, yeni randevu için bizi arayın." |

### Real Mod'a Geçiş (Prompt-8 veya sonrası)
```bash
WHATSAPP_MOCK=false
WHATSAPP_API_URL=https://api.whatsapp-provider.com/v1
WHATSAPP_API_KEY=<gerçek-anahtar>
```
`sendReal()` fonksiyonu axios ile `POST /messages` atar; başarısızlıkta `status=failed` kaydeder.

---

## 28. Tüm Bildirim Akışı — Uçtan Uca

```
[Kullanıcı] PATCH /appointments/{id} {status: "cancelled"}
        │
        └─▶ [Appointment Service]
                 WaitlistEngine → branş eşleşme kontrolü
                        │
              ┌────────────────────────┤
              │ Eşleşme BULUNDU         │ Bulunamadı
              │                         │
              ▼                         ▼
  waitlist.match_found        appointment.cancelled
        event                       event
              │                         │
              └──[RabbitMQ]───────────┘
                           │
              ┌───────────┴───────────┐
              │   [Notification Service]  │
              │   matchFoundConsumer       cancelledConsumer
              │        │                       │
              │        ▼                       ▼
              │   1. WhatsApp(match_found)  WhatsApp(cancelled)
              │   2. Doctor offset oku         sent_messages
              │   3. BullMQ.add(delay=X)       ──────────
              │        │
              │   [X saat sonra]
              │        │
              │        ▼
              │   BullMQ Worker tetiklenir
              │        │
              │        ▼
              │   WhatsApp(confirmation)
              │        │
              │        ▼
              │   sent_messages DB kaydı
              └──────────────────────────────

[Tedavi Tamamlandı] PATCH {status: "completed"}
        │
        └─▶ appointment.completed event (RabbitMQ)
                 completedConsumer
                        │
                 BullMQ.add(delay=24h)
                        │
                 [24 saat sonra]
                        │
                 WhatsApp(postOp)
```

---

## 29. `sent_messages` Tablosu

`shared/db/init/01_init.sql`'e eklendi:

```sql
CREATE TABLE sent_messages (
    id            UUID DEFAULT gen_random_uuid(),
    clinic_id     UUID NOT NULL,
    patient_id    UUID NOT NULL,
    channel       VARCHAR(50)  DEFAULT 'whatsapp',
    message_type  VARCHAR(100) NOT NULL,  -- confirmation|match_found|postop|cancelled_notice
    content       TEXT         NOT NULL,
    status        VARCHAR(50)  DEFAULT 'sent',  -- sent|failed|pending
    sent_at       TIMESTAMPTZ  DEFAULT NOW(),
    metadata      JSONB        DEFAULT '{}'
);
```

- **RLS aktif** — `clinic_isolation` politikası uygulandı
- İndeksler: `clinic_id`, `patient_id`, `message_type`
- Mock modda `metadata`: `{phone, mock: true}`; Real modda `{phone}`

---

## 30. Appointment Service Güncellemeleri

Prompt-4 kapsamında `appointment_service.py`'ye iki yeni event eklendi:

| Durum Değişikliği | Yayınlanan Event | Routing Key |
|---|---|---|
| `CANCELLED` | Hali hazırda vardı | `appointment.cancelled` veya `waitlist.match_found` |
| `CONFIRMED` | **Yeni eklendi** | `appointment.confirmed` |
| `COMPLETED` | **Yeni eklendi** | `appointment.completed` |

Payload'lar şu alanları içerir: `event`, `clinic_id`, `appointment_id`, `patient_id`, `doctor_id`, `specialty`, `scheduled_at` / `completed_at`.

---

---

## 32. Prompt 5 — Inventory Service: Genel Bakış

`services/inventory-service` servisi iki ana bileşen üzerine kuruludur:

1. **InventoryItem** — Kliniğin bölünebilir sarf malzeme stoğu (pamuk, enjektör vb.). CRUD + stok ayarlama (`adjust_quantity`).
2. **CycleMaterial** — QR kodlu, yaşam döngüsü izlenen malzemeler (matkap ucu, motor, implant). Oluşturma → Aktivasyon → Döngü Kapatma + anomali tespiti.

---

## 33. Prompt 5 — SQL Şeması Güncellemeleri

`shared/db/init/01_init.sql` içinde aşağıdaki sütunlar güncellendi/eklendi:

### `inventory_items` tablosu (yeni sütunlar)
| Sütun | Tip | Açıklama |
|---|---|---|
| `category` | `VARCHAR(100)` | Malzeme kategorisi |
| `min_stock_level` | `NUMERIC(10,2)` | Minimum stok uyarı seviyesi |
| `cost_per_unit` | `NUMERIC(10,2)` | Birim maliyet |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | Son güncelleme zamanı |

### `cycle_materials` tablosu (değişiklikler)
| Sütun | Değişiklik | Açıklama |
|---|---|---|
| `start_date` | `NOT NULL` → nullable | QR aktivasyonunda set edilir |
| `category` | **Yeni eklendi** | Malzeme kategorisi |
| `actual_lifespan` | **Yeni — GENERATED ALWAYS AS** | `(end_date - start_date)` hesaplı sütun |
| `is_high_waste` | **Yeni eklendi** | Anomali bayrağı |
| `end_reason` | **Yeni eklendi** | Döngü kapanma sebebi |
| `waste_note` | **Yeni eklendi** | Serbest metin notları |

---

## 34. Prompt 5 — Dosya Yapısı

```
services/inventory-service/
├── main.py                          # Lifespan, CORS, router kayıtları
├── requirements.txt                 # qrcode[pil] dahil
├── Dockerfile
├── app/
│   ├── core/
│   │   ├── config.py                # ANOMALY_THRESHOLD_RATIO = 0.25
│   │   └── database.py              # AsyncEngine, get_db(), Base
│   ├── models/
│   │   ├── inventory_item.py        # InventoryItem SQLAlchemy modeli
│   │   └── cycle_material.py        # CycleMaterial modeli (actual_lifespan: okunur)
│   ├── schemas/
│   │   ├── items.py                 # ItemCreate/Update/Response, AdjustQuantityRequest
│   │   ├── qr.py                    # QRGenerateRequest/Response, QRActivateRequest/Response
│   │   └── cycle.py                 # CycleEndRequest/Response, CycleMaterialResponse
│   ├── services/
│   │   ├── items_service.py         # CRUD + adjust_quantity()
│   │   ├── qr_service.py            # generate_qr(), activate_qr()
│   │   └── cycle_service.py         # end_cycle() + anomali tespiti, list_cycles()
│   └── routers/
│       ├── items.py                 # /inventory/items
│       ├── qr.py                    # /inventory/qr
│       └── cycle.py                 # /inventory/cycle
```

---

## 35. Prompt 5 — API Endpoint'leri

### InventoryItem (`/inventory/items`)
| Method | Path | Rol | Açıklama |
|---|---|---|---|
| `GET` | `/inventory/items` | any | Klinik stok listesi |
| `POST` | `/inventory/items` | admin/staff | Yeni kalem ekle |
| `GET` | `/inventory/items/{id}` | any | Kalem detayı |
| `PATCH` | `/inventory/items/{id}` | admin/staff | Kalem güncelle |
| `DELETE` | `/inventory/items/{id}` | admin | Kalem sil |
| `POST` | `/inventory/items/{id}/adjust` | admin/staff | Stok artır/azalt (delta + reason) |

### QR (`/inventory/qr`)
| Method | Path | Rol | Açıklama |
|---|---|---|---|
| `POST` | `/inventory/qr/generate` | admin/staff | Yeni malzeme kaydı + QR PNG (base64) |
| `POST` | `/inventory/qr/activate` | admin/staff | QR okutma → start_date = bugün |

### Cycle (`/inventory/cycle`)
| Method | Path | Rol | Açıklama |
|---|---|---|---|
| `GET` | `/inventory/cycle` | any | Cycle listesi (filtre: only_active, only_waste) |
| `POST` | `/inventory/cycle/end` | admin/staff | Döngüyü kapat + anomali tespiti |

---

## 36. Prompt 5 — QR Yaşam Döngüsü

```
generate_qr()          activate_qr()        end_cycle()
     │                      │                    │
     ▼                      ▼                    ▼
CycleMaterial        start_date = today    end_date = today
  is_active = False   is_active = True     is_active = False
  start_date = NULL                        anomali kontrolü →
                                           is_high_waste = ?
```

**QR kod içeriği**: UUID string (örn. `"a3f2e1b4-..."`). Uygulama bu UUID'yi `qr_id` olarak tanır.

**QR PNG üretimi** (`qr_service.py`):
```python
img = qrcode.make(qr_id)         # qrcode[pil]
buffer = io.BytesIO()
img.save(buffer, format="PNG")
b64 = base64.b64encode(buffer.getvalue()).decode()
```

---

## 37. Prompt 5 — Anomali Tespiti Algoritması

`cycle_service.py → end_cycle()`:

```python
ANOMALY_THRESHOLD_RATIO = 0.25   # config.py'den

actual = (today - material.start_date).days
if actual < material.expected_lifespan * ANOMALY_THRESHOLD_RATIO:
    material.is_high_waste = True
    # "YÜKSEK İSRAF: Beklenen X gün, gerçekleşen Y gün (%25 eşiğinin altında)"
```

| Durum | Şart | Sonuç |
|---|---|---|
| Normal kullanım | `actual ≥ expected * 0.25` | `is_high_waste = False` |
| Erken bozulma/kayıp | `actual < expected * 0.25` | `is_high_waste = True`, `anomaly_message` dolu |
| Beklenen ömür tanımsız | `expected_lifespan is None` | Kontrol atlanır |

`CycleEndResponse` hem ham değerleri (actual, expected, is_high_waste) hem de insan okunabilir `anomaly_message` döndürür.

---

## 38. Prompt 5 — RLS Entegrasyonu

Her router fonksiyonu ilk iş olarak `await set_rls_context(db, claims["clinic_id"])` çağırır. Bu, `SET LOCAL app.current_clinic_id = '<uuid>'` çalıştırır ve PostgreSQL RLS politikaları çarpraz-klinik veri sızıntısını engeller (transaction bazlı izolasyon).

```python
@router.get("/inventory/items")
async def read_items(claims = Depends(get_verified_claims), db = Depends(get_db)):
    await set_rls_context(db, claims["clinic_id"])
    return await list_items(clinic_id=claims["clinic_id"], db=db)
```

---

## 39. Sonraki Adımlar (Prompt 5 Sonu)

| Prompt | Kapsam | Durum |
|---|---|---|
| **Prompt 1** | Monorepo iskeleti, docker-compose | ✅ Tamamlandı |
| **Prompt 2** | Auth Service, JWT, RLS, shared middleware | ✅ Tamamlandı |
| **Prompt 3** | Appointment Service, WaitlistEngine, RabbitMQ events | ✅ Tamamlandı |
| **Prompt 4** | Notification Service, BullMQ scheduler, WhatsApp mock | ✅ Tamamlandı |
| **Prompt 5** | Inventory Service — QR kodlar, döngüsel malzeme, anomali | ✅ Tamamlandı |
| **Prompt 6** | Analytics Service — Recovered Revenue dashboard | ⏳ Bekliyor |
| **Prompt 7** | Frontend — Next.js App Router klinik paneli | ⏳ Bekliyor |
| **Prompt 8** | Integration Gateway — DentSoft mapping layer | ⏳ Bekliyor |

---

## 40. Prompt 6 Kapsamı ve Kararlar

### Hedef
"Patron Finansal Karar Merkezi" — hekimin her sabah bakacağı dashboard:
- Bu ay ne kadar kurtarılan ciro var? (Recovered Revenue)
- İptal ve no-show oranları nasıl?
- Hangi malzemelerde israf yüksek?
- Hangi hekim daha iyi performans gösteriyor?

### Teknik Kararlar

| Karar | Tercih | Gerekçe |
|---|---|---|
| Cache katmanı | Redis (DB-4) | Ağır aggregation sorgularını DB'den ayırmak |
| TTL | 3600 sn (1 saat) | Raporun gün içinde stale olmaması, DB yükünün azalması |
| Report hesaplama | Ham SQL + pandas | Aggregation'da ORM overhead'i yoktur; pandas branş karşılaştırması için temizleyici |
| Recovered Revenue tanımı | `match_found` bildirimi gönderilen her slot = kurtarılan randevu | Optimistik ölçüm; sistemin değer yarattığı anın kanıtı |
| Specialty tarife | Config bazlı sabit tarife (`SPECIALTY_FEE`) | MVP'de FK ile doctor.fee kullanmak yerine hızlı MVP çıktısı |
| DB bağlantısı | Mevcut PostgreSQL (RLS korumalı) | Analytics ayrı DB gerektirmez; RLS veri izolasyonunu garanti eder |

---

## 41. Analytics Service — Dosya Yapısı

```
services/analytics-service/
├── main.py                          # lifespan: Redis init/close + router kaydı
├── requirements.txt                 # pandas 2.2.2, redis[asyncio], python-jose
├── Dockerfile
├── app/
│   ├── core/
│   │   ├── config.py                # CACHE_TTL_SECONDS=3600, SPECIALTY_FEE dict
│   │   ├── database.py              # AsyncEngine, get_db()
│   │   └── cache.py                 # init_redis, get_cache, set_cache, build_key
│   ├── queries.py                   # Ham SQL — 5 sorgu fonksiyonu
│   ├── schemas.py                   # Tüm response modelleri
│   ├── routers.py                   # /analytics prefix — 4 endpoint
│   └── services/
│       ├── revenue_service.py       # Recovered Revenue hesaplama
│       ├── appointment_stats_service.py  # İstatistikler (pandas ile rate hesabı)
│       ├── inventory_stats_service.py    # Waste raporu
│       └── doctor_stats_service.py      # Hekim karnesi
```

---

## 42. Redis Caching Mimarisi

`app/core/cache.py` — her servis fonksiyonu aynı pattern'i izler:

```python
cache_key = build_key("report_name", clinic_id, start_date, end_date)
cached = await get_cache(cache_key)
if cached:
    return Schema(**cached, cached=True)     # önbellekten

data = await ...compute...                   # DB'den hesapla
await set_cache(cache_key, data.model_dump())
return data
```

**Anahtar şeması**: `analytics:<rapor_adı>:<clinic_id>:<tarih_aralığı>`  
Örnekler:
- `analytics:recovered_revenue:a3f2...:2026-04-01:2026-04-22`
- `analytics:appt_stats:a3f2...:2026-04-01:2026-04-22`
- `analytics:waste_report:a3f2...`  ← tarihsiz (tüm dönem)
- `analytics:doctor_perf:a3f2...:2026-04-01:2026-04-22`

Response içinde `cached: bool` alanı mevcuttur — frontend önbellek durumunu gösterebilir.

---

## 43. Recovered Revenue Motoru

### Kurtarılan Ciro Tanımı
`sent_messages.message_type = 'match_found'` olan her kayıt, sistemin bir iptal sonucu waitlist üzerinden eşleştirme yaptığını ve hastaya bildirim gönderdiğini kanıtlar. Her böyle bildirim = bir "kurtarılan randevu".

### Hesaplama Akışı
```
sent_messages (match_found)
  → cancelled_appointment_id → appointments → doctors.specialty
  → SPECIALTY_FEE[specialty] → fee
  → Toplam: SUM(fee per notification)
```

### Branş Tarifeleri (`config.py`)
| Branş | Ücret (TRY) |
|---|---|
| İmplant | 8.000 |
| Estetik Diş | 5.000 |
| Ağız Cerrahisi | 4.000 |
| Ortodonti | 3.500 |
| Endodonti | 2.500 |
| Periodontoloji | 2.000 |
| Genel Diş | 1.500 |
| Çocuk Diş | 1.200 |
| Varsayılan | 2.000 |

### SQL Sorgusu (`queries.py → query_waitlist_fills`)
```sql
SELECT sm.id, sm.sent_at, a.id AS original_appointment_id,
       d.specialty, p.full_name AS patient_name
FROM sent_messages sm
JOIN appointments a ON a.id = (sm.metadata->>'cancelled_appointment_id')::UUID
JOIN doctors d ON d.id = a.doctor_id
JOIN patients p ON p.id = sm.patient_id
WHERE sm.clinic_id = :clinic_id
  AND sm.message_type = 'match_found'
  AND sm.sent_at >= :start_date AND sm.sent_at < :end_date
```

`metadata` sütununda GIN index mevcut; sorgu performanslıdır.

---

## 44. Randevu İstatistikleri (pandas)

`appointment_stats_service.py` — toplam istatistikler DB aggregation ile, branş oranları pandas ile hesaplanır:

```python
df = pd.DataFrame(specialty_rows)
df["cancel_rate_pct"]   = (df["cancelled"] / df["total"].replace(0, pd.NA) * 100).round(1)
df["no_show_rate_pct"]  = (df["no_show"]   / df["total"].replace(0, pd.NA) * 100).round(1)
```

**Response alanları**: `total`, `cancelled`, `no_show`, `completed`, `upcoming`, `cancel_rate_pct`, `no_show_rate_pct`, `completion_rate_pct`, `by_specialty[]`

---

## 45. Envanter İsraf Raporu

`inventory_stats_service.py` — iki sorgu birleştirilir:

1. **`query_high_waste_materials`** — `is_high_waste = TRUE` kayıtların tam listesi
2. **`query_waste_by_category`** — Kategori bazlı özet:

```sql
SELECT category,
       COUNT(*) AS total_cycles,
       COUNT(*) FILTER (WHERE is_high_waste) AS high_waste_count,
       ROUND(100.0 * ... / NULLIF(..., 0), 1) AS waste_rate_pct,
       ROUND(AVG(actual_lifespan), 1) AS avg_actual_lifespan
FROM cycle_materials
WHERE clinic_id = :clinic_id AND end_date IS NOT NULL
GROUP BY category
```

**Hekim branşıyla korelasyon**: `by_category` listesiyle hangi kategoride en çok israf olduğu görülür (ör. "anguldurva" kategorisinde %40 israf → o branşa yönelik aksiyon).

---

## 46. Hekim Performans Karnesi

**SQL**: CTE tabanlı — önce tüm randevuları çeker, sonra sadık hasta sayısını yan tabloda hesaplar ve JOIN ile birleştirir.

```sql
WITH appts AS (...),
     loyal AS (
       SELECT doctor_id, COUNT(DISTINCT patient_id) AS loyal_patients
       FROM (
         SELECT doctor_id, patient_id FROM appts
         GROUP BY doctor_id, patient_id HAVING COUNT(*) > 1
       ) sub GROUP BY doctor_id
     )
SELECT doctor_id, doctor_name, specialty,
       COUNT(*) AS total, ...,
       COALESCE(loyal.loyal_patients, 0) AS loyal_patient_count
FROM appts LEFT JOIN loyal ...
GROUP BY ...
ORDER BY completion_rate_pct DESC NULLS LAST
```

**Sadık Hasta Tanımı**: Aynı hekime seçilen dönemde birden fazla randevusu olan hasta.

---

## 47. Analytics API Endpoint'leri

Tüm endpoint'ler `/analytics` prefix'i altındadır.

| Method | Path | Açıklama | Cache |
|---|---|---|---|
| `GET` | `/analytics/revenue/recovered` | Kurtarılan ciro — toplam + branş bazlı | 1 saat |
| `GET` | `/analytics/appointments/stats` | İptal/no-show/completion oranları | 1 saat |
| `GET` | `/analytics/inventory/waste-report` | High-waste malzeme listesi + kategori özeti | 1 saat |
| `GET` | `/analytics/doctors/performance` | Hekim karnesi — doluluk + sadık hasta | 1 saat |

**Query parametreleri** (revenue, appointments, doctors için):
```
?start_date=2026-04-01&end_date=2026-04-22
```
Belirtilmezse varsayılan: `ayın 1'i → bugün`.

**Örnek cevap — Recovered Revenue:**
```json
{
  "period_start": "2026-04-01",
  "period_end": "2026-04-22",
  "total_recovered_appointments": 7,
  "total_recovered_revenue": 42000.0,
  "by_specialty": [
    {"specialty": "İmplant", "count": 3, "revenue": 24000},
    {"specialty": "Ortodonti", "count": 4, "revenue": 14000}
  ],
  "appointments": [...],
  "cached": false
}
```

---

## 48. SQL Şeması Güncellemesi

`shared/db/init/01_init.sql` — iki yeni index eklendi:

```sql
-- Analytics: metadata->>'cancelled_appointment_id' aramasını hızlandırır
CREATE INDEX IF NOT EXISTS idx_sent_messages_metadata
    ON sent_messages USING GIN (metadata);

-- Tarih aralığı filtresi için
CREATE INDEX IF NOT EXISTS idx_sent_messages_sent_at
    ON sent_messages(sent_at);
```

---

## 49. Sonraki Adımlar (Prompt 6 Sonu)

| Prompt | Kapsam | Durum |
|---|---|---|
| **Prompt 1** | Monorepo iskeleti, docker-compose | ✅ Tamamlandı |
| **Prompt 2** | Auth Service, JWT, RLS, shared middleware | ✅ Tamamlandı |
| **Prompt 3** | Appointment Service, WaitlistEngine, RabbitMQ events | ✅ Tamamlandı |
| **Prompt 4** | Notification Service, BullMQ scheduler, WhatsApp mock | ✅ Tamamlandı |
| **Prompt 5** | Inventory Service — QR kodlar, döngüsel malzeme, anomali | ✅ Tamamlandı |
| **Prompt 6** | Analytics Service — Recovered Revenue, istatistikler, hekim karnesi | ✅ Tamamlandı |
| **Prompt 7** | Frontend — Next.js 14 App Router klinik paneli | ⏳ Bekliyor |
| **Prompt 8** | Integration Gateway — DentSoft mapping layer | ⏳ Bekliyor |

---

## 50. Prompt 7 Kapsamı ve Kararlar

### Hedef
Patronun her sabah bakacağı tek panel: Auth → Dashboard → Randevular → Yedek Liste → Envanter. Tüm backend servislerine OAuth Bearer token ile bağlanan, klinik izole (clinic_id JWT'den çıkarılır), mobil uyumlu Next.js 14 uygulaması.

### Teknik Kararlar

| Karar | Tercih | Gerekçe |
|---|---|---|
| Framework | Next.js 14 App Router | Server Components + streaming; modern standart |
| Stil | Tailwind CSS | Utility-first; hızlı iterasyon |
| Bileşen kütüp. | Radix UI primitives + custom | Shadcn/UI yaklaşımı — erişilebilir, unstyled primitives |
| Grafik | Recharts | React-native chart lib; kolay özelleştirme |
| HTTP | axios | İnterceptor desteği — Bearer token otomatik ekleme |
| Toast | sonner | Hafif, modern bildirim |
| Auth depolama | localStorage | SSR'siz client-only app için yeterli |
| JWT decode | Manuel base64 | jose kütüphanesine gerek kalmadan istemci tarafında |
| Tasarım dili | Mavi (#2563eb) + Beyaz + Slate grisi | Profesyonel klinik havası |
| Container | Docker standalone output | `output: 'standalone'` — minimal production image |

---

## 51. Frontend — Dosya Yapısı

```
frontend/
├── Dockerfile                    # Multi-stage: deps → builder → runner (standalone)
├── package.json                  # next 14, recharts, axios, sonner, radix-ui, date-fns
├── next.config.ts                # output: 'standalone'
├── tailwind.config.ts            # brand paleti, shimmer animasyonu
├── tsconfig.json                 # path alias @/*
├── postcss.config.js
├── .env.local.example            # NEXT_PUBLIC_API_URL=http://localhost/api
└── src/
    ├── app/
    │   ├── layout.tsx             # Root layout — Sonner Toaster
    │   ├── page.tsx               # redirect('/dashboard')
    │   ├── globals.css            # Tailwind directives + shimmer keyframe
    │   ├── login/page.tsx         # Login sayfası
    │   └── dashboard/
    │       ├── layout.tsx         # Sidebar + Topbar + auth guard
    │       ├── page.tsx           # Dashboard (revenue + stats + charts)
    │       ├── appointments/page.tsx  # Randevu listesi + iptal
    │       ├── waitlist/page.tsx      # Yedek liste + çıkar
    │       └── inventory/page.tsx     # Stok + QR döngüler + modal
    ├── components/
    │   ├── layout/
    │   │   ├── Sidebar.tsx        # Sabit sol panel, aktif link highlight
    │   │   └── Topbar.tsx         # Sayfa başlığı + tarih + bildirim butonu
    │   ├── ui/
    │   │   ├── Button.tsx         # 5 variant, 3 boyut
    │   │   ├── Badge.tsx          # 6 renk variant
    │   │   └── Skeleton.tsx       # Skeleton, StatCardSkeleton, TableRowSkeleton
    │   └── dashboard/
    │       ├── RevenueCard.tsx    # Hero gradient kartı — Kurtarılan Ciro
    │       ├── StatsCards.tsx     # 4 istatistik kartı
    │       ├── AppointmentChart.tsx    # Recharts BarChart — branş dağılımı
    │       └── DoctorPerformanceTable.tsx  # Hekim karnesi tablosu
    ├── hooks/
    │   ├── useAuth.ts             # login(), logout(), me, claims
    │   ├── useDashboard.ts        # revenue + stats + doctorPerf + wasteReport
    │   ├── useAppointments.ts     # list, cancel, create
    │   ├── useWaitlist.ts         # list, remove
    │   └── useInventory.ts        # items, cycles, generateQr, activateQr, endCycle
    ├── lib/
    │   ├── api-client.ts          # axios instance + interceptors
    │   ├── auth.ts                # token storage + JWT decode
    │   └── utils.ts               # cn(), formatCurrency(), formatDate(), formatPercent()
    └── types/index.ts             # Tüm TypeScript arayüzleri
```

---

## 52. API Client — Bearer Token Otomasyonu

`src/lib/api-client.ts` — tek axios instance, tüm hook'lar buradan import eder:

```typescript
// Request interceptor — her isteğe otomatik token
apiClient.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Response interceptor — 401 → token temizle + /login
apiClient.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401) {
      clearTokens();
      window.location.href = '/login';
    }
    return Promise.reject(error);
  },
);
```

Servis grupları: `authApi`, `appointmentApi`, `waitlistApi`, `inventoryApi`, `analyticsApi` — her biri aynı axios instance'ını kullanır.

---

## 53. Auth Katmanı — Token + Claims

`src/lib/auth.ts`:
- Token'lar `localStorage`'da `dentai_access_token` / `dentai_refresh_token` anahtarlarıyla saklanır.
- `decodeToken(token)` — `atob()` ile base64url decode; sunucu doğrulaması gerektirmez.
- `getCurrentClaims()` → `{ user_id, clinic_id, role, email, full_name }` — multi-tenancy için `clinic_id` JWT'den gelir.
- `isTokenExpired(token)` — `exp * 1000 < Date.now()` kontrolü.

`Dashboard layout` client-side auth guard:
```typescript
useEffect(() => {
  if (!isAuthenticated()) router.replace('/login');
}, [router]);
```

---

## 54. Dashboard Sayfası ve Bileşenler

### RevenueCard
- Mavi gradient (brand-700 → brand-900) hero kart
- Kurtarılan ciro büyük font (text-5xl)
- Branş bazlı mini kart grid (max 6 branş)
- Loading state: skeleton kartlar
- `cached: true` ise ⚡ ibaresi gösterilir

### StatsCards
- 4 kart: Toplam / Tamamlanan / İptal / No-Show
- Her kart: icon + büyük sayı + yüzde alt bilgi
- Loading: `StatCardSkeleton` (animate-pulse)

### AppointmentChart (Recharts)
- Grouped BarChart: Tamamlanan (yeşil) | İptal (kırmızı) | No-Show (turuncu)
- X ekseni: branş adı; responsive container

### DoctorPerformanceTable
- completion_rate_pct'e göre renk badge (yeşil ≥75, sarı ≥50, kırmızı)
- cancel_rate_pct > %20 → kırmızı font
- Skeleton loading: `TableRowSkeleton`

---

## 55. Randevu, Yedek Liste, Envanter Sayfaları

### Randevu Sayfası (`/dashboard/appointments`)
- Durum filter pill'leri: Tümü / Planlandı / Onaylı / Tamamlandı / İptal / Gelmedi
- Tablo: tarih, hasta, hekim·branş, tür, durum badge, iptal butonu (X)
- İptal: `PATCH /appointments/{id}` → optimistik UI güncelleme

### Yedek Liste Sayfası (`/dashboard/waitlist`)
- Öncelik sırasına göre sıralı (priority desc)
- Öncelik badge: Yüksek (kırmızı) / Normal (turuncu) / Düşük (mavi)
- Çıkar butonu → `DELETE /waitlist/{id}`
- Footer notu: "Yüksek öncelikli hastalar randevu iptallerinde otomatik bildirim alır."

### Envanter Sayfası (`/dashboard/inventory`)
- **Tab 1 — Sarf Malzemeleri**: stok miktarı, düşük stok için AlertTriangle + kırmızı badge
- **Tab 2 — QR Döngüler**: is_high_waste satırları kırmızı arkaplan; kategori bazlı israf özeti kutusu
- **QR Generate Modal**: name + category + expected_lifespan formu → `POST /inventory/qr/generate` → QR PNG (base64 img) gösterimi
- Üst satır: toplam uyarı sayaçları (düşük stok, yüksek israf)

---

## 56. Sonraki Adımlar (Prompt 7 Sonu)

| Prompt | Kapsam | Durum |
|---|---|---|
| **Prompt 1** | Monorepo iskeleti, docker-compose | ✅ Tamamlandı |
| **Prompt 2** | Auth Service, JWT, RLS, shared middleware | ✅ Tamamlandı |
| **Prompt 3** | Appointment Service, WaitlistEngine, RabbitMQ events | ✅ Tamamlandı |
| **Prompt 4** | Notification Service, BullMQ scheduler, WhatsApp mock | ✅ Tamamlandı |
| **Prompt 5** | Inventory Service — QR kodlar, döngüsel malzeme, anomali | ✅ Tamamlandı |
| **Prompt 6** | Analytics Service — Recovered Revenue, istatistikler, hekim karnesi | ✅ Tamamlandı |
| **Prompt 7** | Frontend — Next.js 14, Tailwind, Recharts, Bearer client | ✅ Tamamlandı |
| **Prompt 8** | Integration Gateway — DentSoft mapping layer + Production | ✅ Tamamlandı |

---

## 57. Prompt 8 Kapsamı ve Kararlar

**Hedef:** Sistemi "ablamın bilgisayarında Başla tuşuna basılmaya hazır" production durumuna getirmek.

Prompt 8 dört ana teslimattan oluşmaktadır:

| Teslimat | Açıklama |
|----------|---------|
| Integration Service | Harici sistemlerden (DentSoft vb.) Excel/JSON hasta aktarımı |
| WhatsApp Live Mode | Mock → Meta Cloud API geçişi, exponential-backoff retry |
| docker-compose.prod.yml | Production optimize ortam (log limiti, bellek limiti, restart:always) |
| README.md | Kapsamlı kurulum ve kullanım kılavuzu |

**Kararlar:**

- Integration Service ayrı bir FastAPI servisi olarak port **8005**'te çalışır; diğer servislerle aynı PostgreSQL veritabanını kullanır, ancak bağımsız olarak ölçeklenir.
- Duplicate tespiti **bellekte** yapılır: `_patient_key(name, phone)` ile `Set[tuple]` tutulur. Veritabanındaki mevcut kayıtlar önce yüklenir, ardından her batch'te yeni eklenenler sete dahil edilir. Bu yaklaşım N+1 sorgusunu önler.
- Excel sütun normalizasyonu (`strip().lower().replace(" ","_")`) harici sistemlerin tutarsız başlıklarına karşı toleranslıdır.
- Batch boyutu `IMPORT_BATCH_SIZE=200` ile yapılandırılabilirdir; büyük dosyalarda tek bir SQL işlemi yerine parçalı INSERT yapılır.
- WhatsApp için `WHATSAPP_PROVIDER` env var eklendi: `mock` (varsayılan) veya `meta`. Meta Cloud API v19 kullanılmaktadır.

---

## 58. Integration Service — Dosya Yapısı

```
services/integration-service/
├── Dockerfile                      # python:3.12-slim, port 8005
├── requirements.txt                # fastapi, openpyxl, pandas, sqlalchemy[asyncio], asyncpg
├── main.py                         # lifespan, CORS, router bağlama
└── app/
    ├── __init__.py
    ├── schemas.py                  # ExternalPatient, PatientImportRequest, ImportResult
    ├── routers.py                  # POST /integration/import/patients (JSON + Excel)
    ├── core/
    │   ├── __init__.py
    │   ├── config.py               # Settings (pydantic-settings)
    │   └── database.py             # AsyncEngine, get_db()
    └── services/
        ├── __init__.py
        └── import_service.py       # import_patients_json(), import_patients_excel(), _run_import()
```

---

## 59. Patient Import Akışı ve Duplicate Tespiti

```
POST /integration/import/patients/excel
          │
          ▼
  UploadFile → pandas.read_excel()
          │
          ▼  Column normalization: strip().lower().replace(" ","_")
          │
          ▼
  ExternalPatient Pydantic doğrulama
  (telefon: +90 prefix, e-posta: küçük harf)
          │
          ▼
  _run_import(clinic_id, patients, db)
    1. SELECT full_name, phone FROM patients WHERE clinic_id = :cid
       → mevcut kayıtlar "seen" set'ine yüklenir
    2. Yeni listede her hasta için:
       key = (normalized_name, normalized_phone)
       key ∈ seen → skipped_duplicates++
       key ∉ seen → insert_batch'e ekle, seen.add(key)
    3. Her IMPORT_BATCH_SIZE (200) kayıtta bir:
       INSERT INTO patients (...) VALUES (...),(...),... ON CONFLICT DO NOTHING
    4. ImportResult döndür: imported / skipped_duplicates / failed / errors
```

**Güvenlik Notları:**
- JWT doğrulaması zorunludur (Authorization: Bearer token)
- `clinic_id` token içindeki `sub` ile karşılaştırılır; başkasının kliniğine aktarım engellenir
- Yüklenen dosya bellekte işlenir, diske yazılmaz (güvenli geçici işleme)

---

## 60. WhatsApp Live Mode Mimarisi

### Konfigürasyon Değişkenleri

| Değişken | Mock Mod | Live Mod |
|----------|---------|---------|
| `WHATSAPP_PROVIDER` | `mock` | `meta` |
| `WHATSAPP_MOCK` | `true` | `false` |
| `WHATSAPP_PHONE_NUMBER_ID` | (boş) | Meta Business Phone Number ID |
| `WHATSAPP_API_KEY` | (boş) | Meta System User Access Token |

### Mock → Live Geçiş Mantığı (`config.ts`)

```typescript
mockMode:
  process.env.WHATSAPP_PROVIDER === 'mock' ||
  process.env.WHATSAPP_MOCK === 'true' ||
  !process.env.WHATSAPP_PHONE_NUMBER_ID ||
  !process.env.WHATSAPP_API_KEY,
```

Tüm koşullardan herhangi biri `true` ise mock mod devreye girer. `mockMode` güvenli varsayılandır.

### Retry Politikası (Live Mod)

```
Deneme 1 → başarısız (5xx) → 500ms bekle
Deneme 2 → başarısız (5xx) → 1000ms bekle
Deneme 3 → başarısız (5xx) → 2000ms bekle
Deneme 4 → başarısız → hata kayıt, throw
4xx hata → anında hata kayıt, throw (yeniden deneme yok)
```

Her gönderim (başarılı veya başarısız) `sent_messages` tablosuna kaydedilir.

### Meta Cloud API Endpoint

```
POST https://graph.facebook.com/v19.0/{phone_number_id}/messages
Authorization: Bearer {access_token}

Body:
{
  "messaging_product": "whatsapp",
  "to": "+905XXXXXXXXX",
  "type": "text",
  "text": { "preview_url": false, "body": "Mesaj metni..." }
}
```

---

## 61. docker-compose.prod.yml — Tasarım Kararları

| Özellik | Dev Compose | Prod Compose |
|---------|-------------|-------------|
| `restart` | `unless-stopped` | `always` |
| Dahili port açma | ✓ (postgres:5432, redis:6379 vs.) | ✗ (sadece gateway + frontend) |
| Log driver | varsayılan | `json-file`, max-size: 50m, max-file: 5 |
| Bellek limiti | yok | `deploy.resources.limits.memory: 256m` |
| Ortam | dev fallback | `${VAR}` (fallback yok, eksikse crash) |
| Şifre değişkenleri | `:-dentai_secret` fallback | zorunlu, fallback yok |

**Neden bellek limiti?** Sunucu 8 servis çalıştırdığında sınırsız bellek tüketimi diğer servisleri etkiler. 256m, FastAPI servisleri için yeterli üst sınırdır.

**Neden dahili port açılmıyor?** Production'da PostgreSQL, Redis ve RabbitMQ'ya yalnızca container ağı üzerinden erişilmelidir.

---

## 62. Nginx Gateway — Integration Servisi Eklentisi

```nginx
upstream integration_service {
  server integration-service:8005;
}

location /api/integration/ {
  limit_req zone=api_limit burst=5 nodelay;
  proxy_pass http://integration_service/;
  proxy_set_header Host $host;
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  client_max_body_size 20m;   # Excel dosyası için body limiti
}
```

`burst=5` sınırı: Integration servisine yüksek frekanslı istek beklenmez; bulk import işlemleri için düşük burst yeterlidir.

`client_max_body_size 20m`: Excel dosyaları 1–5 MB arasında olsa da güvenli üst sınır olarak 20 MB tanımlandı.

---

## 63. Production Hazırlık Kontrol Listesi

- [ ] Tüm `CHANGE_ME_*` şifreler `.env` içinde dolduruldu
- [ ] `.env` dosyası Git'te yok (`.gitignore`'da)
- [ ] `JWT_SECRET` ≥ 32 rastgele karakter (örn. `openssl rand -hex 32`)
- [ ] `docker compose -f docker-compose.prod.yml up --build -d` başarıyla tamamlandı
- [ ] `curl http://localhost/health` → `{"status":"ok","service":"gateway"}`
- [ ] `curl http://localhost/api/auth/health` → `{"status":"ok"}`
- [ ] İlk klinik ve admin kullanıcı oluşturuldu (API çağrısıyla)
- [ ] PostgreSQL yedek cron görevi kuruldu (`pg_dump`)
- [ ] WhatsApp: mock mod veya live mod test edildi
- [ ] Integration servisi: test Excel dosyası yüklendi, `imported > 0` döndü

---

## 64. Tüm Promptlar — Final Özet

| Prompt | Kapsam | Temel Teknik Kararlar |
|--------|---------|-----------------------|
| **1** | Monorepo iskeleti | Docker Compose, Nginx, shared klasörü |
| **2** | Auth | JWT HS256, bcrypt, RLS (`SET LOCAL`), refresh token rotasyonu |
| **3** | Appointment + Waitlist | WaitlistEngine, `filled_from_waitlist`, RabbitMQ topic exchange |
| **4** | Notification + Scheduler | BullMQ, 4 consumer, `maxRetriesPerRequest: null` |
| **5** | Inventory + QR | `CycleMaterial`, anomali skoru, `GENERATED ALWAYS AS actual_lifespan` |
| **6** | Analytics + Cache | Recovered Revenue JOIN, Redis 5dk TTL, doktor karnesi |
| **7** | Frontend | Next.js 14 App Router, axios Bearer interceptor, Recharts |
| **8** | Integration + Production | Excel import, duplicate set, Meta API retry, prod compose |

---

## 65. Sistem Hazır Durumu

Tüm 8 prompt tamamlanmıştır. Sistemi çalıştırmak için:

```bash
cp .env.example .env
# .env'yi düzenle (şifreleri değiştir)
docker compose up --build -d
# → http://localhost:3000 açılır, giriş ekranı gelir
```

**Servis Sayısı:** 8 mikroservis + 3 altyapı (PostgreSQL, Redis, RabbitMQ) + Nginx gateway + Next.js frontend = **13 container**

**Toplam Dosya:** ~120 kaynak dosyası (Python, TypeScript, SQL, YAML, Dockerfile)

**Mimari Dayanıklılık:**
- Tüm servisler `healthcheck` ile izleniyor
- JWT → RLS → klinik izolasyonu her katmanda korunuyor
- WhatsApp mock/live mod .env değişkeniyle anlık geçiş
- Excel import: duplicate koruma + batch INSERT + hata toleransı

---

*Bu dosya Prompt-1'den Prompt-8'e kadar tüm çıktıları belgelemektedir. Sistem production için hazırdır.*

