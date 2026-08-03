# Vercel Login — Neon + Upstash + Railway

UI Vercel’de kalır. Login için **Postgres (Neon) + Redis (Upstash) + auth API (Railway)** gerekir.  
Next.js doğrudan veritabanına bağlanmaz.

```
Browser → Vercel (ui) → NEXT_PUBLIC_API_URL → Railway gateway → auth-service
                                              ↓                ↓
                                           Neon Postgres    Upstash Redis
```

---

## 1) Neon (PostgreSQL)

1. [console.neon.tech](https://console.neon.tech) → Create Project (Postgres 16, EU/Frankfurt tercihen).
2. **Connect** → iki string kopyala:
   - **Pooled** (`-pooler`) → Railway `DATABASE_URL` (uygulama)
   - **Direct** (pooler yok) → lokal şema script’i
3. Pooled string’i asyncpg formatına çevir (veya auth-service otomatik normalize eder):

```text
postgresql+asyncpg://USER:PASSWORD@ep-xxx-pooler....neon.tech/neondb?ssl=require
```

### Şema + demo seed

```powershell
cd C:\Users\dince\Desktop\daf2026
$env:DATABASE_URL = "postgresql://USER:PASSWORD@ep-xxx....neon.tech/neondb?sslmode=require"  # DIRECT
python scripts/apply_neon_schema.py
```

Demo:

| Alan | Değer |
|------|--------|
| Klinik kodu | `80C791` |
| E-posta | `admin@demo.com` |
| Şifre | `Admin1234` |

---

## 2) Upstash Redis

1. [upstash.com](https://upstash.com) → Redis → EU region.
2. `REDIS_URL` (genelde `rediss://...`) kopyala → Railway.

---

## 3) Railway (auth + gateway)

### Seçenek A — Docker Compose (VPS / lokal cloud test)

`.env` (commit etme):

```env
ENVIRONMENT=production
DATABASE_URL=postgresql+asyncpg://...@ep-xxx-pooler....neon.tech/neondb?ssl=require
REDIS_URL=rediss://default:...@....upstash.io:6379
JWT_SECRET=en_az_32_karakter_rastgele_string_buraya
CORS_ALLOWED_ORIGINS=https://dentt-ai.vercel.app,http://localhost:3000
ALLOW_PUBLIC_REGISTER=false
GATEWAY_PORT=8081
```

```powershell
docker compose -f docker-compose.cloud.yml up --build -d
curl http://localhost:8081/api/auth/health
```

### Seçenek B — Railway Dashboard

1. Repo’yu Railway’e bağla (`dincerv/DenttAI`).
2. **Servis 1 — auth**
   - Dockerfile: `services/auth-service/Dockerfile`
   - Root: repo kökü
   - Env: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `ENVIRONMENT=production`,  
     `CORS_ALLOWED_ORIGINS=https://dentt-ai.vercel.app`, `ALLOW_PUBLIC_REGISTER=false`
   - Private networking adı tercihen `auth-service` (veya gateway’de `AUTH_SERVICE_HOST` set et)
3. **Servis 2 — gateway**
   - Dockerfile: `gateway/Dockerfile.cloud`
   - Public domain generate et
   - Env: `AUTH_SERVICE_HOST=<auth internal host>`, `AUTH_SERVICE_PORT=8001`
4. Gateway public URL örneği: `https://dentai-gateway.up.railway.app`

Doğrulama:

```text
GET https://<gateway>/api/auth/health
→ {"status":"ok","service":"auth-service","checks":{"postgres":"ok","redis":"ok"}}
```

---

## 4) Vercel env checklist

Project → Settings → Environment Variables (Production + Preview):

| Key | Value |
|-----|--------|
| `NEXT_PUBLIC_API_URL` | `https://<railway-gateway-public>/api` |

Örnek: `https://dentai-gateway.up.railway.app/api`

Sonra **Redeploy** (env build’e gömülür).

### CORS

Railway auth env’de Vercel origin olmalı:

```text
CORS_ALLOWED_ORIGINS=https://dentt-ai.vercel.app,https://*.vercel.app
```

Not: FastAPI `CORSMiddleware` wildcard subdomain’i (`*.vercel.app`) desteklemez. Preview URL’ler için her preview origin’i tek tek ekle veya Production domain’i kullan.

Önerilen minimum:

```text
CORS_ALLOWED_ORIGINS=https://dentt-ai.vercel.app,http://localhost:3000
```

### Cookie

`ENVIRONMENT=production` iken refresh cookie `Secure + SameSite=None` olur (cross-site Vercel→API).

---

## 5) Login testi

1. `https://dentt-ai.vercel.app/login`
2. Klinik: `80C791` · E-posta: `admin@demo.com` · Şifre: `Admin1234`
3. DevTools → Network → `POST .../api/auth/login` → **200**
4. CORS / cookie hatası varsa: origin listesi ve `ENVIRONMENT=production` kontrol et

---

## Güvenlik

- Neon / Upstash / JWT secret’ları **asla** git’e koyma.
- `ALLOW_PUBLIC_REGISTER=false` kalsın.
- Bu stack sadece **login (auth)**; randevu/stok API’leri sonra eklenir.
