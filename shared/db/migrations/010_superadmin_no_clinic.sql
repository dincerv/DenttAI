-- ============================================================
-- Migration 010: Super Admin artık hiçbir kliniğe ait değil
-- users.clinic_id → nullable (sadece super_admin için NULL olabilir)
-- ============================================================

-- 1. NOT NULL kısıtını kaldır
ALTER TABLE users ALTER COLUMN clinic_id DROP NOT NULL;

-- 2. Eski unique constraint'i kaldır (NULL içerdiğinde çalışmaz)
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_clinic_unique;

-- 3. Yeni: klinik kullanıcıları için (email, clinic_id) unique (clinic_id NOT NULL olduğunda)
CREATE UNIQUE INDEX IF NOT EXISTS users_email_clinic_unique
    ON users(email, clinic_id)
    WHERE clinic_id IS NOT NULL;

-- 4. Yeni: super_admin'in email'i global olarak unique
CREATE UNIQUE INDEX IF NOT EXISTS users_super_admin_email_unique
    ON users(email)
    WHERE role = 'super_admin';

-- 5. Mevcut super_admin kullanıcıların clinic_id'sini NULL yap
UPDATE users SET clinic_id = NULL WHERE role = 'super_admin';
