#!/usr/bin/env python3
"""
Neon (veya herhangi bir Postgres) üzerine DentAI şema + demo seed uygular.

Kullanım:
  set DATABASE_URL=postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require
  python scripts/apply_neon_schema.py
  python scripts/apply_neon_schema.py --seed-only

Notlar:
  - Migration için DIRECT (non-pooler) connection string kullan.
  - Secret'ı commit etme; sadece env olarak ver.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INIT_SQL = ROOT / "shared" / "db" / "init" / "01_init.sql"
MIGRATIONS_DIR = ROOT / "shared" / "db" / "migrations"

DEMO_CLINIC_ID = "d0be60eb-5d3e-43b6-960e-77014f59397a"
DEMO_CLINIC_CODE = "80C791"
OWNER_EMAIL = "admin@demo.com"
OWNER_PASS = "Admin1234"
SUPER_EMAIL = "superadmin@dentai.io"


def _ensure_deps() -> None:
    try:
        import psycopg  # noqa: F401
        from passlib.context import CryptContext  # noqa: F401
    except ImportError:
        import subprocess

        subprocess.run(
            [sys.executable, "-m", "pip", "install", "psycopg[binary]", "passlib[bcrypt]", "bcrypt", "-q"],
            check=True,
        )


def normalize_sync_url(url: str) -> str:
    """psycopg için libpq URL (postgresql://)."""
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url[len("postgresql+asyncpg://") :]
    elif url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if "sslmode=" not in url and "ssl=" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}sslmode=require"
    return url


def _table_exists(conn, name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s",
            (name,),
        )
        return cur.fetchone() is not None


def run_sql_file(conn, path: Path, *, ignore_duplicate: bool = True) -> None:
    import psycopg
    from psycopg import errors as pg_errors

    sql = path.read_text(encoding="utf-8")
    print(f"  → {path.relative_to(ROOT)}")
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    except (
        pg_errors.DuplicateObject,
        pg_errors.DuplicateTable,
        pg_errors.DuplicateColumn,
        pg_errors.UniqueViolation,
    ) as e:
        conn.rollback()
        if ignore_duplicate:
            print(f"    (atlandı — zaten var: {e.__class__.__name__})")
            return
        raise
    except Exception:
        conn.rollback()
        raise


def apply_schema(conn) -> None:
    print("\n== Şema: extension + init ==")
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    conn.commit()

    if not INIT_SQL.exists():
        raise SystemExit(f"Init SQL bulunamadı: {INIT_SQL}")

    if _table_exists(conn, "clinics"):
        print("  → init atlandı (clinics tablosu zaten var)")
    else:
        run_sql_file(conn, INIT_SQL)

    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    print(f"\n== Migration'lar ({len(files)}) ==")
    for path in files:
        run_sql_file(conn, path)


def seed_demo(conn) -> None:
    import bcrypt

    print("\n== Demo seed ==")
    # passlib + yeni bcrypt sürümü çakışabiliyor; doğrudan bcrypt kullan
    pwd_hash = bcrypt.hashpw(OWNER_PASS.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO clinics (id, name, slug, is_active)
            VALUES (%s, 'Demo Klinik', 'demo', true)
            ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, is_active = true
            """,
            (DEMO_CLINIC_ID,),
        )
        # code sütunu migration 006 sonrası var
        cur.execute(
            "UPDATE clinics SET code = %s WHERE id = %s",
            (DEMO_CLINIC_CODE, DEMO_CLINIC_ID),
        )
        cur.execute(
            "SELECT id FROM users WHERE email = %s AND clinic_id = %s",
            (OWNER_EMAIL, DEMO_CLINIC_ID),
        )
        if cur.fetchone():
            cur.execute(
                """
                UPDATE users
                SET hashed_password = %s, is_active = true, role = 'owner', full_name = 'Admin Kullanici'
                WHERE email = %s AND clinic_id = %s
                """,
                (pwd_hash, OWNER_EMAIL, DEMO_CLINIC_ID),
            )
        else:
            cur.execute(
                """
                INSERT INTO users (clinic_id, email, hashed_password, full_name, role, is_active)
                VALUES (%s, %s, %s, 'Admin Kullanici', 'owner', true)
                """,
                (DEMO_CLINIC_ID, OWNER_EMAIL, pwd_hash),
            )

        cur.execute(
            "SELECT id FROM users WHERE email = %s AND role = 'super_admin'",
            (SUPER_EMAIL,),
        )
        if cur.fetchone():
            cur.execute(
                """
                UPDATE users
                SET hashed_password = %s, is_active = true, clinic_id = NULL
                WHERE email = %s AND role = 'super_admin'
                """,
                (pwd_hash, SUPER_EMAIL),
            )
        else:
            cur.execute(
                """
                INSERT INTO users (clinic_id, email, hashed_password, full_name, role, is_active)
                VALUES (NULL, %s, %s, 'Super Admin', 'super_admin', true)
                """,
                (SUPER_EMAIL, pwd_hash),
            )
    conn.commit()
    print(f"  ✔ Klinik kodu: {DEMO_CLINIC_CODE}")
    print(f"  ✔ Owner: {OWNER_EMAIL} / {OWNER_PASS}")
    print(f"  ✔ Super: {SUPER_EMAIL} / {OWNER_PASS}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Neon şema + demo seed")
    parser.add_argument("--seed-only", action="store_true", help="Sadece demo kullanıcı seed")
    parser.add_argument("--schema-only", action="store_true", help="Seed yapma")
    args = parser.parse_args()

    raw = os.environ.get("DATABASE_URL", "").strip()
    if not raw:
        raise SystemExit("DATABASE_URL env zorunlu (Neon direct connection string)")

    _ensure_deps()
    import psycopg

    url = normalize_sync_url(raw)
    print(f"Bağlanılıyor… host={url.split('@')[-1].split('/')[0]}")

    with psycopg.connect(url) as conn:
        if not args.seed_only:
            apply_schema(conn)
        if not args.schema_only:
            seed_demo(conn)

    print("\nTamam.")


if __name__ == "__main__":
    main()
