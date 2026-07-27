-- ============================================================
-- DentAI Flow — Batch Management & Multi-Tenant SaaS Migration
-- Bu dosya 002_production_hardening.sql sonrasında çalıştırılır.
--
-- Özet:
--   1. inventory_items tablosundaki eski Unique(name) kısıtlamasını
--      tamamen kaldırır (eğer hâlâ varsa).
--   2. Composite unique constraint'i doğrular:
--        (clinic_id, name, expiry_date, batch_number)
--      Bu sayede:
--        - Aynı isimli ürün farklı partiler halinde eklenebilir
--        - Her klinik (tenant) kendi verilerini izole takip eder
--        - FEFO (First Expired, First Out) mantığıyla yönetilir
--   3. FEFO sorgularını hızlandıran ek index eklenir.
--
-- Multi-Tenant NOT:
--   clinic_id sütunu tenant_id rolü üstlenir.
--   RLS (Row Level Security) 01_init.sql'de aktifleştirilmiştir.
-- ============================================================

-- 1. Eski Unique(name) varsa kaldır (idempotent)
DO $$
BEGIN
    -- inventory_items üzerinde sadece "name" sütununa bağlı unique constraint bul ve kaldır
    IF EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE tablename = 'inventory_items'
          AND indexdef ILIKE '%unique%'
          AND indexdef ILIKE '%(name)%'
          AND indexdef NOT ILIKE '%clinic_id%'
    ) THEN
        -- Dinamik olarak bul ve kaldır
        EXECUTE (
            SELECT 'DROP INDEX IF EXISTS ' || indexname
            FROM pg_indexes
            WHERE tablename = 'inventory_items'
              AND indexdef ILIKE '%unique%'
              AND indexdef ILIKE '%(name)%'
              AND indexdef NOT ILIKE '%clinic_id%'
            LIMIT 1
        );
        RAISE NOTICE 'Eski Unique(name) constraint kaldırıldı.';
    ELSE
        RAISE NOTICE 'Unique(name) bulunamadı, zaten temiz.';
    END IF;
END $$;

-- 2. Composite unique constraint'i doğrula (01_init.sql'de tanımlı, burada güvenlik için)
-- Bu constraint: clinic_id + name + expiry_date + batch_number
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_inventory_batch'
          AND conrelid = 'inventory_items'::regclass
    ) THEN
        ALTER TABLE inventory_items
            ADD CONSTRAINT uq_inventory_batch
            UNIQUE (clinic_id, name, expiry_date, batch_number);
        RAISE NOTICE 'Composite unique constraint oluşturuldu: uq_inventory_batch';
    ELSE
        RAISE NOTICE 'uq_inventory_batch zaten mevcut.';
    END IF;
END $$;

-- 3. FEFO sorguları için optimize edilmiş index
-- Aynı klinik + aynı isim → SKT'ye göre sıralı erişim
CREATE INDEX IF NOT EXISTS idx_inventory_fefo
    ON inventory_items (clinic_id, name, expiry_date ASC NULLS LAST);

-- 4. Batch number bazlı hızlı erişim
CREATE INDEX IF NOT EXISTS idx_inventory_batch_number
    ON inventory_items (clinic_id, batch_number)
    WHERE batch_number IS NOT NULL;

-- Bitti.
