-- ─────────────────────────────────────────────────────────────────────────────
-- 012_appointment_duration_minutes.sql
-- appointments tablosuna sure kolonu ekler (zaman araligi destegi)
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE appointments
ADD COLUMN IF NOT EXISTS duration_minutes INTEGER NOT NULL DEFAULT 30;
