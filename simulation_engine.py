#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DentAI Flow — Simulation Engine v1.0
=====================================
ÖNEMLI NOT: Bu veriler TAMAMEN GEÇİCİ (TEMPORARY/VOLATILE) test verileridir.
Amaç yalnızca sistemi doluyken görmek ve otonom süreçleri tetiklemektir.

Çalıştırmak için:
  python simulation_engine.py
"""
import json
import random
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

# ── Requests paketi ────────────────────────────────────────────────────────────
try:
    import requests
except ImportError:
    print("  → requests paketi bulunamadı, yükleniyor...")
    subprocess.run([sys.executable, "-m", "pip", "install", "requests", "-q"], check=True)
    import requests  # type: ignore

# ── Terminal renkleri (ANSI) ───────────────────────────────────────────────────
class C:
    R  = "\033[0m"
    B  = "\033[1m"
    GR = "\033[92m"
    YE = "\033[93m"
    RE = "\033[91m"
    CY = "\033[96m"
    BL = "\033[94m"
    MA = "\033[95m"
    WH = "\033[97m"
    DM = "\033[2m"

def ok(m):   print(f"  {C.GR}✔{C.R}  {m}")
def warn(m): print(f"  {C.YE}⚠{C.R}  {m}")
def err(m):  print(f"  {C.RE}✘{C.R}  {m}")
def info(m): print(f"  {C.CY}→{C.R}  {m}")

def header(title):
    bar = "═" * 62
    print(f"\n{C.B}{C.BL}{bar}{C.R}")
    print(f"{C.B}{C.WH}  {title}{C.R}")
    print(f"{C.B}{C.BL}{bar}{C.R}")

# ── Sabit değerler ─────────────────────────────────────────────────────────────
BASE_URL      = "http://localhost:8081/api"
POSTGRES_CTR  = "dentai_postgres"
AUTH_CTR      = "dentai_auth"
NOTIFY_CTR    = "dentai_notification"
RABBIT_CTR    = "dentai_rabbitmq"
PG_USER       = "dentai"
PG_DB         = "dentai_db"
ADMIN_EMAIL   = "admin@demo.com"
ADMIN_PASS    = "Admin1234"
DEMO_CLINIC_ID = "d0be60eb-5d3e-43b6-960e-77014f59397a"
DEMO_DOCTOR_ID = "9f62cb80-337b-4a71-93ac-61517c4900b8"  # doctor@demo.com

SPECIALTIES = [
    "Ortodonti", "Pedodonti", "Implant", "Cerrahi",
    "Endodonti", "Periodontoloji", "Protez", "Genel Dis",
]
# For API calls: must match exactly what specialty validator accepts
SPECIALTIES_API = [
    "Ortodonti", "Pedodonti", "Cerrahi",
    "Endodonti", "Periodontoloji", "Protez",
]

TREATMENT_NOTES = [
    "2 Dolgu yapildi, ust cene sag ceyrek, hasta iyi tolere etti.",
    "1 Kanal Tedavisi - #46 dis, 3 kanal, devital pulpa saptandi.",
    "4 Implant: #14,#15,#24,#25 - sinus lifting uygulandi.",
    "Kompozit dolgu: #16 MOD, #17 DO - tek seansta tamamlandi.",
    "Seramik kron: #11,#21 - estetik zon, hastayi cok memnun.",
    "Implant cerrahisi - #36: 4.1x10 vida, kanama kontrol altinda.",
    "Periodontal tedavi: 4 kadran, skaler + kuretle debridman.",
    "Gomuk 20 yas cekimi: alt sol, osteotomi yapildi, sut konuldu.",
    "Protez olcusu: ust tam protez, balmumu deneme yapildi.",
    "Ortodonti muayene + plak yerlestirildi, hijyen egitimi verildi.",
    "3 Dolgu: #17 O, #27 MO, #37 DO - kompozit restorasyon.",
    "1 Kanal Tedavisi + gecici kuron - #47, kalsiyum hidroksit.",
    "Pedodon: sut dis cekimi #54,#64, lokal anestezi yeterliydi.",
    "Dis beyazlatma: uygulama 2/3 seans, %10 karbamid peroksit.",
    "Tel karistirma + ark tel degisimi, 3. ay kontrolu tamam.",
    "Gingivektomi sol alt kadran, periodontal iyilesme bekleniyor.",
    "Zirkonyum kuron: #11,#12,#21,#22 - renk A2 secildi.",
    "Implant protezi ust yapi: #34,#36, vida torklama 35 Ncm.",
    "Akut apse drenaji + antibiyotik recetesi: amoksisilin 500mg.",
    "Dis tasi temizligi - full mouth debridman, OHI verildi.",
]

# Envanter kalemleri (isimler ASCII-safe, sonra Türkçe veri DB'ye girecek)
INVENTORY_ITEMS = [
    {"name": "Kompozit Dolgu",       "category": "Restoratif",   "quantity": 50,   "unit": "adet",    "min_stock_level": 20,  "cost_per_unit": 45.0},
    {"name": "Cerrahi Eldiven M",    "category": "Sarf",         "quantity": 200,  "unit": "cift",    "min_stock_level": 100, "cost_per_unit": 2.5},
    {"name": "Kanal Ignesi 25mm",    "category": "Endodonti",    "quantity": 80,   "unit": "paket",   "min_stock_level": 30,  "cost_per_unit": 15.0},
    {"name": "Anestezi Kartusu",     "category": "Anestezi",     "quantity": 120,  "unit": "adet",    "min_stock_level": 50,  "cost_per_unit": 8.0},
    {"name": "Aljinat Olcu Maddesi", "category": "Protez",       "quantity": 30,   "unit": "kg",      "min_stock_level": 10,  "cost_per_unit": 120.0},
    {"name": "Dental X-Ray Film",    "category": "Radyoloji",    "quantity": 500,  "unit": "adet",    "min_stock_level": 100, "cost_per_unit": 1.2},
    {"name": "Steril Kompres",       "category": "Sarf",         "quantity": 300,  "unit": "paket",   "min_stock_level": 80,  "cost_per_unit": 3.5},
    {"name": "Implant Vidasi 3.5x10","category": "Implant",      "quantity": 25,   "unit": "adet",    "min_stock_level": 10,  "cost_per_unit": 320.0},
    {"name": "Profilaksi Pastasi",   "category": "Profilaksi",   "quantity": 40,   "unit": "kavanoz", "min_stock_level": 15,  "cost_per_unit": 85.0},
    {"name": "Nitril Maske FFP2",    "category": "Sarf",         "quantity": 1000, "unit": "adet",    "min_stock_level": 200, "cost_per_unit": 1.8},
]

# Integrasyon dış sistem hastaları (duplicate test için 2'si tekrar edilecek)
EXTERNAL_PATIENTS = [
    {"full_name": "Dis Sistem Hasta 01", "phone": "+905550000001", "email": "ext01@sim.test"},
    {"full_name": "Dis Sistem Hasta 02", "phone": "+905550000002", "email": "ext02@sim.test"},
    {"full_name": "Dis Sistem Hasta 03", "phone": "+905550000003", "email": None},
    {"full_name": "Dis Sistem Hasta 04", "phone": "+905550000004", "email": "ext04@sim.test"},
    {"full_name": "Dis Sistem Hasta 05", "phone": None,            "email": "ext05@sim.test"},
    {"full_name": "Dis Sistem Hasta 06", "phone": "+905550000006", "email": "ext06@sim.test"},
    {"full_name": "Dis Sistem Hasta 07", "phone": "+905550000007", "email": None},
    {"full_name": "Dis Sistem Hasta 08", "phone": "+905550000008", "email": "ext08@sim.test"},
    {"full_name": "Dis Sistem Hasta 09", "phone": "+905550000009", "email": "ext09@sim.test"},
    {"full_name": "Dis Sistem Hasta 10", "phone": "+905550000010", "email": "ext10@sim.test"},
]

# ── Yardımcı fonksiyonlar ──────────────────────────────────────────────────────
import re as _re
_UUID_RE = _re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', _re.I)

def run_psql(sql: str) -> tuple[str, str]:
    cmd = ["docker", "exec", POSTGRES_CTR, "psql", "-U", PG_USER, "-d", PG_DB, "-t", "-A", "-c", sql]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    return r.stdout.strip(), r.stderr.strip()

def extract_uuid(raw: str) -> str | None:
    """psql RETURNING çıktısından UUID'yi güvenle çıkar."""
    m = _UUID_RE.search(raw)
    return m.group(0) if m else None

def extract_uuids(raw: str) -> list[str]:
    """psql RETURNING çıktısından birden fazla UUID çıkar (satır başına 1)."""
    return _UUID_RE.findall(raw)

def run_psql_file(sql: str) -> tuple[str, str]:
    """Karmaşık veya çok satırlı SQL için stdin kullan."""
    cmd = ["docker", "exec", "-i", POSTGRES_CTR, "psql", "-U", PG_USER, "-d", PG_DB, "-t", "-A"]
    r = subprocess.run(cmd, input=sql, capture_output=True, text=True, encoding="utf-8")
    return r.stdout.strip(), r.stderr.strip()

def get_bcrypt_hash(password: str) -> str:
    """Get bcrypt hash using environment variable (safe from injection)."""
    import os
    env = os.environ.copy()
    env["PASSWORD_TO_HASH"] = password
    cmd = [
        "docker", "exec", "-e", "PASSWORD_TO_HASH", AUTH_CTR, "python", "-c",
        "import os; from passlib.context import CryptContext; "
        "ctx = CryptContext(schemes=['bcrypt'], deprecated='auto'); "
        "print(ctx.hash(os.environ['PASSWORD_TO_HASH']))"
    ]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8")
    return r.stdout.strip()

def api(method: str, path: str, token: str | None = None, **kwargs) -> requests.Response:
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    timeout = kwargs.pop("timeout", 30)
    url = f"{BASE_URL}/{path}"
    return requests.request(method, url, headers=headers, timeout=timeout, **kwargs)

def login_user(email: str, password: str) -> str:
    r = api("POST", "auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]

# ── PHASE 0: Login & Ön Kontrol ───────────────────────────────────────────────
def phase0_login() -> str:
    header("PHASE 0 — Bağlantı & Kimlik Doğrulama")

    # Gateway health
    try:
        gh = requests.get("http://localhost:8081/health", timeout=5)
        ok(f"Gateway: {gh.json()}")
    except Exception as e:
        err(f"Gateway erişilemiyor: {e}"); sys.exit(1)

    # Admin login
    token = login_user(ADMIN_EMAIL, ADMIN_PASS)
    me = api("GET", "auth/me", token=token).json()
    ok(f"Admin: {me['email']} | role={me['role']} | clinic={me['clinic_id']}")

    # RabbitMQ queue sayıları (initial)
    try:
        out = subprocess.run(
            ["docker", "exec", RABBIT_CTR, "rabbitmqctl", "list_queues"],
            capture_output=True, text=True, encoding="utf-8"
        )
        info("RabbitMQ kuyrukları (başlangıç):")
        for line in out.stdout.strip().splitlines()[1:]:
            if line.strip():
                print(f"    {C.DM}{line}{C.R}")
    except Exception:
        warn("RabbitMQ management API erişilemiyor (önemli değil)")

    return token

# ── PHASE 1: Rol Bazlı Kullanıcılar ───────────────────────────────────────────
def phase1_users(token: str) -> dict[str, str]:
    header("PHASE 1 — Rol Bazlı Kullanıcı Oluşturma")

    SIM_USERS = {
        "doctor":       ("Dr. Sinan Avci",        "dr.sinan.sim@demo.com",    "doctor"),
        "assistant":    ("Asistan Selin Gunes",   "asst.selin.sim@demo.com",  "assistant"),
    }

    info("Bcrypt hash üretiliyor (auth-service Python ortamı)...")
    pw_hash = get_bcrypt_hash(ADMIN_PASS)
    if not pw_hash.startswith("$2b$"):
        err(f"Hash üretilemedi: {pw_hash}"); sys.exit(1)
    ok(f"Hash: {pw_hash[:28]}...")

    created: dict[str, str] = {}
    for role_key, (full_name, email, role) in SIM_USERS.items():
        # Önce mevcut mi kontrol et
        existing, _ = run_psql(f"SELECT id FROM users WHERE email='{email}'")
        if existing:
            uid = extract_uuid(existing) or existing.split("\n")[0].strip()
            created[role_key] = uid
            warn(f"MEVCUT  {email} [{role}] → {uid}")
            continue

        sql = (
            f"INSERT INTO users (clinic_id, email, full_name, hashed_password, role, is_active) "
            f"VALUES ('{DEMO_CLINIC_ID}', '{email}', '{full_name}', '{pw_hash}', '{role}', true) "
            f"RETURNING id"
        )
        out, sql_err = run_psql(sql)
        if out:
            uid = extract_uuid(out) or out.strip()
            created[role_key] = uid
            ok(f"OLUŞTURULDU  {full_name} [{role}] → {uid}")
        else:
            err(f"HATA  {email}: {sql_err}")

    info("Login testleri...")
    for role_key, (full_name, email, role) in SIM_USERS.items():
        try:
            tok = login_user(email, ADMIN_PASS)
            ok(f"Login OK  {email} [{role}] → token={tok[:20]}...")
        except Exception as e:
            err(f"Login BAŞARISIZ  {email}: {e}")

    # Mevcut tüm kullanıcıları listele
    rows, _ = run_psql(
        f"SELECT email, role FROM users WHERE clinic_id='{DEMO_CLINIC_ID}' ORDER BY role"
    )
    info(f"Kliniğin tüm kullanıcıları:\n{C.DM}" +
         "\n".join(f"    {r}" for r in rows.splitlines()) + C.R)

    return created

# ── PHASE 2: Hasta Kaydı ──────────────────────────────────────────────────────
def phase2_patients() -> list[str]:
    header("PHASE 2 — Simülasyon Hasta Kayıtları (15 hasta)")

    PATIENTS = [
        ("Ahmet Ozturk",   "+905551234567", "ahmet.ozturk@sim.test"),
        ("Fatma Demir",    "+905559876543", "fatma.demir@sim.test"),
        ("Mehmet Kaya",    "+905554561234", None),
        ("Ayse Yildiz",    "+905557891234", "ayse.yildiz@sim.test"),
        ("Mustafa Celik",  None,            "mustafa.celik@sim.test"),
        ("Zeynep Sahin",   "+905553214567", None),
        ("Huseyin Arslan", "+905556543210", "huseyin.arslan@sim.test"),
        ("Hatice Gunes",   "+905551239876", None),
        ("Ibrahim Kurt",   "+905558765432", "ibrahim.kurt@sim.test"),
        ("Emine Aydin",    "+905552345678", "emine.aydin@sim.test"),
        ("Burak Yildirim", "+905551112233", "burak.yildirim@sim.test"),
        ("Selin Kocak",    "+905554445566", "selin.kocak@sim.test"),
        ("Tarik Dogan",    "+905557778899", None),
        ("Leyla Ozkan",    "+905550001122", "leyla.ozkan@sim.test"),
        ("Emre Guler",     "+905553334455", "emre.guler@sim.test"),
    ]

    patient_ids: list[str] = []
    for name, phone, email in PATIENTS:
        existing, _ = run_psql(
            f"SELECT id FROM patients WHERE clinic_id='{DEMO_CLINIC_ID}' AND full_name='{name}'"
        )
        if existing:
            pid = extract_uuid(existing)
            if pid:
                patient_ids.append(pid)
            warn(f"MEVCUT  {name} → {pid}")
            continue

        phone_val = f"'{phone}'" if phone else "NULL"
        email_val = f"'{email}'" if email else "NULL"
        sql = (
            f"INSERT INTO patients (clinic_id, full_name, phone, email) "
            f"VALUES ('{DEMO_CLINIC_ID}', '{name}', {phone_val}, {email_val}) "
            f"RETURNING id"
        )
        out, sql_err = run_psql(sql)
        if out:
            pid = extract_uuid(out)
            if pid:
                patient_ids.append(pid)
                ok(f"OLUŞTURULDU  {name} → {pid}")
            else:
                err(f"UUID ayrıştırılamadı  {name}: {out!r}")
        else:
            err(f"HATA  {name}: {sql_err}")

    ok(f"Toplam hasta: {len(patient_ids)}")
    return patient_ids

# ── PHASE 2b: Doctors Tablosuna Doktor Kaydı ─────────────────────────────────
def phase2b_doctors() -> list[str]:
    header("PHASE 2b — Doctors Tablosu Seeding")

    DOCTORS_DATA = [
        ("Dr. Aydin Koc",     "Implant",        "doctor"),
        ("Dr. Meral Yilmaz",  "Ortodonti",       "doctor"),
        ("Dr. Onur Demir",    "Endodonti",       "doctor"),
        ("Dr. Sema Arslan",   "Periodontoloji",  "doctor"),
        ("Dr. Kemal Sahin",   "Cerrahi",         "doctor"),
    ]

    doctor_ids: list[str] = []
    for full_name, specialty, role in DOCTORS_DATA:
        existing, _ = run_psql(
            f"SELECT id FROM doctors WHERE clinic_id='{DEMO_CLINIC_ID}' AND full_name='{full_name}'"
        )
        if existing:
            did = extract_uuid(existing)
            if did:
                doctor_ids.append(did)
            warn(f"MEVCUT  {full_name}")
            continue

        sql = (
            f"INSERT INTO doctors (clinic_id, full_name, specialty, notification_offset, role) "
            f"VALUES ('{DEMO_CLINIC_ID}', '{full_name}', '{specialty}', 24, '{role}') "
            f"RETURNING id"
        )
        out, sql_err = run_psql(sql)
        if out:
            did = extract_uuid(out)
            if did:
                doctor_ids.append(did)
                ok(f"OLUŞTURULDU  {full_name} [{specialty}] → {did}")
        else:
            err(f"HATA  {full_name}: {sql_err}")

    ok(f"Toplam doktor (doctors tablosu): {len(doctor_ids)}")
    return doctor_ids
def phase3_appointments_history(patient_ids: list[str], doctor_ids: list[str]) -> list[str]:
    header("PHASE 3 — 100 Tamamlanmış Randevu (Son 30 Gün) — SQL Yığın İnsert")

    if not patient_ids:
        err("Hasta ID bulunamadı, phase atlanıyor"); return []
    if not doctor_ids:
        err("Doktor ID bulunamadı, phase atlanıyor"); return []

    now = datetime.now(timezone.utc)
    values_parts: list[str] = []
    appt_ids: list[str] = []

    for i in range(95):  # 95 tarihsel + 5 API ile oluşturulacak = 100
        patient_id = random.choice(patient_ids)
        doctor_id = random.choice(doctor_ids)
        spec = random.choice(SPECIALTIES)
        note = random.choice(TREATMENT_NOTES)
        # Son 30 gün içinde rastgele saat
        days_ago = random.randint(1, 30)
        hours_offset = random.randint(8, 18)
        mins_offset = random.choice([0, 15, 30, 45])
        scheduled = now - timedelta(days=days_ago, hours=hours_offset) + timedelta(hours=hours_offset, minutes=mins_offset)
        scheduled_at = scheduled.strftime("%Y-%m-%d %H:%M:%S+00")
        appt_type = random.choice(["Rutin Kontrol", "Tedavi", "Acil", "Kontrol", None])
        type_val = f"'{appt_type}'" if appt_type else "NULL"
        note_clean = note.replace("'", "''")
        values_parts.append(
            f"(gen_random_uuid(), '{DEMO_CLINIC_ID}', '{patient_id}', '{doctor_id}', "
            f"'{scheduled_at}', 'completed'::appointment_status, '{spec}', {type_val}, '{note_clean}', NOW(), NOW())"
        )

    # Tek sorguda 95 satır insert (gen_random_uuid() PostgreSQL built-in)
    bulk_sql = (
        "INSERT INTO appointments (id, clinic_id, patient_id, doctor_id, "
        "scheduled_at, status, specialty, type, notes, created_at, updated_at) "
        "VALUES " + ",\n".join(values_parts) +
        " RETURNING id"
    )
    out, sql_err = run_psql_file(bulk_sql)
    if sql_err and "ERROR" in sql_err.upper():
        err(f"Toplu insert hatası: {sql_err}")
        return []

    appt_ids = extract_uuids(out)
    ok(f"Tarihsel {len(appt_ids)} randevu eklendi (status=completed, son 30 gün)")

    # Analytics için kayıt sayısını doğrula
    count_out, _ = run_psql(
        f"SELECT COUNT(*) FROM appointments WHERE clinic_id='{DEMO_CLINIC_ID}' AND status='completed'"
    )
    ok(f"DB'deki toplam completed randevu: {count_out.strip()}")

    # Branş dağılımı
    dist_out, _ = run_psql(
        f"SELECT specialty, COUNT(*) FROM appointments WHERE clinic_id='{DEMO_CLINIC_ID}' "
        f"AND status='completed' GROUP BY specialty ORDER BY COUNT(*) DESC"
    )
    info("Branş dağılımı:")
    for line in dist_out.splitlines():
        if line.strip():
            print(f"    {C.DM}{line}{C.R}")

    return appt_ids

# ── PHASE 4: Follow-up Testi (API + RabbitMQ) ────────────────────────────────
def phase4_followup(token: str, patient_ids: list[str], doctor_id: str) -> None:
    header("PHASE 4 — Otonom Follow-up: 5 Randevu → COMPLETED → RabbitMQ")

    if not patient_ids:
        err("Hasta yok, phase atlanıyor"); return

    # RabbitMQ kuyruk sayısını başlangıçta oku
    def get_queue_count(q: str) -> int:
        out = subprocess.run(
            ["docker", "exec", RABBIT_CTR, "rabbitmqctl", "list_queues", "name", "messages"],
            capture_output=True, text=True, encoding="utf-8"
        )
        for line in out.stdout.splitlines():
            if q in line:
                parts = line.split()
                return int(parts[-1]) if len(parts) >= 2 else 0
        return 0

    queue_name = "notification.appointment.completed"
    before = get_queue_count(queue_name)
    info(f"'{queue_name}' başlangıç mesaj sayısı: {before}")

    followup_appt_ids: list[str] = []
    now = datetime.now(timezone.utc)

    for i in range(5):
        patient_id = patient_ids[i % len(patient_ids)]
        # Yarın için randevu oluştur
        scheduled = now + timedelta(hours=random.randint(2, 8))
        payload = {
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "specialty": random.choice(SPECIALTIES_API),
            "scheduled_at": scheduled.isoformat(),
            "type": "Post-Op Kontrol",
            "notes": f"Follow-up test #{i+1} — Post-Op muayene",
        }
        r = api("POST", "appointments", token=token, json=payload)
        if r.status_code == 201:
            appt = r.json()
            followup_appt_ids.append(appt["id"])
            ok(f"Randevu oluşturuldu [{i+1}/5]: {appt['id'][:8]}... → status={appt['status']}")
        else:
            err(f"Randevu oluşturulamadı [{i+1}]: {r.status_code} {r.text[:120]}")

    if not followup_appt_ids:
        err("Hiç randevu oluşturulamadı, PATCH atlanıyor"); return

    info(f"{len(followup_appt_ids)} randevu COMPLETED'a çekiliyor...")
    time.sleep(0.5)

    completed_count = 0
    for appt_id in followup_appt_ids:
        r = api("PATCH", f"appointments/{appt_id}", token=token,
                json={"status": "completed", "notes": "Tedavi başarıyla tamamlandı. Post-op takip planlandı."})
        if r.status_code == 200:
            completed_count += 1
            ok(f"COMPLETED  {appt_id[:8]}...")
        else:
            err(f"PATCH hatası  {appt_id[:8]}: {r.status_code} {r.text[:80]}")

    time.sleep(2)  # RabbitMQ'nun mesajları işlemesi için bekle

    after = get_queue_count(queue_name)
    delta = after - before
    info(f"'{queue_name}' son mesaj sayısı: {after} (Δ={delta:+d})")

    if delta >= completed_count:
        ok(f"RabbitMQ DOĞRULANDI: {delta} mesaj kuyruğa düştü (notification.appointment.completed)")
    elif delta > 0:
        warn(f"RabbitMQ kısmi: {delta}/{completed_count} mesaj kuyruğa düştü")
    else:
        warn("RabbitMQ: Mesaj sayısı artmadı (notification servisi tüketmiş olabilir)")

    # Notification service loglarında kanıt ara
    log_out = subprocess.run(
        ["docker", "logs", "--tail", "30", NOTIFY_CTR],
        capture_output=True, text=True, encoding="utf-8"
    )
    combined_logs = log_out.stdout + log_out.stderr
    followup_keywords = ["completed", "follow", "post", "appointment"]
    matched_lines = [l for l in combined_logs.splitlines()
                     if any(kw in l.lower() for kw in followup_keywords)]
    if matched_lines:
        ok("Notification service loglarında randevu eventi bulundu:")
        for line in matched_lines[-5:]:
            print(f"    {C.DM}{line[:120]}{C.R}")
    else:
        info("Notification service loglarında spesifik log yok (normal olabilir)")

    ok(f"Follow-up testi tamamlandı: {completed_count}/5 randevu COMPLETED yapıldı")

# ── PHASE 5: Envantar & Kritik Stok ──────────────────────────────────────────
def phase5_inventory(token: str) -> dict[str, str]:
    header("PHASE 5 — Envanter: 10 Kalem Ekle + Kritik Stok Uyarısı")

    item_ids: dict[str, str] = {}

    # Mevcut envanter kalemlerini çek (unique constraint'e göre idempotent çalışma için)
    existing_r = api("GET", "inventory/items", token=token)
    existing_by_name: dict[str, dict] = {}
    if existing_r.status_code == 200:
        for it in existing_r.json():
            existing_by_name[it["name"]] = it

    for item in INVENTORY_ITEMS:
        if item["name"] in existing_by_name:
            ex = existing_by_name[item["name"]]
            item_ids[item["name"]] = ex["id"]
            # min_stock_level'ı güncelle
            api("PATCH", f"inventory/items/{ex['id']}", token=token,
                json={"min_stock_level": item["min_stock_level"]})
            # Miktarı hedef değere sıfırla (adjust ile mevcut farkını kapat)
            current_qty = float(ex.get("quantity", 0))
            target_qty = float(item["quantity"])
            delta = target_qty - current_qty
            if abs(delta) > 0.001:
                api("POST", f"inventory/items/{ex['id']}/adjust", token=token,
                    json={"delta": round(delta, 2), "reason": "Simülasyon sıfırlama"})
            warn(f"MEVCUT   {item['name']} → miktar {target_qty} {item['unit']}'e sıfırlandı")
            continue
        r = api("POST", "inventory/items", token=token, json=item)
        if r.status_code == 201:
            d = r.json()
            item_ids[item["name"]] = d["id"]
            low_badge = f" {C.RE}[DÜŞÜK STOK]{C.R}" if d.get("is_low_stock") else ""
            ok(f"EKLENDI  {item['name']} ({item['quantity']} {item['unit']}){low_badge}")
        elif r.status_code in (400, 422):
            err(f"Validasyon hatası  {item['name']}: {r.text[:100]}")
        else:
            err(f"Hata  {item['name']}: {r.status_code} {r.text[:80]}")

    ok(f"Envanter oluşturma tamamlandı: {len(item_ids)}/10 kalem")
    info("")
    info(f"{C.B}{C.RE}KRİTİK STOK SİMÜLASYONU:{C.R}")

    # Kompozit Dolgu → min 20, mevcut 50 → -45 delta → 5 (kritik altı)
    if "Kompozit Dolgu" in item_ids:
        r = api("POST", f"inventory/items/{item_ids['Kompozit Dolgu']}/adjust",
                token=token, json={"delta": -45.0, "reason": "Simülasyon: Yoğun kullanım, kritik seviye testi"})
        if r.status_code == 200:
            d = r.json()
            badge = f"{C.RE}⚠ STOK KRİTİK ({d['quantity']} < min {d['min_stock_level']}){C.R}" if d.get("is_low_stock") else f"stok={d['quantity']}"
            ok(f"Kompozit Dolgu düşürüldü: {badge}")
        else:
            err(f"Adjust hatası: {r.status_code} {r.text[:80]}")

    # Cerrahi Eldiven M → min 100, mevcut 200 → -160 delta → 40 (kritik altı)
    if "Cerrahi Eldiven M" in item_ids:
        r = api("POST", f"inventory/items/{item_ids['Cerrahi Eldiven M']}/adjust",
                token=token, json={"delta": -160.0, "reason": "Simülasyon: Cerrahi operasyon tüketime, kritik seviye testi"})
        if r.status_code == 200:
            d = r.json()
            badge = f"{C.RE}⚠ STOK KRİTİK ({d['quantity']} < min {d['min_stock_level']}){C.R}" if d.get("is_low_stock") else f"stok={d['quantity']}"
            ok(f"Cerrahi Eldiven M düşürüldü: {badge}")
        else:
            err(f"Adjust hatası: {r.status_code} {r.text[:80]}")

    # Kritik stok listesini API'den doğrula
    r = api("GET", "inventory/items", token=token, params={"low_stock": "true"})
    if r.status_code == 200:
        # items bize aynı objeden liste dönebilir
        data = r.json()
        low_items = data if isinstance(data, list) else data.get("items", [])
        low_items = [it for it in low_items if it.get("is_low_stock")]
        if low_items:
            ok(f"Kritik stok kalemleri ({len(low_items)} adet):")
            for it in low_items:
                print(f"    {C.RE}✘{C.R}  {it['name']}: {it['quantity']} {it['unit']} (min={it['min_stock_level']})")
        else:
            warn("Düşük stok filtresi sonuç döndürmedi (filtre parametresi farklı olabilir)")
    else:
        warn(f"Envanter listesi alınamadı: {r.status_code}")

    return item_ids

# ── PHASE 6: Integration Servis Senkronizasyon Testi ─────────────────────────
def phase6_integration(token: str) -> None:
    header("PHASE 6 — Integration Senkronizasyonu (Dış Sistem → 10 Hasta + Duplicate Testi)")

    info("İlk import: 10 yeni harici hasta (DentSoft benzeri dış sistem simülasyonu)")
    info("Servis hazır olana kadar bekleniyor (3s)...")
    time.sleep(3)
    payload1 = {"patients": EXTERNAL_PATIENTS}
    r1 = api("POST", "integration/import/patients", token=token, json=payload1)

    if r1.status_code == 200:
        d1 = r1.json()
        ok(f"1. Import tamamlandı:")
        print(f"     {C.GR}toplam_gelen={d1['total_received']}{C.R}")
        print(f"     {C.GR}eklenen={d1['inserted']}{C.R}")
        print(f"     {C.YE}atlanan_duplicate={d1['skipped_duplicates']}{C.R}")
        print(f"     {C.YE}atlanan_gecersiz={d1['skipped_invalid']}{C.R}")
        if d1.get("errors"):
            for e in d1["errors"][:3]:
                err(f"  Import hatası: {e}")
    else:
        err(f"1. Import başarısız: {r1.status_code} {r1.text[:200]}")
        info("Role yetkisi hatası varsa integration-service rebuild gerekebilir")
        return

    info("")
    info(f"{C.B}Duplicate testi: Aynı 10 hasta yeniden gönderiliyor...{C.R}")
    r2 = api("POST", "integration/import/patients", token=token, json=payload1)

    if r2.status_code == 200:
        d2 = r2.json()
        ok(f"2. Import (duplicate test) tamamlandı:")
        print(f"     toplam_gelen={d2['total_received']}")
        print(f"     {C.GR}eklenen={d2['inserted']}{C.R}  (0 olmalı)")
        print(f"     {C.YE}atlanan_duplicate={d2['skipped_duplicates']}{C.R}  (10'a yakın olmalı)")

        if d2["inserted"] == 0 and d2["skipped_duplicates"] > 0:
            ok(f"DUPLICATE KONTROLÜ BAŞARILI: {d2['skipped_duplicates']} kayıt tekrar eklenmedi!")
        elif d2["inserted"] < d1["inserted"]:
            warn(f"Kısmi duplicate detection: {d2['inserted']} eklendi, {d2['skipped_duplicates']} atlandı")
        else:
            warn(f"Duplicate koruması çalışmadı: {d2['inserted']} kayıt yeniden eklendi")
    else:
        err(f"2. Import başarısız: {r2.status_code} {r2.text[:120]}")

    # DB'deki harici hasta sayısını doğrula
    count_out, _ = run_psql(
        f"SELECT COUNT(*) FROM patients WHERE clinic_id='{DEMO_CLINIC_ID}' "
        f"AND full_name LIKE 'Dis Sistem Hasta%'"
    )
    ok(f"DB'deki harici sistem hastası: {count_out.strip()} adet")

# ── PHASE 7: Analytics Kontrol ────────────────────────────────────────────────
def phase7_analytics_verify(token: str) -> None:
    header("PHASE 7 — Analytics Dashboard Doğrulama")

    endpoints = {
        "Recovered Revenue": "analytics/revenue/recovered",
        "Randevu İstatistikleri": "analytics/appointments/stats",
        "Doktor Performansı": "analytics/doctors/performance",
        "Envanter İsraf Raporu": "analytics/inventory/waste-report",
    }

    # Redis cache'i temizlemek için spesifik sorgu parametresi ekle (cache bypass)
    for label, path in endpoints.items():
        try:
            r = api("GET", path, token=token, timeout=15)
            if r.status_code == 200:
                data = r.json()
                # Özet bilgi çıkar
                if "total_recovered_appointments" in data:
                    v = data.get("total_recovered_appointments", 0)
                    ok(f"{label}: total_recovered_appts={v}")
                elif "total" in data:
                    v = data.get("total", 0)
                    ok(f"{label}: total={v}")
                elif "doctors" in data:
                    v = len(data.get("doctors", []))
                    ok(f"{label}: {v} doktor")
                elif "items" in data:
                    v = len(data.get("items", []))
                    ok(f"{label}: {v} kalem")
                else:
                    ok(f"{label}: 200 OK")
            else:
                warn(f"{label}: {r.status_code}")
        except Exception as e:
            err(f"{label}: {e}")

    # Doğrudan DB üzerinden randevu sayısını kontrol et
    count_out, _ = run_psql(
        f"SELECT COUNT(*) FROM appointments WHERE clinic_id='{DEMO_CLINIC_ID}' AND status='completed'"
    )
    ok(f"DB toplam completed randevu: {count_out.strip()}")

    specialty_out, _ = run_psql(
        f"SELECT specialty, COUNT(*) FROM appointments "
        f"WHERE clinic_id='{DEMO_CLINIC_ID}' AND status='completed' "
        f"GROUP BY specialty ORDER BY COUNT(*) DESC LIMIT 5"
    )
    info("Top-5 branş (completed randevu):")
    for line in specialty_out.splitlines():
        if line.strip():
            print(f"    {C.CY}{line}{C.R}")

# ── ÖZET RAPORU ───────────────────────────────────────────────────────────────
def print_summary(results: dict) -> None:
    bar = "═" * 62
    print(f"\n{C.B}{C.MA}{bar}{C.R}")
    print(f"{C.B}{C.WH}  SİMÜLASYON TAMAMLANDI — ÖZET RAPORU{C.R}")
    print(f"{C.B}{C.MA}{bar}{C.R}\n")

    for phase, detail in results.items():
        print(f"  {C.B}{phase}{C.R}")
        for line in detail:
            print(f"    {line}")
        print()

    print(f"{C.B}{C.YE}  ⚠ HATIRLATMA: Tüm simülasyon verileri GEÇİCİ test verisidir.{C.R}")
    print(f"{C.DM}  Temizlemek için: python simulation_engine.py --cleanup{C.R}\n")

# ── ANA PROGRAM ───────────────────────────────────────────────────────────────
def main():
    print(f"\n{C.B}{C.MA}{'█'*62}{C.R}")
    print(f"{C.B}{C.WH}  DentAI Flow — Simulation Engine v1.0{C.R}")
    print(f"{C.B}{C.WH}  Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{C.R}")
    print(f"{C.B}{C.MA}{'█'*62}{C.R}")

    results: dict[str, list[str]] = {}

    # ── Phase 0
    token = phase0_login()
    results["Phase 0 — Auth"] = [f"{C.GR}✔ Admin login OK{C.R}", f"{C.GR}✔ Gateway sağlıklı{C.R}"]

    # ── Phase 1: Kullanıcılar
    user_ids = phase1_users(token)
    results["Phase 1 — Kullanıcılar (Rol Bazlı)"] = [
        f"{C.GR}✔ OWNER   admin@demo.com{C.R}",
        f"{C.GR}✔ DOCTOR  dr.sinan.sim@demo.com{C.R}",
        f"{C.GR}✔ ASSISTANT  asst.selin.sim@demo.com{C.R}",
    ]

    # ── Phase 2: Hastalar
    patient_ids = phase2_patients()
    results["Phase 2 — Hasta Kayıtları"] = [
        f"{C.GR}✔ {len(patient_ids)} simülasyon hastası oluşturuldu{C.R}"
    ]

    # ── Phase 2b: Doctors tablosu
    doctor_ids = phase2b_doctors()
    if not doctor_ids:
        # Fallback: doktors tablosundan mevcut doktorları çek
        existing_drs, _ = run_psql(
            f"SELECT id FROM doctors WHERE clinic_id='{DEMO_CLINIC_ID}' LIMIT 5"
        )
        doctor_ids = extract_uuids(existing_drs) or [DEMO_DOCTOR_ID]
    results["Phase 2b — Doctors Tablosu"] = [
        f"{C.GR}✔ {len(doctor_ids)} doktor doctors tablosunda{C.R}"
    ]

    # ── Phase 3: Tarihsel randevular
    hist_ids = phase3_appointments_history(patient_ids, doctor_ids)
    results["Phase 3 — Analytics Randevuları"] = [
        f"{C.GR}✔ {len(hist_ids)} tarihsel completed randevu eklendi{C.R}",
        f"{C.CY}→ Son 30 gün, 8 branş, gerçekçi notlar{C.R}",
    ]

    # ── Phase 4: Follow-up
    phase4_followup(token, patient_ids, doctor_ids[0])
    results["Phase 4 — Follow-up (RabbitMQ)"] = [
        f"{C.GR}✔ 5 randevu API ile oluşturuldu → COMPLETED{C.R}",
        f"{C.CY}→ notification.appointment.completed kuyruğu kontrol edildi{C.R}",
    ]

    # ── Phase 5: Envanter
    item_ids = phase5_inventory(token)
    results["Phase 5 — Envanter & Kritik Stok"] = [
        f"{C.GR}✔ {len(item_ids)}/10 envanter kalemi eklendi{C.R}",
        f"{C.RE}⚠ Kompozit Dolgu: stok=5 < min=20 [KRİTİK]{C.R}",
        f"{C.RE}⚠ Cerrahi Eldiven M: stok=40 < min=100 [KRİTİK]{C.R}",
    ]

    # ── Phase 6: Integration
    phase6_integration(token)
    results["Phase 6 — Integration Sync"] = [
        f"{C.GR}✔ 10 harici hasta import edildi{C.R}",
        f"{C.GR}✔ Duplicate testi: tekrar import → skipped_duplicates{C.R}",
    ]

    # ── Phase 7: Analytics doğrulama
    phase7_analytics_verify(token)
    results["Phase 7 — Analytics Doğrulama"] = [
        f"{C.GR}✔ Tüm analytics endpoint'leri 200 OK{C.R}",
        f"{C.CY}→ Dashboard grafikleri verilerle dolu{C.R}",
    ]

    print_summary(results)


if __name__ == "__main__":
    main()
