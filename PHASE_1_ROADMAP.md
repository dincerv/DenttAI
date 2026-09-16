# DentAI Flow — Faz 1 Yol Haritası: Güvenlik ve Stabilite

> Bu dosya, WhatsApp / Takvim geliştirmeden **önce** tamamlanması gereken Faz 1 işlerinin adım adım rehberidir.  
> Her görevi sırayla bitir, checkbox’ı işaretle, sonraki göreve geç.  
> Son güncelleme: 2026-08-02

**Önce sistemi çalıştır:** [`GETTING_STARTED.md`](./GETTING_STARTED.md)  
**İlgili dokümanlar:** `TECHNICAL_REQUIREMENTS.md` · `.cursor/rules/security.mdc` · `.cursor/rules/database-conventions.mdc`

---

## 0. Faz 1 Özeti

| Alan | Hedef |
|------|--------|
| Amaç | Production öncesi güvenlik boşluklarını kapatmak + DB şemasını kodla hizalamak |
| Kapsam dışı | Yeni özellik (WhatsApp live, Google Calendar), UI redesign, Shadcn kurulumu |
| Tahmini süre | 1–2 hafta |
| Aktif klasörler | `ui/`, `services/`, `shared/`, `gateway/` — `frontend/` ve `backend/`’e dokunma |
| Branch önerisi | `refactor/phase-1-security-stability` |

### Görev sırası (bağımlılık sırasına göre)

```
R-05  gitignore (hızlı, risk yok)
  ↓
R-02  secret default’ları kaldır
  ↓
R-03  register kilidi
  ↓
R-01  middleware.ts
  ↓
R-04  PermissionContext default deny
  ↓
R-06  şema drift migration
  ↓
R-07  eksik FK / ON DELETE (R-06 ile aynı migration’da olabilir)
  ↓
✓ Faz 1 kabul testi
```

> **Not:** R-06 ve R-07 tek migration dosyasında birleştirilebilir (`016_schema_drift_and_fk_hardening.sql`). Aşağıda ayrı görev olarak yazıldı; uygulama sırasında birleştirilebilir.

---

## Genel kurallar (Faz 1 boyunca)

- [ ] Değişiklikleri yalnızca `ui/`, `services/`, `shared/`, `gateway/` altında yap
- [ ] Her görev bitince lokal smoke test yap (aşağıdaki kabul kriterleri)
- [ ] Commit formatı: `security(...)`, `fix(...)`, `refactor(db): ...` — `git-workflow.mdc`’ye uy
- [ ] Yeni secret / şifre commit etme
- [ ] Faz 1 bitmeden Faz 2’ye (kırık API, duplicate silme) geçme

---

## R-05 — Hassas dosyaları `.gitignore`’a ekle

**Öncelik:** P0 · **Risk:** Düşük · **Süre:** ~15 dk  
**Neden ilk:** En hızlı güvenlik kazanımı; sonraki commit’lerde sızıntıyı engeller.

### Mevcut durum

- `.gitignore` yalnızca `.env` içeriyor
- `.env.local` ve `HESAPLAR.md` (demo şifreler) izleniyor olabilir

### Yapılacaklar

- [ ] `.gitignore` güncelle:

```gitignore
.env
.env.local
.env.*.local
.env.monitoring
HESAPLAR.md
*.pem
*.key
```

- [ ] Tracked ise Git indeksinden çıkar (dosyayı silmeden):

```bash
git rm --cached HESAPLAR.md
git rm --cached ui/.env.local
git rm --cached frontend/.env.local   # varsa
```

- [ ] `HESAPLAR.md` yerine `HESAPLAR.example.md` oluştur (şifre yerine `CHANGE_ME`)
- [ ] `.env.example` ve `ui/.env.local.example` güncel mi kontrol et

### Kabul kriterleri

- [ ] `git status` içinde `HESAPLAR.md` / `.env.local` “untracked ignored” veya hiç görünmüyor
- [ ] Demo hesap bilgisi artık repoda düz şifre olarak yok (veya sadece example’da placeholder)

### Commit

```
security(chore): hassas dosyaları gitignore'a ekle
```

---

## R-02 — Hardcoded secret default’larını kaldır

**Öncelik:** P0 · **Risk:** Orta (env eksikse servis ayağa kalkmaz — bu istenen davranış) · **Süre:** ~0.5–1 gün

### Mevcut durum

Şu dosyalarda `JWT_SECRET = "change_me_in_production..."` default’ı var:

| Dosya |
|-------|
| `services/auth-service/app/core/config.py` |
| `services/appointment-service/app/core/config.py` |
| `services/inventory-service/app/core/config.py` |
| `services/analytics-service/app/core/config.py` |
| `services/integration-service/app/core/config.py` |
| `services/whatsapp-ingestion-service/app/core/config.py` |

Ayrıca kontrol et:

- [ ] `docker-compose.yml` içindeki `${JWT_SECRET:-change_me...}` fallback
- [ ] `WHATSAPP_WEBHOOK_VERIFY_TOKEN` default’ları
- [ ] `DATABASE_URL` içinde gömülü `dentai_secret` fallback’leri
- [ ] `notification-service/src/config/config.ts`
- [ ] `csrf_fallback_secret` benzeri default’lar (`services/*/main.py`)

### Yapılacaklar

- [ ] Pydantic Settings’te zorunlu alan yap; default string verme:

```python
# YANLIŞ
JWT_SECRET: str = "change_me_in_production_at_least_32_chars"

# DOĞRU
JWT_SECRET: str  # env yoksa startup'ta ValidationError
```

- [ ] Production ortamında uzunluk kontrolü (≥32 karakter) — mümkünse `shared/config_validator.py` ile tüm servislere bağla
- [ ] `docker-compose.yml` / `docker-compose.prod.yml` fallback’lerini kaldır veya sadece `development` profile’da tut
- [ ] `.env.example` içine açıklayıcı placeholder ekle (`CHANGE_ME_JWT_SECRET_MIN_32_CHARS`)
- [ ] Lokal `.env` dosyanda gerçek değerlerin olduğundan emin ol (commit etme)

### Kabul kriterleri

- [ ] `.env` dolu iken `docker compose up` tüm servisler ayağa kalkar
- [ ] `JWT_SECRET` boşken auth-service (ve diğerleri) net hata ile fail eder
- [ ] Kaynak kodda `change_me_in_production` araması sonuç vermez (veya yalnızca `.example` / docs)

### Commit

```
security(shared): hardcoded secret default'larını kaldır
```

---

## R-03 — `/auth/register` endpoint’ini kilitle

**Öncelik:** P0 · **Risk:** Orta · **Süre:** ~0.5 gün  
**Dosyalar:** `services/auth-service/app/routers/auth.py`, ilgili service/schema

### Mevcut durum

- `POST /auth/register` herkese açık (rate limit var ama self-service tenant oluşturmaya izin veriyor)
- README’de de public register akışı anlatılıyor

### Karar (uygulanacak yaklaşım)

**Invite-only / admin-only:** Public self-register kapatılır.

Önerilen davranış:

| Ortam | Davranış |
|-------|----------|
| `production` | `POST /auth/register` → **403** veya endpoint kaldırılır |
| `development` | Sadece `super_admin` JWT ile veya `ALLOW_PUBLIC_REGISTER=true` env ile açık |
| Klinik owner oluşturma | Mevcut admin/owner user create endpoint’leri üzerinden |

### Yapılacaklar

- [ ] `ALLOW_PUBLIC_REGISTER` env ekle (default: `false`)
- [ ] `register` router’ında kontrol:

```python
if not settings.ALLOW_PUBLIC_REGISTER:
    raise HTTPException(status_code=403, detail="Public registration is disabled")
```

- [ ] Alternatif (tercih edilirse): register’ı `require_role("super_admin")` arkasına al
- [ ] OpenAPI / README’deki “herkese kayıt” örneklerini güncelle
- [ ] `.env.example`’a `ALLOW_PUBLIC_REGISTER=false` ekle
- [ ] Seed / `reseed.py` akışının hâlâ çalıştığını doğrula (seed admin üzerinden mi gidiyor?)

### Kabul kriterleri

- [ ] Token olmadan `POST /api/auth/register` → 403 (veya 401)
- [ ] Mevcut login + demo seed hâlâ çalışır
- [ ] Owner’ın kullanıcı oluşturma (`/auth/users` vb.) etkilenmez

### Commit

```
security(auth): public register endpoint'ini kapat
```

---

## R-01 — Next.js `middleware.ts` ekle

**Öncelik:** P0 · **Risk:** Yüksek (yanlış yapılırsa login döngüsü) · **Süre:** 1–2 gün  
**Dosya hedefi:** `ui/src/middleware.ts` (veya `ui/middleware.ts` — Next.js kök/src kuralına göre)

### Kritik mimari kısıt

Şu an access token **`sessionStorage`**’da. Next.js middleware **yalnızca cookie / header** görür; `sessionStorage` göremez.

Bu yüzden middleware için **önce şu karar uygulanmalı:**

#### Seçenek A (önerilen — Faz 1)

1. Login sonrası backend’in set ettiği **refresh cookie** varlığını kontrol et (`dentai_refresh_token` veya mevcut cookie adı).
2. Cookie yoksa `/dashboard/*` → `/login` redirect.
3. Cookie varsa geçir; asıl JWT doğrulama client `AuthContext` + backend’de kalsın.
4. Access token’ı tamamen cookie’ye taşımak Faz 1’de zorunlu değil (Faz 2/3’e bırakılabilir).

#### Seçenek B (daha güvenli — daha büyük iş)

1. Access token’ı da `httpOnly` cookie yap.
2. Middleware cookie’den JWT decode/verify (kısa kontrol).
3. Frontend `sessionStorage` kullanımını kaldır.

**Faz 1 kararı:** Önce **Seçenek A**. Seçenek B ayrı ticket olarak Faz 2 sonuna taşınabilir.

### Yapılacaklar

- [ ] Cookie adını backend’den doğrula (`auth-service` set-cookie)
- [ ] `ui/src/middleware.ts` oluştur:

```typescript
// Pseudocode — gerçek cookie adı koddan alınacak
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = Boolean(request.cookies.get('dentai_refresh_token')?.value);

  const isDashboard = pathname.startsWith('/dashboard');
  const isLogin = pathname.startsWith('/login');

  if (isDashboard && !hasSession) {
    return NextResponse.redirect(new URL('/login', request.url));
  }
  if (isLogin && hasSession) {
    return NextResponse.redirect(new URL('/dashboard', request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ['/dashboard/:path*', '/login'],
};
```

- [ ] `ui/src/app/page.tsx` yorumunu gerçek davranışla uyumlu hale getir
- [ ] CORS / cookie `SameSite` / `Path` ayarlarının middleware’in cookie’yi görmesine engel olmadığını kontrol et
- [ ] Lokal: login → dashboard → logout → dashboard’a doğrudan URL ile gir → login’e düşmeli

### Kabul kriterleri

- [ ] Cookie yokken `/dashboard` → `/login`
- [ ] Login sonrası `/dashboard` açılır
- [ ] Logout sonrası korumalı sayfa erişilemez
- [ ] API çağrıları (apiClient) bozulmaz

### Commit

```
security(frontend): dashboard için middleware auth guard ekle
```

---

## R-04 — `PermissionContext` default deny

**Öncelik:** P0 · **Risk:** Orta (yeni sayfa map’e eklenmezse Forbidden görünür — doğru davranış) · **Süre:** ~2–4 saat  
**Dosya:** `ui/src/context/PermissionContext.tsx`

### Mevcut durum

```typescript
// Unknown routes — allow (no restriction)
return true;
```

Loading sırasında da `canAccess: () => true` — kısa “flash” riski.

### Yapılacaklar

- [ ] Bilinmeyen path için `return false` (default deny)
- [ ] `ROUTE_MODULE_MAP` içindeki tüm mevcut dashboard path’lerini listele ve eksik olanları ekle:

| Path | Module |
|------|--------|
| `/dashboard` | dashboard / home |
| `/dashboard/appointments` | appointments |
| `/dashboard/waitlist` | waitlist |
| `/dashboard/inventory` | inventory |
| `/dashboard/integrations` | integrations |
| `/dashboard/permissions` | permissions |
| `/dashboard/admin/tenants` | admin |

- [ ] Loading state: `canAccess` → `false` **veya** RouteGuard’da “yükleniyor” skeleton göster (403 flash olmasın)
- [ ] `RouteGuard` + `Forbidden` akışını manuel test et (assistant rolü ile)

### Kabul kriterleri

- [ ] Map’te olmayan bir path → Forbidden
- [ ] `owner` / `super_admin` mevcut sayfalara erişir
- [ ] `assistant` yalnızca `allowed_pages` içindeki sayfalara erişir
- [ ] Sayfa yüklenirken yanlışlıkla Forbidden flash’ı olmaz (veya kısa skeleton vardır)

### Commit

```
security(frontend): PermissionContext bilinmeyen rotalarda default deny
```

---

## R-06 — Şema drift tamiri (migration)

**Öncelik:** P0 · **Risk:** Yüksek (yanlış migration prod’u bozar) · **Süre:** 1–2 gün  
**Hedef dosya:** `shared/db/migrations/016_schema_drift_fix.sql`  
**Kaynak gerçeği:** `shared/db/migrations/` (Docker deploy bunu kullanır). `backend/shared/` duplicate — dokunma / senkron notu bırak.

### Eksik / drift listesi (kodda var, SQL’de yok veya eksik)

| # | Eksik | Kullanıldığı yer |
|---|--------|------------------|
| 1 | Tablo `patient_notes` | `appointment-service/.../patient_notes.py`, `notification-service` |
| 2 | Tablo `clinic_integrations` | `integration-service` PMS sync |
| 3 | `doctors.user_id` | users ↔ doctors bağlama |
| 4 | `patients.notes` | `waitlist_engine.py` |
| 5 | `appointments.specialty`, `appointments.updated_at` | ORM / servis |
| 6 | `waitlist.doctor_id`, `waitlist.preferred_days`, `waitlist.notes` | waitlist kodu |
| 7 | `ai_usage_events` RLS politikası | multi-tenant gap |
| 8 | `shared/db/migrations/002_*.sql` boş mu? | `backend/shared` ile karşılaştır, gerekirse sync |

### Migration yazım kuralları

- [ ] `IF NOT EXISTS` / idempotent
- [ ] Her yeni tabloda: `clinic_id`, `created_at`, RLS enable + policy
- [ ] FK’lerde `ON DELETE` açıkça belirt
- [ ] Önce staging / lokal Docker’da uygula
- [ ] ORM modellerini migration’dan **sonra** doğrula (alan uyumu)

### `patient_notes` minimum şema (taslak — koddan netleştir)

```sql
CREATE TABLE IF NOT EXISTS patient_notes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
  patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  doctor_id UUID REFERENCES doctors(id) ON DELETE SET NULL,
  appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,
  note_type VARCHAR(50),
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- + indexes + RLS
```

> Gerçek kolon listesini `services/appointment-service/app/routers/patient_notes.py` INSERT/SELECT ifadelerinden çıkar.

### `clinic_integrations` minimum şema (taslak)

```sql
CREATE TABLE IF NOT EXISTS clinic_integrations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
  provider VARCHAR(50) NOT NULL,          -- dentsoft | drdentes | ...
  config JSONB NOT NULL DEFAULT '{}'::jsonb,
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (clinic_id, provider)
);
-- + RLS
```

### Yapılacaklar checklist

- [ ] Koddan kolon listelerini çıkar (patient_notes, clinic_integrations)
- [ ] `016_....sql` yaz
- [ ] Lokal DB’ye uygula (`scripts/deploy.sh` veya psql)
- [ ] Patient notes API smoke test
- [ ] PMS / integrations endpoint smoke test (varsa)
- [ ] Waitlist sorgusu `patients.notes` ile hata vermiyor
- [ ] `ai_usage_events` için RLS policy ekle
- [ ] `002` boş dosya sorununu çöz (içerik sync veya not)

### Kabul kriterleri

- [ ] Servisler “relation does not exist” / “column does not exist” hatası vermez
- [ ] Yeni tablolarda RLS aktif
- [ ] Migration ikinci kez çalıştırılınca patlamaz (idempotent)

### Commit

```
refactor(db): şema drift için 016 migration ekle
```

---

## R-07 — Eksik FK ve ON DELETE tamamla

**Öncelik:** P0 · **Risk:** Orta–Yüksek (mevcut orphan data varsa migration fail olabilir) · **Süre:** ~0.5–1 gün  
**Tercihen:** R-06 ile aynı PR / aynı SQL dosyası

### Bilinen boşluklar

| İlişki | Sorun | Önerilen ON DELETE |
|--------|--------|---------------------|
| `appointments.patient_id` → `patients` | ON DELETE yok | `RESTRICT` veya `CASCADE` (ürün kararı) |
| `appointments.doctor_id` → `doctors` | ON DELETE yok | `RESTRICT` veya `SET NULL` |
| `waitlist.patient_id` → `patients` | ON DELETE yok | `CASCADE` |
| `sent_messages.patient_id` | FK yok | FK + `SET NULL` |
| `inventory_adjustments.clinic_id` | FK yok | FK + `CASCADE` |

### Karar notları (uygulamadan önce netleştir)

- [ ] Hasta silme politikası: klinik pratikte hasta siliniyor mu, soft-delete mi?
  - Hard delete yoksa → `RESTRICT` güvenli
  - Cascade isteniyorsa → önce orphan kontrol sorgusu çalıştır
- [ ] Orphan kayıt varsa migration öncesi temizlik script’i yaz

### Yapılacaklar

- [ ] Orphan kontrol sorguları çalıştır
- [ ] `ALTER TABLE ... ADD CONSTRAINT` / `ON DELETE` güncellemeleri
- [ ] İndeks + RLS etkilenmediyse dokunma

### Kabul kriterleri

- [ ] FK constraint’ler `\d tablo` / information_schema’da görünür
- [ ] Normal randevu CRUD çalışır
- [ ] Bağlı kayıt silme senaryosu beklenen hatayı veya cascade’i üretir

### Commit

```
refactor(db): eksik foreign key ve ON DELETE davranışlarını tamamla
```

---

## Faz 1 Kabul Testi (Definition of Done)

Tüm R-01…R-07 bittikten sonra bu listeyi baştan sona geç:

### Güvenlik

- [ ] Token/cookie yokken `/dashboard` açılmıyor
- [ ] Public register kapalı
- [ ] Kaynak kodda zayıf secret default yok
- [ ] `HESAPLAR.md` / `.env.local` Git’te değil
- [ ] Bilinmeyen dashboard rotası Forbidden

### Veritabanı

- [ ] `patient_notes` ve `clinic_integrations` mevcut + RLS’li
- [ ] Drift kolonları mevcut
- [ ] Kritik FK’lar tanımlı
- [ ] `docker compose up --build -d` sonrası temel akışlar çalışıyor

### Smoke (manuel)

| # | Senaryo | Beklenen |
|---|---------|----------|
| 1 | Login (owner) | Dashboard açılır |
| 2 | Logout → `/dashboard` URL | Login’e yönlenir |
| 3 | Assistant ile yasak sayfa | Forbidden |
| 4 | Randevu listele / oluştur | 200 |
| 5 | Hasta notu ekle (varsa UI) | 200, DB’de kayıt |
| 6 | Register (public) | 403 |

### Dokümantasyon güncellemesi (Faz 1 kapanırken)

- [ ] `TECHNICAL_REQUIREMENTS.md` içinde R-01…R-07 durumlarını **Tamamlandı** yap
- [ ] `.cursor/rules/project-context.mdc` “Bilinen Teknik Borçlar” listesinden Faz 1 maddelerini çıkar / güncelle
- [ ] Bu dosyada aşağıdaki “İlerleme” tablosunu güncelle

---

## İlerleme Takibi

| ID | Görev | Durum | PR / Commit | Tarih |
|----|-------|--------|-------------|-------|
| R-05 | gitignore + hassas dosyalar | ✅ Bitti | (henüz commit yok) | 2026-08-02 |
| R-02 | Secret default kaldırma | ✅ Bitti | (henüz commit yok) | 2026-08-02 |
| R-03 | Register kilidi | ✅ Bitti | (henüz commit yok) | 2026-08-02 |
| R-01 | middleware.ts | ✅ Bitti | (henüz commit yok) | 2026-08-02 |
| R-04 | Permission default deny | ✅ Bitti | (henüz commit yok) | 2026-08-02 |
| R-06 | Şema drift migration | ✅ Bitti | `016_...sql` + `002` sync | 2026-08-02 |
| R-07 | FK / ON DELETE | ✅ Bitti | `016` içinde | 2026-08-02 |
| DoD | Faz 1 kabul testi | ✅ Bitti | smoke testler geçti | 2026-08-02 |

Durum değerleri: `⬜ Yapılmadı` · `🟡 Devam` · `✅ Bitti` · `⏸️ Engelli`

---

## Engeller / Açık Kararlar

| # | Konu | Seçenekler | Karar |
|---|------|------------|-------|
| 1 | Middleware auth kaynağı | A: refresh cookie · B: access httpOnly cookie | **Faz 1: A** |
| 2 | Public register | Tamamen kapat · super_admin only · env flag | **Env flag, default false** |
| 3 | Hasta silmede appointment FK | RESTRICT · CASCADE · soft-delete | ⬜ Karar bekleniyor |
| 4 | `frontend/` + `backend/` silme | Faz 1’de mi Faz 2’de mi? | **Faz 2 (R-10)** — Faz 1’de dokunma |

---

## Faz 1 bittikten sonra

Sıradaki dosya / faz: **Faz 2 — Frontend İyileştirme** (`TECHNICAL_REQUIREMENTS.md` §4)

1. Kırık `fetch('/api/...')` düzeltmeleri  
2. Gateway route eksikleri  
3. Duplicate klasör silme  
4. Monolitik sayfa parçalama  

WhatsApp live / Takvim **ancak Faz 1 + Faz 2 kritik maddeleri bittikten sonra**.
