"""
Hasta import servisi — duplicate korumalı toplu ekleme + profil güncelleme.

Duplicate tespiti (öncelik sırası):
  1. external_id (klinik + harici PMS id)
  2. national_id (TC)
  3. (clinic_id, LOWER(TRIM(full_name)), phone)

Mevcut kayıtta boş alanlar COALESCE ile doldurulur (overwrite yok).
"""
from __future__ import annotations

import io
import logging
from datetime import datetime
from uuid import UUID

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas.integration import ExternalClinicalVisit, ExternalPatient, ImportResult, PatientImportRequest

logger = logging.getLogger(__name__)

_FDI_PERMANENT = frozenset(n for q in (10, 20, 30, 40) for n in range(q + 1, q + 9))

_PROCEDURE_TOOTH_STATUS = {
    "dolgu": "filled",
    "kanal": "rct",
    "kron": "crown",
    "veneer": "crown",
    "cekim": "missing",
    "implant": "implant",
    "kopru": "bridge",
}

_COL_ALIASES = {
    "full_name": "full_name",
    "ad_soyad": "full_name",
    "adsoyad": "full_name",
    "hasta_adi": "full_name",
    "hasta": "full_name",
    "isim": "full_name",
    "ad": "full_name",
    "phone": "phone",
    "telefon": "phone",
    "tel": "phone",
    "cep": "phone",
    "email": "email",
    "e_posta": "email",
    "eposta": "email",
    "national_id": "national_id",
    "tc": "national_id",
    "tckn": "national_id",
    "tc_kimlik": "national_id",
    "tc_kimlik_no": "national_id",
    "kimlik": "national_id",
    "birth_date": "birth_date",
    "dogum": "birth_date",
    "dogum_tarihi": "birth_date",
    "insurance_type": "insurance_type",
    "sigorta": "insurance_type",
    "sigorta_tipi": "insurance_type",
    "insurance_provider": "insurance_provider",
    "sigorta_kurumu": "insurance_provider",
    "notes": "notes",
    "not": "notes",
    "notlar": "notes",
    "sex": "sex",
    "cinsiyet": "sex",
    "gender": "sex",
    "address": "address",
    "adres": "address",
    "city": "city",
    "il": "city",
    "district": "district",
    "ilce": "district",
    "ilçe": "district",
    "country": "country",
    "ulke": "country",
    "ülke": "country",
    "external_id": "external_id",
    "avatar_url": "avatar_url",
    "file_number": "file_number",
    "dosya_no": "file_number",
    "archive_number": "archive_number",
    "arsiv_no": "archive_number",
    "occupation": "occupation",
    "meslek": "occupation",
    "nationality": "nationality",
    "uyruk": "nationality",
    "blood_type": "blood_type",
    "kan_grubu": "blood_type",
}


def _normalize_col(name: object) -> str:
    raw = str(name or "").strip().lower().replace(" ", "_")
    return _COL_ALIASES.get(raw, raw)


def _parse_date(value: str | None):
    if not value:
        return None
    raw = value.strip()[:10]
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _cell(row, key: str) -> str | None:
    val = row.get(key)
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    text_val = str(val).strip()
    return text_val or None


def _normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = "".join(ch for ch in phone if ch.isdigit())
    if digits.startswith("90") and len(digits) == 12:
        return f"+{digits}"
    if digits.startswith("0") and len(digits) == 11:
        return f"+90{digits[1:]}"
    if len(digits) == 10:
        return f"+90{digits}"
    return phone.strip() or None


def _patient_key(full_name: str, phone: str | None) -> str:
    return f"{full_name.strip().lower()}|{(phone or '').strip()}"


def _row_payload(p: ExternalPatient, clinic_id: UUID, phone: str | None) -> dict:
    return {
        "clinic_id": str(clinic_id),
        "full_name": p.full_name.strip(),
        "phone": phone,
        "email": p.email,
        "national_id": p.national_id,
        "birth_date": _parse_date(p.birth_date),
        "insurance_type": p.insurance_type or "none",
        "insurance_provider": p.insurance_provider,
        "notes": p.notes,
        "sex": p.sex,
        "address": p.address,
        "city": p.city,
        "district": p.district,
        "country": p.country,
        "external_id": p.external_id,
        "avatar_url": p.avatar_url,
        "file_number": p.file_number,
        "archive_number": p.archive_number,
        "occupation": p.occupation,
        "nationality": p.nationality,
        "blood_type": p.blood_type,
        "_clinical_visits": list(p.clinical_visits or []),
    }


def _fdi_from_hint(hint: str | None) -> int | None:
    if not hint:
        return None
    digits = "".join(ch for ch in str(hint) if ch.isdigit())
    if not digits:
        return None
    try:
        n = int(digits)
    except ValueError:
        return None
    return n if n in _FDI_PERMANENT else None


def _visit_tag(visit: ExternalClinicalVisit) -> str:
    ref = (visit.external_ref or "").strip() or "x"
    return f"[ds:{ref}]"


async def _apply_clinical_visits(
    db: AsyncSession,
    clinic_id: UUID,
    patient_id: str,
    visits: list[ExternalClinicalVisit],
) -> None:
    if not visits:
        return

    for visit in visits[:30]:
        tag = _visit_tag(visit)
        exists = (
            await db.execute(
                text(
                    """
                    SELECT 1 FROM treatments
                    WHERE clinic_id = CAST(:cid AS UUID)
                      AND patient_id = CAST(:pid AS UUID)
                      AND notes LIKE :tag
                    LIMIT 1
                    """
                ),
                {"cid": str(clinic_id), "pid": patient_id, "tag": f"%{tag}%"},
            )
        ).first()
        if exists:
            continue

        procedure = visit.procedure or "diger"
        status = visit.status if visit.status in ("planned", "completed", "cancelled") else "completed"
        tooth = _fdi_from_hint(visit.tooth_hint)
        note_parts = [
            tag,
            visit.when_text,
            f"Hekim: {visit.doctor}" if visit.doctor else None,
            visit.procedure_raw,
            f"Diş ipucu: {visit.tooth_hint}" if visit.tooth_hint and tooth is None else None,
            visit.note,
        ]
        notes = " · ".join(p for p in note_parts if p)[:1000]

        await db.execute(
            text(
                """
                INSERT INTO treatments (
                    id, clinic_id, patient_id, tooth_fdi, procedure, status, price, notes,
                    completed_at, created_at, updated_at
                )
                VALUES (
                    gen_random_uuid(), CAST(:cid AS UUID), CAST(:pid AS UUID), :tooth,
                    :procedure, :status, 0, :notes,
                    CASE WHEN :status = 'completed' THEN NOW() ELSE NULL END,
                    NOW(), NOW()
                )
                """
            ),
            {
                "cid": str(clinic_id),
                "pid": patient_id,
                "tooth": tooth,
                "procedure": procedure,
                "status": status,
                "notes": notes,
            },
        )

        if tooth and status == "completed":
            tooth_status = _PROCEDURE_TOOTH_STATUS.get(procedure, "planned")
            await db.execute(
                text(
                    """
                    INSERT INTO tooth_records (id, clinic_id, patient_id, tooth_fdi, status, notes, updated_at)
                    VALUES (
                        gen_random_uuid(), CAST(:cid AS UUID), CAST(:pid AS UUID), :tooth,
                        :status, :notes, NOW()
                    )
                    ON CONFLICT (clinic_id, patient_id, tooth_fdi)
                    DO UPDATE SET
                        status = EXCLUDED.status,
                        notes = COALESCE(tooth_records.notes, EXCLUDED.notes),
                        updated_at = NOW()
                    """
                ),
                {
                    "cid": str(clinic_id),
                    "pid": patient_id,
                    "tooth": tooth,
                    "status": tooth_status,
                    "notes": visit.procedure_raw or visit.note,
                },
            )

        note_content = " · ".join(
            p
            for p in [
                visit.when_text,
                visit.procedure_raw,
                visit.doctor,
                visit.note,
                tag,
            ]
            if p
        )[:5000]
        if note_content:
            note_exists = (
                await db.execute(
                    text(
                        """
                        SELECT 1 FROM patient_notes
                        WHERE clinic_id = CAST(:cid AS UUID)
                          AND patient_id = CAST(:pid AS UUID)
                          AND content LIKE :tag
                        LIMIT 1
                        """
                    ),
                    {"cid": str(clinic_id), "pid": patient_id, "tag": f"%{tag}%"},
                )
            ).first()
            if not note_exists:
                await db.execute(
                    text(
                        """
                        INSERT INTO patient_notes
                            (clinic_id, patient_id, doctor_id, appointment_id, note_type, content)
                        VALUES
                            (CAST(:cid AS UUID), CAST(:pid AS UUID), NULL, NULL, 'treatment', :content)
                        """
                    ),
                    {"cid": str(clinic_id), "pid": patient_id, "content": note_content},
                )


async def _load_existing_index(db: AsyncSession, clinic_id: UUID) -> dict[str, dict[str, str]]:
    """name_phone / tc / external_id → patient_id eşlemesi."""
    result = await db.execute(
        text(
            """
            SELECT id, full_name, phone, national_id, external_id
            FROM patients
            WHERE clinic_id = :cid
            """
        ),
        {"cid": str(clinic_id)},
    )
    by_key: dict[str, str] = {}
    by_tc: dict[str, str] = {}
    by_ext: dict[str, str] = {}
    for row in result.mappings().all():
        pid = str(row["id"])
        by_key[_patient_key(row["full_name"] or "", row["phone"])] = pid
        if row["national_id"]:
            by_tc[str(row["national_id"])] = pid
        if row["external_id"]:
            by_ext[str(row["external_id"])] = pid
    return {"by_key": by_key, "by_tc": by_tc, "by_ext": by_ext}


def _find_existing_id(index: dict[str, dict[str, str]], p: ExternalPatient, phone: str | None) -> str | None:
    if p.external_id and p.external_id in index["by_ext"]:
        return index["by_ext"][p.external_id]
    if p.national_id and p.national_id in index["by_tc"]:
        return index["by_tc"][p.national_id]
    key = _patient_key(p.full_name, phone)
    return index["by_key"].get(key)


async def import_patients_json(
    req: PatientImportRequest,
    clinic_id: UUID,
    db: AsyncSession,
) -> ImportResult:
    return await _run_import(req.patients, clinic_id, db)


async def import_patients_excel(
    file_bytes: bytes,
    clinic_id: UUID,
    db: AsyncSession,
) -> ImportResult:
    try:
        try:
            df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
        except Exception:
            df = pd.read_csv(io.BytesIO(file_bytes), dtype=str)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dosya okunamadı: {exc}",
        ) from exc

    df.columns = [_normalize_col(c) for c in df.columns]

    if "full_name" not in df.columns:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Dosyada 'full_name' veya 'ad_soyad' sutunu bulunamadi",
        )

    patients: list[ExternalPatient] = []
    skipped_invalid = 0
    errors: list[str] = []

    for idx, row in df.iterrows():
        try:
            p = ExternalPatient(
                full_name=_cell(row, "full_name") or "",
                phone=_cell(row, "phone"),
                email=_cell(row, "email"),
                national_id=_cell(row, "national_id"),
                birth_date=_cell(row, "birth_date"),
                insurance_type=_cell(row, "insurance_type"),
                insurance_provider=_cell(row, "insurance_provider"),
                notes=_cell(row, "notes"),
                sex=_cell(row, "sex"),
                address=_cell(row, "address"),
                city=_cell(row, "city"),
                district=_cell(row, "district"),
                country=_cell(row, "country"),
                external_id=_cell(row, "external_id"),
                avatar_url=_cell(row, "avatar_url"),
                file_number=_cell(row, "file_number"),
                archive_number=_cell(row, "archive_number"),
                occupation=_cell(row, "occupation"),
                nationality=_cell(row, "nationality"),
                blood_type=_cell(row, "blood_type"),
            )
            patients.append(p)
        except Exception as e:
            skipped_invalid += 1
            errors.append(f"Satir {int(idx) + 2}: {e}")

    result = await _run_import(patients, clinic_id, db)
    result.skipped_invalid += skipped_invalid
    result.errors.extend(errors[:20])
    return result


_UPDATE_SQL = text("""
    UPDATE patients SET
        email = COALESCE(email, :email),
        national_id = COALESCE(national_id, :national_id),
        birth_date = COALESCE(birth_date, :birth_date),
        insurance_type = CASE
            WHEN insurance_type IS NULL OR insurance_type = 'none'
            THEN COALESCE(:insurance_type, insurance_type)
            ELSE insurance_type
        END,
        insurance_provider = COALESCE(insurance_provider, :insurance_provider),
        notes = CASE
            WHEN :notes IS NULL THEN notes
            WHEN notes IS NULL OR BTRIM(notes) = '' THEN :notes
            WHEN :notes LIKE '%[Dentsoft]%' THEN :notes
            WHEN length(:notes) > length(notes) THEN :notes
            ELSE notes
        END,
        sex = COALESCE(sex, :sex),
        address = COALESCE(address, :address),
        city = COALESCE(city, :city),
        district = COALESCE(district, :district),
        country = COALESCE(country, :country),
        external_id = COALESCE(external_id, :external_id),
        avatar_url = COALESCE(avatar_url, :avatar_url),
        file_number = COALESCE(file_number, :file_number),
        archive_number = COALESCE(archive_number, :archive_number),
        occupation = COALESCE(occupation, :occupation),
        nationality = COALESCE(nationality, :nationality),
        blood_type = COALESCE(blood_type, :blood_type),
        phone = COALESCE(:phone, phone),
        updated_at = NOW()
    WHERE id = CAST(:id AS UUID) AND clinic_id = CAST(:clinic_id AS UUID)
""")

_INSERT_SQL = text("""
    INSERT INTO patients (
        id, clinic_id, full_name, phone, email,
        national_id, birth_date, insurance_type, insurance_provider, notes,
        sex, address, city, district, country, external_id, avatar_url,
        file_number, archive_number, occupation, nationality, blood_type
    )
    VALUES (
        gen_random_uuid(), CAST(:clinic_id AS UUID), :full_name, :phone, :email,
        :national_id, :birth_date, COALESCE(:insurance_type, 'none'), :insurance_provider, :notes,
        :sex, :address, :city, :district, :country, :external_id, :avatar_url,
        :file_number, :archive_number, :occupation, :nationality, :blood_type
    )
    RETURNING id
""")


def _sql_params(row: dict) -> dict:
    return {k: v for k, v in row.items() if not k.startswith("_")}


async def _run_import(
    patients: list[ExternalPatient],
    clinic_id: UUID,
    db: AsyncSession,
) -> ImportResult:
    index = await _load_existing_index(db, clinic_id)

    to_insert: list[dict] = []
    to_update: list[dict] = []
    skipped_duplicates = 0
    seen_batch: set[str] = set()

    for p in patients:
        phone = _normalize_phone(p.phone)
        batch_key = p.external_id or p.national_id or _patient_key(p.full_name, phone)
        if batch_key in seen_batch:
            skipped_duplicates += 1
            continue
        seen_batch.add(batch_key)

        existing_id = _find_existing_id(index, p, phone)
        payload = _row_payload(p, clinic_id, phone)

        if existing_id:
            payload["id"] = existing_id
            to_update.append(payload)
            if p.national_id:
                index["by_tc"][p.national_id] = existing_id
            if p.external_id:
                index["by_ext"][p.external_id] = existing_id
            continue

        key = _patient_key(p.full_name, phone)
        index["by_key"][key] = "__pending__"
        if p.national_id:
            index["by_tc"][p.national_id] = "__pending__"
        if p.external_id:
            index["by_ext"][p.external_id] = "__pending__"
        to_insert.append(payload)

    inserted = 0
    updated = 0
    batch_size = settings.IMPORT_BATCH_SIZE

    for i in range(0, len(to_update), batch_size):
        batch = to_update[i: i + batch_size]
        for row in batch:
            try:
                async with db.begin_nested():
                    result = await db.execute(_UPDATE_SQL, _sql_params(row))
                    if result.rowcount:
                        updated += 1
                    visits = row.get("_clinical_visits") or []
                    if visits and row.get("id"):
                        await _apply_clinical_visits(db, clinic_id, str(row["id"]), visits)
            except IntegrityError:
                skipped_duplicates += 1
        await db.flush()

    for i in range(0, len(to_insert), batch_size):
        batch = to_insert[i: i + batch_size]
        for row in batch:
            try:
                async with db.begin_nested():
                    result = await db.execute(_INSERT_SQL, _sql_params(row))
                    new_id = result.scalar()
                    inserted += 1
                    visits = row.get("_clinical_visits") or []
                    if visits and new_id:
                        await _apply_clinical_visits(db, clinic_id, str(new_id), visits)
            except IntegrityError:
                skipped_duplicates += 1
        await db.flush()

    # Telefonsuz hastaya bağlı randevuları telefonlu adaşına taşı (name+phone unique engeli).
    await db.execute(
        text("""
            UPDATE appointments AS a
            SET patient_id = twin.id, updated_at = NOW()
            FROM patients AS empty
            JOIN patients AS twin
              ON twin.clinic_id = empty.clinic_id
             AND lower(trim(twin.full_name)) = lower(trim(empty.full_name))
             AND twin.phone IS NOT NULL AND BTRIM(twin.phone) <> ''
             AND twin.id <> empty.id
            WHERE a.clinic_id = CAST(:cid AS UUID)
              AND a.patient_id = empty.id
              AND (empty.phone IS NULL OR BTRIM(empty.phone) = '')
        """),
        {"cid": str(clinic_id)},
    )

    await db.commit()
    logger.info(
        "Patient import tamamlandı",
        extra={
            "clinic_id": str(clinic_id),
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped_duplicates,
        },
    )

    return ImportResult(
        total_received=len(patients),
        inserted=inserted,
        updated=updated,
        skipped_duplicates=skipped_duplicates,
        skipped_invalid=0,
        errors=[],
    )
