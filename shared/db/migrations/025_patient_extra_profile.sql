-- Migration: 025_patient_extra_profile
-- Date: 2026-09-27
-- Purpose: Dentsoft kartından gelen ek profil alanları

BEGIN;

ALTER TABLE patients
    ADD COLUMN IF NOT EXISTS file_number      VARCHAR(64),
    ADD COLUMN IF NOT EXISTS archive_number   VARCHAR(64),
    ADD COLUMN IF NOT EXISTS occupation       VARCHAR(100),
    ADD COLUMN IF NOT EXISTS nationality      VARCHAR(100),
    ADD COLUMN IF NOT EXISTS blood_type       VARCHAR(20);

COMMIT;
