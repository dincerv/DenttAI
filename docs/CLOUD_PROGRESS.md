# DentAI Flow — Bulut İlerleme Sırası

> Bu dosya **tek kaynaklı sıra listesidir**. Her adım bitmeden sonrakine geçme.  
> Son güncelleme: 2026-08-04

---

## Durum özeti

| Faz | Anlam | Durum |
|-----|--------|--------|
| **Faz 1** | Güvenlik / şema stabilite | Kod tamam |
| **Faz C0** | Vercel login (Neon + Upstash + Railway auth) | **TAMAM** |
| **Faz C0.5** | Login yavaşlığını azalt (cold start) | **Şimdi** |
| **Faz C1** | Appointment (+ waitlist) buluta | Sonra |
| **Faz C2** | Gateway + diğer servisler + RabbitMQ | Sonra |
| **Faz 2** | Teknik borç (duplicate klasör, kırık fetch) | Paralel / sonra |

### Canlı URL’ler

| Parça | URL |
|-------|-----|
| UI | `https://dentt-ai.vercel.app` |
| Auth API | `https://denttai-production.up.railway.app` |
| Demo | klinik `80C791` · `admin@demo.com` · `Admin1234` |

---

## Neden giriş yavaş?

İlk istekte genelde **cold start** (ücretsiz / düşük plan):

1. **Railway** — az kullanılan container uykuya yatabilir → uyanma 5–30 sn  
2. **Neon** — compute suspend → ilk sorgu yavaş  
3. Sonraki girişler genelde daha hızlı (her ikisi de “sıcak”ken)

Bu mimari hatası değil; **ücretsiz katman bedeli**.

---

## SIRA — Şimdi (C0.5 — hız)

Tek tek, atlama.

- [x] **H1.** Railway Serverless = OFF (uykuda değil)
- [x] **H2.** Neon Free: scale-to-zero **5 dk sabit** (değiştirilemez — kabul)
- [ ] **H3.** Keep-alive: 5 dk’da bir `/health` ping (Neon’u sıcak tutar)
- [ ] **H4.** İkinci login hızını kontrol et

**H3 bitince C1’e geç.**

---

## SIRA — Sonra (C1 — randevu API)

Login’den sonra dashboard’un asıl ihtiyacı:

1. **C1.1** Railway’e `appointment-service` ekle (aynı Neon `DATABASE_URL` + JWT)  
2. **C1.2** Gateway’i aç **veya** UI path’lerini geçici uyumlu tut  
   - Hedef: `NEXT_PUBLIC_API_URL=https://api.../api` (gateway)  
3. **C1.3** Vercel’den randevu listesi / oluşturma çalışır  
4. **C1.4** Waitlist endpoint’leri

---

## SIRA — Daha sonra (C2+)

1. Inventory + analytics  
2. RabbitMQ (CloudAMQP) + notification  
3. Custom domain: `app.` + `api.` (cookie sadeleştirme)  
4. Faz 2: `_deprecated_frontend` / `backend` sil, kırık `fetch('/api/...')`

---

## C0 checklist (kapanış — tamam)

- [x] Neon + şema + demo seed  
- [x] Upstash Redis  
- [x] Railway auth Online  
- [x] Vercel `NEXT_PUBLIC_API_URL=https://denttai-production.up.railway.app`  
- [x] Vercel’den giriş çalışıyor  
- [ ] Refresh sonrası oturum (F5) — sen bir kez doğrula  
- [x] Secret’lar git’te yok  

---

## Mimari omurga (değişmez)

```
Browser → Vercel (ui) → Auth/API (Railway) → Neon + Upstash
```

- Next.js asla DB’ye bağlanmaz  
- Servisleri **teker teker** ekle  
- Gateway’i C1’de geri almak doğru hedef (şimdilik UI → auth doğrudan)

Detay: [VERCEL_CLOUD_LOGIN.md](./VERCEL_CLOUD_LOGIN.md)

---

## Bir sonraki tek adım

> **C1 — Appointment + Gateway (Railway)**  
> 1) Yeni servis: appointment (`services/appointment-service/Dockerfile`)  
> 2) Yeni servis: gateway (`gateway/Dockerfile.cloud`)  
> 3) Vercel: `NEXT_PUBLIC_API_URL=https://<gateway>/api`  
> Detay adımlar sohbette / aşağıda.
