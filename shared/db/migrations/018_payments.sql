-- Migration: 018_payments
-- Tarih: 2026-09-18
-- Açıklama: Hasta ödeme takibi — borç/alacak + taksit + işlem geçmişi

BEGIN;

-- ── 1. payments tablosu ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS payments (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id       UUID         NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    patient_id      UUID         NOT NULL,
    patient_name    VARCHAR(255),                         -- denormalized: join maliyetini azaltır
    appointment_id  UUID         REFERENCES appointments(id) ON DELETE SET NULL,

    -- Tutar bilgileri
    amount          NUMERIC(10,2) NOT NULL CHECK (amount > 0),
    paid_amount     NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (paid_amount >= 0),

    -- Durum
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'partial', 'paid', 'cancelled', 'refunded')),

    -- İçerik
    description     TEXT,
    treatment_type  VARCHAR(100),
    payment_method  VARCHAR(50)
        CHECK (payment_method IN ('cash', 'credit_card', 'bank_transfer', 'insurance', 'mixed')),

    -- Taksit
    installment_count INTEGER NOT NULL DEFAULT 1 CHECK (installment_count >= 1),

    -- Tarihler
    due_date   DATE,
    paid_at    TIMESTAMPTZ,
    notes      TEXT,

    -- Audit
    created_by  UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── 2. payment_transactions — her ödeme hareketi ──────────────────────

CREATE TABLE IF NOT EXISTS payment_transactions (
    id          UUID  PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id  UUID  NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
    clinic_id   UUID  NOT NULL,

    amount          NUMERIC(10,2) NOT NULL CHECK (amount > 0),
    payment_method  VARCHAR(50)   NOT NULL,
    notes           TEXT,

    created_by  UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── 3. Index'ler ─────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_payments_clinic_status
    ON payments(clinic_id, status);

CREATE INDEX IF NOT EXISTS idx_payments_clinic_patient
    ON payments(clinic_id, patient_id);

CREATE INDEX IF NOT EXISTS idx_payments_clinic_due
    ON payments(clinic_id, due_date)
    WHERE status IN ('pending', 'partial');

CREATE INDEX IF NOT EXISTS idx_payment_transactions_payment
    ON payment_transactions(payment_id);

CREATE INDEX IF NOT EXISTS idx_payment_transactions_clinic
    ON payment_transactions(clinic_id);

-- ── 4. RLS ───────────────────────────────────────────────────────────────

ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS payments_isolation ON payments;
CREATE POLICY payments_isolation ON payments
    USING (clinic_id = current_setting('app.current_clinic_id', true)::UUID);

ALTER TABLE payment_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_transactions FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS payment_transactions_isolation ON payment_transactions;
CREATE POLICY payment_transactions_isolation ON payment_transactions
    USING (clinic_id = current_setting('app.current_clinic_id', true)::UUID);

-- ── 5. updated_at trigger ─────────────────────────────────────────────

CREATE OR REPLACE FUNCTION update_payments_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_payments_updated_at ON payments;
CREATE TRIGGER trg_payments_updated_at
    BEFORE UPDATE ON payments
    FOR EACH ROW EXECUTE FUNCTION update_payments_updated_at();

COMMIT;
