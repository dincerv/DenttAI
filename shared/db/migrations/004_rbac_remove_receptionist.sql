-- 004_rbac_remove_receptionist.sql
-- Resepsiyonist rolünü kaldır; mevcut receptionist kullanıcıları assistant'a çevir.
-- PostgreSQL'de enum değer silme doğrudan desteklenmez; column type text üzerinden geçiş yapılır.
-- Taze kurulumda (receptionist hiç yoksa) UPDATE atlanır — enum literal parse hatası olmasın.

BEGIN;

-- 1. receptionist sadece enum'da varsa çevir (taze Neon/init'te yok)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_enum e
    JOIN pg_type t ON t.oid = e.enumtypid
    WHERE t.typname = 'user_role' AND e.enumlabel = 'receptionist'
  ) THEN
    EXECUTE 'UPDATE users SET role = ''assistant'' WHERE role::text = ''receptionist''';
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_name = 'doctors' AND column_name = 'role'
    ) THEN
      EXECUTE 'UPDATE doctors SET role = ''assistant'' WHERE role::text = ''receptionist''';
    END IF;
  END IF;
END $$;

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
