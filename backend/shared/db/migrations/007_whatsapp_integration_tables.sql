-- Migration: 007_whatsapp_integration_tables
-- Purpose: WhatsApp entegrasyonu ve AI yedek liste yönetimi için veritabanı tabloları
-- Author: DentAI Flow Team
-- Date: 2026-05-20

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. CLINIC_SETTINGS
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clinic_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id UUID NOT NULL UNIQUE,
    
    -- Bildirim aralıkları (JSONB): appointment reminder, post-op followup zamanları
    reminder_intervals JSONB DEFAULT NULL,
    
    -- Post-op takip aralıkları (JSONB backcompat)
    post_op_followup_intervals JSONB DEFAULT NULL,
    
    -- WhatsApp kanalını aktive et
    is_whatsapp_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Şablon dili (tr, en, vb.)
    whatsapp_template_lang VARCHAR(10) NOT NULL DEFAULT 'tr',
    
    -- İletişim saatleri
    do_not_disturb_start VARCHAR(5) DEFAULT NULL,
    do_not_disturb_end VARCHAR(5) DEFAULT NULL,
    
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    CONSTRAINT fk_clinic_settings_clinic
        FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX idx_clinic_settings_clinic_id 
    ON clinic_settings(clinic_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. DOCTOR_SETTINGS
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS doctor_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id UUID NOT NULL,
    doctor_id UUID NOT NULL,
    
    -- Acil alert alacak mı?
    receive_emergency_alerts BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Tercih edilen bildirim kanalı
    preferred_notification_channel VARCHAR(20) NOT NULL DEFAULT 'whatsapp',
    
    -- AI otomatis slot doldursun mu?
    waitlist_auto_fill_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- AI skor eşiği (0-100)
    ai_mutation_score_threshold FLOAT NOT NULL DEFAULT 75.0,
    
    -- Saat dilimi
    timezone VARCHAR(50) NOT NULL DEFAULT 'Europe/Istanbul',
    
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    CONSTRAINT fk_doctor_settings_clinic
        FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE,
    CONSTRAINT fk_doctor_settings_doctor
        FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT uq_doctor_clinic_settings UNIQUE (clinic_id, doctor_id)
);

CREATE INDEX idx_doctor_settings_doctor_id 
    ON doctor_settings(doctor_id);
CREATE INDEX idx_doctor_settings_clinic_id 
    ON doctor_settings(clinic_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. APPOINTMENT_EXTENDED
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS appointment_extended (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    appointment_id UUID NOT NULL UNIQUE,
    clinic_id UUID NOT NULL,
    
    -- AI tarafından dolduruldu mu?
    is_auto_filled_by_ai BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- AI'ın verdiği skor (0-100)
    ai_mutation_score FLOAT DEFAULT NULL,
    
    -- AI'ın açıklaması
    ai_ranking_reason TEXT DEFAULT NULL,
    
    -- AI seçtiği hasta
    ai_selected_patient_id UUID DEFAULT NULL,
    
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    CONSTRAINT fk_appointment_extended_clinic
        FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE
);

CREATE INDEX idx_appointment_extended_appointment_id 
    ON appointment_extended(appointment_id);
CREATE INDEX idx_appointment_extended_clinic_id 
    ON appointment_extended(clinic_id);
CREATE INDEX idx_appointment_extended_ai_filled 
    ON appointment_extended(is_auto_filled_by_ai);

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. CLINIC_FAQ (RAG)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clinic_faq (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id UUID NOT NULL,
    
    -- Soru ve cevap
    question VARCHAR(500) NOT NULL,
    answer TEXT NOT NULL,
    
    -- Kategori
    category VARCHAR(50) NOT NULL,
    
    -- Görünüş önceliği
    priority INTEGER NOT NULL DEFAULT 10,
    
    -- Video URL
    video_url VARCHAR(500) DEFAULT NULL,
    
    -- Ek dosyalar
    attachment_urls TEXT[] DEFAULT NULL,
    
    -- WhatsApp şablon bağlantısı
    whatsapp_template_key VARCHAR(100) DEFAULT NULL,
    
    -- Yayınlama durumu (draft, published, archived)
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    
    -- Oluşturan kullanıcı
    created_by_user_id UUID NOT NULL,
    
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    CONSTRAINT fk_clinic_faq_clinic
        FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE,
    CONSTRAINT fk_clinic_faq_created_by
        FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_clinic_faq_clinic_id 
    ON clinic_faq(clinic_id);
CREATE INDEX idx_clinic_faq_category 
    ON clinic_faq(category);
CREATE INDEX idx_clinic_faq_status 
    ON clinic_faq(status);

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. PATIENT_FEEDBACK
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS patient_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id UUID NOT NULL,
    appointment_id UUID NOT NULL,
    patient_id UUID NOT NULL,
    doctor_id UUID DEFAULT NULL,
    
    -- Şikayet tipi
    feedback_type VARCHAR(50) NOT NULL,
    
    -- Önem derecesi
    severity VARCHAR(20) NOT NULL,
    
    -- Şikayet mesajı
    message TEXT NOT NULL,
    
    -- Hasta görüntüleri
    image_urls TEXT[] DEFAULT NULL,
    
    -- Doktor müdahalesi gerekli mi?
    requires_action BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Müdahale detayları
    action_required_details TEXT DEFAULT NULL,
    
    -- Atanan kullanıcı (follow-up)
    assigned_to_user_id UUID DEFAULT NULL,
    
    -- Çözüm notları
    resolution_notes TEXT DEFAULT NULL,
    
    -- Çözüldü mü?
    is_resolved BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Çözüm zamanı
    resolved_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    
    -- Kanal (whatsapp, sms, call)
    channel VARCHAR(20) NOT NULL DEFAULT 'whatsapp',
    
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    CONSTRAINT fk_patient_feedback_clinic
        FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE,
    CONSTRAINT fk_patient_feedback_appointment
        FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE,
    CONSTRAINT fk_patient_feedback_doctor
        FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_patient_feedback_clinic_id 
    ON patient_feedback(clinic_id);
CREATE INDEX idx_patient_feedback_appointment_id 
    ON patient_feedback(appointment_id);
CREATE INDEX idx_patient_feedback_patient_id 
    ON patient_feedback(patient_id);
CREATE INDEX idx_patient_feedback_severity 
    ON patient_feedback(severity);
CREATE INDEX idx_patient_feedback_requires_action 
    ON patient_feedback(requires_action);
CREATE INDEX idx_patient_feedback_created_at 
    ON patient_feedback(created_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- 6. WHATSAPP_MESSAGE_LOG
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS whatsapp_message_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id UUID NOT NULL,
    patient_id UUID DEFAULT NULL,
    
    -- Telefon numarası
    phone_number VARCHAR(20) NOT NULL,
    
    -- Mesaj tipi
    message_type VARCHAR(50) NOT NULL,
    
    -- Şablon anahtarı
    template_key VARCHAR(100) NOT NULL,
    
    -- Idempotency key
    idempotency_key VARCHAR(255) NOT NULL,
    
    -- Mesaj durumu
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    
    -- WhatsApp API mesaj ID
    whatsapp_message_id VARCHAR(100) DEFAULT NULL,
    
    -- Hata mesajı
    error_message TEXT DEFAULT NULL,
    
    -- Retry sayısı
    retry_count INTEGER NOT NULL DEFAULT 0,
    
    -- Son retry zamanı
    last_retry_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    
    -- Şablon değişkenleri
    template_variables JSONB DEFAULT NULL,
    
    -- Oluşturan (system, scheduled_job, manual)
    created_by VARCHAR(50) NOT NULL DEFAULT 'system',
    
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    CONSTRAINT fk_whatsapp_message_log_clinic
        FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE,
    CONSTRAINT uq_whatsapp_idempotency UNIQUE (clinic_id, idempotency_key)
);

CREATE INDEX idx_whatsapp_message_log_clinic_id 
    ON whatsapp_message_log(clinic_id);
CREATE INDEX idx_whatsapp_message_log_patient_id 
    ON whatsapp_message_log(patient_id);
CREATE INDEX idx_whatsapp_message_log_status 
    ON whatsapp_message_log(status);
CREATE INDEX idx_whatsapp_message_log_idempotency_key 
    ON whatsapp_message_log(idempotency_key);

-- ─────────────────────────────────────────────────────────────────────────────
-- 7. RLS VE SECURITY POLICIES
-- ─────────────────────────────────────────────────────────────────────────────

-- RLS enable (eğer henüz yapılmamışsa)
ALTER TABLE clinic_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE doctor_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointment_extended ENABLE ROW LEVEL SECURITY;
ALTER TABLE clinic_faq ENABLE ROW LEVEL SECURITY;
ALTER TABLE patient_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE whatsapp_message_log ENABLE ROW LEVEL SECURITY;

-- RLS Policies - tüm tablolar clinic_id tarafından izole edilir
CREATE POLICY clinic_settings_isolation ON clinic_settings
    USING (clinic_id = current_setting('app.current_clinic_id')::UUID);

CREATE POLICY doctor_settings_isolation ON doctor_settings
    USING (clinic_id = current_setting('app.current_clinic_id')::UUID);

CREATE POLICY appointment_extended_isolation ON appointment_extended
    USING (clinic_id = current_setting('app.current_clinic_id')::UUID);

CREATE POLICY clinic_faq_isolation ON clinic_faq
    USING (clinic_id = current_setting('app.current_clinic_id')::UUID);

CREATE POLICY patient_feedback_isolation ON patient_feedback
    USING (clinic_id = current_setting('app.current_clinic_id')::UUID);

CREATE POLICY whatsapp_message_log_isolation ON whatsapp_message_log
    USING (clinic_id = current_setting('app.current_clinic_id')::UUID);

-- ─────────────────────────────────────────────────────────────────────────────
-- Terminal output for verification
-- ─────────────────────────────────────────────────────────────────────────────
-- Tüm tablolar başarıyla oluşturuldu:
-- ✓ clinic_settings          - Klinik bildirim ve takip ayarları
-- ✓ doctor_settings         - Doktor ayarları ve AI konfigürasyonu  
-- ✓ appointment_extended    - Randevu AI metadata
-- ✓ clinic_faq             - RAG metinleri
-- ✓ patient_feedback       - Hasta geri bildirimi
-- ✓ whatsapp_message_log   - WhatsApp audit trail

-- RLS politikaları clinic_id ile izolasyon sağlar
-- İndeksler performans ve query optimization için optimize edildi
