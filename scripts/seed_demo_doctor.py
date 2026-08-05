#!/usr/bin/env python3
import os
import sys

try:
    import psycopg
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "psycopg[binary]", "-q"], check=True)
    import psycopg

CLINIC = "d0be60eb-5d3e-43b6-960e-77014f59397a"
raw = os.environ["DATABASE_URL"].strip()
url = raw.replace("postgresql+asyncpg://", "postgresql://").replace("postgres://", "postgresql://")
if "sslmode=" not in url:
    url += ("&" if "?" in url else "?") + "sslmode=require"

with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO doctors (clinic_id, full_name, specialty, role)
            SELECT %s, 'Dt. Demo Hekim', 'Genel', 'doctor'
            WHERE NOT EXISTS (
              SELECT 1 FROM doctors
              WHERE clinic_id = %s AND full_name = 'Dt. Demo Hekim'
            )
            """,
            (CLINIC, CLINIC),
        )
        cur.execute(
            "SELECT id::text, full_name, specialty FROM doctors WHERE clinic_id = %s",
            (CLINIC,),
        )
        rows = cur.fetchall()
    conn.commit()

print("Doktorlar:")
for r in rows:
    print(f"  - {r[1]} ({r[2]}) id={r[0]}")
