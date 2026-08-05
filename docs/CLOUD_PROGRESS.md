# DentAI Flow — Bulut İlerleme Sırası

> Son güncelleme: 2026-08-05

---

## Tamamlanan

Login · Randevu · Yedek liste · Gateway · Neon/Upstash

Keep-alive → **en sona alındı** (senin tercihin).

---

## SIRA — Şimdi: Inventory (C1.6)

### I1. Yeni Railway servisi

1. **+ New** → GitHub `DenttAI`
2. Config-as-code path: `railway.inventory.toml`
3. Variables (auth ile aynı):

```
DATABASE_URL=...
REDIS_URL=...
JWT_SECRET=...
ENVIRONMENT=production
CORS_ALLOWED_ORIGINS=https://dentt-ai.vercel.app,http://localhost:3000
```

4. Deploy → Online  
5. Private DNS not et: `xxxx.railway.internal`

### I2. Gateway’e bağla

`acceptable-courage` → Variables → ekle:

```
INVENTORY_SERVICE_URL=http://<inventory-private-host>:8080
```

Redeploy gateway.

### I3. Test

- `https://acceptable-courage-production-1a8d.up.railway.app/api/inventory/health`
- Vercel → **Envanter** sayfası

---

## Sonra

Analytics → RabbitMQ → Notification → **Keep-alive (en son)** → Faz 2

---

## Bir sonraki tek adım

> **I1 — Inventory servisini Railway’e ekle** (`railway.inventory.toml`).  
> Online olunca private host’u yaz.
