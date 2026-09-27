-- Migration: 023_dental_chart
-- Date: 2026-09-18
-- Purpose: FDI odontogram + per-tooth treatment plan (clinic-side; no GİB)

BEGIN;

CREATE TABLE IF NOT EXISTS tooth_records (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id   UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    patient_id  UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    tooth_fdi   SMALLINT NOT NULL
        CHECK (tooth_fdi / 10 BETWEEN 1 AND 4 AND tooth_fdi % 10 BETWEEN 1 AND 8),
    status      VARCHAR(20) NOT NULL DEFAULT 'healthy'
        CHECK (status IN (
            'healthy', 'caries', 'filled', 'rct', 'crown',
            'missing', 'implant', 'bridge', 'planned'
        )),
    notes       TEXT,
    updated_by  UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_tooth_records_patient UNIQUE (clinic_id, patient_id, tooth_fdi)
);

CREATE TABLE IF NOT EXISTS treatments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id       UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    patient_id      UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    tooth_fdi       SMALLINT
        CHECK (tooth_fdi IS NULL OR (tooth_fdi / 10 BETWEEN 1 AND 4 AND tooth_fdi % 10 BETWEEN 1 AND 8)),
    procedure       VARCHAR(30) NOT NULL
        CHECK (procedure IN (
            'muayene', 'dolgu', 'kanal', 'cekim', 'kron', 'kopru',
            'implant', 'protez', 'veneer', 'ortodonti', 'temizlik', 'diger'
        )),
    status          VARCHAR(20) NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned', 'completed', 'cancelled')),
    price           NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (price >= 0),
    notes           TEXT,
    appointment_id  UUID REFERENCES appointments(id) ON DELETE SET NULL,
    payment_id      UUID REFERENCES payments(id) ON DELETE SET NULL,
    doctor_id       UUID REFERENCES users(id) ON DELETE SET NULL,
    created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tooth_records_patient
    ON tooth_records (clinic_id, patient_id);

CREATE INDEX IF NOT EXISTS idx_treatments_patient
    ON treatments (clinic_id, patient_id, status);

CREATE INDEX IF NOT EXISTS idx_treatments_clinic_created
    ON treatments (clinic_id, created_at DESC);

ALTER TABLE tooth_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE tooth_records FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tooth_records_isolation ON tooth_records;
CREATE POLICY tooth_records_isolation ON tooth_records
    USING (clinic_id = current_setting('app.current_clinic_id', true)::UUID);

ALTER TABLE treatments ENABLE ROW LEVEL SECURITY;
ALTER TABLE treatments FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS treatments_isolation ON treatments;
CREATE POLICY treatments_isolation ON treatments
    USING (clinic_id = current_setting('app.current_clinic_id', true)::UUID);

CREATE OR REPLACE FUNCTION update_treatments_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_treatments_updated_at ON treatments;
CREATE TRIGGER trg_treatments_updated_at
    BEFORE UPDATE ON treatments
    FOR EACH ROW EXECUTE FUNCTION update_treatments_updated_at();

COMMIT;
