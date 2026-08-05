# DentAI Flow — Bulut İlerleme Sırası

> Tek kaynaklı sıra. Son güncelleme: 2026-08-05

---

## Durum: C0 + C1 çalışıyor

```
Vercel UI (dentt-ai.vercel.app)
    ↓ NEXT_PUBLIC_API_URL=.../api
Gateway (acceptable-courage-production-1a8d.up.railway.app)
    ├── /api/auth/*         → DenttAI (auth)
    └── /api/appointments/* → meticulous-rejoicing (appointment)
    ↓
Neon Postgres + Upstash Redis
```

| Kontrol | Sonuç |
|---------|--------|
| Login | OK |
| Randevular sayfası | OK (UI açılıyor) |
| Takvim boş / "Doktor seçin" | Normal — DB’de henüz doktor yok |
| rabbitmq disconnected | Bilinçli (C2’ye kadar) |

Demo: klinik `80C791` · `admin@demo.com` · `Admin1234`

---

## SIRA — Şimdi (C1.5 veri)

- [ ] **D1.** En az 1 doktor ekle (UI veya seed)
- [ ] **D2.** Manuel randevu oluştur → takvimde görün
- [ ] **D3.** F5 ile oturum düşüyor mu kontrol et

## SIRA — Sonra

1. **C1.6** Inventory servisini Railway + gateway’e ekle (isteğe bağlı)  
2. **C2** RabbitMQ (CloudAMQP) — iptal/waitlist event’leri  
3. **C0.5** UptimeRobot keep-alive (Neon 5 dk sleep)  
4. **Faz 2** Teknik borç (`_deprecated_frontend`, kırık fetch)

---

## Bir sonraki tek adım

> **D1 — Doktor ekle.** Randevular → Diş Hekimleri / sistemde doktor oluştur.  
> Yoksa “doktor ekleyemiyorum” yaz, seed SQL hazırlarız.
