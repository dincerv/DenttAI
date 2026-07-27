# DentAI Flow

> Diş kliniklerinde randevu kaçaklarını önleyen, malzeme ömrünü takip eden ve **Kurtarılan Geliri** raporlayan çok kiracılı mikroservis ekosistemi.  
> "Başla tuşuna basmaya hazır" — tüm sistem tek `docker compose up` komutuyla ayağa kalkar.

---

## Mimari Özeti

```
Browser / Mobile
      │
      ▼
  Next.js Frontend (port 3000)
      │
      ▼
  Nginx API Gateway (port 80/443)
      │
  ┌───┴────────────────────────────────────────┐
  │  auth      appt    inventory   analytics   │
  │  (8001)   (8002)    (8003)      (8004)     │
  │         notification  integration          │
  │          (3001)       (8005)               │
  └────────────┬───────────────────────────────┘
               ▼
     PostgreSQL 16 │ Redis 7 │ RabbitMQ 3.13
```

| Servis | Dil / Framework | Sorumluluk | Port |
|--------|----------------|-----------|------|
| **auth-service** | Python / FastAPI | Multi-tenant JWT, refresh token, RLS | 8001 |
| **appointment-service** | Python / FastAPI | Randevu CRUD, WaitlistEngine, RabbitMQ | 8002 |
| **notification-service** | Node.js / TypeScript | WhatsApp bildirimleri, BullMQ scheduler | 3001 |
| **inventory-service** | Python / FastAPI | QR stok takibi, anomali tespiti | 8003 |
| **analytics-service** | Python / FastAPI | Patron Dashboard, Recovered Revenue | 8004 |
| **integration-service** | Python / FastAPI | Excel/JSON hasta içe aktarma (DentSoft) | 8005 |
| **whatsapp-ingestion-service** | Python / FastAPI | WhatsApp webhook ingest + Celery dispatch | 8010 |
| **gateway** | Nginx 1.27 | Reverse proxy, rate limiting | 80/443 |
| **frontend** | Next.js 14 App Router | Klinik yönetim paneli | 3000 |

---

## Klasör Yapısı

```
dentai-flow/
├── docker-compose.yml          ← Geliştirme ortamı
├── docker-compose.prod.yml     ← Production (log limiti, bellek limiti, restart:always)
├── .env.example                ← Ortam değişkenleri şablonu
│
├── services/
│   ├── auth-service/
│   ├── appointment-service/
│   ├── notification-service/
│   ├── inventory-service/
│   ├── analytics-service/
│   └── integration-service/    ← Yeni: DentSoft mapping katmanı
│
├── gateway/
│   ├── Dockerfile
│   └── nginx.conf
│
├── frontend/                   ← Next.js 14 App Router
│
└── shared/
    ├── auth_middleware.py
    └── db/init/01_init.sql     ← 10 tablo, RLS policy, indeksler
```

---

## Gereksinimler

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) ≥ 24
- Docker Compose v2 (Docker Desktop ile gelir)
- Git

---

## Hızlı Başlangıç (Geliştirme)

```bash
# 1. Repoyu klonla
git clone <repo-url> dentai-flow
cd dentai-flow

# 2. Ortam değişkenlerini hazırla
cp .env.example .env
# .env dosyasını aç; CHANGE_ME ile başlayan tüm değerleri doldur

# 3. Tüm servisleri başlat
docker compose up --build -d

# 4. Logları izle
docker compose logs -f

# 5. Servisleri kontrol et
docker compose ps
```

Tarayıcıda aç:

| Adres | İçerik |
|-------|--------|
| http://localhost:3000 | Dashboard (Frontend) |
| http://localhost/api/auth/docs | Auth API Docs |
| http://localhost/api/appointments/docs | Appointment API Docs |
| http://localhost/api/analytics/docs | Analytics API Docs |
| http://localhost/api/integration/docs | Integration API Docs |
| http://localhost/api/whatsapp/health | WhatsApp Ingestion Health |
| http://localhost:15672 | RabbitMQ Management UI |

---

## Production Dağıtımı

```bash
# .env içindeki tüm şifreler güçlü ve benzersiz olmalı
docker compose -f docker-compose.prod.yml up --build -d
```

Production compose farkları:
- Dahili servisler **dış porta açılmaz** (sadece gateway: 80/443, frontend: 3000)
- Her servis için bellek limiti (`deploy.resources.limits.memory: 256m`)
- JSON loglama + rotasyon (`max-size: 50m, max-file: 5`)
- `restart: always`

---

## Monitoring Stack (Prometheus + Grafana + Uptime + Netdata)

Monitoring stack ayrı compose dosyası ile çalışır.

```bash
# 1) Monitoring env dosyasını oluştur
cp .env.monitoring.example .env.monitoring

# 2) Şifreleri güçlü değerlerle güncelle
# - MONITORING_BASIC_AUTH_PASSWORD
# - GRAFANA_ADMIN_PASSWORD

# 3) Monitoring servislerini başlat
docker compose --env-file .env.monitoring -f docker-compose.monitoring.yml up -d --build
```

Erişim adresleri (Basic Auth ile korunur):

| Adres | İçerik |
|-------|--------|
| http://127.0.0.1:8090/prometheus/ | Prometheus UI |
| http://127.0.0.1:8090/alertmanager/ | Alertmanager UI |
| http://127.0.0.1:8090/grafana/ | Grafana UI |
| http://127.0.0.1:8090/status/ | Uptime Kuma |
| http://127.0.0.1:8090/netdata/ | Netdata |

Notlar:
- Prometheus, `integration-service` içindeki `/metrics` endpoint'ini scrape eder.
- Alert kuralları `monitoring/prometheus/alerts.yml` dosyasından yüklenir.
- Bildirim hedefi `Alertmanager` üzerinden e-posta olarak gönderilir (SMTP ayarları `.env.monitoring` içinde zorunlu).
- Monitoring compose, varsayılan olarak `dentai_network` harici ağına bağlanır (`MONITORING_NETWORK_NAME`).

---

## Yeni Klinik Oluşturma

```bash
BASE=http://localhost/api

# 1. Klinik kaydet
curl -X POST $BASE/auth/clinics \
  -H "Content-Type: application/json" \
  -d '{"name":"Akdeniz Ağız Sağlığı","slug":"akdeniz"}'
# → {"id":"<clinic_id>","slug":"akdeniz"}

# 2. Admin kullanıcı oluştur
curl -X POST $BASE/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "clinic_id":"<clinic_id>",
    "email":"admin@akdeniz.com",
    "password":"GüçlüŞifre123!",
    "full_name":"Klinik Yöneticisi",
    "role":"admin"
  }'

# 3. Giriş yap
curl -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@akdeniz.com","password":"GüçlüŞifre123!"}'
# → {"access_token":"...","refresh_token":"..."}
```

---

## Hasta Verisi İçe Aktarma (DentSoft / Excel)

Integration Service, harici klinik yazılımlarından hasta kaydı aktarır.

### Excel Formatı

| Sütun | Zorunlu | Örnek |
|-------|---------|-------|
| `full_name` | ✓ | Ayşe Demir |
| `phone` | ✓ | +905301234567 |
| `email` | — | ayse@mail.com |

Sütun adları büyük/küçük harf ve boşluk toleranslıdır (`Ad Soyad`, `full name`, `FULL_NAME` hepsi kabul edilir).

```bash
curl -X POST http://localhost/api/integration/import/patients/excel \
  -H "Authorization: Bearer <token>" \
  -F "clinic_id=<clinic_id>" \
  -F "file=@hastalar.xlsx"
# → {"imported":284,"skipped_duplicates":12,"failed":0,"errors":[]}
```

**Duplicate Koruması:** Aynı klinik içinde `(full_name, telefon)` çifti mevcutsa kayıt sessizce atlanır.

---

## Kurtarılan Gelir (Recovered Revenue) Nasıl Hesaplanır?

Kurtarılan Gelir, bekleme listesindeki hastalar sayesinde geri kazanılan iptal seansı ücretidir.

```
1. Randevu iptal edilir
        ↓
2. WaitlistEngine → aynı branşta bekleyen hasta bulunur
        ↓
3. "match.found" eventi RabbitMQ'ya yayınlanır
        ↓
4. Notification Service → hasta WhatsApp ile bilgilendirilir
        ↓
5. Randevu tamamlanırsa → completed + filled_from_waitlist = TRUE
        ↓
6. Analytics Service bu seanstaki ücreti recovered_revenue olarak toplar
```

**Formül:**
```sql
recovered_revenue = SUM(fee)
  WHERE status = 'completed'
    AND filled_from_waitlist = TRUE
    AND clinic_id = :cid
    AND completed_at BETWEEN :start AND :end
```

Doluluk oranı %75 olan bir klinik için bekleme listesi aktif kullanıldığında aylık kayıp yaklaşık **%50 azalır**.

---

## WhatsApp Live Mode Aktivasyonu

Varsayılan: mock mod (mesajlar yalnızca veritabanına yazılır, gerçek gönderilmez).

### Canlı Moda Geçiş

1. [Meta Business Suite](https://business.facebook.com/) → WhatsApp → API Ayarları:
   - **Phone Number ID** kopyala
   - System User ile **Kalıcı Erişim Token'ı** oluştur

2. `.env` güncelle:
   ```env
   WHATSAPP_PROVIDER=meta
   WHATSAPP_MOCK=false
   WHATSAPP_PHONE_NUMBER_ID=<phone_number_id>
   WHATSAPP_API_KEY=<access_token>
   ```

3. Servisi yeniden başlat:
   ```bash
   docker compose restart notification-service
   ```

**Retry Politikası:** Başarısız gönderimler 500ms → 1s → 2s gecikmeyle 3 kez daha denenir. HTTP 4xx hataları yeniden denenmez.

---

## Ortam Değişkenleri

| Değişken | Varsayılan | Açıklama |
|----------|-----------|---------|
| `POSTGRES_PASSWORD` | — | **Değiştirilmeli** |
| `REDIS_PASSWORD` | — | **Değiştirilmeli** |
| `RABBITMQ_PASS` | — | **Değiştirilmeli** |
| `JWT_SECRET` | — | **Değiştirilmeli** (≥32 karakter) |
| `WHATSAPP_PROVIDER` | mock | `mock` veya `meta` |
| `WHATSAPP_MOCK` | true | `true` = mock mod |
| `WHATSAPP_PHONE_NUMBER_ID` | — | Meta Cloud API (live mod) |
| `WHATSAPP_API_KEY` | — | Meta erişim token'ı (live mod) |
| `IMPORT_BATCH_SIZE` | 200 | Excel içe aktarma parti büyüklüğü |

---

## Production Hazırlık Kontrol Listesi

- [ ] Tüm `CHANGE_ME_*` değerleri dolduruldu
- [ ] `.env` dosyası `.gitignore`'da
- [ ] `JWT_SECRET` ≥32 rastgele karakter
- [ ] PostgreSQL yedek planı hazırlandı (`pg_dump`)
- [ ] WhatsApp live mod test edildi (gerçek numaraya mesaj gönderildi)
- [ ] `docker compose -f docker-compose.prod.yml up -d` başarılı
- [ ] `http://localhost/health` → `{"status":"ok"}` yanıtı alındı
- [ ] İlk klinik ve admin kullanıcı oluşturuldu
- [ ] Excel ile hasta verisi içe aktarıldı, duplicate koruması doğrulandı

---

## Geliştirici Komutları
