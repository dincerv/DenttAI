-- Migration: 020_invoices
-- Date: 2026-09-18
-- Purpose: Clinic-side e-Fatura / e-Arşiv records (GİB send comes later)

BEGIN;

CREATE TABLE IF NOT EXISTS invoices (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id       UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    patient_id      UUID NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    payment_id      UUID REFERENCES payments(id) ON DELETE SET NULL,

    invoice_no      VARCHAR(32),
    invoice_type    VARCHAR(20) NOT NULL DEFAULT 'e_arsiv'
        CHECK (invoice_type IN ('e_fatura', 'e_arsiv')),
    status          VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'issued', 'cancelled')),
    gib_status      VARCHAR(20) NOT NULL DEFAULT 'not_sent'
        CHECK (gib_status IN ('not_sent', 'queued', 'sent', 'rejected')),

    buyer_name      VARCHAR(255) NOT NULL,
    buyer_tax_id    VARCHAR(11),
    buyer_tax_office VARCHAR(100),
    buyer_address   TEXT,

    subtotal        NUMERIC(10,2) NOT NULL CHECK (subtotal >= 0),
    vat_rate        NUMERIC(5,2)  NOT NULL DEFAULT 10 CHECK (vat_rate >= 0 AND vat_rate <= 100),
    vat_amount      NUMERIC(10,2) NOT NULL CHECK (vat_amount >= 0),
    total           NUMERIC(10,2) NOT NULL CHECK (total > 0),

    description     TEXT,
    notes           TEXT,
    issued_at       TIMESTAMPTZ,
    cancelled_at    TIMESTAMPTZ,

    created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS invoice_items (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id   UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    clinic_id    UUID NOT NULL,
    description  VARCHAR(255) NOT NULL,
    quantity     NUMERIC(10,2) NOT NULL DEFAULT 1 CHECK (quantity > 0),
    unit_price   NUMERIC(10,2) NOT NULL CHECK (unit_price >= 0),
    vat_rate     NUMERIC(5,2)  NOT NULL DEFAULT 10,
    line_total   NUMERIC(10,2) NOT NULL CHECK (line_total >= 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_invoices_clinic_no
    ON invoices (clinic_id, invoice_no)
    WHERE invoice_no IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_invoices_payment_active
    ON invoices (payment_id)
    WHERE payment_id IS NOT NULL AND status <> 'cancelled';

CREATE INDEX IF NOT EXISTS idx_invoices_clinic_status
    ON invoices (clinic_id, status);

CREATE INDEX IF NOT EXISTS idx_invoices_clinic_patient
    ON invoices (clinic_id, patient_id);

CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice
    ON invoice_items (invoice_id);

ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS invoices_isolation ON invoices;
CREATE POLICY invoices_isolation ON invoices
    USING (clinic_id = current_setting('app.current_clinic_id', true)::UUID);

ALTER TABLE invoice_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice_items FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS invoice_items_isolation ON invoice_items;
CREATE POLICY invoice_items_isolation ON invoice_items
    USING (clinic_id = current_setting('app.current_clinic_id', true)::UUID);

CREATE OR REPLACE FUNCTION update_invoices_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_invoices_updated_at ON invoices;
CREATE TRIGGER trg_invoices_updated_at
    BEFORE UPDATE ON invoices
    FOR EACH ROW EXECUTE FUNCTION update_invoices_updated_at();

COMMIT;
