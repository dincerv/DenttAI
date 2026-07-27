"""
Integration Routers — hasta içe aktarma (JSON ve Excel/CSV), PMS konfigürasyon ve sync.

Tüm endpoint'ler:
  - JWT Bearer token zorunlu
  - RLS context set edilir (set_rls_context)
  - Admin veya staff rolü gerekir (hassas toplu işlem)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.registry import get_adapter, list_providers
from app.core.database import get_db
from app.schemas import (
    DoctorMappingResponse,
    DoctorMappingUpdate,
    ExternalDoctorSummary,
    ImportResult,
    IntegrationConfigCreate,
    IntegrationConfigResponse,
    IntegrationConfigUpdate,
    LocalDoctorSummary,
    PatientImportRequest,
    SessionCookieUpdate,
    SyncResultResponse,
    TestConnectionResponse,
)
from app.services.import_service import import_patients_excel, import_patients_json
from app.services.sync_engine import sync_clinic
from app.tasks.post_op_tasks import send_postop_followup_for_appointment
from shared.auth_middleware import require_role, set_rls_context

router = APIRouter(prefix="/integration", tags=["integration"])

_ALLOWED_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
    "application/vnd.ms-excel",                                            # xls
    "text/csv",
    "application/csv",
    "application/octet-stream",  # bazı istemciler generic gönderir
}


@router.post(
    "/appointments/{appointment_id}/post-op-reachout",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Tamamlanan tedavi için manuel post-op WhatsApp ulaşımı tetikle",
)
async def trigger_post_op_reachout(
    appointment_id: str,
    claims: dict = Depends(require_role("owner", "doctor", "assistant")),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    appt = (
        await db.execute(
            text(
                """
                SELECT status, treatment_follow_up_enabled
                FROM appointments
                WHERE id = CAST(:appointment_id AS uuid)
                  AND clinic_id = CAST(:clinic_id AS uuid)
                LIMIT 1
                """
            ),
            {
                "appointment_id": appointment_id,
                "clinic_id": str(claims["clinic_id"]),
            },
        )
    ).mappings().first()

    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Randevu bulunamadi")

    if appt["status"] != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Post-op ulasimi sadece tamamlanan randevular icin tetiklenebilir",
        )

    if not appt["treatment_follow_up_enabled"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tedavi kontrolu kapali olan randevular icin post-op ulasimi tetiklenemez",
        )

    send_postop_followup_for_appointment.delay(str(claims["clinic_id"]), appointment_id)
    return {"status": "queued", "appointment_id": appointment_id}


def _has_session_cookie(config: dict | None) -> bool:
    if not isinstance(config, dict):
        return False
    return bool(str(config.get("session_cookie") or "").strip())


def _doctor_mappings(config: dict | None) -> dict[str, str | None]:
    if not isinstance(config, dict):
        return {}
    mappings = config.get("doctor_mappings") or {}
    if not isinstance(mappings, dict):
        return {}
    return {str(key): (str(value) if value else None) for key, value in mappings.items()}


@router.post(
    "/import/patients",
    response_model=ImportResult,
    status_code=status.HTTP_200_OK,
    summary="Hasta listesini JSON olarak içe aktar",
    description=(
        "DentSoft gibi harici sistemlerden dışa aktarılan hasta JSON listesini sisteme aktarır. "
        "Aynı klinikte (full_name + phone) eşleşen kayıtlar atlanır (duplicate koruması)."
    ),
)
async def import_patients_from_json(
    body: PatientImportRequest,
    claims: dict = Depends(require_role("owner", "assistant")),
    db: AsyncSession = Depends(get_db),
) -> ImportResult:
    await set_rls_context(db, claims["clinic_id"])
    return await import_patients_json(body, clinic_id=claims["clinic_id"], db=db)


@router.post(
    "/import/patients/excel",
    response_model=ImportResult,
    status_code=status.HTTP_200_OK,
    summary="Hasta listesini Excel/CSV dosyası olarak içe aktar",
    description=(
        "xlsx, xls veya csv dosyasını multipart/form-data ile yükleyin. "
        "Zorunlu sütun: full_name. Opsiyonel: phone, email. "
        "Duplicate kayıtlar atlanır."
    ),
)
async def import_patients_from_excel(
    file: UploadFile = File(..., description="xlsx / xls / csv dosyası"),
    claims: dict = Depends(require_role("owner", "assistant")),
    db: AsyncSession = Depends(get_db),
) -> ImportResult:
    await set_rls_context(db, claims["clinic_id"])
    file_bytes = await file.read()
    return await import_patients_excel(file_bytes, clinic_id=claims["clinic_id"], db=db)


# ═══════════════════════════════════════════════════════════
# Entegrasyon Konfigürasyon Endpoint'leri
# ═══════════════════════════════════════════════════════════

@router.get(
    "/providers",
    summary="Desteklenen PMS sağlayıcılarını listele",
)
async def get_providers(
    claims: dict = Depends(require_role("owner")),
):
    return {"providers": list_providers()}


@router.get(
    "/config",
    response_model=list[IntegrationConfigResponse],
    summary="Klinik entegrasyon ayarlarını listele",
)
async def list_integrations(
    claims: dict = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
) -> list[IntegrationConfigResponse]:
    await set_rls_context(db, claims["clinic_id"])
    result = await db.execute(
        text("""
            SELECT id, clinic_id, provider, display_name, is_active, config,
                   last_sync_at, last_sync_status, last_sync_message,
                   sync_interval_minutes, created_at, updated_at
            FROM clinic_integrations
            WHERE clinic_id = CAST(:cid AS UUID)
            ORDER BY created_at DESC
        """),
        {"cid": str(claims["clinic_id"])},
    )
    rows = result.fetchall()
    return [
        IntegrationConfigResponse(
            id=str(r[0]), clinic_id=str(r[1]), provider=r[2],
            display_name=r[3], is_active=r[4], has_session_cookie=_has_session_cookie(r[5]), last_sync_at=r[6],
            last_sync_status=r[7], last_sync_message=r[8],
            sync_interval_minutes=r[9], created_at=r[10], updated_at=r[11],
        )
        for r in rows
    ]


@router.post(
    "/config",
    response_model=IntegrationConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Yeni PMS entegrasyonu ekle",
)
async def create_integration(
    body: IntegrationConfigCreate,
    claims: dict = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
) -> IntegrationConfigResponse:
    await set_rls_context(db, claims["clinic_id"])
    import json
    result = await db.execute(
        text("""
            INSERT INTO clinic_integrations (clinic_id, provider, display_name, config, sync_interval_minutes)
            VALUES (CAST(:cid AS UUID), :provider, :display_name, CAST(:config AS JSONB), :interval)
            RETURNING id, clinic_id, provider, display_name, is_active, config,
                      last_sync_at, last_sync_status, last_sync_message,
                      sync_interval_minutes, created_at, updated_at
        """),
        {
            "cid": str(claims["clinic_id"]),
            "provider": body.provider,
            "display_name": body.display_name,
            "config": json.dumps(body.config),
            "interval": body.sync_interval_minutes,
        },
    )
    await db.commit()
    r = result.fetchone()
    return IntegrationConfigResponse(
        id=str(r[0]), clinic_id=str(r[1]), provider=r[2],
        display_name=r[3], is_active=r[4], has_session_cookie=_has_session_cookie(r[5]), last_sync_at=r[6],
        last_sync_status=r[7], last_sync_message=r[8],
        sync_interval_minutes=r[9], created_at=r[10], updated_at=r[11],
    )


@router.patch(
    "/config/{integration_id}",
    response_model=IntegrationConfigResponse,
    summary="Entegrasyon ayarlarını güncelle",
)
async def update_integration(
    integration_id: str,
    body: IntegrationConfigUpdate,
    claims: dict = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
) -> IntegrationConfigResponse:
    await set_rls_context(db, claims["clinic_id"])
    import json

    updates: list[str] = []
    params: dict = {"iid": integration_id, "cid": str(claims["clinic_id"])}

    if body.display_name is not None:
        updates.append("display_name = :display_name")
        params["display_name"] = body.display_name
    if body.config is not None:
        updates.append("config = CAST(:config AS JSONB)")
        params["config"] = json.dumps(body.config)
    if body.is_active is not None:
        updates.append("is_active = :is_active")
        params["is_active"] = body.is_active
    if body.sync_interval_minutes is not None:
        updates.append("sync_interval_minutes = :interval")
        params["interval"] = body.sync_interval_minutes

    if not updates:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Güncellenecek alan belirtilmedi")

    updates.append("updated_at = NOW()")
    # ⚠️ Safe — updates listesi sadece hardcoded string literals'tan oluşur
    # (bind parameters kullanılmıştır, user input doğrudan SQL'e enjekte EDİLMEMİŞTİR)
    set_clause = ", ".join(updates)

    result = await db.execute(
        text(f"""
            UPDATE clinic_integrations
            SET {set_clause}
            WHERE id = CAST(:iid AS UUID) AND clinic_id = CAST(:cid AS UUID)
            RETURNING id, clinic_id, provider, display_name, is_active, config,
                      last_sync_at, last_sync_status, last_sync_message,
                      sync_interval_minutes, created_at, updated_at
        """),
        params,
    )
    await db.commit()
    r = result.fetchone()
    if not r:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Entegrasyon bulunamadı")
    return IntegrationConfigResponse(
        id=str(r[0]), clinic_id=str(r[1]), provider=r[2],
        display_name=r[3], is_active=r[4], has_session_cookie=_has_session_cookie(r[5]), last_sync_at=r[6],
        last_sync_status=r[7], last_sync_message=r[8],
        sync_interval_minutes=r[9], created_at=r[10], updated_at=r[11],
    )


@router.delete(
    "/config/{integration_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Entegrasyonu sil",
)
async def delete_integration(
    integration_id: str,
    claims: dict = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    await db.execute(
        text("""
            DELETE FROM clinic_integrations
            WHERE id = CAST(:iid AS UUID) AND clinic_id = CAST(:cid AS UUID)
        """),
        {"iid": integration_id, "cid": str(claims["clinic_id"])},
    )
    await db.commit()


@router.patch(
    "/config/{integration_id}/session",
    response_model=IntegrationConfigResponse,
    summary="Oturum çerezini güncelle",
    description="Session Bridge: kullanıcının tarayıcı çerezlerini günceller.",
)
async def update_session_cookie(
    integration_id: str,
    body: SessionCookieUpdate,
    claims: dict = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
) -> IntegrationConfigResponse:
    await set_rls_context(db, claims["clinic_id"])
    result = await db.execute(
        text("""
            UPDATE clinic_integrations
            SET config = jsonb_set(COALESCE(config, '{}'::jsonb), '{session_cookie}', to_jsonb(CAST(:cookie AS text))),
                updated_at = NOW()
            WHERE id = CAST(:iid AS UUID) AND clinic_id = CAST(:cid AS UUID)
            RETURNING id, clinic_id, provider, display_name, is_active, config,
                      last_sync_at, last_sync_status, last_sync_message,
                      sync_interval_minutes, created_at, updated_at
        """),
        {
            "iid": integration_id,
            "cid": str(claims["clinic_id"]),
            "cookie": body.session_cookie,
        },
    )
    await db.commit()
    r = result.fetchone()
    if not r:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Entegrasyon bulunamadı")
    return IntegrationConfigResponse(
        id=str(r[0]), clinic_id=str(r[1]), provider=r[2],
        display_name=r[3], is_active=r[4], has_session_cookie=_has_session_cookie(r[5]), last_sync_at=r[6],
        last_sync_status=r[7], last_sync_message=r[8],
        sync_interval_minutes=r[9], created_at=r[10], updated_at=r[11],
    )


@router.get(
    "/config/{integration_id}/doctor-mappings",
    response_model=DoctorMappingResponse,
    summary="Harici hekimleri ve eşlemeleri getir",
)
async def get_doctor_mappings(
    integration_id: str,
    claims: dict = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
) -> DoctorMappingResponse:
    await set_rls_context(db, claims["clinic_id"])
    row = await db.execute(
        text("""
            SELECT provider, config
            FROM clinic_integrations
            WHERE id = CAST(:iid AS UUID) AND clinic_id = CAST(:cid AS UUID)
            LIMIT 1
        """),
        {"iid": integration_id, "cid": str(claims["clinic_id"])}
    )
    integration = row.fetchone()
    if not integration:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Entegrasyon bulunamadı")

    provider, config = integration
    adapter = get_adapter(provider, config or {})
    external_doctors = await adapter.fetch_doctors()
    mappings = _doctor_mappings(config)

    local_rows = (await db.execute(
        text("""
            SELECT d.id, d.full_name, d.specialty
            FROM doctors d
            INNER JOIN users u ON u.id = d.user_id
            WHERE d.clinic_id = CAST(:cid AS UUID)
              AND u.is_active = true
              AND u.role = 'doctor'
            ORDER BY d.full_name
        """),
        {"cid": str(claims["clinic_id"])}
    )).mappings().all()

    return DoctorMappingResponse(
        local_doctors=[
            LocalDoctorSummary(id=str(r["id"]), full_name=r["full_name"], specialty=r.get("specialty"))
            for r in local_rows
        ],
        external_doctors=[
            ExternalDoctorSummary(
                external_name=doctor.full_name,
                mapped_doctor_id=mappings.get(doctor.full_name),
            )
            for doctor in external_doctors
        ],
    )


@router.patch(
    "/config/{integration_id}/doctor-mappings",
    response_model=DoctorMappingResponse,
    summary="Harici hekim eşlemelerini kaydet",
)
async def update_doctor_mappings(
    integration_id: str,
    body: DoctorMappingUpdate,
    claims: dict = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
) -> DoctorMappingResponse:
    await set_rls_context(db, claims["clinic_id"])
    await db.execute(
        text("""
            UPDATE clinic_integrations
            SET config = jsonb_set(COALESCE(config, '{}'::jsonb), '{doctor_mappings}', CAST(:mappings AS JSONB)),
                updated_at = NOW()
            WHERE id = CAST(:iid AS UUID) AND clinic_id = CAST(:cid AS UUID)
        """),
        {
            "iid": integration_id,
            "cid": str(claims["clinic_id"]),
            "mappings": __import__("json").dumps(body.mappings),
        },
    )
    await db.commit()
    return await get_doctor_mappings(integration_id=integration_id, claims=claims, db=db)


# ═══════════════════════════════════════════════════════════
# Sync Endpoint'leri
# ═══════════════════════════════════════════════════════════

@router.post(
    "/sync",
    response_model=SyncResultResponse,
    summary="Manuel senkronizasyon başlat",
    description="Kliniğin aktif PMS entegrasyonundan verileri çeker ve yerel DB'ye yazar.",
)
async def trigger_sync(
    claims: dict = Depends(require_role("owner", "assistant")),
    db: AsyncSession = Depends(get_db),
) -> SyncResultResponse:
    await set_rls_context(db, claims["clinic_id"])
    result = await sync_clinic(claims["clinic_id"], db)
    return SyncResultResponse(
        provider=result.provider,
        patients_pulled=result.patients_pulled,
        patients_inserted=result.patients_inserted,
        appointments_pulled=result.appointments_pulled,
        appointments_inserted=result.appointments_inserted,
        doctors_pulled=result.doctors_pulled,
        errors=result.errors,
        synced_at=result.synced_at,
    )


@router.post(
    "/test-connection",
    response_model=TestConnectionResponse,
    summary="PMS bağlantısını test et",
)
async def test_connection(
    claims: dict = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
) -> TestConnectionResponse:
    await set_rls_context(db, claims["clinic_id"])
    row = await db.execute(
        text("""
            SELECT provider, config FROM clinic_integrations
            WHERE clinic_id = CAST(:cid AS UUID) AND is_active = true
            LIMIT 1
        """),
        {"cid": str(claims["clinic_id"])},
    )
    integration = row.fetchone()
    if not integration:
        return TestConnectionResponse(
            provider="none", success=False,
            message="Aktif entegrasyon bulunamadı",
        )
    provider, config = integration
    try:
        adapter = get_adapter(provider, config or {})
        ok = await adapter.test_connection()
        return TestConnectionResponse(
            provider=provider, success=ok,
            message="Bağlantı başarılı" if ok else "Bağlantı başarısız",
        )
    except Exception as exc:
        return TestConnectionResponse(
            provider=provider, success=False,
            message=f"Bağlantı hatası: {exc}",
        )
