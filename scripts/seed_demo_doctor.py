#!/usr/bin/env python3
"""Demo klinik için doktor + (opsiyonel) doctor kullanıcısı seed."""
import os
import sys

try:
    import bcrypt
    import psycopg
except ImportError:
    import subprocess
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "psycopg[binary]", "bcrypt", "-q"],
        check=True,
    )
    import bcrypt
    import psycopg

CLINIC = "d0be60eb-5d3e-43b6-960e-77014f59397a"
DOCTOR_EMAIL = "doctor@demo.com"
DOCTOR_PASS = "Admin1234"
DOCTOR_NAME = "Dt. Demo Hekim"


def main() -> None:
    raw = os.environ["DATABASE_URL"].strip()
    url = raw.replace("postgresql+asyncpg://", "postgresql://").replace("postgres://", "postgresql://")
    if "sslmode=" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"

    pwd_hash = bcrypt.hashpw(DOCTOR_PASS.encode(), bcrypt.gensalt()).decode()

    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (clinic_id, email, hashed_password, full_name, role, is_active)
                SELECT %s, %s, %s, %s, 'doctor', true
                WHERE NOT EXISTS (
                  SELECT 1 FROM users WHERE email = %s AND clinic_id = %s
                )
                """,
                (CLINIC, DOCTOR_EMAIL, pwd_hash, DOCTOR_NAME, DOCTOR_EMAIL, CLINIC),
            )
            cur.execute(
                "SELECT id FROM users WHERE email = %s AND clinic_id = %s",
                (DOCTOR_EMAIL, CLINIC),
            )
            user_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO doctors (clinic_id, full_name, specialty, role, user_id)
                SELECT %s, %s, 'Genel', 'doctor', %s
                WHERE NOT EXISTS (
                  SELECT 1 FROM doctors WHERE clinic_id = %s AND full_name = %s
                )
                """,
                (CLINIC, DOCTOR_NAME, user_id, CLINIC, DOCTOR_NAME),
            )
            cur.execute(
                """
                UPDATE doctors
                SET user_id = %s, specialty = COALESCE(specialty, 'Genel')
                WHERE clinic_id = %s AND full_name = %s AND user_id IS NULL
                """,
                (user_id, CLINIC, DOCTOR_NAME),
            )
            cur.execute(
                "SELECT id::text, full_name, specialty, user_id::text FROM doctors WHERE clinic_id = %s",
                (CLINIC,),
            )
            rows = cur.fetchall()
        conn.commit()

    print("Doktorlar:")
    for r in rows:
        print(f"  - {r[1]} ({r[2]}) id={r[0]} user_id={r[3]}")
    print(f"Login (opsiyonel): {DOCTOR_EMAIL} / {DOCTOR_PASS} · klinik 80C791")


if __name__ == "__main__":
    main()
