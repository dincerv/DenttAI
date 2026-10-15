# Dentsoft → DentAI randevu aktarımı — inceleme notları

> İnceleme: 2026-10-15, `clinic.dentsoft.com.tr` takvim sayfası, salt okuma.
> Bu dosyada hasta verisi ve giriş bilgisi tutulmaz.

## Takvim sayfası (`/Calendar/Index`) yüklenirken atılan istekler

Takvim FullCalendar (resourceTimeGrid) ile çiziliyor. Veri iki XHR'dan geliyor:

| Amaç | Yöntem | Yol |
|------|--------|-----|
| Hekimler (takvim sütunları) | GET | `/Calendar/DoctorList/resourceTimeGridDay/0?v=66&start=<ISO>&end=<ISO>` |
| Randevular (takvim kutuları) | GET | `/Calendar/AppointmentList/resourceTimeGridDay/0?v=66&start=<ISO>&end=<ISO>` |

- `start` / `end`: ISO 8601, saat dilimiyle. Örnek: `2026-10-16T00:00:00+03:00` → `2026-10-17T00:00:00+03:00` (URL-encoded).
- FullCalendar standardı olduğu için `start`/`end` aralığını bir haftaya veya aya genişletmek muhtemelen çalışır; **doğrulanmadı**.
- Bu uçlar doğrudan tarayıcı adres çubuğundan açılınca **boş cevap** dönüyor. Sayfanın AJAX başlıklarını bekliyorlar (büyük ihtimalle `X-Requested-With: XMLHttpRequest`). Eklentideki `fetchPagedJson` / `fetchDentsoftHtml` bu başlığı zaten gönderiyor.
- Eklentinin `interceptUrlPatterns` listesindeki `'/Calendar/.*(Appointment|Event|List)'` deseni bu iki isteği zaten yakalıyor; ama yakalanan veri şu an randevu olarak işlenmiyor.

Diğer takvim istekleri (randevu aktarımı için gerekmez):
`/Calendar/NoteList/<YYYY-MM-DD>`, `/Calendar/UserTask/<YYYY-MM-DD>`, `/Calendar/AppointmentOutOfHour`.

### Henüz bilinmeyen

- `AppointmentList` ve `DoctorList` cevaplarının **JSON alan adları**. Tarayıcı aracı cevap gövdesini okuyamadığı için DevTools'tan elle kopyalanması gerekiyor:
  - Randevu kimliği, hasta kimliği/adı, `resourceId` (hekim), başlangıç/bitiş saati, tedavi türü, durum rengi/kodu.
  - `DoctorList`: hekim kimliği (`id`) ve adı (`title`).

## Hekim pop-up'ı (`UserDashboard` modal)

Takvimde hekim başlığına tıklanınca açılıyor.

| Yöntem | Yol |
|--------|-----|
| GET | `/Modal/-View-Calendar-Modal-UserDashboard/<base64(JSON)>` |

Parametre base64 kodlu JSON:

```json
{"UserID":"<Dentsoft şifreli hekim kodu>","Year":"2026","Month":"10"}
```

- `UserID` Dentsoft'un ürettiği şifreli bir değer (base64 → 16 bayt), bizim tarafta üretilemez. Hekim başına bir kez sayfadan/DoctorList'ten okunmalı.
- `Year` / `Month` serbestçe değiştirilebilir. Pop-up'taki yıl seçicisi 50 yıl geriye gidiyor, yani geçmiş taraması mümkün.
- Doğrudan açıldığında oturumla **çalışıyor** (AJAX başlığı istemiyor).
- Cevap **HTML** (JSON değil). Tablo sütunları:
  `Hasta` (link) · `Klinik Hasta Türü` (Yeni/Eski Hasta) · `Randevu Tarihi` (sadece gün, **saat yok**) · `Randevu Kabul Tedavi Yapan` · `Sevk Kabul Tedavi Yapan` · `Hasta Durumu` (Bitti / Planlama Yapılmadı / Tedavi Başlamadı).
- Hasta linkinin `href` formatı henüz bilinmiyor (`/Patient/Index/<id>` olması bekleniyor).

## Takvim durumları (renk lejantı)

Randevu Verildi (Yeni / Eski / Acil / Online / Recall) · Hasta Geldi · Hasta Odaya Alındı · Hasta Klinikten Çıktı · Ertelendi / İptal / Gelmedi · Doktor Çalışmıyor.
Bunlar DentAI `appointments.status` değerlerine eşlenecek.

## Uygulanan akış (eklenti 0.4.0)

| Parça | Dosya |
|-------|-------|
| Takvim çekimi + normalize + alan yapısı teşhisi | `browser-extension/src/dentsoft-calendar.js` |
| Periyodik akış, geçmiş tarama, tekrar gönderim engeli | `browser-extension/src/calendar-sync.js` |
| Import ucu | `POST /api/integration/import/appointments` (`services/api/app/services/pms_appointment_import_service.py`) |
| Şema | `shared/db/migrations/026_pms_appointment_sync.sql` (`appointments` / `doctors` için `external_source` + `external_id`) |

1. Her 15 dakikada (ve popup'tan "Şimdi senkronize et" ile) hasta senkronundan sonra takvim çalışır. Açık Dentsoft sekmesinin içinde, sayfanın oturumuyla haftalık parçalar halinde `DoctorList` + `AppointmentList` çağrılır (istekler arası 250 ms).
2. **İleri pencere:** bugün −7 gün → +13 hafta, her çalışmada yeniden okunur; saat/durum/iptal değişiklikleri DentAI'de güncellenir.
3. **Geçmiş tarama:** her çalışmada 26 hafta geriye gider. 104 hafta üst üste boş gelirse veya 2000 yılına ulaşırsa biter. İmleç yalnızca gönderim başarılıysa ilerler.
4. Kullanıcı Dentsoft takvimini gezerken yakalanan `DoctorList` / `AppointmentList` cevapları da anında aynı hattan gönderilir.
5. Eklenti her randevunun özetini (hash) saklar; değişmeyen randevu tekrar gönderilmez.
6. Backend eşleştirmesi:
   - Hekim: Dentsoft kimliği → normalize isim → yoksa yeni doktor kaydı.
   - Hasta: Dentsoft hasta kimliği → isim + telefon → tek isim eşleşmesi → yoksa yeni hasta.
   - Randevu: `(clinic_id, external_source, external_id)` ile eklenir veya güncellenir.
7. Durum eşlemesi (başlık/sınıf metninden): Gelmedi → `no_show`, İptal/Ertelendi → `cancelled`, Klinikten Çıktı → `completed`, Geldi/Odaya Alındı → `confirmed`, diğerleri → `scheduled`. "Doktor Çalışmıyor" ve arka plan blokları atlanır.

### Alan eşlemesinin doğrulanması

`AppointmentList` JSON alan adları henüz canlı veriyle doğrulanmadı; normalize birden çok aday alan adını dener. Popup'taki **"Takvim alan yapısını kopyala"** düğmesi yalnızca alan adlarını ve tiplerini kopyalar (hasta verisi içermez). Bu çıktıyla eşleme kesinleştirilecek.

### Açık

- UserDashboard pop-up'ından Yeni/Eski hasta ve tedavi durumu (HTML) — henüz kullanılmıyor.
