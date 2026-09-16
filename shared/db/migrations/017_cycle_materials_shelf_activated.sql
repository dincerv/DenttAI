-- Migration: 017_cycle_materials_shelf_activated
-- ORM'de olan ama Neon/init şemasında eksik kolonlar

ALTER TABLE cycle_materials
    ADD COLUMN IF NOT EXISTS shelf_code VARCHAR(20),
    ADD COLUMN IF NOT EXISTS activated_at TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS idx_cycle_materials_shelf_code
    ON cycle_materials (shelf_code)
    WHERE shelf_code IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_cycle_materials_activated_at
    ON cycle_materials (clinic_id, activated_at);
