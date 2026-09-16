# DentAI Flow — Bulut İlerleme Sırası

> Son güncelleme: 2026-08-05

---

## Tamamlanan

Login · Randevu · Yedek liste · Envanter · Gateway · Neon/Upstash · Demo veri

Keep-alive → **en son**

---

## SIRA — Şimdi: Analytics

### A1. Yeni Railway servisi

1. **+ New** → GitHub `DenttAI`
2. Config-as-code path: `railway.analytics.toml`
3. Variables (auth ile aynı / Reference):

```
DATABASE_URL=...
REDIS_URL=...
JWT_SECRET=...
ENVIRONMENT=production
CORS_ALLOWED_ORIGINS=https://dentt-ai.vercel.app,http://localhost:3000
```

AI chat şimdilik opsiyonel (`GEMINI_API_KEY` yoksa dashboard metrikleri yine çalışır).

4. Deploy → Online  
5. Private DNS: `xxxx.railway.internal`

### A2. Gateway’e bağla

`acceptable-courage` → Variables:

```
ANALYTICS_SERVICE_URL=http://<analytics-private-host>:8080
```

Redeploy gateway.

### A3. Test

- `…/api/analytics/health`
- Vercel → **Dashboard** (Recovered Revenue, randevu istatistikleri)

---

## Sonra

RabbitMQ → Notification / WhatsApp (önce mock) → **Keep-alive (en son)** → Faz 2

---

## Bir sonraki tek adım

> **A1 — Analytics servisini Railway’e ekle** (`railway.analytics.toml`).  
> Online olunca private host’u yaz.
