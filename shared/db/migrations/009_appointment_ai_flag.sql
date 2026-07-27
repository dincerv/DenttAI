-- Migration: 009_appointment_ai_flag
-- Purpose: Appointment tablosuna AI otomatis doldurma flag'i ekle
-- Author: DentAI Flow Team
-- Date: 2026-05-20

-- ─────────────────────────────────────────────────────────────────────────────
-- Appointment tablosuna is_auto_filled_by_ai sütunu ekle
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE appointments 
ADD COLUMN is_auto_filled_by_ai BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX idx_appointments_ai_filled 
    ON appointments(is_auto_filled_by_ai);

-- ─────────────────────────────────────────────────────────────────────────────
-- Açıklama
-- ─────────────────────────────────────────────────────────────────────────────
-- is_auto_filled_by_ai: Randevu AI tarafından yedek listeden dolduruldu mu?
-- 
-- Bu flag'in amacı:
-- 1. Doktor ve operatörlerin manuel vs AI atamasını ayırt etmesi
-- 2. AI performans metrikleri (success rate, no-show rate) takibi
-- 3. Audit trail ve transparency
-- 4. Gelecekte AI davranışını fine-tune etmek
