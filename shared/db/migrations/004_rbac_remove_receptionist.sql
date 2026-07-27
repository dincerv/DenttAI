-- 004_rbac_remove_receptionist.sql
-- Resepsiyonist rolünü kaldır; mevcut receptionist kullanıcıları assistant'a çevir.
-- PostgreSQL'de enum değer silme doğrudan desteklenmez; column type text üzerinden geçiş yapılır.

BEGIN;

-- 1. Mevcut receptionist kullanıcılarını assistant'a çevir
UPDATE users SET role = 'assistant' WHERE role = 'receptionist';
UPDATE doctors SET role = 'assistant' WHERE role = 'receptionist';

-- 2. Kolonları text'e çevir (geçici)
ALTER TABLE users
  ALTER COLUMN role DROP DEFAULT,
  ALTER COLUMN role TYPE text USING role::text;

ALTER TABLE doctors
  ALTER COLUMN role DROP DEFAULT,
  ALTER COLUMN role TYPE text USING role::text;

-- 3. Eski enum'u kaldır
DROP TYPE IF EXISTS user_role;

-- 4. Yeni enum oluştur (receptionist olmadan, super_admin dahil)
CREATE TYPE user_role AS ENUM ('super_admin', 'owner', 'doctor', 'assistant');

-- 5. Kolonları yeni enum'a çevir
ALTER TABLE users
  ALTER COLUMN role TYPE user_role USING role::user_role,
  ALTER COLUMN role SET DEFAULT 'assistant';

ALTER TABLE doctors
  ALTER COLUMN role TYPE user_role USING role::user_role,
  ALTER COLUMN role SET DEFAULT 'doctor';

COMMIT;
