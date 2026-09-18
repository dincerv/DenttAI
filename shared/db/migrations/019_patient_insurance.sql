-- Migration: 019_patient_insurance
-- Date: 2026-09-18
-- Purpose: Patient insurance profile + payment payer split + payments.patient FK
-- Official Medula/GIB APIs come later; this is the clinic-side data foundation.

BEGIN;

-- ── 1. Patient insurance / identity fields ───────────────────────────────

ALTER TABLE patients
    ADD COLUMN IF NOT EXISTS national_id          VARCHAR(11),
    ADD COLUMN IF NOT EXISTS birth_date           DATE,
    ADD COLUMN IF NOT EXISTS insurance_type       VARCHAR(20) NOT NULL DEFAULT 'none',
    ADD COLUMN IF NOT EXISTS insurance_provider   VARCHAR(100),
    ADD COLUMN IF NOT EXISTS insurance_number     VARCHAR(50),
    ADD COLUMN IF NOT EXISTS notes                TEXT,
    ADD COLUMN IF NOT EXISTS updated_at           TIMESTAMPTZ NOT NULL DEFAULT now();

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'patients_insurance_type_check'
    ) THEN
        ALTER TABLE patients
            ADD CONSTRAINT patients_insurance_type_check
            CHECK (insurance_type IN ('none', 'sgk', 'private', 'mixed'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'patients_national_id_check'
    ) THEN
        ALTER TABLE patients
            ADD CONSTRAINT patients_national_id_check
            CHECK (national_id IS NULL OR national_id ~ '^[0-9]{11}$');
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS idx_patients_clinic_national_id
    ON patients (clinic_id, national_id)
    WHERE national_id IS NOT NULL;

-- ── 2. Payment payer split ───────────────────────────────────────────────

ALTER TABLE payments
    ADD COLUMN IF NOT EXISTS payer_type         VARCHAR(20) NOT NULL DEFAULT 'patient',
    ADD COLUMN IF NOT EXISTS insurance_amount   NUMERIC(10,2) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS patient_amount     NUMERIC(10,2);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'payments_payer_type_check'
    ) THEN
        ALTER TABLE payments
            ADD CONSTRAINT payments_payer_type_check
            CHECK (payer_type IN ('patient', 'sgk', 'private', 'mixed'));
    END IF;
END $$;

UPDATE payments
SET patient_amount = amount - COALESCE(insurance_amount, 0)
WHERE patient_amount IS NULL;

ALTER TABLE payments
    ALTER COLUMN patient_amount SET DEFAULT 0,
    ALTER COLUMN patient_amount SET NOT NULL;

-- ── 3. Repair orphan payment.patient_id (fake UUIDs from v1 UI) ──────────

INSERT INTO patients (id, clinic_id, full_name)
SELECT p.patient_id, p.clinic_id, COALESCE(NULLIF(TRIM(p.patient_name), ''), 'Bilinmeyen Hasta')
FROM payments p
WHERE NOT EXISTS (SELECT 1 FROM patients t WHERE t.id = p.patient_id)
ON CONFLICT (id) DO NOTHING;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'payments_patient_fk'
    ) THEN
        ALTER TABLE payments
            ADD CONSTRAINT payments_patient_fk
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE RESTRICT;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_payments_clinic_payer
    ON payments (clinic_id, payer_type);

COMMIT;
