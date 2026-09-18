-- Migration: 021_prescriptions
-- Date: 2026-09-18
-- Purpose: Clinic-side e-reçete records (Medula send comes later)

BEGIN;

CREATE TABLE IF NOT EXISTS prescriptions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id       UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    patient_id      UUID NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    appointment_id  UUID REFERENCES appointments(id) ON DELETE SET NULL,
    doctor_id       UUID REFERENCES users(id) ON DELETE SET NULL,

    prescription_no VARCHAR(32),
    status          VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'issued', 'cancelled')),
    medula_status   VARCHAR(20) NOT NULL DEFAULT 'not_sent'
        CHECK (medula_status IN ('not_sent', 'queued', 'sent', 'rejected')),

    diagnosis       TEXT,
    notes           TEXT,
    issued_at       TIMESTAMPTZ,
    cancelled_at    TIMESTAMPTZ,

    created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS prescription_items (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prescription_id  UUID NOT NULL REFERENCES prescriptions(id) ON DELETE CASCADE,
    clinic_id        UUID NOT NULL,
    drug_name        VARCHAR(255) NOT NULL,
    barcode          VARCHAR(50),
    dosage           VARCHAR(100),
    quantity         NUMERIC(10, 2) NOT NULL DEFAULT 1 CHECK (quantity > 0),
    instructions     TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_prescriptions_clinic_no
    ON prescriptions (clinic_id, prescription_no)
    WHERE prescription_no IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_prescriptions_clinic_status
    ON prescriptions (clinic_id, status);

CREATE INDEX IF NOT EXISTS idx_prescriptions_clinic_patient
    ON prescriptions (clinic_id, patient_id);

CREATE INDEX IF NOT EXISTS idx_prescription_items_rx
    ON prescription_items (prescription_id);

ALTER TABLE prescriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE prescriptions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS prescriptions_isolation ON prescriptions;
CREATE POLICY prescriptions_isolation ON prescriptions
    USING (clinic_id = current_setting('app.current_clinic_id', true)::UUID);

ALTER TABLE prescription_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE prescription_items FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS prescription_items_isolation ON prescription_items;
CREATE POLICY prescription_items_isolation ON prescription_items
    USING (clinic_id = current_setting('app.current_clinic_id', true)::UUID);

CREATE OR REPLACE FUNCTION update_prescriptions_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_prescriptions_updated_at ON prescriptions;
CREATE TRIGGER trg_prescriptions_updated_at
    BEFORE UPDATE ON prescriptions
    FOR EACH ROW EXECUTE FUNCTION update_prescriptions_updated_at();

COMMIT;
