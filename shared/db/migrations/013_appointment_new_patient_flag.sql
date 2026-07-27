-- ─────────────────────────────────────────────────────────────────────────────
-- 013_appointment_new_patient_flag.sql
-- Randevu bazında yeni/eski hasta takibi (is_new_patient)
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE appointments
ADD COLUMN IF NOT EXISTS is_new_patient BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_appointments_clinic_scheduled_new_patient
ON appointments(clinic_id, scheduled_at, is_new_patient);
