-- ============================================================
-- Migration 006: Clinic code (6-char login code) + email_domain
-- ============================================================

-- 1. code sütunu: 6 haneli benzersiz klinik giriş kodu
ALTER TABLE clinics ADD COLUMN IF NOT EXISTS code VARCHAR(6);

-- Mevcut kliniklere rastgele 6 haneli büyük harf+rakam kodu ata
UPDATE clinics
SET code = UPPER(SUBSTRING(MD5(id::text || RANDOM()::text), 1, 6))
WHERE code IS NULL;

-- Benzersizlik kısıtı (çakışma ihtimaline karşı döngü yapmak yerine
-- migration sırasında uygula; uygulama katmanı benzersizliği garanti eder)
CREATE UNIQUE INDEX IF NOT EXISTS uq_clinics_code ON clinics (code);

-- 2. email_domain sütunu: e.g. "demo.com" veya "uzman"
ALTER TABLE clinics ADD COLUMN IF NOT EXISTS email_domain VARCHAR(255);

-- Mevcut kliniklere slug'ı email_domain olarak ata
UPDATE clinics SET email_domain = slug WHERE email_domain IS NULL;
