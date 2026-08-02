-- Migration: 016_schema_drift_and_fk_hardening
-- Tarih: 2026-08-02
-- Açıklama: Kod-DB şema drift düzeltmesi + eksik FK/ON DELETE + ai_usage_events RLS

BEGIN;

-- ═══════════════════════════════════════════════════════════
-- 1. patient_notes
-- ═══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS patient_notes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id       UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    patient_id      UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id       UUID REFERENCES doctors(id) ON DELETE SET NULL,
    appointment_id  UUID REFERENCES appointments(id) ON DELETE SET NULL,
    note_type       VARCHAR(50),
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_patient_notes_clinic ON patient_notes(clinic_id);
CREATE INDEX IF NOT EXISTS idx_patient_notes_patient ON patient_notes(clinic_id, patient_id);
CREATE INDEX IF NOT EXISTS idx_patient_notes_appointment ON patient_notes(appointment_id);

ALTER TABLE patient_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE patient_notes FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS patient_notes_isolation ON patient_notes;
CREATE POLICY patient_notes_isolation ON patient_notes
    USING (clinic_id = current_setting('app.current_clinic_id', true)::UUID);

-- ═══════════════════════════════════════════════════════════
-- 2. clinic_integrations
-- ═══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS clinic_integrations (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id              UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    provider               VARCHAR(50) NOT NULL,
    display_name           VARCHAR(255),
    config                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active              BOOLEAN NOT NULL DEFAULT true,
    last_sync_at           TIMESTAMPTZ,
    last_sync_status       VARCHAR(50),
    last_sync_message      TEXT,
    sync_interval_minutes  INT NOT NULL DEFAULT 60,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (clinic_id, provider)
);

CREATE INDEX IF NOT EXISTS idx_clinic_integrations_clinic
    ON clinic_integrations(clinic_id) WHERE is_active = true;

ALTER TABLE clinic_integrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE clinic_integrations FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS clinic_integrations_isolation ON clinic_integrations;
CREATE POLICY clinic_integrations_isolation ON clinic_integrations
    USING (clinic_id = current_setting('app.current_clinic_id', true)::UUID);

-- ═══════════════════════════════════════════════════════════
-- 3. Eksik kolonlar
-- ═══════════════════════════════════════════════════════════
ALTER TABLE doctors
    ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_doctors_user_id ON doctors(user_id);

ALTER TABLE patients
    ADD COLUMN IF NOT EXISTS notes TEXT;

ALTER TABLE appointments
    ADD COLUMN IF NOT EXISTS specialty VARCHAR(100),
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_appointments_specialty
    ON appointments(clinic_id, specialty);

ALTER TABLE waitlist
    ADD COLUMN IF NOT EXISTS doctor_id UUID REFERENCES doctors(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS preferred_days VARCHAR(100),
    ADD COLUMN IF NOT EXISTS notes TEXT;

CREATE INDEX IF NOT EXISTS idx_waitlist_doctor ON waitlist(doctor_id);

-- ═══════════════════════════════════════════════════════════
-- 4. ai_usage_events RLS
-- ═══════════════════════════════════════════════════════════
ALTER TABLE ai_usage_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_usage_events FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ai_usage_events_isolation ON ai_usage_events;
CREATE POLICY ai_usage_events_isolation ON ai_usage_events
    USING (clinic_id = current_setting('app.current_clinic_id', true)::UUID);

-- ═══════════════════════════════════════════════════════════
-- 5. Eksik FK / ON DELETE (R-07)
-- ═══════════════════════════════════════════════════════════

-- appointments.patient_id → RESTRICT (hasta silinirken randevu engellensin)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'appointments_patient_id_fkey'
    ) THEN
        ALTER TABLE appointments
            ADD CONSTRAINT appointments_patient_id_fkey
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE RESTRICT;
    ELSE
        ALTER TABLE appointments DROP CONSTRAINT appointments_patient_id_fkey;
        ALTER TABLE appointments
            ADD CONSTRAINT appointments_patient_id_fkey
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE RESTRICT;
    END IF;
END $$;

-- appointments.doctor_id → RESTRICT
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'appointments_doctor_id_fkey'
    ) THEN
        ALTER TABLE appointments DROP CONSTRAINT appointments_doctor_id_fkey;
    END IF;
    ALTER TABLE appointments
        ADD CONSTRAINT appointments_doctor_id_fkey
        FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE RESTRICT;
END $$;

-- waitlist.patient_id → CASCADE
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'waitlist_patient_id_fkey'
    ) THEN
        ALTER TABLE waitlist DROP CONSTRAINT waitlist_patient_id_fkey;
    END IF;
    ALTER TABLE waitlist
        ADD CONSTRAINT waitlist_patient_id_fkey
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE;
END $$;

-- sent_messages.patient_id FK (varsa SET NULL)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sent_messages' AND column_name = 'patient_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'sent_messages_patient_id_fkey'
    ) THEN
        ALTER TABLE sent_messages
            ADD CONSTRAINT sent_messages_patient_id_fkey
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE SET NULL;
    END IF;
END $$;

-- inventory_adjustments.clinic_id FK
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'inventory_adjustments_clinic_id_fkey'
    ) THEN
        ALTER TABLE inventory_adjustments
            ADD CONSTRAINT inventory_adjustments_clinic_id_fkey
            FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE;
    END IF;
END $$;

COMMIT;
