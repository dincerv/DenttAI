-- ============================================================
-- DentAI Flow — Production Hardening Migration
-- Bu dosya mevcut 01_init.sql sonrasında çalıştırılır.
-- Amaç: eksik indexler, unique constraint'ler, treatment_type
-- normalizasyonu ve ölçek dostu iyileştirmeler.
-- ============================================================

-- ────────────────────────────────────────────────────────────
-- 1. UNIQUE CONSTRAINTS (Duplicate koruması DB seviyesinde)
-- ────────────────────────────────────────────────────────────

-- Aynı klinik içinde aynı isim+telefon çifti tekrar eklenemesin
CREATE UNIQUE INDEX IF NOT EXISTS idx_patients_clinic_name_phone
    ON patients (clinic_id, LOWER(TRIM(full_name)), COALESCE(phone, ''));

-- Aynı klinik içinde aynı hasta+branş aktif waitlist kaydı tekrar eklenemesin
CREATE UNIQUE INDEX IF NOT EXISTS idx_waitlist_unique_active
    ON waitlist (clinic_id, patient_id, specialty)
    WHERE is_active = TRUE;

-- ────────────────────────────────────────────────────────────
-- 2. COMPOSITE INDEXES (Ölçek dostu sorgular)
-- ────────────────────────────────────────────────────────────

-- appointments: clinic + tarih + status — en sık kullanılan filtreleme
CREATE INDEX IF NOT EXISTS idx_appointments_clinic_date_status
    ON appointments (clinic_id, scheduled_at, status);

-- appointments: doctor + tarih — doctor performance sorguları
CREATE INDEX IF NOT EXISTS idx_appointments_doctor_date
    ON appointments (doctor_id, scheduled_at);

-- appointments: clinic + doctor + tarih — dashboard analytics
CREATE INDEX IF NOT EXISTS idx_appointments_clinic_doctor_date
    ON appointments (clinic_id, doctor_id, scheduled_at);

-- patients: clinic + isim araması — liste ve arama
CREATE INDEX IF NOT EXISTS idx_patients_clinic_name
    ON patients (clinic_id, full_name);

-- inventory_items: clinic + category — stok listesi
CREATE INDEX IF NOT EXISTS idx_inventory_clinic_category
    ON inventory_items (clinic_id, category);

-- inventory_items: düşük stok alarmı
CREATE INDEX IF NOT EXISTS idx_inventory_low_stock
    ON inventory_items (clinic_id)
    WHERE quantity <= min_stock_level;

-- cycle_materials: clinic + aktif — ömrü dolmak üzere sorguları
CREATE INDEX IF NOT EXISTS idx_cycle_materials_clinic_active
    ON cycle_materials (clinic_id, is_active)
    WHERE is_active = TRUE;

-- cycle_materials: high waste analizi
CREATE INDEX IF NOT EXISTS idx_cycle_materials_high_waste
    ON cycle_materials (clinic_id)
    WHERE is_high_waste = TRUE;

-- doctors: clinic bazlı listeleme
CREATE INDEX IF NOT EXISTS idx_doctors_clinic
    ON doctors (clinic_id);

-- ────────────────────────────────────────────────────────────
-- 3. TREATMENT TYPE NORMALIZATION
-- ────────────────────────────────────────────────────────────
-- Analytics'te ILIKE '%dolgu%' gibi pahalı text scan'ler yerine
-- appointments tablosuna normalized treatment_type sütunu eklenir.
-- Bu sütun INSERT/UPDATE sırasında trigger ile otomatik doldurulur.

-- Yeni sütun
ALTER TABLE appointments
    ADD COLUMN IF NOT EXISTS treatment_type VARCHAR(50);

-- Treatment type çıkarma fonksiyonu (notes alanından)
CREATE OR REPLACE FUNCTION extract_treatment_type(notes TEXT)
RETURNS VARCHAR(50) AS $$
BEGIN
    IF notes IS NULL THEN RETURN NULL; END IF;
    -- Sıra önemli: daha spesifik ifadeler önce kontrol edilir
    IF notes ILIKE '%implant%' THEN RETURN 'implant'; END IF;
    IF notes ILIKE '%ortodonti%' OR notes ILIKE '%breket%' OR notes ILIKE '%ark tel%' THEN RETURN 'ortodonti'; END IF;
    IF notes ILIKE '%kanal%' OR notes ILIKE '%endodon%' OR notes ILIKE '%pulpa%' THEN RETURN 'kanal'; END IF;
    IF notes ILIKE '%kron%' OR notes ILIKE '%kuron%' OR notes ILIKE '%zirkonyum%' OR notes ILIKE '%seramik%' THEN RETURN 'kron'; END IF;
    IF notes ILIKE '%cekim%' OR notes ILIKE '%cekimi%' OR notes ILIKE '%ekstraksiyon%' THEN RETURN 'cekim'; END IF;
    IF notes ILIKE '%protez%' OR notes ILIKE '%olcu%' THEN RETURN 'protez'; END IF;
    IF notes ILIKE '%dolgu%' OR notes ILIKE '%kompozit%' OR notes ILIKE '%restorasyon%' THEN RETURN 'dolgu'; END IF;
    IF notes ILIKE '%temizlik%' OR notes ILIKE '%skaler%' OR notes ILIKE '%debridman%' OR notes ILIKE '%tasi%' THEN RETURN 'temizlik'; END IF;
    IF notes ILIKE '%beyazlatma%' THEN RETURN 'beyazlatma'; END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Mevcut kayıtları doldur
UPDATE appointments
SET treatment_type = extract_treatment_type(notes)
WHERE treatment_type IS NULL AND notes IS NOT NULL;

-- Yeni/güncellenen kayıtlarda otomatik doldur
CREATE OR REPLACE FUNCTION trg_set_treatment_type()
RETURNS TRIGGER AS $$
BEGIN
    NEW.treatment_type := extract_treatment_type(NEW.notes);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_treatment_type ON appointments;
CREATE TRIGGER set_treatment_type
    BEFORE INSERT OR UPDATE OF notes ON appointments
    FOR EACH ROW
    EXECUTE FUNCTION trg_set_treatment_type();

-- Treatment type üzerinde index
CREATE INDEX IF NOT EXISTS idx_appointments_treatment_type
    ON appointments (clinic_id, treatment_type, scheduled_at);

-- Bitti.
