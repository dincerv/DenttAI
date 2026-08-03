# DentAI Flow — Nasıl Çalıştırılır?

> Bu rehber Windows (PowerShell) içindir.  
> Faz 1’e başlamadan önce sistemi bir kez ayağa kaldırıp login olduğundan emin ol.  
> Son güncelleme: 2026-08-03

> **Vercel’de login:** Neon + Upstash + Railway gerekir → [docs/VERCEL_CLOUD_LOGIN.md](docs/VERCEL_CLOUD_LOGIN.md)

---

## Mimari (güncel compose)

```
Tarayıcı → UI (localhost:3000)
              ↓
         Nginx Gateway (localhost:8081/api)
              ↓
         auth · appointment · inventory · analytics · integration · notification · whatsapp-ingestion
              ↓
         PostgreSQL · Redis · RabbitMQ
```

| Servis | Container | Port |
|--------|-----------|------|
| Frontend | `dentai_ui` | http://localhost:3000 |
| API Gateway | `dentai_gateway` | http://localhost:8081 |
| PostgreSQL | `dentai_postgres` | localhost:5432 |
| Redis | `dentai_redis` | localhost:6379 |
| RabbitMQ UI | `dentai_rabbitmq` | http://localhost:15672 |

> Not: Eski `backend/Dockerfile` (tek container) eksikti ve build kırılıyordu.  
> `docker-compose.yml` mikroservis + gateway yapısına geri alındı.

---

## 0. Gereksinimler

Kurulu olmalı:

| Araç | Not |
|------|-----|
| **Docker Desktop** | Çalışır durumda (whale ikonu yeşil) |
| **Git** | Repo için |
| **Node.js 20+** | Sadece UI’yi lokal hot-reload ile çalıştıracaksan |
| **Python 3.11+** | Sadece `reseed.py` için |

PowerShell’de kontrol:

```powershell
docker --version
docker compose version
```

---

## 1. Projeyi aç

```powershell
cd C:\Users\dince\Desktop\daf2026
```

---

## 2. Ortam dosyasını hazırla

```powershell
copy .env.example .env
```

`.env` dosyasını düzenle. Geliştirme için örnek (sonra güçlendir):

```env
POSTGRES_USER=dentai
POSTGRES_PASSWORD=dentai_secret
POSTGRES_DB=dentai_db

REDIS_PASSWORD=redis_secret

RABBITMQ_USER=dentai
RABBITMQ_PASS=rabbitmq_secret

JWT_SECRET=dev_local_jwt_secret_at_least_32_chars_long
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

WHATSAPP_PROVIDER=mock
WHATSAPP_MOCK=true

NEXT_PUBLIC_API_URL=http://localhost:8081/api
```

> Not: `docker-compose.yml` içinde bazı default şifreler var; `.env` olmasa da çoğu zaman ayağa kalkar. Yine de `.env` kullanmak doğru alışkanlık.

UI için (Docker dışında `npm run dev` kullanacaksan):

```powershell
cd ui
copy .env.local.example .env.local
```

`ui/.env.local` içeriği:

```env
NEXT_PUBLIC_API_URL=http://localhost:8081/api
```

---

## 3. Tüm sistemi Docker ile başlat

Proje kökünde:

```powershell
cd C:\Users\dince\Desktop\daf2026
docker compose up --build -d
```

İlk build 5–15 dakika sürebilir.

### Durum kontrolü

```powershell
docker compose ps
```

Hepsi `running` / `healthy` olmalı: `postgres`, `redis`, `rabbitmq`, `gateway`, `ui` ve mikroservisler.

### Log izleme

```powershell
docker compose logs -f
```

Sadece gateway veya auth:

```powershell
docker compose logs -f gateway
docker compose logs -f auth-service
```

Durdurmak:

```powershell
docker compose down
```

Volume’larla sıfırdan (DB silinir — dikkat):

```powershell
docker compose down -v
docker compose up --build -d
```

---

## 4. Sağlık kontrolü

Tarayıcı veya PowerShell:

```powershell
# Gateway health
curl http://localhost:8081/health

# UI
start http://localhost:3000
```

| Adres | Ne |
|-------|----|
| http://localhost:3000 | Frontend (login) |
| http://localhost:8081/health | Gateway health |
| http://localhost:8081/api/auth/docs | Auth OpenAPI |
| http://localhost:15672 | RabbitMQ Management (`dentai` / `.env` şifresi) |

---

## 5. Demo veri — zorunlu (login için)

Init SQL tek başına kullanıcı oluşturmaz. Ayrıca migration’ları uygula:

```powershell
cd C:\Users\dince\Desktop\daf2026
Get-ChildItem shared\db\migrations\*.sql | Sort-Object Name | ForEach-Object {
  Get-Content $_.FullName -Raw | docker exec -i dentai_postgres psql -U dentai -d dentai_db
}
```

### Hızlı demo hesap (Python yoksa)

```powershell
$pw = "Admin1234"
$hash = docker exec -e PASSWORD_TO_HASH=$pw dentai_auth python -c "import os; from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt'], deprecated='auto').hash(os.environ['PASSWORD_TO_HASH']))"
$clinicId = "d0be60eb-5d3e-43b6-960e-77014f59397a"
@"
INSERT INTO clinics (id, name, slug, is_active)
VALUES ('$clinicId', 'Demo Klinik', 'demo', true)
ON CONFLICT (id) DO NOTHING;
UPDATE clinics SET code = '80C791' WHERE id = '$clinicId';
INSERT INTO users (clinic_id, email, hashed_password, full_name, role, is_active)
VALUES
  ('$clinicId', 'admin@demo.com', '$hash', 'Admin Kullanici', 'owner', true),
  (NULL, 'superadmin@dentai.io', '$hash', 'Super Admin', 'super_admin', true)
ON CONFLICT DO NOTHING;
"@ | docker exec -i dentai_postgres psql -U dentai -d dentai_db
```

### Tam reseed (Python 3 kuruluysa)

```powershell
python reseed.py
# veya: py -3 reseed.py
```

> ENTER ile onay ister. DB’yi temizleyip zengin demo veri doldurur.

### Demo giriş bilgileri

| Alan | Değer |
|------|--------|
| Klinik kodu | `80C791` (owner/doctor/assistant için) |
| Owner e-posta | `admin@demo.com` |
| Şifre | `Admin1234` |
| Super admin | `superadmin@dentai.io` — klinik kodu **gerekmez** |

---

## 6. Giriş testi (Faz 1 öncesi zorunlu)

1. http://localhost:3000/login aç  
2. Klinik kodu: `80C791`  
3. E-posta: `admin@demo.com`  
4. Şifre: `Admin1234`  
5. Dashboard açılmalı  

Bu adım başarısızsa Faz 1’e geçme; önce log’a bak:

```powershell
docker compose logs backend --tail 100
docker compose logs ui --tail 50
```

---

## 7. İki çalışma modu

### A) Tam Docker (basit — önerilen başlangıç)

```powershell
docker compose up --build -d
```

UI + backend container’da. Kod değişince image rebuild gerekir.

### B) API Docker + UI lokal (geliştirme)

Gateway + servisleri Docker’da bırak, UI’de hot reload:

```powershell
# Terminal 1 — altyapı + API (UI hariç)
cd C:\Users\dince\Desktop\daf2026
docker compose up -d postgres redis rabbitmq auth-service appointment-service inventory-service analytics-service integration-service whatsapp-ingestion-service notification-service gateway

# Terminal 2 — UI lokal
cd C:\Users\dince\Desktop\daf2026\ui
npm install
npm run dev
```

Sonra: http://localhost:3000  
API: `NEXT_PUBLIC_API_URL=http://localhost:8081/api`

> `ui` container’ı da çalışıyorsa port 3000 çakışır:

```powershell
docker compose stop ui
```

---

## 8. Sık karşılaşılan sorunlar

| Sorun | Çözüm |
|-------|--------|
| Port 3000 / 8081 / 5432 dolu | O portu kullanan uygulamayı kapat veya `docker compose down` |
| Gateway / auth unhealthy | `docker compose logs gateway auth-service --tail 80` |
| `Dockerfile: no such file` | Eski `backend` servisi kaldırıldı; güncel `docker-compose.yml` kullan |
| Gateway `no such file` (entrypoint) | Windows CRLF — `gateway/docker-entrypoint.sh` LF olmalı; `docker compose build gateway` |
| Postgres unhealthy / `database "dentai" does not exist` | Healthcheck DB adı: `dentai_db` — güncel compose kullan; gerekirse `docker compose down -v` |
| Init SQL hata / RLS function | `shared/db/init/01_init.sql` güncellendi; volume’u sıfırla: `docker compose down -v` |
| Login 401 / network error | `NEXT_PUBLIC_API_URL` = `http://localhost:8081/api` mi? |
| Demo hesap yok | `python reseed.py` |
| Docker Desktop kapalı | Desktop’ı aç, engine yeşil olana kadar bekle |
| İlk init şema eksik | Postgres volume’u silip yeniden kur: `docker compose down -v` sonra `up --build -d` |

---

## 9. Makefile kısayolları (opsiyonel)

Git Bash / WSL / Make kuruluysa:

```bash
make up      # docker compose up -d
make down
make logs
make ps
make db      # psql shell
```

Windows’ta Make yoksa doğrudan `docker compose ...` kullan.

---

## 10. Faz 1’e geçiş checklist

Bunlar yeşil olmadan kod değiştirmeye başlama:

- [ ] `docker compose ps` → backend + ui healthy/running  
- [ ] http://localhost:3000 açılıyor  
- [ ] http://localhost:8081/health OK  
- [ ] `admin@demo.com` ile login oluyor  
- [ ] Dashboard sayfaları yükleniyor  

Tamamsa sıradaki dosya: **[`PHASE_1_ROADMAP.md`](./PHASE_1_ROADMAP.md)** — R-05’ten başla.
