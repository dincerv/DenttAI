-- ============================================================
-- DentAI Flow — PostgreSQL Başlangıç Şeması
-- Row Level Security (RLS) aktif — her klinik sadece kendi verisini görür
-- Bu dosya container ilk başladığında otomatik çalışır
-- ============================================================

-- ── Klinikler (Tenant'lar) ───────────────────────────────
CREATE TABLE IF NOT EXISTS clinics (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    slug        VARCHAR(100) UNIQUE NOT NULL,
    settings    JSONB DEFAULT '{}',
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- RLS yardımcı fonksiyonu — policy'lerden ÖNCE tanımlanmalı
CREATE OR REPLACE FUNCTION current_clinic_id() RETURNS UUID AS $$
BEGIN
    RETURN NULLIF(current_setting('app.current_clinic_id', TRUE), '')::UUID;
END;
$$ LANGUAGE plpgsql STABLE;

-- ── Kullanıcı rolleri ────────────────────────────────────
CREATE TYPE user_role AS ENUM ('super_admin', 'owner', 'doctor', 'assistant');

-- ── Kullanıcılar (Auth için) ─────────────────────────────
-- Klinik bazlı izolasyon; her kullanıcı bir kliniğe aittir
CREATE TABLE IF NOT EXISTS users (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id      UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    email          VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name      VARCHAR(255) NOT NULL,
    role           user_role DEFAULT 'assistant',
    is_active      BOOLEAN DEFAULT TRUE,
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT users_email_clinic_unique UNIQUE (email, clinic_id)
);

-- ── Refresh Token Kayıtları ──────────────────────────────
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked     BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Doktorlar ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS doctors (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id            UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    full_name            VARCHAR(255) NOT NULL,
    specialty            VARCHAR(100),
    notification_offset  INT DEFAULT 24,  -- Saat cinsinden (X saat önce bildirim)
    role                 user_role DEFAULT 'doctor',
    created_at           TIMESTAMPTZ DEFAULT NOW()
);

-- ── Hastalar ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS patients (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id   UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    full_name   VARCHAR(255) NOT NULL,
    phone       VARCHAR(20),
    email       VARCHAR(255),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Randevu durumları ────────────────────────────────────
CREATE TYPE appointment_status AS ENUM ('scheduled', 'confirmed', 'cancelled', 'completed', 'no_show');

-- ── Randevular ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS appointments (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id    UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    patient_id   UUID NOT NULL REFERENCES patients(id),
    doctor_id    UUID NOT NULL REFERENCES doctors(id),
    scheduled_at TIMESTAMPTZ NOT NULL,
    status       appointment_status DEFAULT 'scheduled',
    type         VARCHAR(100),
    notes        TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ── Yedek listesi ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS waitlist (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id    UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    patient_id   UUID NOT NULL REFERENCES patients(id),
    specialty    VARCHAR(100),
    priority     INT DEFAULT 0,
    is_active    BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ── Sarf malzemeleri (Batch / Parti yönetimi) ────────────
-- Aynı isimli ürün farklı son kullanma tarihli partiler halinde girilebilir.
-- FEFO: First Expired, First Out mantığıyla tüketilir.
CREATE TABLE IF NOT EXISTS inventory_items (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    name             VARCHAR(255) NOT NULL,
    category         VARCHAR(100),               -- implant | steril | sarf | ekipman
    quantity         NUMERIC(10,2) DEFAULT 0,
    unit             VARCHAR(50),
    min_stock_level  NUMERIC(10,2) DEFAULT 0,    -- uyarı eşiği
    cost_per_unit    NUMERIC(12,2),              -- analitik için birim maliyet
    shelf_code       VARCHAR(20),                -- raf kodu
    expiry_date      DATE,                       -- son kullanma tarihi
    batch_number     VARCHAR(100),               -- parti/lot numarası
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_inventory_batch UNIQUE (clinic_id, name, expiry_date, batch_number)
);

-- ── Stok hareket geçmişi ────────────────────────────────
CREATE TABLE IF NOT EXISTS inventory_adjustments (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id          UUID NOT NULL,
    item_id            UUID NOT NULL REFERENCES inventory_items(id) ON DELETE CASCADE,
    delta              NUMERIC(10,3) NOT NULL,
    reason             VARCHAR(255),
    performed_by       UUID,
    performed_by_email VARCHAR(255),
    created_at         TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE inventory_adjustments ENABLE ROW LEVEL SECURITY;
CREATE POLICY inventory_adj_isolation ON inventory_adjustments
    USING (clinic_id = current_clinic_id());
CREATE INDEX IF NOT EXISTS idx_inventory_adj_item ON inventory_adjustments(item_id);
CREATE INDEX IF NOT EXISTS idx_inventory_adj_clinic ON inventory_adjustments(clinic_id);

-- ── Döngüsel malzemeler (QR takipli) ────────────────────
CREATE TABLE IF NOT EXISTS cycle_materials (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id         UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    qr_id             VARCHAR(100) UNIQUE NOT NULL,  -- UUID-tabanlı
    shelf_code        VARCHAR(20),                -- gözle okunabilir raf kodu
    name              VARCHAR(255) NOT NULL,
    category          VARCHAR(100),               -- anguldurva | tur | file | diger
    start_date        DATE,                       -- QR aktif edildiğinde doldurulur
    end_date          DATE,                       -- imha sırasında doldurulur
    activated_at      TIMESTAMPTZ,                -- aktivasyon zamanı
    expected_lifespan INT,                        -- Gün cinsinden beklenen ömür
    actual_lifespan   INT GENERATED ALWAYS AS     -- Otomatik hesaplanan gerçek ömür
                         (CASE WHEN end_date IS NOT NULL AND start_date IS NOT NULL
                               THEN (end_date - start_date)
                               ELSE NULL END) STORED,
    is_active         BOOLEAN DEFAULT TRUE,
    is_high_waste     BOOLEAN DEFAULT FALSE,      -- Anomali fırlaması
    end_reason        VARCHAR(255),              -- Neden bitti (kırıldı / tükendi / imha)
    waste_note        TEXT,                       -- Anomali notu
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- ── Row Level Security ───────────────────────────────────
-- Her tablo için RLS aktif edilir.
-- app.current_clinic_id değeri Auth Middleware tarafından her bağlantıda
-- SET LOCAL app.current_clinic_id = '<uuid>' şeklinde iletilir.
-- current_clinic_id() fonksiyonu dosyanın başında tanımlanır.

-- ─── Tablolarda RLS aktif ────────────────────────────────
ALTER TABLE users            ENABLE ROW LEVEL SECURITY;
ALTER TABLE refresh_tokens   ENABLE ROW LEVEL SECURITY;
ALTER TABLE clinics          ENABLE ROW LEVEL SECURITY;
ALTER TABLE doctors          ENABLE ROW LEVEL SECURITY;
ALTER TABLE patients         ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointments     ENABLE ROW LEVEL SECURITY;
ALTER TABLE waitlist         ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory_items  ENABLE ROW LEVEL SECURITY;
ALTER TABLE cycle_materials  ENABLE ROW LEVEL SECURITY;

-- ─── RLS Policy'leri ────────────────────────────────────
-- Kural: clinic_id sütunlu her tablo yalnızca mevcut klinik verisini gösterir.
-- BYPASSRLS: superuser ve servis hesaplarına ihtiyaç duyulmaz;
--            uygulama katmanı her zaman current_clinic_id'yi set eder.

-- clinics: owner sadece kendi kliniğini görür
CREATE POLICY clinic_isolation ON clinics
    USING (id = current_clinic_id());

-- users
CREATE POLICY users_isolation ON users
    USING (clinic_id = current_clinic_id());

-- refresh_tokens: kullanıcı bazlı (clinic dolaylı korunur)
CREATE POLICY refresh_tokens_isolation ON refresh_tokens
    USING (user_id IN (
        SELECT id FROM users WHERE clinic_id = current_clinic_id()
    ));

-- doctors
CREATE POLICY doctors_isolation ON doctors
    USING (clinic_id = current_clinic_id());

-- patients
CREATE POLICY patients_isolation ON patients
    USING (clinic_id = current_clinic_id());

-- appointments
CREATE POLICY appointments_isolation ON appointments
    USING (clinic_id = current_clinic_id());

-- waitlist
CREATE POLICY waitlist_isolation ON waitlist
    USING (clinic_id = current_clinic_id());

-- inventory_items
CREATE POLICY inventory_isolation ON inventory_items
    USING (clinic_id = current_clinic_id());

-- cycle_materials
CREATE POLICY cycle_materials_isolation ON cycle_materials
    USING (clinic_id = current_clinic_id());

-- ── Gönderilen Bildirimler (İzlenebilirlik) ───────────────
CREATE TABLE IF NOT EXISTS sent_messages (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id     UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    patient_id    UUID NOT NULL,
    channel       VARCHAR(50)  NOT NULL DEFAULT 'whatsapp',  -- whatsapp | sms | email
    message_type  VARCHAR(100) NOT NULL,                    -- confirmation | match_found | postop | cancelled_notice
    content       TEXT         NOT NULL,
    status        VARCHAR(50)  NOT NULL DEFAULT 'sent',      -- sent | failed | pending
    sent_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    metadata      JSONB        DEFAULT '{}'
);

ALTER TABLE sent_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY sent_messages_isolation ON sent_messages
    USING (clinic_id = current_clinic_id());

CREATE INDEX IF NOT EXISTS idx_sent_messages_clinic   ON sent_messages(clinic_id);
CREATE INDEX IF NOT EXISTS idx_sent_messages_patient  ON sent_messages(patient_id);
CREATE INDEX IF NOT EXISTS idx_sent_messages_type     ON sent_messages(message_type);
-- Analytics: match_found sorgularında metadata->>'cancelled_appointment_id' aranır
CREATE INDEX IF NOT EXISTS idx_sent_messages_metadata ON sent_messages USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_sent_messages_sent_at  ON sent_messages(sent_at);


CREATE INDEX IF NOT EXISTS idx_users_email            ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_clinic           ON users(clinic_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash    ON refresh_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_appointments_clinic    ON appointments(clinic_id);
CREATE INDEX IF NOT EXISTS idx_appointments_scheduled ON appointments(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_appointments_status    ON appointments(status);
CREATE INDEX IF NOT EXISTS idx_waitlist_clinic        ON waitlist(clinic_id, specialty, priority);
CREATE INDEX IF NOT EXISTS idx_cycle_materials_qr     ON cycle_materials(qr_id);
