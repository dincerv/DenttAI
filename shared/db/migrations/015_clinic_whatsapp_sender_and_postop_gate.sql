-- Migration 015: Clinic-specific WhatsApp sender selection and post-op gating
ALTER TABLE clinic_settings
ADD COLUMN IF NOT EXISTS whatsapp_business_account_id VARCHAR(100),
ADD COLUMN IF NOT EXISTS whatsapp_phone_number_id VARCHAR(100);

CREATE INDEX IF NOT EXISTS idx_clinic_settings_whatsapp_phone_number_id
ON clinic_settings (whatsapp_phone_number_id)
WHERE whatsapp_phone_number_id IS NOT NULL;
