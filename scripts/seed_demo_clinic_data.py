#!/usr/bin/env python3
"""
Demo klinik (80C791) için örnek veri: hasta, randevu, waitlist, envanter, cycle.

Kullanım:
  set DATABASE_URL=postgresql://...
  python scripts/seed_demo_clinic_data.py

Idempotent: sabit UUID + ON CONFLICT / WHERE NOT EXISTS.
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

CLINIC = UUID("d0be60eb-5d3e-43b6-960e-77014f59397a")
DOCTOR_NAME = "Dt. Demo Hekim"

# Sabit hasta UUID'leri (yeniden çalıştırılabilir)
PATIENTS = [
    ("a1000001-0000-4000-8000-000000000001", "Ahmet Öztürk", "+905551234567", "ahmet@demo.test"),
    ("a1000001-0000-4000-8000-000000000002", "Fatma Demir", "+905559876543", "fatma@demo.test"),
    ("a1000001-0000-4000-8000-000000000003", "Mehmet Kaya", "+905554561234", None),
    ("a1000001-0000-4000-8000-000000000004", "Ayşe Yıldız", "+905557891234", "ayse@demo.test"),
    ("a1000001-0000-4000-8000-000000000005", "Mustafa Çelik", "+905553214567", "mustafa@demo.test"),
    ("a1000001-0000-4000-8000-000000000006", "Zeynep Şahin", "+905556543210", None),
    ("a1000001-0000-4000-8000-000000000007", "Hüseyin Arslan", "+905551239876", "huseyin@demo.test"),
    ("a1000001-0000-4000-8000-000000000008", "Hatice Güneş", "+905558765432", None),
    ("a1000001-0000-4000-8000-000000000009", "İbrahim Kurt", "+905552345678", "ibrahim@demo.test"),
    ("a1000001-0000-4000-8000-00000000000a", "Emine Aydın", "+905551112233", "emine@demo.test"),
]

# name, category, qty, unit, min, cost, shelf, expiry (days from today), batch
INVENTORY = [
    ("b2000001-0000-4000-8000-000000000001", "Kompozit Dolgu", "Restoratif", 12, "adet", 20, 45.0, "A1", 180, "LOT-CMP-01"),
    ("b2000001-0000-4000-8000-000000000002", "Kompozit Dolgu", "Restoratif", 40, "adet", 20, 45.0, "A1", 400, "LOT-CMP-02"),
    ("b2000001-0000-4000-8000-000000000003", "Cerrahi Eldiven M", "Sarf", 200, "çift", 100, 2.5, "B2", 365, "LOT-GLV-01"),
    ("b2000001-0000-4000-8000-000000000004", "Kanal İğnesi 25mm", "Endodonti", 80, "paket", 30, 15.0, "C3", 540, "LOT-END-01"),
    ("b2000001-0000-4000-8000-000000000005", "Anestezi Kartuşu", "Anestezi", 120, "adet", 50, 8.0, "A4", 300, "LOT-ANS-01"),
    ("b2000001-0000-4000-8000-000000000006", "Aljinat Ölçü Maddesi", "Protez", 30, "kg", 10, 120.0, "D1", 200, "LOT-ALG-01"),
    ("b2000001-0000-4000-8000-000000000007", "Dental X-Ray Fotoğraf", "Radyoloji", 500, "adet", 100, 1.2, "E2", 730, "LOT-XRY-01"),
    ("b2000001-0000-4000-8000-000000000008", "Steril Kompres", "Sarf", 300, "paket", 80, 3.5, "B3", 450, "LOT-KMP-01"),
    ("b2000001-0000-4000-8000-000000000009", "İmplant Vidası 3.5x10", "İmplant", 7, "adet", 10, 320.0, "F1", 900, "LOT-IMP-01"),
    ("b2000001-0000-4000-8000-00000000000a", "Nitril Maske FFP2", "Sarf", 1000, "adet", 200, 1.8, "B1", 600, "LOT-MSK-01"),
]

CYCLE = [
    ("c3000001-0000-4000-8000-000000000001", "QR-ANG-DEMO-01", "Anguldurva A1", "anguldurva", 180),
    ("c3000001-0000-4000-8000-000000000002", "QR-TUR-DEMO-01", "Türbin T2", "tur", 120),
    ("c3000001-0000-4000-8000-000000000003", "QR-FIL-DEMO-01", "File Set F1", "file", 90),
    ("c3000001-0000-4000-8000-000000000004", "QR-ANG-DEMO-02", "Anguldurva A2", "anguldurva", 180),
    ("c3000001-0000-4000-8000-000000000005", "QR-MISC-DEMO-01", "Apex Locator", "diger", 365),
]


def _ensure_deps() -> None:
    try:
        import psycopg  # noqa: F401
    except ImportError:
        import subprocess

        subprocess.run(
            [sys.executable, "-m", "pip", "install", "psycopg[binary]", "-q"],
            check=True,
        )


def normalize_url(url: str) -> str:
    url = url.strip().strip('"').strip("'")
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url[len("postgresql+asyncpg://") :]
    elif url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if "sslmode=" not in url and "ssl=" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"
    return url


def load_database_url() -> str:
    env = os.environ.get("DATABASE_URL")
    if env:
        return normalize_url(env)
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                return normalize_url(line.split("=", 1)[1])
    raise SystemExit("DATABASE_URL gerekli (.env veya ortam değişkeni)")


def ensure_doctor(cur) -> UUID:
    cur.execute(
        """
        INSERT INTO doctors (clinic_id, full_name, specialty, role)
        SELECT %s, %s, 'Genel', 'doctor'
        WHERE NOT EXISTS (
          SELECT 1 FROM doctors WHERE clinic_id = %s AND full_name = %s
        )
        """,
        (CLINIC, DOCTOR_NAME, CLINIC, DOCTOR_NAME),
    )
    cur.execute(
        "SELECT id FROM doctors WHERE clinic_id = %s AND full_name = %s LIMIT 1",
        (CLINIC, DOCTOR_NAME),
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError("Demo doktor bulunamadı / oluşturulamadı")
    return row[0]


def seed_patients(cur) -> list[UUID]:
    ids: list[UUID] = []
    for pid, name, phone, email in PATIENTS:
        cur.execute(
            """
            INSERT INTO patients (id, clinic_id, full_name, phone, email)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (pid, CLINIC, name, phone, email),
        )
        ids.append(UUID(pid))
    # Eski seed ile çakışan isimler varsa yine kullan
    cur.execute(
        "SELECT id FROM patients WHERE clinic_id = %s ORDER BY created_at NULLS LAST, full_name LIMIT 15",
        (CLINIC,),
    )
    found = [r[0] for r in cur.fetchall()]
    return found if found else ids


def seed_appointments(cur, doctor_id: UUID, patient_ids: list[UUID]) -> int:
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    specs = [
        "Genel Diş",
        "Endodonti",
        "İmplant",
        "Ortodonti",
        "Periodontoloji",
        "Protez",
        "Cerrahi",
        "Pedodonti",
    ]
    plans = [
        (-14, "completed", "Diş taşı temizliği tamamlandı."),
        (-10, "completed", "Kompozit dolgu #16."),
        (-7, "no_show", "Hasta gelmedi."),
        (-3, "cancelled", "Hasta iptal etti."),
        (-1, "completed", "Kanal tedavisi seans 1."),
        (0, "confirmed", "Kontrol randevusu."),
        (1, "scheduled", "İmplant konsültasyon."),
        (3, "scheduled", "Ortodonti plak kontrolü."),
        (5, "scheduled", "Kron prova."),
        (8, "scheduled", "Yeni hasta muayene."),
    ]
    n = 0
    for i, (day_off, status, notes) in enumerate(plans):
        pid = patient_ids[i % len(patient_ids)]
        appt_id = UUID(f"d4000001-0000-4000-8000-{i+1:012d}")
        scheduled = now + timedelta(days=day_off, hours=9 + (i % 7))
        cur.execute(
            """
            INSERT INTO appointments (
              id, clinic_id, patient_id, doctor_id, scheduled_at, status,
              type, notes, specialty, duration_minutes, is_new_patient
            )
            VALUES (
              %s, %s, %s, %s, %s, %s::appointment_status,
              'Tedavi', %s, %s, 30, %s
            )
            ON CONFLICT (id) DO NOTHING
            """,
            (
                appt_id,
                CLINIC,
                pid,
                doctor_id,
                scheduled,
                status,
                notes,
                specs[i % len(specs)],
                i == 9,
            ),
        )
        n += cur.rowcount
    return n


def seed_waitlist(cur, doctor_id: UUID, patient_ids: list[UUID]) -> int:
    entries = [
        (0, "İmplant", 3, "Pzt,Çar", "Erken slot ister"),
        (1, "Ortodonti", 2, "Sal,Per", None),
        (2, "Endodonti", 1, "Cuma", "Ağrı şikayeti"),
        (3, "Genel Diş", 0, "Her gün", None),
        (4, "Cerrahi", 2, "Pzt", "Gömülü 20 yaş"),
        (5, "Protez", 1, "Çar,Cum", None),
        (6, "Periodontoloji", 0, "Sal", None),
        (7, "Pedodonti", 1, "Her gün", "Çocuk hasta"),
    ]
    n = 0
    for i, (pidx, specialty, priority, days, notes) in enumerate(entries):
        pid = patient_ids[pidx % len(patient_ids)]
        wid = UUID(f"e5000001-0000-4000-8000-{i+1:012d}")
        cur.execute(
            """
            INSERT INTO waitlist (
              id, clinic_id, patient_id, specialty, priority, is_active,
              doctor_id, preferred_days, notes
            )
            VALUES (%s, %s, %s, %s, %s, true, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (wid, CLINIC, pid, specialty, priority, doctor_id, days, notes),
        )
        if cur.rowcount:
            n += 1
            continue
        # Unique active index çakışması
        cur.execute(
            """
            INSERT INTO waitlist (
              clinic_id, patient_id, specialty, priority, is_active,
              doctor_id, preferred_days, notes
            )
            SELECT %s, %s, %s, %s, true, %s, %s, %s
            WHERE NOT EXISTS (
              SELECT 1 FROM waitlist
              WHERE clinic_id = %s AND patient_id = %s AND specialty = %s AND is_active = true
            )
            """,
            (CLINIC, pid, specialty, priority, doctor_id, days, notes, CLINIC, pid, specialty),
        )
        n += cur.rowcount
    return n


def seed_inventory(cur) -> int:
    n = 0
    today = date.today()
    for iid, name, cat, qty, unit, min_s, cost, shelf, exp_days, batch in INVENTORY:
        expiry = today + timedelta(days=exp_days)
        cur.execute(
            """
            INSERT INTO inventory_items (
              id, clinic_id, name, category, quantity, unit,
              min_stock_level, cost_per_unit, shelf_code, expiry_date, batch_number
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (iid, CLINIC, name, cat, qty, unit, min_s, cost, shelf, expiry, batch),
        )
        if cur.rowcount:
            n += 1
            continue
        cur.execute(
            """
            INSERT INTO inventory_items (
              clinic_id, name, category, quantity, unit,
              min_stock_level, cost_per_unit, shelf_code, expiry_date, batch_number
            )
            SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            WHERE NOT EXISTS (
              SELECT 1 FROM inventory_items
              WHERE clinic_id = %s AND name = %s AND batch_number = %s
            )
            """,
            (CLINIC, name, cat, qty, unit, min_s, cost, shelf, expiry, batch, CLINIC, name, batch),
        )
        n += cur.rowcount
    return n


def seed_cycle(cur) -> int:
    n = 0
    today = date.today()
    for cid, qr, name, cat, lifespan in CYCLE:
        start = today - timedelta(days=lifespan // 3)
        cur.execute(
            """
            INSERT INTO cycle_materials (
              id, clinic_id, qr_id, name, category, start_date,
              expected_lifespan, is_active
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, true)
            ON CONFLICT (id) DO NOTHING
            """,
            (cid, CLINIC, qr, name, cat, start, lifespan),
        )
        if cur.rowcount:
            n += 1
            continue
        cur.execute(
            """
            INSERT INTO cycle_materials (
              clinic_id, qr_id, name, category, start_date, expected_lifespan, is_active
            )
            SELECT %s, %s, %s, %s, %s, %s, true
            WHERE NOT EXISTS (SELECT 1 FROM cycle_materials WHERE qr_id = %s)
            """,
            (CLINIC, qr, name, cat, start, lifespan, qr),
        )
        n += cur.rowcount
    return n


def main() -> None:
    _ensure_deps()
    import psycopg

    url = load_database_url()
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            doctor_id = ensure_doctor(cur)
            patient_ids = seed_patients(cur)
            appt_n = seed_appointments(cur, doctor_id, patient_ids)
            wait_n = seed_waitlist(cur, doctor_id, patient_ids)
            inv_n = seed_inventory(cur)
            cyc_n = seed_cycle(cur)

            cur.execute("SELECT COUNT(*) FROM patients WHERE clinic_id = %s", (CLINIC,))
            p_total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM appointments WHERE clinic_id = %s", (CLINIC,))
            a_total = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM waitlist WHERE clinic_id = %s AND is_active",
                (CLINIC,),
            )
            w_total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM inventory_items WHERE clinic_id = %s", (CLINIC,))
            i_total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM cycle_materials WHERE clinic_id = %s", (CLINIC,))
            c_total = cur.fetchone()[0]
        conn.commit()

    print("Demo klinik verisi hazır (80C791)")
    print(f"  Doktor : {DOCTOR_NAME} ({doctor_id})")
    print(f"  Hasta  : +{len(patient_ids)} seed / toplam {p_total}")
    print(f"  Randevu: +{appt_n} yeni / toplam {a_total}")
    print(f"  Waitlist:+{wait_n} yeni / aktif {w_total}")
    print(f"  Envanter:+{inv_n} yeni / toplam {i_total}")
    print(f"  Cycle  : +{cyc_n} yeni / toplam {c_total}")


if __name__ == "__main__":
    main()
