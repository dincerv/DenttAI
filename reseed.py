#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DentAI Flow — Simulation Re-Seed v2.0
=======================================
DB'yi komple temizler ve Dt. Burak, Dt. Şule, Dt. Şükrü
+ 2 asistan + super_admin ile yeniden doldurur.

Çalıştırmak için:
  python reseed.py

UYARI: clinics tablosu HARİÇ tüm veriler silinir!
"""
import random
import subprocess
import sys
import re as _re
from datetime import datetime, timedelta, timezone

try:
    import requests
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "requests", "-q"], check=True)
    import requests  # type: ignore


# ── Terminal renkleri ─────────────────────────────────────────────────────────
class C:
    R  = "\033[0m"; B  = "\033[1m"; GR = "\033[92m"
    YE = "\033[93m"; RE = "\033[91m"; CY = "\033[96m"
    BL = "\033[94m"; WH = "\033[97m"; DM = "\033[2m"

def ok(m):   print(f"  {C.GR}✔{C.R}  {m}")
def warn(m): print(f"  {C.YE}⚠{C.R}  {m}")
def err(m):  print(f"  {C.RE}✘{C.R}  {m}")
def info(m): print(f"  {C.CY}→{C.R}  {m}")
def header(t):
    print(f"\n{C.B}{C.BL}{'═'*62}{C.R}\n{C.B}{C.WH}  {t}{C.R}\n{C.B}{C.BL}{'═'*62}{C.R}")

# ── Sabit değerler ────────────────────────────────────────────────────────────
BASE_URL       = "http://localhost:8081/api"
POSTGRES_CTR   = "dentai_postgres"
AUTH_CTR       = "dentai_auth"
PG_USER        = "dentai"
PG_DB          = "dentai_db"
DEMO_CLINIC_ID = "d0be60eb-5d3e-43b6-960e-77014f59397a"

OWNER_EMAIL = "admin@demo.com"
OWNER_PASS  = "Admin1234"

_UUID_RE = _re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', _re.I)

# ── Psql yardımcıları ─────────────────────────────────────────────────────────
def run_psql(sql: str) -> tuple[str, str]:
    cmd = ["docker", "exec", POSTGRES_CTR, "psql", "-U", PG_USER, "-d", PG_DB, "-t", "-A", "-c", sql]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    return r.stdout.strip(), r.stderr.strip()

def run_psql_file(sql: str) -> tuple[str, str]:
    cmd = ["docker", "exec", "-i", POSTGRES_CTR, "psql", "-U", PG_USER, "-d", PG_DB, "-t", "-A"]
    r = subprocess.run(cmd, input=sql, capture_output=True, text=True, encoding="utf-8")
    return r.stdout.strip(), r.stderr.strip()

def extract_uuid(raw: str) -> str | None:
    m = _UUID_RE.search(raw); return m.group(0) if m else None

def extract_uuids(raw: str) -> list[str]:
    return _UUID_RE.findall(raw)

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
    if token: headers["Authorization"] = f"Bearer {token}"
    return requests.request(method, f"{BASE_URL}/{path}", headers=headers, timeout=30, **kwargs)

def login_user(email: str, password: str) -> str:
    r = api("POST", "auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


# ── PHASE 0: Temizleme ────────────────────────────────────────────────────────
def phase0_truncate():
    header("PHASE 0 — Veritabanı Temizleme")
    warn("Tüm randevu, hasta, doktor, kullanıcı ve envanter verileri siliniyor...")

    # clinics dışındaki her şeyi temizle (TRUNCATE CASCADE)
    tables = [
        "appointments",
        "waitlist_entries",
        "inventory_cycle_materials",
        "inventory_cycles",
        "inventory_qr_links",
        "inventory_items",
        "patients",
        "doctors",
        "refresh_tokens",
        "users",
    ]
    for t in tables:
        out, sql_err = run_psql(f"TRUNCATE TABLE {t} CASCADE;")
        if "ERROR" in (sql_err or "").upper():
            warn(f"  {t}: {sql_err}")
        else:
            ok(f"  TRUNCATE {t}")

    ok("Temizleme tamamlandı — clinics tablosu korundu")


# ── PHASE 1: Kullanıcı ve Doktor Oluşturma ────────────────────────────────────
def phase1_users_and_doctors(pw_hash: str) -> dict[str, str]:
    """
    Döndürür: {"owner": user_id, "burak": doctor_id, "sule": doctor_id, ...}
    """
    header("PHASE 1 — Kullanıcılar & Doktorlar")

    USERS = [
        # (full_name, email, role)
        ("Admin Kullanici",    OWNER_EMAIL,          "owner"),
        ("Dt. Burak Ozcelik",  "burak@demo.com",     "doctor"),
        ("Dt. Sule Yilmaz",    "sule@demo.com",      "doctor"),
        ("Dt. Sukru Arslan",   "sukru@demo.com",     "doctor"),
        ("Asistan Elif Kaya",  "asistan1@demo.com",  "assistant"),
        ("Asistan Can Demir",  "asistan2@demo.com",  "assistant"),
        # super_admin — demo klinikle ilişkili değil ama bir clinic_id lazım
        ("Super Admin",        "superadmin@dentai.io", "super_admin"),
    ]

    SPECIALTIES = {
        "burak@demo.com":  "Implant",
        "sule@demo.com":   "Ortodonti",
        "sukru@demo.com":  "Endodonti",
    }

    user_ids: dict[str, str] = {}
    doctor_ids: dict[str, str] = {}   # email -> doctor_id

    for full_name, email, role in USERS:
        sql = (
            f"INSERT INTO users (clinic_id, email, full_name, hashed_password, role, is_active) "
            f"VALUES ('{DEMO_CLINIC_ID}', '{email}', '{full_name}', '{pw_hash}', '{role}', true) "
            f"RETURNING id"
        )
        out, sql_err = run_psql(sql)
        uid = extract_uuid(out)
        if uid:
            user_ids[email] = uid
            ok(f"  USER  {full_name} [{role}] → {uid}")
        else:
            err(f"  HATA  {email}: {sql_err}")

    # Doctors tablosu — her hekim için kayıt + user_id bağlantısı
    DOCTOR_USERS = [
        ("burak@demo.com",  "Dt. Burak Ozcelik", "Implant"),
        ("sule@demo.com",   "Dt. Sule Yilmaz",   "Ortodonti"),
        ("sukru@demo.com",  "Dt. Sukru Arslan",  "Endodonti"),
    ]

    for email, full_name, specialty in DOCTOR_USERS:
        uid = user_ids.get(email)
        if not uid:
            warn(f"  Kullanıcı bulunamadı, doktor kaydı atlanıyor: {email}")
            continue
        sql = (
            f"INSERT INTO doctors (clinic_id, full_name, specialty, notification_offset, role, user_id) "
            f"VALUES ('{DEMO_CLINIC_ID}', '{full_name}', '{specialty}', 24, 'doctor', '{uid}') "
            f"RETURNING id"
        )
        out, sql_err = run_psql(sql)
        did = extract_uuid(out)
        if did:
            doctor_ids[email] = did
            ok(f"  DOCTOR  {full_name} [{specialty}] → {did}")
        else:
            err(f"  HATA doctors  {email}: {sql_err}")

    # Login testleri
    info("Login testleri...")
    for full_name, email, role in USERS:
        try:
            tok = login_user(email, OWNER_PASS)
            ok(f"  Login OK  {email}")
        except Exception as e:
            err(f"  Login BAŞARISIZ  {email}: {e}")

    return {
        "owner_id":     user_ids.get(OWNER_EMAIL, ""),
        "burak_did":    doctor_ids.get("burak@demo.com", ""),
        "sule_did":     doctor_ids.get("sule@demo.com", ""),
        "sukru_did":    doctor_ids.get("sukru@demo.com", ""),
    }


# ── PHASE 2: Hastalar ─────────────────────────────────────────────────────────
def phase2_patients() -> list[str]:
    header("PHASE 2 — 15 Hasta")

    PATIENTS = [
        ("Ahmet Ozturk",     "+905551234567",  "ahmet@sim.test"),
        ("Fatma Demir",      "+905559876543",  "fatma@sim.test"),
        ("Mehmet Kaya",      "+905554561234",  None),
        ("Ayse Yildiz",      "+905557891234",  "ayse@sim.test"),
        ("Mustafa Celik",    None,             "mustafa@sim.test"),
        ("Zeynep Sahin",     "+905553214567",  None),
        ("Huseyin Arslan",   "+905556543210",  "huseyin@sim.test"),
        ("Hatice Gunes",     "+905551239876",  None),
        ("Ibrahim Kurt",     "+905558765432",  "ibrahim@sim.test"),
        ("Emine Aydin",      "+905552345678",  "emine@sim.test"),
        ("Burak Yildirim",   "+905551112233",  "byllmz@sim.test"),
        ("Selin Kocak",      "+905554445566",  "selin@sim.test"),
        ("Tarik Dogan",      "+905557778899",  None),
        ("Leyla Ozkan",      "+905550001122",  "leyla@sim.test"),
        ("Emre Guler",       "+905553334455",  "emre@sim.test"),
    ]

    ids: list[str] = []
    bulk_vals = []
    for name, phone, email in PATIENTS:
        phone_val = f"'{phone}'" if phone else "NULL"
        email_val = f"'{email}'" if email else "NULL"
        bulk_vals.append(
            f"(gen_random_uuid(), '{DEMO_CLINIC_ID}', '{name}', {phone_val}, {email_val})"
        )

    sql = (
        "INSERT INTO patients (id, clinic_id, full_name, phone, email) VALUES "
        + ",\n".join(bulk_vals) + " RETURNING id"
    )
    out, sql_err = run_psql_file(sql)
    if "ERROR" in (sql_err or "").upper():
        err(f"Hasta insert hatası: {sql_err}")
    else:
        ids = extract_uuids(out)
        ok(f"  {len(ids)} hasta oluşturuldu")
    return ids


# ── PHASE 3: Randevular ────────────────────────────────────────────────────────
def phase3_appointments(patient_ids: list[str], doctor_map: dict[str, str]) -> None:
    header("PHASE 3 — Randevular (25-30 adet / hekim)")

    TREATMENT_NOTES = [
        "2 Dolgu yapildi, ust cene sag ceyrek.",
        "1 Kanal Tedavisi - #46 dis, 3 kanal, devital pulpa.",
        "4 Implant: #14,#15,#24,#25 - sinus lifting uygulandi.",
        "Kompozit dolgu: #16 MOD, #17 DO - tek seans.",
        "Seramik kron: #11,#21 - estetik zon.",
        "Implant cerrahisi - #36: 4.1x10 vida.",
        "Periodontal tedavi skaler + kuretle debridman.",
        "Gomuk 20 yas cekimi: alt sol, osteotomi yapildi.",
        "Protez olcusu: ust tam protez, balmumu deneme.",
        "Ortodonti plak yerlestirildi, hijyen egitimi.",
        "3 Dolgu: #17 O, #27 MO, #37 DO - kompozit.",
        "Kanal Tedavisi + gecici kuron - #47.",
        "Pedodon: sut dis cekimi, lokal anestezi.",
        "Dis beyazlatma uygulama - 2/3 seans.",
        "Tel karistirma + ark tel degisimi.",
        "Gingivektomi sol alt kadran.",
        "Zirkonyum kuron: #11,#12,#21,#22 - renk A2.",
        "Implant protezi ust yapi - vida torklama 35 Ncm.",
        "Akut apse drenaji + antibiyotik.",
        "Dis tasi temizligi full mouth debridman.",
    ]
    SPECIALTIES = [
        "Ortodonti", "Implant", "Endodonti", "Periodontoloji",
        "Protez", "Cerrahi", "Pedodonti", "Genel Dis",
    ]

    now = datetime.now(timezone.utc)
    doctor_emails = {
        "burak_did":  "burak@demo.com",
        "sule_did":   "sule@demo.com",
        "sukru_did":  "sukru@demo.com",
    }

    all_values: list[str] = []
    for key, email in doctor_emails.items():
        doctor_id = doctor_map.get(key)
        if not doctor_id:
            warn(f"  {email} için doktor ID bulunamadı, atlanıyor")
            continue

        n_appts = random.randint(25, 30)
        for _ in range(n_appts):
            patient_id = random.choice(patient_ids)
            spec       = random.choice(SPECIALTIES)
            note       = random.choice(TREATMENT_NOTES).replace("'", "''")

            # Zaman dağılımı: bugün + geçen hafta + geçen ay + yaklaşan
            bucket = random.choices(
                ["today", "last_week", "last_month", "upcoming"],
                weights=[10, 35, 40, 15]
            )[0]
            if bucket == "today":
                days_ago = 0
                h = random.randint(9, 17)
                d = now.replace(hour=h, minute=random.choice([0, 15, 30, 45]), second=0, microsecond=0)
                status_ = random.choice(["completed", "completed", "scheduled"])
            elif bucket == "last_week":
                days_ago = random.randint(1, 7)
                h = random.randint(9, 17)
                d = now - timedelta(days=days_ago) + timedelta(hours=h - now.hour)
                status_ = "completed"
            elif bucket == "last_month":
                days_ago = random.randint(8, 30)
                h = random.randint(9, 17)
                d = now - timedelta(days=days_ago) + timedelta(hours=h - now.hour)
                status_ = random.choice(["completed", "completed", "cancelled", "no_show"])
            else:  # upcoming
                days_ahead = random.randint(1, 14)
                h = random.randint(9, 17)
                d = now + timedelta(days=days_ahead) + timedelta(hours=h - now.hour)
                status_ = "scheduled"

            scheduled_at = d.strftime("%Y-%m-%d %H:%M:%S+00")
            all_values.append(
                f"(gen_random_uuid(), '{DEMO_CLINIC_ID}', '{patient_id}', '{doctor_id}', "
                f"'{scheduled_at}', '{status_}'::appointment_status, '{spec}', "
                f"'Tedavi', '{note}', NOW(), NOW())"
            )

    if not all_values:
        err("  Randevu verisi oluşturulamadı"); return

    sql = (
        "INSERT INTO appointments (id, clinic_id, patient_id, doctor_id, "
        "scheduled_at, status, specialty, type, notes, created_at, updated_at) VALUES "
        + ",\n".join(all_values) + " RETURNING id"
    )
    out, sql_err = run_psql_file(sql)
    if "ERROR" in (sql_err or "").upper():
        err(f"  Randevu insert hatası: {sql_err}")
        return

    ids = extract_uuids(out)
    ok(f"  {len(ids)} randevu oluşturuldu")

    # Branş + durum dağılımı
    dist, _ = run_psql(
        f"SELECT specialty, status, COUNT(*) FROM appointments "
        f"WHERE clinic_id='{DEMO_CLINIC_ID}' GROUP BY specialty, status ORDER BY specialty"
    )
    info("  Dağılım:")
    for line in dist.splitlines():
        if line.strip():
            print(f"      {C.DM}{line}{C.R}")


# ── PHASE 4: Envanter ─────────────────────────────────────────────────────────
def phase4_inventory(owner_token: str) -> None:
    header("PHASE 4 — Envanter Kalemleri")

    ITEMS = [
        {"name": "Kompozit Dolgu",        "category": "Restoratif",  "quantity": 50,   "unit": "adet",    "min_stock_level": 20,  "cost_per_unit": 45.0,  "shelf_code": "A1"},
        {"name": "Cerrahi Eldiven M",     "category": "Sarf",        "quantity": 200,  "unit": "cift",    "min_stock_level": 100, "cost_per_unit": 2.5,   "shelf_code": "B2"},
        {"name": "Kanal Ignesi 25mm",     "category": "Endodonti",   "quantity": 80,   "unit": "paket",   "min_stock_level": 30,  "cost_per_unit": 15.0,  "shelf_code": "C3"},
        {"name": "Anestezi Kartusu",      "category": "Anestezi",    "quantity": 120,  "unit": "adet",    "min_stock_level": 50,  "cost_per_unit": 8.0,   "shelf_code": "A4"},
        {"name": "Aljinat Olcu Maddesi",  "category": "Protez",      "quantity": 30,   "unit": "kg",      "min_stock_level": 10,  "cost_per_unit": 120.0, "shelf_code": "D1"},
        {"name": "Dental X-Ray Film",     "category": "Radyoloji",   "quantity": 500,  "unit": "adet",    "min_stock_level": 100, "cost_per_unit": 1.2,   "shelf_code": "E2"},
        {"name": "Steril Kompres",        "category": "Sarf",        "quantity": 300,  "unit": "paket",   "min_stock_level": 80,  "cost_per_unit": 3.5,   "shelf_code": "B3"},
        {"name": "Implant Vidasi 3.5x10", "category": "Implant",     "quantity": 25,   "unit": "adet",    "min_stock_level": 10,  "cost_per_unit": 320.0, "shelf_code": "F1"},
        {"name": "Profilaksi Pastasi",    "category": "Profilaksi",  "quantity": 40,   "unit": "kavanoz", "min_stock_level": 15,  "cost_per_unit": 85.0,  "shelf_code": "G2"},
        {"name": "Nitril Maske FFP2",     "category": "Sarf",        "quantity": 1000, "unit": "adet",    "min_stock_level": 200, "cost_per_unit": 1.8,   "shelf_code": "B1"},
    ]

    item_ids: list[str] = []
    for it in ITEMS:
        r = api("POST", "inventory/items", token=owner_token, json=it)
        if r.status_code in (200, 201):
            iid = r.json().get("id", "")
            item_ids.append(iid)
            ok(f"  [{it['shelf_code']}] {it['name']} ×{it['quantity']}")
        else:
            err(f"  HATA  {it['name']}: {r.status_code} {r.text[:80]}")

    # 2 kalem kritik stoka düşür (min altına)
    if len(item_ids) >= 8:
        # Kompozit Dolgu: qty=50, min=20 → delta=-38 → qty=12 (kritik)
        r2 = api("POST", f"inventory/items/{item_ids[0]}/adjust", token=owner_token,
                 json={"delta": -38, "reason": "Simülasyon kritik stok testi"})
        if r2.status_code in (200, 201):
            ok(f"  KRİTİK stoka düşürüldü: Kompozit Dolgu")
        else:
            warn(f"  Stok düşürme başarısız #{item_ids[0]}: {r2.status_code}")

        # Implant Vidasi: qty=25, min=10 → delta=-18 → qty=7 (kritik)
        r3 = api("POST", f"inventory/items/{item_ids[7]}/adjust", token=owner_token,
                 json={"delta": -18, "reason": "Simülasyon kritik stok testi"})
        if r3.status_code in (200, 201):
            ok(f"  KRİTİK stoka düşürüldü: Implant Vidasi")
        else:
            warn(f"  Stok düşürme başarısız #{item_ids[7]}: {r3.status_code} {r3.text[:80]}")

    ok(f"  Toplam {len(item_ids)} envanter kalemi oluşturuldu")


# ── ANA FONKSİYON ─────────────────────────────────────────────────────────────
def main():
    header("DentAI Flow — Simulation Re-Seed v2.0")
    print(f"\n{C.RE}{C.B}  ⚠  UYARI: Tüm mevcut veriler silinecek!{C.R}")
    if "--yes" not in sys.argv:
        print(f"  Devam etmek için ENTER, iptal için CTRL+C...\n")
        try:
            input()
        except (KeyboardInterrupt, EOFError):
            print("\n  İptal edildi."); sys.exit(0)

    # 0 — Temizle
    phase0_truncate()

    # Hash üret
    info("Bcrypt hash üretiliyor...")
    pw_hash = get_bcrypt_hash(OWNER_PASS)
    if not pw_hash.startswith("$2b$"):
        err(f"Hash üretilemedi: {pw_hash}"); sys.exit(1)
    ok(f"Hash: {pw_hash[:28]}...")

    # 1 — Kullanıcılar + Doktorlar
    doctor_map = phase1_users_and_doctors(pw_hash)

    # 2 — Hastalar
    patient_ids = phase2_patients()
    if not patient_ids:
        err("Hasta oluşturulamadı, durduruluyor"); sys.exit(1)

    # 3 — Randevular
    phase3_appointments(patient_ids, doctor_map)

    # 4 — Envanter (owner token gerekir)
    try:
        owner_token = login_user(OWNER_EMAIL, OWNER_PASS)
        phase4_inventory(owner_token)
    except Exception as e:
        warn(f"Envanter aşaması başarısız: {e}")

    # Özet
    header("ÖZET")
    rows, _ = run_psql(
        f"SELECT role, COUNT(*) FROM users WHERE clinic_id='{DEMO_CLINIC_ID}' GROUP BY role"
    )
    info("Kullanıcı dağılımı:")
    for line in rows.splitlines():
        if line.strip(): print(f"    {C.DM}{line}{C.R}")

    cnt, _ = run_psql(f"SELECT COUNT(*) FROM appointments WHERE clinic_id='{DEMO_CLINIC_ID}'")
    ok(f"Toplam randevu: {cnt}")
    pcnt, _ = run_psql(f"SELECT COUNT(*) FROM patients WHERE clinic_id='{DEMO_CLINIC_ID}'")
    ok(f"Toplam hasta: {pcnt}")
    icnt, _ = run_psql(f"SELECT COUNT(*) FROM inventory_items WHERE clinic_id='{DEMO_CLINIC_ID}'")
    ok(f"Toplam envanter kalemi: {icnt}")

    print(f"\n{C.GR}{C.B}  ✔  Re-seed tamamlandı!{C.R}")
    print(f"\n  Giriş bilgileri (şifre: {C.B}{OWNER_PASS}{C.R}):")
    ACCOUNTS = [
        ("admin@demo.com",          "owner",       "Klinik Sahibi"),
        ("burak@demo.com",          "doctor",      "Dt. Burak Özçelik"),
        ("sule@demo.com",           "doctor",      "Dt. Şule Yılmaz"),
        ("sukru@demo.com",          "doctor",      "Dt. Şükrü Arslan"),
        ("asistan1@demo.com",       "assistant",   "Asistan Elif Kaya"),
        ("asistan2@demo.com",       "assistant",   "Asistan Can Demir"),
        ("superadmin@dentai.io",    "super_admin", "Süper Admin"),
    ]
    for email, role, name in ACCOUNTS:
        print(f"    {C.CY}{email:<30}{C.R}  {C.DM}{role:<12}{C.R}  {name}")


if __name__ == "__main__":
    main()
