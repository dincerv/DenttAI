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
from uuid import UUID

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas import ExternalPatient, ImportResult, PatientImportRequest

logger = logging.getLogger(__name__)


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
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    if "full_name" not in df.columns:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Dosyada 'full_name' sütunu bulunamadı",
        )

    patients: list[ExternalPatient] = []
    skipped_invalid = 0
    errors: list[str] = []

    for idx, row in df.iterrows():
        try:
            p = ExternalPatient(
                full_name=str(row.get("full_name", "")).strip(),
                phone=row.get("phone") if pd.notna(row.get("phone")) else None,
                email=row.get("email") if pd.notna(row.get("email")) else None,
            )
            patients.append(p)
        except Exception as e:
            skipped_invalid += 1
            errors.append(f"Satır {int(idx) + 2}: {e}")  # +2: header + 1-indexed

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

    to_insert: list[dict] = []
    skipped_duplicates = 0

    for p in patients:
        key = _patient_key(p.full_name, p.phone)
        if key in existing_keys:
            skipped_duplicates += 1
            continue
        # Bellek içi set'e ekle — aynı import içindeki tekrarları da engeller
        existing_keys.add(key)
        to_insert.append({
            "clinic_id": str(clinic_id),
            "full_name": p.full_name.strip(),
            "phone":     p.phone,
            "email":     p.email,
        })

    inserted = 0
    batch_size = settings.IMPORT_BATCH_SIZE
    # executemany ile rowcount güvenilir değil; her satır ayrı execute edilir.
    # ON CONFLICT DO NOTHING durumunda rowcount=0 döner → gerçek inserted sayısı.
    insert_sql = text("""
        INSERT INTO patients (id, clinic_id, full_name, phone, email)
        VALUES (gen_random_uuid(), CAST(:clinic_id AS UUID), :full_name, :phone, :email)
        ON CONFLICT (clinic_id, LOWER(TRIM(full_name)), COALESCE(phone, ''))
        DO NOTHING
    """)
    for i in range(0, len(to_insert), batch_size):
        batch = to_insert[i: i + batch_size]
        for row in batch:
            result = await db.execute(insert_sql, row)
            inserted += result.rowcount
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
