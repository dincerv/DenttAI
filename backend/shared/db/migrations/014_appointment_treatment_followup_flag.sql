-- Migration 014: Appointment Treatment Follow-up Flag
-- Tedavi kontrolü: AI'ın yaşlı hastalara mesaj atmaması gibi durumlar için
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS treatment_follow_up_enabled BOOLEAN NOT NULL DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS idx_appointments_clinic_followup ON appointments(clinic_id, treatment_follow_up_enabled);
