"""
Hasta import servisi — duplicate korumalı toplu ekleme.

Duplicate tespiti:
  (clinic_id, LOWER(TRIM(full_name)), phone) üçlüsünün aynı olması.
  Bu kombinasyon patients tablosunda unique index ile de güvence altına alınır.

İşlem adımları:
  1. Her satırı ExternalPatient ile valide et.
  2. Mevcut kayıtları bellek içi set ile karşılaştır (N+1 sorgu yok).
  3. Yeni kayıtları IMPORT_BATCH_SIZE'lık gruplar halinde bulk INSERT et.
  4. ImportResult döndür.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime
from uuid import UUID

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas.integration import ExternalPatient, ImportResult, PatientImportRequest

logger = logging.getLogger(__name__)

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
    text = str(val).strip()
    return text or None


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
    """Normalize edilmiş duplicate tespit anahtarı."""
    return f"{full_name.strip().lower()}|{(phone or '').strip()}"


async def _load_existing_keys(db: AsyncSession, clinic_id: UUID) -> set[str]:
    """Klinik için mevcut hasta (name|phone) anahtarlarını yükler.
    Büyük klinikler için: sadece isim+telefon hash'lerini çeker,
    tam satır yerine sadece anahtar bilgileri belleğe alır."""
    result = await db.execute(
        text("""
            SELECT LOWER(TRIM(full_name)) || '|' || COALESCE(phone, '')
            FROM patients
            WHERE clinic_id = :cid
        """),
        {"cid": str(clinic_id)},
    )
    return {row[0] for row in result.fetchall()}


async def _load_existing_tcs(db: AsyncSession, clinic_id: UUID) -> set[str]:
    result = await db.execute(
        text(
            """
            SELECT national_id FROM patients
            WHERE clinic_id = :cid AND national_id IS NOT NULL
            """
        ),
        {"cid": str(clinic_id)},
    )
    return {row[0] for row in result.fetchall() if row[0]}


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
    """
    Excel (xlsx/xls) veya CSV dosyasını pandas ile okuyup ExternalPatient listesine çevirir.
    Beklenen sütunlar: full_name, phone (opsiyonel), email (opsiyonel).
    Sütun adları büyük/küçük harf ve boşluğa göre normalize edilir.
    """
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

    # Sütun adlarını normalize et
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
            )
            patients.append(p)
        except Exception as e:
            skipped_invalid += 1
            errors.append(f"Satir {int(idx) + 2}: {e}")

    result = await _run_import(patients, clinic_id, db)
    result.skipped_invalid += skipped_invalid
    result.errors.extend(errors[:20])  # Maksimum 20 hata mesajı döndür
    return result


async def _run_import(
    patients: list[ExternalPatient],
    clinic_id: UUID,
    db: AsyncSession,
) -> ImportResult:
    existing_keys = await _load_existing_keys(db, clinic_id)
    existing_tcs = await _load_existing_tcs(db, clinic_id)

    to_insert: list[dict] = []
    skipped_duplicates = 0

    for p in patients:
        phone = _normalize_phone(p.phone)
        key = _patient_key(p.full_name, phone)
        if key in existing_keys:
            skipped_duplicates += 1
            continue
        # Bellek içi set'e ekle — aynı import içindeki tekrarları da engeller
        if p.national_id and p.national_id in existing_tcs:
            skipped_duplicates += 1
            continue
        existing_keys.add(key)
        if p.national_id:
            existing_tcs.add(p.national_id)
        to_insert.append({
            "clinic_id": str(clinic_id),
            "full_name": p.full_name.strip(),
            "phone": phone,
            "email": p.email,
            "national_id": p.national_id,
            "birth_date": _parse_date(p.birth_date),
            "insurance_type": p.insurance_type or "none",
            "insurance_provider": p.insurance_provider,
            "notes": p.notes,
        })

    inserted = 0
    batch_size = settings.IMPORT_BATCH_SIZE
    # executemany ile rowcount güvenilir değil; her satır ayrı execute edilir.
    insert_sql = text("""
        INSERT INTO patients (
            id, clinic_id, full_name, phone, email,
            national_id, birth_date, insurance_type, insurance_provider, notes
        )
        VALUES (
            gen_random_uuid(), CAST(:clinic_id AS UUID), :full_name, :phone, :email,
            :national_id, :birth_date, COALESCE(:insurance_type, 'none'), :insurance_provider, :notes
        )
    """)
    for i in range(0, len(to_insert), batch_size):
        batch = to_insert[i: i + batch_size]
        for row in batch:
            try:
                async with db.begin_nested():
                    result = await db.execute(insert_sql, row)
                    inserted += result.rowcount or 1
            except IntegrityError:
                skipped_duplicates += 1
        await db.flush()  # Her batch sonunda DB'ye yaz, belleği boşalt

    await db.commit()
    logger.info(
        "Patient import tamamlandı",
        extra={"clinic_id": str(clinic_id), "inserted": inserted, "skipped": skipped_duplicates},
    )

    return ImportResult(
        total_received=len(patients),
        inserted=inserted,
        skipped_duplicates=skipped_duplicates,
        skipped_invalid=0,
        errors=[],
    )
