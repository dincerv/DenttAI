-- Migration: 022_clinic_links
-- Date: 2026-09-18
-- Purpose: Waitlist recovered-slot audit, e-SMM invoice type, treatment_type from type/notes

BEGIN;

ALTER TABLE waitlist
    ADD COLUMN IF NOT EXISTS matched_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS cancelled_appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_waitlist_matched
    ON waitlist (clinic_id, matched_at)
    WHERE matched_at IS NOT NULL;

ALTER TABLE invoices DROP CONSTRAINT IF EXISTS invoices_invoice_type_check;
ALTER TABLE invoices ADD CONSTRAINT invoices_invoice_type_check
    CHECK (invoice_type IN ('e_fatura', 'e_arsiv', 'e_smm'));

DROP FUNCTION IF EXISTS extract_treatment_type(TEXT) CASCADE;

CREATE OR REPLACE FUNCTION extract_treatment_type(source TEXT)
RETURNS VARCHAR(50) AS $$
BEGIN
    IF source IS NULL OR btrim(source) = '' THEN RETURN NULL; END IF;
    IF source ILIKE '%implant%' THEN RETURN 'implant'; END IF;
    IF source ILIKE '%ortodonti%' OR source ILIKE '%breket%' OR source ILIKE '%ark tel%' THEN RETURN 'ortodonti'; END IF;
    IF source ILIKE '%kanal%' OR source ILIKE '%endodon%' OR source ILIKE '%pulpa%' THEN RETURN 'kanal'; END IF;
    IF source ILIKE '%kron%' OR source ILIKE '%kuron%' OR source ILIKE '%zirkonyum%' OR source ILIKE '%seramik%' THEN RETURN 'kron'; END IF;
    IF source ILIKE '%cekim%' OR source ILIKE '%cekimi%' OR source ILIKE '%çekim%' OR source ILIKE '%ekstraksiyon%' THEN RETURN 'cekim'; END IF;
    IF source ILIKE '%protez%' OR source ILIKE '%olcu%' OR source ILIKE '%ölçü%' THEN RETURN 'protez'; END IF;
    IF source ILIKE '%dolgu%' OR source ILIKE '%kompozit%' OR source ILIKE '%restorasyon%' THEN RETURN 'dolgu'; END IF;
    IF source ILIKE '%temizlik%' OR source ILIKE '%skaler%' OR source ILIKE '%debridman%' OR source ILIKE '%tasi%' OR source ILIKE '%taşı%' THEN RETURN 'temizlik'; END IF;
    IF source ILIKE '%beyazlatma%' THEN RETURN 'beyazlatma'; END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE FUNCTION trg_set_treatment_type()
RETURNS TRIGGER AS $$
BEGIN
    NEW.treatment_type := COALESCE(
        extract_treatment_type(NEW.type),
        extract_treatment_type(NEW.notes),
        extract_treatment_type(NEW.specialty)
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_treatment_type ON appointments;
CREATE TRIGGER set_treatment_type
    BEFORE INSERT OR UPDATE OF notes, type, specialty ON appointments
    FOR EACH ROW
    EXECUTE FUNCTION trg_set_treatment_type();

UPDATE appointments
SET treatment_type = COALESCE(
        extract_treatment_type(type),
        extract_treatment_type(notes),
        extract_treatment_type(specialty)
    )
WHERE treatment_type IS NULL;

COMMIT;
