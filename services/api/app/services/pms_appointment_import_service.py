"""
PMS takvim randevularÄ±nÄ± iÃ§e aktarma (tarayÄ±cÄ± eklentisi â†’ DentAI).

EÅŸleÅŸtirme:
  Hekim  : doctors.external_id â†’ normalize isim â†’ yoksa yeni doktor kaydÄ±
  Hasta  : patients.external_id â†’ isim + telefon â†’ tek isim eÅŸleÅŸmesi â†’ yoksa yeni hasta
  Randevu: (clinic_id, external_source, external_id) â€” varsa gÃ¼ncellenir, yoksa eklenir.

PMS tek doÄŸruluk kaynaÄŸÄ±dÄ±r: aynÄ± harici randevu tekrar gelirse alanlarÄ± Ã¼zerine yazÄ±lÄ±r.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.integration import PmsAppointmentImportRequest, PmsAppointmentImportResult, PmsAppointmentIn
from app.services.import_service import _normalize_phone, _patient_key
from app.services.sync_engine import _normalize_doctor_name

logger = logging.getLogger(__name__)

# TÃ¼rkiye 2016'dan beri sabit UTC+3; PMS saat dilimi gÃ¶ndermezse bu varsayÄ±lÄ±r.
_TR_TZ = timezone(timedelta(hours=3))
_MAX_ERRORS = 20


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=_TR_TZ)


def _duration_minutes(a: PmsAppointmentIn) -> int:
    if not a.end:
        return 30
    minutes = int((_aware(a.end) - _aware(a.start)).total_seconds() // 60)
    return max(5, min(minutes, 600)) if minutes > 0 else 30


class _DoctorResolver:
    def __init__(self, db: AsyncSession, clinic_id: str, source: str, result: PmsAppointmentImportResult):
        self.db = db
        self.cid = clinic_id
        self.source = source
        self.result = result
        self.by_ext: dict[str, str] = {}
        self.by_name: dict[str, tuple[str, bool]] = {}
        self.specialty: dict[str, str | None] = {}

    async def load(self) -> None:
        rows = await self.db.execute(
            text("""
                SELECT id, full_name, specialty, user_id, external_source, external_id
                FROM doctors
                WHERE clinic_id = CAST(:cid AS UUID)
            """),
            {"cid": self.cid},
        )
        for r in rows.mappings().all():
            did = str(r["id"])
            self.specialty[did] = r["specialty"]
            if r["external_id"] and r["external_source"] == self.source:
                self.by_ext[str(r["external_id"])] = did
            key = _normalize_doctor_name(r["full_name"] or "")
            if not key:
                continue
            has_ext = bool(r["external_id"])
            current = self.by_name.get(key)
            # GiriÅŸ hesabÄ± olan (user_id) hekim, aynÄ± isimli dÄ±ÅŸ kayda tercih edilir.
            if current is None or (r["user_id"] and not current[1]):
                self.by_name[key] = (did, has_ext)

    async def resolve(self, external_id: str | None, name: str | None) -> str | None:
        if external_id and external_id in self.by_ext:
            return self.by_ext[external_id]
        clean_name = (name or "").strip()
        key = _normalize_doctor_name(clean_name)
        if not key:
            return None

        match = self.by_name.get(key)
        if match:
            did, has_ext = match
            if external_id and not has_ext:
                await self.db.execute(
                    text("""
                        UPDATE doctors SET external_source = :src, external_id = :ext
                        WHERE id = CAST(:did AS UUID) AND external_id IS NULL
                    """),
                    {"src": self.source, "ext": external_id, "did": did},
                )
                self.by_name[key] = (did, True)
            if external_id:
                self.by_ext[external_id] = did
            return did

        row = await self.db.execute(
            text("""
                INSERT INTO doctors (id, clinic_id, full_name, role, external_source, external_id)
                VALUES (gen_random_uuid(), CAST(:cid AS UUID), :name, 'doctor', :src, :ext)
                RETURNING id
            """),
            {"cid": self.cid, "name": clean_name[:255], "src": self.source if external_id else None, "ext": external_id},
        )
        did = str(row.scalar())
        self.result.doctors_created += 1
        self.by_name[key] = (did, bool(external_id))
        self.specialty[did] = None
        if external_id:
            self.by_ext[external_id] = did
        return did


class _PatientResolver:
    def __init__(self, db: AsyncSession, clinic_id: str, result: PmsAppointmentImportResult):
        self.db = db
        self.cid = clinic_id
        self.result = result
        self.by_ext: dict[str, str] = {}
        self.by_key: dict[str, str] = {}
        self.by_name: dict[str, list[str]] = {}
        self.has_ext: set[str] = set()

    async def load(self) -> None:
        # Tüm klinik hastalarını belleğe alma — 502/timeout riski. resolve() ihtiyaç oldukça sorgular.
        return

    def _remember(self, pid: str, full_name: str, phone: str | None, external_id: str | None) -> None:
        self.by_key[_patient_key(full_name, phone)] = pid
        self.by_name.setdefault(full_name.strip().lower(), []).append(pid)
        if external_id:
            self.by_ext[str(external_id)] = pid
            self.has_ext.add(pid)

    async def resolve(self, external_id: str | None, name: str, raw_phone: str | None) -> str:
        if external_id and external_id in self.by_ext:
            return self.by_ext[external_id]

        phone = _normalize_phone(raw_phone)

        if external_id:
            row = await self.db.execute(
                text("""
                    SELECT id, full_name, phone, external_id FROM patients
                    WHERE clinic_id = CAST(:cid AS UUID) AND external_id = :ext
                    LIMIT 1
                """),
                {"cid": self.cid, "ext": external_id},
            )
            hit = row.mappings().first()
            if hit:
                self._remember(str(hit["id"]), hit["full_name"] or "", hit["phone"], hit["external_id"])
                if phone:
                    await self.db.execute(
                        text("UPDATE patients SET phone = :phone WHERE id = CAST(:pid AS UUID)"),
                        {"phone": phone, "pid": str(hit["id"])},
                    )
                return str(hit["id"])

        pid = self.by_key.get(_patient_key(name, phone))
        if not pid:
            candidates = self.by_name.get(name.strip().lower(), [])
            if len(candidates) == 1:
                pid = candidates[0]

        if not pid:
            # İsim (+ telefon) ile tek eşleşme ara — tüm tabloyu yüklemeden.
            rows = await self.db.execute(
                text("""
                    SELECT id, full_name, phone, external_id FROM patients
                    WHERE clinic_id = CAST(:cid AS UUID)
                      AND lower(trim(full_name)) = lower(trim(:name))
                    LIMIT 5
                """),
                {"cid": self.cid, "name": name.strip()},
            )
            matches = list(rows.mappings().all())
            if phone:
                for m in matches:
                    if _normalize_phone(m["phone"]) == phone:
                        pid = str(m["id"])
                        self._remember(pid, m["full_name"] or "", m["phone"], m["external_id"])
                        break
            if not pid and len(matches) == 1:
                m = matches[0]
                pid = str(m["id"])
                self._remember(pid, m["full_name"] or "", m["phone"], m["external_id"])

        if pid:
            if external_id and pid not in self.has_ext:
                await self.db.execute(
                    text("UPDATE patients SET external_id = :ext WHERE id = CAST(:pid AS UUID) AND external_id IS NULL"),
                    {"ext": external_id, "pid": pid},
                )
                self.has_ext.add(pid)
                self.by_ext[external_id] = pid
            if phone:
                await self.db.execute(
                    text("UPDATE patients SET phone = :phone WHERE id = CAST(:pid AS UUID)"),
                    {"phone": phone, "pid": pid},
                )
            return pid

        row = await self.db.execute(
            text("""
                INSERT INTO patients (id, clinic_id, full_name, phone, external_id)
                VALUES (gen_random_uuid(), CAST(:cid AS UUID), :name, :phone, :ext)
                RETURNING id
            """),
            {"cid": self.cid, "name": name.strip()[:255], "phone": phone, "ext": external_id},
        )
        pid = str(row.scalar())
        self.result.patients_created += 1
        self._remember(pid, name, phone, external_id)
        return pid


async def import_pms_appointments(
    body: PmsAppointmentImportRequest,
    clinic_id: UUID,
    db: AsyncSession,
) -> PmsAppointmentImportResult:
    cid = str(clinic_id)
    source = body.source
    result = PmsAppointmentImportResult(total_received=len(body.appointments))

    doctors = _DoctorResolver(db, cid, source, result)
    patients = _PatientResolver(db, cid, result)
    await doctors.load()
    await patients.load()

    names_by_ext = {d.external_id: d.full_name for d in body.doctors}
    for d in body.doctors:
        try:
            async with db.begin_nested():
                await doctors.resolve(d.external_id, d.full_name)
        except DBAPIError as exc:
            _add_error(result, f"Hekim {d.external_id}: {exc.orig}")

    ext_ids = [a.external_id for a in body.appointments]
    existing: dict[str, dict] = {}
    if ext_ids:
        rows = await db.execute(
            text("""
                SELECT id, external_id, patient_id, doctor_id, scheduled_at, duration_minutes,
                       status::text AS status, type, notes, is_new_patient
                FROM appointments
                WHERE clinic_id = CAST(:cid AS UUID)
                  AND external_source = :src
                  AND external_id = ANY(:ext_ids)
            """),
            {"cid": cid, "src": source, "ext_ids": ext_ids},
        )
        existing = {str(r["external_id"]): dict(r) for r in rows.mappings().all()}

    seen: set[str] = set()
    for a in body.appointments:
        if a.external_id in seen:
            continue
        seen.add(a.external_id)
        # Hekim, hasta ve randevu ayrÄ± savepoint'lerde: biri geri alÄ±nÄ±rsa Ã¶nbelleÄŸe yazÄ±lmÄ±ÅŸ kimlikler geÃ§erli kalÄ±r.
        try:
            async with db.begin_nested():
                doctor_name = a.doctor_name or names_by_ext.get(a.doctor_external_id or "")
                doctor_id = await doctors.resolve(a.doctor_external_id, doctor_name)
            if not doctor_id:
                result.skipped_invalid += 1
                _add_error(result, f"Randevu {a.external_id}: hekim bilgisi yok")
                continue
            async with db.begin_nested():
                patient_id = await patients.resolve(a.patient_external_id, a.patient_name, a.patient_phone)
        except DBAPIError as exc:
            result.skipped_invalid += 1
            _add_error(result, f"Randevu {a.external_id}: {exc.orig}")
            continue
        try:
            async with db.begin_nested():
                await _upsert_one(db, cid, source, a, doctor_id, patient_id, doctors.specialty.get(doctor_id), existing, result)
        except DBAPIError as exc:
            result.skipped_invalid += 1
            _add_error(result, f"Randevu {a.external_id}: {exc.orig}")

    await db.commit()
    logger.info(
        "PMS randevu import tamamlandÄ±",
        extra={
            "clinic_id": cid,
            "source": source,
            "inserted": result.inserted,
            "updated": result.updated,
            "unchanged": result.unchanged,
            "skipped": result.skipped_invalid,
        },
    )
    return result


async def _upsert_one(
    db: AsyncSession,
    cid: str,
    source: str,
    a: PmsAppointmentIn,
    doctor_id: str,
    patient_id: str,
    specialty: str | None,
    existing: dict[str, dict],
    result: PmsAppointmentImportResult,
) -> None:
    values = {
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "scheduled_at": _aware(a.start),
        "duration_minutes": _duration_minutes(a),
        "status": a.status,
        "type": a.treatment,
        "notes": a.notes,
        "is_new_patient": bool(a.is_new_patient),
    }

    current = existing.get(a.external_id)
    if current:
        if _same(current, values):
            result.unchanged += 1
            return
        await db.execute(
            text("""
                UPDATE appointments
                SET patient_id = CAST(:patient_id AS UUID),
                    doctor_id = CAST(:doctor_id AS UUID),
                    scheduled_at = :scheduled_at,
                    duration_minutes = :duration_minutes,
                    status = CAST(:status AS appointment_status),
                    type = :type,
                    notes = :notes,
                    is_new_patient = :is_new_patient,
                    external_synced_at = NOW(),
                    updated_at = NOW()
                WHERE id = CAST(:id AS UUID)
            """),
            {**values, "id": str(current["id"])},
        )
        result.updated += 1
        return

    await db.execute(
        text("""
            INSERT INTO appointments (
                id, clinic_id, patient_id, doctor_id, scheduled_at, duration_minutes, status,
                type, notes, is_new_patient, specialty,
                external_source, external_id, external_synced_at
            ) VALUES (
                gen_random_uuid(), CAST(:cid AS UUID), CAST(:patient_id AS UUID), CAST(:doctor_id AS UUID),
                :scheduled_at, :duration_minutes, CAST(:status AS appointment_status),
                :type, :notes, :is_new_patient, :specialty,
                :src, :ext, NOW()
            )
        """),
        {**values, "cid": cid, "specialty": specialty, "src": source, "ext": a.external_id},
    )
    result.inserted += 1


def _same(current: dict, values: dict) -> bool:
    return (
        str(current["patient_id"]) == values["patient_id"]
        and str(current["doctor_id"]) == values["doctor_id"]
        and current["scheduled_at"] == values["scheduled_at"]
        and current["duration_minutes"] == values["duration_minutes"]
        and current["status"] == values["status"]
        and (current["type"] or None) == values["type"]
        and (current["notes"] or None) == values["notes"]
        and bool(current["is_new_patient"]) == values["is_new_patient"]
    )


def _add_error(result: PmsAppointmentImportResult, message: str) -> None:
    if len(result.errors) < _MAX_ERRORS:
        result.errors.append(message[:300])
