-- Migration: 008_waitlist_preferred_doctors
-- Purpose: Waitlist tablosuna tercih edilen doktor kimliklerini ekle
-- Author: DentAI Flow Team
-- Date: 2026-05-20

-- ─────────────────────────────────────────────────────────────────────────────
-- Waitlist tablosuna preferred_doctor_ids sütunu ekle
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE waitlist 
ADD COLUMN preferred_doctor_ids UUID[] DEFAULT NULL;

CREATE INDEX idx_waitlist_preferred_doctor_ids 
    ON waitlist USING GIN (preferred_doctor_ids);

-- ─────────────────────────────────────────────────────────────────────────────
-- Açıklama
-- ─────────────────────────────────────────────────────────────────────────────
-- preferred_doctor_ids: Hasta tercih ettiği doktoru belirtebilir
-- Örnek: ARRAY[doctor_id_1, doctor_id_2]
-- 
-- Bu alanın amacı:
-- 1. Yedek liste hastalarına seçim hakkı vermek
-- 2. AI ranking'i doktor tercihi ile ağırlıklandırmak
-- 3. Randevu doldurulurken doktor eşleştirmesinde kullanmak
