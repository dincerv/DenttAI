-- ─────────────────────────────────────────────────────────────────────────────
-- 011_ai_usage_events.sql
-- Klinik bazli AI token ve maliyet kayitlari
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ai_usage_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id UUID NOT NULL,
    source_service VARCHAR(64) NOT NULL,
    feature_key VARCHAR(64) NOT NULL,
    provider VARCHAR(32) NOT NULL,
    model_name VARCHAR(128) NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
    metadata JSONB DEFAULT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_ai_usage_events_clinic
        FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ai_usage_events_clinic_id
    ON ai_usage_events(clinic_id);

CREATE INDEX IF NOT EXISTS idx_ai_usage_events_created_at
    ON ai_usage_events(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_usage_events_feature_key
    ON ai_usage_events(feature_key);
