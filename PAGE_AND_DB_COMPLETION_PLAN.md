# DentAI Flow â€” Sayfa + DB Tamamlama PlanÄ±

> AmaÃ§: Monolith + Railway ayaktayken **sayfalarÄ± bitirmek**, her adÄ±mda **test etmek**.  
> Branch: `refactor/monolith-migration`  
> CanlÄ±: UI `https://dentai-ui-production.up.railway.app` Â· API `https://denttai-production.up.railway.app`  
>
> **Backend eksikleri (WhatsApp, Celery stub, kolon drift, CSRF):**  
> â†’ ayrÄ±ntÄ±lÄ± denetim + adÄ±mlar: [`BACKEND_COMPLETION_PLAN.md`](./BACKEND_COMPLETION_PLAN.md)

---

## 0. Mevcut durum (Ã¶zet)

### Ne Ã§alÄ±ÅŸÄ±yor (canlÄ± browser smoke 2026-09-16)
| Alan | Durum |
|------|--------|
| Login (superadmin + owner) | âœ… |
| Dashboard (analytics) | âœ… temel |
| Randevular | âœ… Manuel Randevu â†’ POST 201 (hasta+randevu) |
| Yedek Liste | âœ… Hasta ekle â†’ POST 201 |
| Stok / inventory | âœ… Liste + Malzeme Ekle â†’ POST 201 |
| Entegrasyonlar â†’ WhatsApp | âœ… GET/PUT clinic-settings 200 |
| Yetkiler (permissions) | âœ… Liste + yetki modalÄ± aÃ§Ä±lÄ±yor |
| Admin tenants | âœ… (super_admin) |

### Ne eksik / kÄ±rÄ±k
| Alan | Durum | Not |
|------|--------|-----|
| Permissions listesinde `integrations` | âš ï¸ eksik | Modalda yok; asistanlara UIâ€™dan verilemez (AdÄ±m 4) |
| Settings sayfasÄ± | âŒ yok | Entegrasyonlar altÄ±nda WhatsApp var; ayrÄ± settings yok |
| Hastalar sayfasÄ± | âŒ yok | Randevu iÃ§ine gÃ¶mÃ¼lÃ¼ |
| Ã–lÃ¼ bileÅŸenler | âš ï¸ kÄ±smen | WaitlistForm dÃ¼zeltildi; SettingsPanel vb. kalan |
| CSRF + RateLimit | âš ï¸ kapalÄ± | Production gÃ¼venliÄŸi â€” B8 |

### DB / tablolar
| Konu | Durum |
|------|--------|
| Migration seti `002`â€“`017` | âœ… Ã¶zellikler iÃ§in yeterli |
| Neonâ€™da ÅŸema | âœ… login Ã§alÄ±ÅŸtÄ±ÄŸÄ± iÃ§in temel tablolar var |
| Init tek baÅŸÄ±na â€œtam ÅŸemaâ€ deÄŸil | âš ï¸ taze DB = init + tÃ¼m migrationâ€™lar |
| ORM bazÄ± kolonlarÄ± eksik yansÄ±tÄ±yor | âš ï¸ drift (waitlist preferred_doctors, treatment_type vb.) |
| `patients.phone` vs `phone_number` task drift | âš ï¸ post-op / reminder task riski |

**Karar:** BÃ¼yÃ¼k ÅŸema yazmaya gerek yok. Ã–nce Neon doÄŸrulama (AdÄ±m 1), sonra sayfa/API path dÃ¼zeltmeleri.

---

## Ã‡alÄ±ÅŸma kuralÄ± (her adÄ±mda)

1. KÃ¼Ã§Ã¼k deÄŸiÅŸiklik yap  
2. Lokal veya Railwayâ€™de ilgili ekranÄ± test et  
3. Checklistâ€™teki kutuyu iÅŸaretle  
4. Sonra bir sonraki adÄ±ma geÃ§  

Test hesabÄ±:
- Owner: `admin@demo.com` / `Admin1234` / klinik `80C791`
- Superadmin: `superadmin@dentai.io` / `Admin1234` (klinik boÅŸ)

---

## ADIM 1 â€” Neon ÅŸema doÄŸrulama (DB tam mÄ±?)

**AmaÃ§:** CanlÄ± DBâ€™de kritik tablo/kolonlarÄ±n var olduÄŸunu kanÄ±tla.

### 1.1 Ã‡alÄ±ÅŸtÄ±rÄ±lacak kontrol (Neon SQL Editor veya `psql`)

```sql
-- Kritik tablolar
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'clinics','users','refresh_tokens','doctors','patients',
    'appointments','waitlist','inventory_items','inventory_adjustments',
    'cycle_materials','sent_messages','clinic_settings','doctor_settings',
    'appointment_extended','clinic_faq','patient_feedback',
    'whatsapp_message_log','ai_usage_events','patient_notes','clinic_integrations'
  )
ORDER BY 1;

-- Kritik kolonlar (Ã¶rnek)
SELECT column_name FROM information_schema.columns
WHERE table_name = 'cycle_materials'
  AND column_name IN ('shelf_code','activated_at');

SELECT column_name FROM information_schema.columns
WHERE table_name = 'waitlist'
  AND column_name IN ('preferred_doctor_ids','doctor_id','preferred_days','notes');

SELECT column_name FROM information_schema.columns
WHERE table_name = 'patients'
  AND column_name IN ('phone','phone_number');
```

### 1.2 Eksik varsa
```powershell
cd C:\Users\dince\Desktop\daf2026
$env:DATABASE_URL = "<NEON_DIRECT_URL>"   # pooler deÄŸil
python scripts/apply_neon_schema.py --schema-only
```

### Test checklist
- [ ] 19 tablo listede
- [ ] `cycle_materials.shelf_code` / `activated_at` var
- [ ] `patients.phone` var (`phone_number` yoksa taskâ€™larda dÃ¼zeltilecek â€” AdÄ±m 6)
- [ ] Owner login hÃ¢lÃ¢ Ã§alÄ±ÅŸÄ±yor

**Ã‡Ä±ktÄ±:** Bu dosyaya â€œNeon doÄŸrulandÄ±: YYYY-MM-DDâ€ notu.

---

## ADIM 2 â€” Entegrasyonlar sayfasÄ± path dÃ¼zelt (kritik kÄ±rÄ±k)

**AmaÃ§:** WhatsApp / klinik ayarlarÄ± UIâ€™dan okunup yazÄ±labilsin.

### YapÄ±lacaklar
1. `ui/src/app/dashboard/integrations/page.tsx`  
   - `GET/PUT /clinic-settings` â†’ `/integration/whatsapp/clinic-settings`  
   - AynÄ± ÅŸekilde `doctor-settings` varsa â†’ `/integration/whatsapp/doctor-settings`
2. Gerekirse `apiClient` helper (`integrationApi`) ekle
3. Deploy UI (Railway auto)

### Test
- [ ] Entegrasyonlar sayfasÄ± aÃ§Ä±lÄ±yor (404 yok)
- [ ] Klinik WhatsApp ayarlarÄ± yÃ¼kleniyor
- [ ] Bir alanÄ± kaydet â†’ refresh sonrasÄ± kalÄ±yor
- [ ] Network tab: `/api/integration/whatsapp/clinic-settings` â†’ 200

---

## ADIM 3 â€” Waitlist ekleme UI

**AmaÃ§:** Waitlist sayfasÄ±ndan hasta eklenebilsin.

### YapÄ±lacaklar
1. `WaitlistForm.tsx` iÃ§indeki `fetch('/api/...')` â†’ `apiClient` / `waitlistApi`
2. Waitlist sayfasÄ±na formu baÄŸla (modal veya panel)
3. Hasta / doktor selectâ€™leri mevcut appointment APIâ€™lerinden

### Test
- [ ] Waitlist â†’ Yeni ekle
- [ ] Listeye dÃ¼ÅŸÃ¼yor
- [ ] Silme hÃ¢lÃ¢ Ã§alÄ±ÅŸÄ±yor
- [ ] Randevu sayfasÄ±ndaki waitlist akÄ±ÅŸÄ± bozulmadÄ±

---

## ADIM 4 â€” Permissions: `integrations` anahtarÄ±

**AmaÃ§:** Asistanlara entegrasyon sayfasÄ± verilebilsin.

### YapÄ±lacaklar
1. Permissions UIâ€™daki `allowed_pages` listesine `integrations` ekle
2. Sidebar `RouteGuard` ile uyumu kontrol et

### Test
- [ ] Owner bir asistana `integrations` verir
- [ ] Asistan login â†’ Entegrasyonlar menÃ¼de
- [ ] KaldÄ±rÄ±nca menÃ¼den dÃ¼ÅŸer

---

## ADIM 5 â€” Settings yÃ¼zeyi (klinik ayarlarÄ±)

**AmaÃ§:** AyrÄ± veya Entegrasyonlar altÄ±nda tutarlÄ± ayarlar.

### SeÃ§enek A (Ã¶nerilen, hÄ±zlÄ±)
Entegrasyonlar sayfasÄ±nÄ± â€œAyarlar + PMS + WhatsAppâ€ olarak tamamla; ayrÄ± `/settings` aÃ§ma.

### SeÃ§enek B
`/dashboard/settings` route + `SettingsPanel`â€™i `apiClient` ile canlandÄ±r.

### Test
- [ ] HatÄ±rlatma aralÄ±klarÄ± kaydoluyor (`clinic_settings`)
- [ ] Doktor ayarlarÄ± (varsa) kaydoluyor
- [ ] Sayfa yenilemede persist

---

## ADIM 6 â€” Backend drift dÃ¼zeltmeleri (sayfa testleriyle)

**AmaÃ§:** GÃ¶revler ve ORMâ€™nin DB ile uyumu.

### YapÄ±lacaklar
1. `appointment_tasks.py` vb. `patients.phone_number` â†’ `patients.phone`
2. Waitlist / Appointment ORM eksik kolonlarÄ± (ihtiyaÃ§ oldukÃ§a)
3. CSRF + RateLimitâ€™i aÃ§ (login + POST testleriyle)

### Test
- [ ] Login hÃ¢lÃ¢ Ã§alÄ±ÅŸÄ±yor
- [ ] Randevu oluÅŸtur / gÃ¼ncelle
- [ ] Waitlist ekle
- [ ] Stok adjust
- [ ] (Opsiyonel) hatÄ±rlatma job logâ€™unda kolon hatasÄ± yok

---

## ADIM 7 â€” Ã–lÃ¼ `fetch('/api/...')` temizliÄŸi

Dosyalar:
- `WaitlistForm.tsx` (AdÄ±m 3â€™te dÃ¼zeltilir)
- `SettingsPanel.tsx` (AdÄ±m 5â€™te veya sil)
- `SmartCalendar.tsx` (kullanÄ±lmÄ±yorsa sil veya apiClient)
- `PatientDetailCard.tsx` (kullanÄ±lmÄ±yorsa sil veya apiClient)

### Test
- [ ] Repoda `fetch('/api/` kalmadÄ± (`ui/src` grep)
- [ ] Ä°lgili sayfalar regressiyon OK

---

## ADIM 8 â€” Smoke suite (tÃ¼m sayfalar)

Owner ile sÄ±rayla:

| # | Sayfa | Beklenen |
|---|--------|----------|
| 1 | `/login` | GiriÅŸ OK |
| 2 | `/dashboard` | Metrik kartlarÄ± / grafik yÃ¼klenir |
| 3 | `/dashboard/appointments` | Liste + yeni randevu |
| 4 | `/dashboard/waitlist` | Liste + ekle + sil |
| 5 | `/dashboard/inventory` | Liste + QR/cycle (mÃ¼mkÃ¼nse) |
| 6 | `/dashboard/integrations` | Ayarlar kaydet |
| 7 | `/dashboard/permissions` | KullanÄ±cÄ± liste / yetki |
| 8 | Superadmin â†’ `/dashboard/admin/tenants` | Klinik listesi |

Hepsi yeÅŸil â†’ **sayfa bitirme turu tamam**.

---

## ADIM 9 â€” Sabitleme (sayfalar bitince)

1. `RAILWAY_DANGEROUSLY_SKIP_VULNERABILITY_CHECK` kaldÄ±r (UI)
2. CSRF/RateLimit productionâ€™da aÃ§Ä±k
3. PR: `refactor/monolith-migration` â†’ `main`
4. Eski mikroservis / `_deprecated_*` temizlik

---

## Ã–ncelik sÄ±rasÄ± (bu dosyaya gÃ¶re)

```
1 DB doÄŸrula
2 Integrations path (kritik kÄ±rÄ±k)
3 Waitlist ekle
4 Permissions integrations
5 Settings yÃ¼zeyi
6 Backend drift + gÃ¼venlik middleware
7 Ã–lÃ¼ kod temizliÄŸi
8 Full smoke
9 Merge / temizlik
```

---

## Ä°lerleme kaydÄ±

| AdÄ±m | Durum | Tarih | Not |
|------|--------|-------|-----|
| 1 Neon doÄŸrulama | â¬œ | | CanlÄ± login ile dolaylÄ± OK |
| 2 Integrations path | âœ… | 2026-09-16 | PUT clinic-settings 200 canlÄ± |
| 3 Waitlist form | âœ… | 2026-09-16 | apiClient + Hasta ekle UI |
| 4 Permissions `integrations` | âœ… kod | 2026-09-16 | UI ALL_PAGES + API VALID_PAGES; deploy sonrasÄ± asistan testi |
| 5 Settings | â¬œ | | WhatsApp Entegrasyonlarâ€™da OK |
| 6 Backend drift | âœ… kÄ±smi | 2026-09-16 | B1â€“B8 tamam; B9 ORM kalan |
| 7 Ã–lÃ¼ fetch temizliÄŸi | â¬œ | | |
| 8 Full smoke | âœ… kÄ±smi | 2026-09-16 | Owner: waitlist/appt/inv/int/perm yeÅŸil |
| 9 Merge | â¬œ | | |

---

## Åimdi ne yapÄ±yoruz?

**Sonraki aksiyon:** Railway deploy (AdÄ±m 4 + B8) â†’ login + bir POST smoke.  
ArdÄ±ndan WhatsApp canlÄ± test (aÅŸaÄŸÄ±daki rehber).

