"""
Sync Engine — harici PMS sistemlerinden veri çeker ve yerel DB'ye yazar.

Her sync çalıştığında:
  1. clinic_integrations tablosundan aktif kayıtları al
  2. İlgili adaptörü oluştur
  3. Hasta/randevu/doktor çek
  4. Yerel DB'ye duplicate-safe ekle
  5. last_sync_at ve last_sync_status güncelle
"""
from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import PulledPatient, SyncResult
from app.adapters.registry import get_adapter

logger = logging.getLogger(__name__)


def _normalize_doctor_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    lowered = ascii_only.casefold()
    return re.sub(r"[^a-z0-9]+", "", lowered)


async def sync_clinic(clinic_id: UUID, db: AsyncSession) -> SyncResult:
    """
    Belirli bir kliniğin aktif entegrasyonunu senkronize et.
    Tek klinik için tek provider desteklenir (uq_clinic_provider).
    """
    row = await db.execute(
        text("""
            SELECT id, provider, config, last_sync_at
            FROM clinic_integrations
            WHERE clinic_id = :cid AND is_active = true
            LIMIT 1
        """),
        {"cid": str(clinic_id)},
    )
    integration = row.fetchone()
    if not integration:
        return SyncResult(provider="none", errors=["Bu klinik için aktif entegrasyon bulunamadı"])

    integration_id, provider, config, last_sync_at = integration
    result = SyncResult(provider=provider)

    try:
        adapter = get_adapter(provider, config or {})
        await _reconcile_existing_doctor_assignments(clinic_id, db)

        # ── Hastaları çek ve ekle ────────────────────────
        patients = await adapter.fetch_patients()
        result.patients_pulled = len(patients)
        if patients:
            result.patients_inserted = await _upsert_patients(patients, clinic_id, db)

        # ── Randevuları çek ve ekle ──────────────────────
        appointments = await adapter.fetch_appointments(since=last_sync_at)
        result.appointments_pulled = len(appointments)
        if appointments:
            result.appointments_inserted = await _upsert_appointments(appointments, clinic_id, db, config or {})

        # ── Doktorları çek ve logla ──────────────────────
        doctors = await adapter.fetch_doctors()
        result.doctors_pulled = len(doctors)
        # Doktor kayıtları users tablosuna eklenmez — sadece loglama amacıyla
        if doctors:
            logger.info(
                "Sync: %d doktor çekildi (klinik=%s, provider=%s)",
                len(doctors), clinic_id, provider,
            )

        # ── Sync durumunu güncelle ───────────────────────
        now = datetime.now(timezone.utc)
        result.synced_at = now
        await db.execute(
            text("""
                UPDATE clinic_integrations
                SET last_sync_at = :now,
                    last_sync_status = 'success',
                    last_sync_message = :msg,
                    updated_at = :now
                WHERE id = :iid
            """),
            {
                "now": now,
                "msg": f"Hastalar: {result.patients_inserted}/{result.patients_pulled}, Randevular: {result.appointments_inserted}/{result.appointments_pulled}",
                "iid": str(integration_id),
            },
        )
        await db.commit()

    except Exception as exc:
        logger.exception("Sync hatası: clinic=%s, provider=%s", clinic_id, provider)
        result.errors.append(str(exc))
        await db.rollback()
        await db.execute(
            text("""
                UPDATE clinic_integrations
                SET last_sync_status = 'error',
                    last_sync_message = :msg,
                    updated_at = NOW()
                WHERE id = :iid
            """),
            {"msg": str(exc)[:500], "iid": str(integration_id)},
        )
        await db.commit()

    return result


async def sync_all_active(db: AsyncSession) -> list[SyncResult]:
    """Tüm aktif entegrasyonları sırası ile senkronize et (scheduler için)."""
    rows = await db.execute(
        text("SELECT DISTINCT clinic_id FROM clinic_integrations WHERE is_active = true")
    )
    results: list[SyncResult] = []
    for (cid,) in rows.fetchall():
        # Her klinik için RLS context'i ayarla (parameterized query - SQL injection koruması)
        await db.execute(
            text("SELECT set_config('app.current_clinic_id', :cid, true)").bindparams(cid=str(cid))
        )
        r = await sync_clinic(cid, db)
        results.append(r)
    return results


# ── Yardımcı: Duplicate-safe hasta ekle ──────────────────

async def _upsert_patients(patients: list[PulledPatient], clinic_id: UUID, db: AsyncSession) -> int:
    inserted = 0
    sql = text("""
        INSERT INTO patients (id, clinic_id, full_name, phone, email)
        VALUES (gen_random_uuid(), CAST(:clinic_id AS UUID), :full_name, :phone, :email)
        ON CONFLICT (clinic_id, LOWER(TRIM(full_name)), COALESCE(phone, ''))
        DO UPDATE SET
            phone = COALESCE(NULLIF(patients.phone, ''), EXCLUDED.phone),
            email = COALESCE(NULLIF(patients.email, ''), EXCLUDED.email)
    """)
    for p in patients:
        if not p.full_name or len(p.full_name.strip()) < 2:
            continue
        result = await db.execute(sql, {
            "clinic_id": str(clinic_id),
            "full_name": p.full_name.strip(),
            "phone": p.phone,
            "email": p.email,
        })
        inserted += result.rowcount
    await db.flush()
    return inserted


# ── Yardımcı: Randevu ekle (basit mapping) ──────────────

async def _upsert_appointments(appointments, clinic_id: UUID, db: AsyncSession, config: dict) -> int:
    """
    Randevuları ekle. Hasta eşleştirmesi isim+telefon ile yapılır.
    Eşleşmeyen randevular atlanır (hata loglanır).
    """
    inserted = 0
    for a in appointments:
        # Hasta bul
        patient_row = await db.execute(
            text("""
                SELECT id FROM patients
                WHERE clinic_id = CAST(:cid AS UUID)
                  AND LOWER(TRIM(full_name)) = LOWER(TRIM(:name))
                LIMIT 1
            """),
            {"cid": str(clinic_id), "name": a.patient_name},
        )
        patient = patient_row.fetchone()
        if not patient:
            logger.debug("Randevu atlandı — hasta bulunamadı: %s", a.patient_name)
            continue

        # Doktor bul (opsiyonel — en yakın eşleşme)
        doctor = await _find_or_create_doctor(a.doctor_name, clinic_id, db, config)

        # Aynı hasta + aynı saat'te duplicate kontrolü
        dup = await db.execute(
            text("""
                SELECT id FROM appointments
                WHERE clinic_id = CAST(:cid AS UUID)
                  AND patient_id = :pid
                  AND scheduled_at = :sat
                LIMIT 1
            """),
            {
                "cid": str(clinic_id),
                "pid": str(patient[0]),
                "sat": a.scheduled_at,
            },
        )
        if dup.fetchone():
            continue

        notes = a.notes

        await db.execute(
            text("""
                INSERT INTO appointments (id, clinic_id, patient_id, doctor_id, scheduled_at, type, notes, specialty, status)
                VALUES (gen_random_uuid(), CAST(:cid AS UUID), :pid, :did, :sat, :type, :notes, :specialty, 'scheduled')
            """),
            {
                "cid": str(clinic_id),
                "pid": str(patient[0]),
                "did": str(doctor[0]),
                "sat": a.scheduled_at,
                "type": a.appointment_type,
                "notes": notes,
                "specialty": a.specialty,
            },
        )
        inserted += 1

    await db.flush()
    return inserted


async def _find_or_create_doctor(doctor_name: str, clinic_id: UUID, db: AsyncSession, config: dict):
    normalized_name = (doctor_name or "").strip()
    if not normalized_name:
        normalized_name = "Bilinmiyor"
    comparable_name = _normalize_doctor_name(normalized_name)

    doctor_mappings = config.get("doctor_mappings") if isinstance(config, dict) else {}
    mapped_doctor_id = doctor_mappings.get(normalized_name) if isinstance(doctor_mappings, dict) else None
    if mapped_doctor_id:
        mapped_row = await db.execute(
            text("""
                SELECT d.id, d.full_name FROM doctors d
                WHERE d.clinic_id = CAST(:cid AS UUID)
                  AND d.id = CAST(:did AS UUID)
                LIMIT 1
            """),
            {"cid": str(clinic_id), "did": str(mapped_doctor_id)},
        )
        mapped = mapped_row.fetchone()
        if mapped:
            return mapped

    doctor_row = await db.execute(
        text("""
            SELECT d.id, d.full_name FROM doctors d
            WHERE d.clinic_id = CAST(:cid AS UUID)
              AND LOWER(TRIM(d.full_name)) = LOWER(TRIM(:name))
            LIMIT 1
        """),
        {"cid": str(clinic_id), "name": normalized_name},
    )
    doctor = doctor_row.fetchone()
    if doctor:
        return doctor

    all_doctors = await db.execute(
        text("""
            SELECT d.id, d.full_name FROM doctors d
            WHERE d.clinic_id = CAST(:cid AS UUID)
        """),
        {"cid": str(clinic_id)},
    )
    for existing in all_doctors.fetchall():
        if _normalize_doctor_name(existing[1]) == comparable_name:
            return existing

    created = await db.execute(
        text("""
            INSERT INTO doctors (id, clinic_id, full_name, role)
            VALUES (gen_random_uuid(), CAST(:cid AS UUID), :name, 'doctor')
            RETURNING id, full_name
        """),
        {"cid": str(clinic_id), "name": normalized_name},
    )
    return created.fetchone()


async def _reconcile_existing_doctor_assignments(clinic_id: UUID, db: AsyncSession) -> None:
    rows = await db.execute(
        text("""
            SELECT id, full_name, user_id
            FROM doctors
            WHERE clinic_id = CAST(:cid AS UUID)
        """),
        {"cid": str(clinic_id)},
    )

    local_by_name: dict[str, str] = {}
    external_doctors: list[tuple[str, str]] = []
    for doctor_id, full_name, user_id in rows.fetchall():
        normalized = _normalize_doctor_name(full_name)
        if not normalized:
            continue
        if user_id:
            local_by_name.setdefault(normalized, str(doctor_id))
        else:
            external_doctors.append((str(doctor_id), normalized))

    for external_id, normalized in external_doctors:
        local_id = local_by_name.get(normalized)
        if not local_id or local_id == external_id:
            continue
        result = await db.execute(
            text("""
                UPDATE appointments
                SET doctor_id = CAST(:local_id AS UUID)
                WHERE clinic_id = CAST(:cid AS UUID)
                  AND doctor_id = CAST(:external_id AS UUID)
            """),
            {
                "cid": str(clinic_id),
                "local_id": local_id,
                "external_id": external_id,
            },
        )
        if result.rowcount:
            logger.info(
                "Sync: %s mevcut randevu yerel hekime taşındı (clinic=%s, from=%s, to=%s)",
                result.rowcount,
                clinic_id,
                external_id,
                local_id,
            )
