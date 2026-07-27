-- 005_user_allowed_pages.sql
-- Per-user customizable page permissions.
-- Admin (owner) can assign/revoke individual page access for each user.

-- Add allowed_pages column (text array) to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS allowed_pages text[];

-- Set defaults based on existing role
UPDATE users SET allowed_pages = ARRAY['dashboard','appointments','waitlist','inventory','analytics','permissions']
WHERE role IN ('owner', 'super_admin') AND allowed_pages IS NULL;

UPDATE users SET allowed_pages = ARRAY['dashboard','appointments','waitlist']
WHERE role = 'doctor' AND allowed_pages IS NULL;

UPDATE users SET allowed_pages = ARRAY['appointments','waitlist','inventory']
WHERE role = 'assistant' AND allowed_pages IS NULL;
