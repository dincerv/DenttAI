# DentAI Flow — Bulut İlerleme Sırası

> Tek kaynaklı sıra. Son güncelleme: 2026-08-05

---

## Şu an neredeyiz? (öğretici özet)

```
Tarayıcı
   ↓
Vercel (Next.js UI)  ←  dentt-ai.vercel.app
   ↓  NEXT_PUBLIC_API_URL
API katmanı (Railway)
   ├── DenttAI (auth)              Online  ← login / JWT
   ├── meticulous-rejoicing (appt) Online  ← randevu (henüz UI’ya bağlı değil)
   └── gateway                     SONRA   ← /api/auth + /api/appointments birleştirir
   ↓
Neon Postgres + Upstash Redis
```

### Ne yaptık, neden?

| Adım | Ne | Neden |
|------|----|--------|
| Neon | Postgres bulutta | Vercel’deki UI DB’ye bağlanamaz; veriler burada |
| Şema + seed | Tablolar + demo kullanıcı | Login için klinik/kullanıcı şart |
| Upstash | Redis | Auth rate-limit / oturum yardımcıları |
| Railway **DenttAI** | auth-service | Login API |
| Vercel env | `NEXT_PUBLIC_API_URL` → auth | UI login’i buluta yönlendirdi |
| Railway **meticulous-rejoicing** | appointment-service | Randevu API (hazır, gateway bekliyor) |

**Önemli:** UI şu an sadece **auth**’a bakıyor. Randevu sayfası çalışsın diye araya **gateway** koyacağız; tek URL altında `/api/auth` + `/api/appointments`.

---

## Faz durumu

| Faz | Durum |
|-----|--------|
| C0 Login | TAMAM |
| C0.5 Hız (Neon Free 5 dk) | Kısmen — keep-alive sonra |
| **C1 Gateway** | **ŞİMDİ** |
| C1 UI bağla | Gateway’den sonra |

---

## SIRA — C1 Gateway (şimdi)

### G1. Yeni Railway servisi: `gateway`

1. Proje → **+ New** → GitHub `DenttAI` (aynı repo)
2. Settings → Build:
   - Dockerfile path: `gateway/Dockerfile.cloud`
3. Settings → Networking → **Generate Domain** (public — Vercel buraya bağlanacak)
4. Variables:

```
AUTH_SERVICE_HOST=denttai.railway.internal
AUTH_SERVICE_PORT=8080
APPOINTMENT_SERVICE_HOST=meticulous-rejoicing.railway.internal
APPOINTMENT_SERVICE_PORT=8080
```

> Private hostname Settings → Networking → Private Networking’de yazar.  
> Port genelde Railway `PORT` = **8080** (auth’ta gördüğün gibi). Farklıysa oradaki portu yaz.

5. Deploy → Online
6. Test:
   - `https://<gateway>/health`
   - `https://<gateway>/api/auth/health`
   - `https://<gateway>/api/appointments/health`

### G2. Vercel’i gateway’e çevir

```
NEXT_PUBLIC_API_URL=https://<gateway-domain>/api
```

Redeploy → login + randevu aynı API kökünden gider.

### G3. Doğrulama

- [ ] Login hâlâ çalışıyor  
- [ ] `/dashboard/appointments` veri çekiyor (boş liste de OK)  
- [ ] Network’te istekler `<gateway>/api/...`

---

## Bir sonraki tek adım

> **G1 — Gateway servisini ekle** (`gateway/Dockerfile.cloud` + yukarıdaki 4 env).  
> Domain hazır olunca URL’yi buraya yaz.
