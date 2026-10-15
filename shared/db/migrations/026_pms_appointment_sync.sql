-- Migration: 026_pms_appointment_sync
-- Date: 2026-10-16
-- Purpose: PMS (Dentsoft) takviminden gelen randevu ve hekimlerin harici kimlikleri.
--          Aynı harici randevu ikinci kez eklenmez, değişiklikler güncellenir.

BEGIN;

ALTER TABLE appointments
    ADD COLUMN IF NOT EXISTS external_source     VARCHAR(32),
    ADD COLUMN IF NOT EXISTS external_id         VARCHAR(128),
    ADD COLUMN IF NOT EXISTS external_synced_at  TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS uq_appointments_clinic_external
    ON appointments (clinic_id, external_source, external_id)
    WHERE external_id IS NOT NULL;

ALTER TABLE doctors
    ADD COLUMN IF NOT EXISTS external_source  VARCHAR(32),
    ADD COLUMN IF NOT EXISTS external_id      VARCHAR(128);

CREATE UNIQUE INDEX IF NOT EXISTS uq_doctors_clinic_external
    ON doctors (clinic_id, external_source, external_id)
    WHERE external_id IS NOT NULL;

COMMIT;
