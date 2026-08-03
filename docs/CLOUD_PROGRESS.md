# DentAI Flow — Bulut İlerleme Sırası

> Bu dosya **tek kaynaklı sıra listesidir**. Her adım bitmeden sonrakine geçme.  
> Son güncelleme: 2026-08-03

---

## Kısa cevap: Bu doğru mu?

| Soru | Cevap |
|------|--------|
| Vercel’de login için en gerekli adım mı? | **Evet.** UI tek başına yetmez; auth API + Postgres + Redis şart. |
| Mimari kurallara uygun mu? | **Evet.** Next.js DB’ye bağlanmıyor; `apiClient` → gateway → auth-service. |
| Proje büyürken kalıcı mı? | **Kısmen.** Bu, “login’i buluta çıkarma” **Faz C0**. Tüm SaaS’ı taşımak **Faz C1+**. |
| Yanlış / kaçınılacak yol | UI’ya Prisma/pg eklemek, secret’ı frontend’e koymak, sadece Neon kurup API’siz bırakmak. |

### Neden bu stack?

```
Vercel (ui)  →  Railway gateway + auth  →  Neon (Postgres) + Upstash (Redis)
```

- **Neon:** Postgres 16 + RLS ile uyumlu; serverless/pooled connection DentAI için uygun.
- **Upstash:** Auth rate-limit / Redis ihtiyacı; yönetilen Redis.
- **Railway (veya benzeri):** FastAPI + Nginx’i Docker ile koşturmak için; Vercel Python mikroservis koşmaz.
- **Sadece auth önce:** Login blokajını çözer; 7 servisi bir anda taşımak riskli ve pahalı.

### Büyürken hedef mimari (değişmeyecek omurga)

```
Browser → Vercel UI → api.<domain> (gateway) → mikroservisler → Neon + Redis + RabbitMQ
```

Uzun vadede:

1. Tüm servisler aynı gateway arkasında (şimdi sadece auth).
2. Custom domain: `app.dentai...` (UI) + `api.dentai...` (gateway) — mümkünse **aynı site** cookie (`SameSite=Lax`) için.
3. RabbitMQ / Celery / notification buluta alındıkça WhatsApp ve async işler açılır.

Şimdiki `SameSite=None` cross-site cookie: UI ve API farklı domain’deyken **zorunlu geçici çözüm**. Domain birleşince sadeleştirilir.

---

## Faz durumu

| Faz | Anlam | Durum |
|-----|--------|--------|
| **Faz 1** | Güvenlik / şema stabilite (middleware, secrets, register kilidi…) | Kod tarafı tamam |
| **Faz C0** | Vercel login (Neon + Redis + auth API) | Kod hazır · **hesap/deploy sende** |
| **Faz C1** | Appointment + diğer okuma API’leri buluta | Sonra |
| **Faz C2** | RabbitMQ, notification, WhatsApp, analytics | Sonra |
| **Faz 2** | Duplicate klasör silme, kırık `fetch`, sayfa parçalama | Paralel / sonra |

---

## SIRA — Şimdi yapılacaklar (Faz C0)

Her satır: önce checkbox, sonra tek iş. Atlama.

### A. Hesaplar (sen)

- [x] **A1.** Neon proje oluştur (Postgres 16, EU tercihen) — `DenttAI` / Frankfurt
- [x] **A2.** Upstash Redis oluştur (EU) — `dentai-redis`
- [ ] **A3.** Railway (veya benzeri) hesap + GitHub `DenttAI` bağla
- [x] **A4.** Connection string’leri sadece `.env` / platform secret’a koy — **chata yapıştırma, git’e koyma**

### B. Veritabanı

- [x] **B1.** Neon **direct** URL ile şema + seed uygulandı
- [x] **B2.** Demo: klinik `80C791`, `admin@demo.com` / `Admin1234`

### C. API deploy

- [ ] **C1.** Auth servisini deploy et (`services/auth-service/Dockerfile`)
- [ ] **C2.** Gateway deploy et (`gateway/Dockerfile.cloud`)
- [ ] **C3.** Env’ler:  
  `DATABASE_URL` (Neon pooled/asyncpg) · `REDIS_URL` · `JWT_SECRET` (≥32) ·  
  `ENVIRONMENT=production` · `CORS_ALLOWED_ORIGINS=https://dentt-ai.vercel.app` ·  
  `ALLOW_PUBLIC_REGISTER=false`
- [ ] **C4.** Sağlık: `GET https://<gateway>/api/auth/health` → postgres/redis `ok`

### D. Vercel

- [ ] **D1.** Env: `NEXT_PUBLIC_API_URL=https://<gateway>/api`
- [ ] **D2.** Redeploy (env build’e gömülür)
- [ ] **D3.** `/login` → demo hesap → Network’te login **200**

### E. C0 kapanış kriteri

- [ ] Vercel’den giriş oluyor
- [ ] Refresh cookie çalışıyor (F5 sonrası oturum düşmüyor)
- [ ] CORS hatası yok
- [ ] Secret’lar git’te yok

**C0 bitmeden C1’e geçme.**

Detaylı komutlar: [VERCEL_CLOUD_LOGIN.md](./VERCEL_CLOUD_LOGIN.md)

---

## SIRA — Sonra (Faz C1+)

Sadece C0 yeşil olduktan sonra:

1. **C1.1** Appointment (+ waitlist) servisini aynı Neon + gateway’e ekle  
2. **C1.2** Inventory / analytics (okuma odaklı)  
3. **C1.3** Custom domain: `api.` + `app.` (cookie sadeleştirme)  
4. **C2.1** Redis yanında RabbitMQ (CloudAMQP vb.)  
5. **C2.2** notification + integration + WhatsApp  
6. **Faz 2** teknik borç: `_deprecated_frontend` / `backend` sil, kırık `fetch('/api/...')` düzelt  

---

## Bu turda kodda hazır olanlar (atlanmaz / tekrar yazılmaz)

| Parça | Dosya / not |
|-------|-------------|
| CORS + cookie production | `services/auth-service` |
| Neon URL normalize | `app/core/config.py` |
| Şema + seed script | `scripts/apply_neon_schema.py` |
| Auth-only compose | `docker-compose.cloud.yml` |
| Cloud gateway | `gateway/Dockerfile.cloud`, `routes.auth-only.conf` |
| Adım rehberi | `docs/VERCEL_CLOUD_LOGIN.md` |
| Bu sıra dosyası | `docs/CLOUD_PROGRESS.md` ← **buradasın** |

---

## Karar özeti (büyürken)

1. **Doğru omurga:** UI (Vercel) ≠ DB; API (Docker/Railway) → Neon.  
2. **Doğru tempo:** Önce auth login, sonra servis servis.  
3. **Yanlış tempo:** Tüm mikroservisleri aynı anda taşımak veya UI’ya SQL gömmek.  
4. **Her zaman:** Bu dosyadaki sırayı takip et; yeni iş eklenince buraya numaralı satır olarak yaz.

---

## Bir sonraki tek adım

> **A3 — Railway:** [railway.app](https://railway.app) → Login (GitHub) → New Project → Deploy from GitHub repo `dincerv/DenttAI`.  
> Bitince “Railway bağladım” yaz; C1/C2 (auth + gateway) env’lerini birlikte gireceğiz.
