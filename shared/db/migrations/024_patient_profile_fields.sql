-- Migration: 024_patient_profile_fields
-- Date: 2026-09-27
-- Purpose: Dentsoft/PMS'ten gelen ek hasta profil alanları (cinsiyet, adres, harici id)

BEGIN;

ALTER TABLE patients
    ADD COLUMN IF NOT EXISTS sex              VARCHAR(20),
    ADD COLUMN IF NOT EXISTS address          VARCHAR(500),
    ADD COLUMN IF NOT EXISTS city             VARCHAR(100),
    ADD COLUMN IF NOT EXISTS district         VARCHAR(100),
    ADD COLUMN IF NOT EXISTS country          VARCHAR(100),
    ADD COLUMN IF NOT EXISTS external_id      VARCHAR(128),
    ADD COLUMN IF NOT EXISTS avatar_url       VARCHAR(500);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'patients_sex_check'
    ) THEN
        ALTER TABLE patients
            ADD CONSTRAINT patients_sex_check
            CHECK (sex IS NULL OR sex IN ('female', 'male', 'other', 'unknown'));
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS idx_patients_clinic_external_id
    ON patients (clinic_id, external_id)
    WHERE external_id IS NOT NULL;

COMMIT;
