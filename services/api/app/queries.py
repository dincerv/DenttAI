"""
Ham SQL sorguları — Analytics Service.

Bu modül doğrudan asyncpg ile çalışır; SQLAlchemy ORM yerine
ham SQL kullanarak aggregation sorgularında maksimum performans sağlar.
Tüm sorgular RLS set edildikten SONRA aynı session üzerinde çalışır.
"""
from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# ── Recovered Revenue ──────────────────────────────────────────────────────


async def query_waitlist_fills(
    db: AsyncSession,
    clinic_id: UUID,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """
    Belirtilen tarih aralığında 'waitlist.match_found' bildirimi gönderilen
    randevuları getirir. Her kayıt 'kurtarılan' bir randevuyu temsil eder.

    Birleştirme mantığı:
      sent_messages.message_type = 'match_found'
      + metadata->>'cancelled_appointment_id' üzerinden iptal edilen randevunun
        doktoru ve branşı alınır.
      + Bildirim gönderilen hasta = beklistedeki hasta (sm.patient_id)
    """
    sql = text("""
        SELECT
            sm.id               AS message_id,
            sm.sent_at,
            a.id                AS original_appointment_id,
            d.specialty,
            p.full_name         AS patient_name
        FROM sent_messages sm
        JOIN appointments a
            ON a.id = (sm.metadata->>'cancelled_appointment_id')::UUID
        JOIN doctors d
            ON d.id = a.doctor_id
        JOIN patients p
            ON p.id = sm.patient_id
        WHERE sm.clinic_id    = :clinic_id
          AND sm.message_type = 'match_found'
          AND sm.sent_at      >= :start_date
          AND sm.sent_at      <  :end_date
        ORDER BY sm.sent_at DESC
    """)
    result = await db.execute(sql, {
        "clinic_id": str(clinic_id),
        "start_date": start_date,
        "end_date": end_date,
    })
    return [dict(row._mapping) for row in result.fetchall()]


# ── Appointment Stats ──────────────────────────────────────────────────────


async def query_appointment_stats(
    db: AsyncSession,
    clinic_id: UUID,
    start_date: date,
    end_date: date,
    doctor_id: UUID | None = None,
) -> dict:
    """Toplam, branş bazlı dağılım ve durum sayıları."""
    doctor_filter = "AND doctor_id = :doctor_id" if doctor_id else ""
    sql = text(f"""
        SELECT
            COUNT(*)                                                    AS total,
            COUNT(*) FILTER (WHERE status = 'cancelled')               AS cancelled,
            COUNT(*) FILTER (WHERE status = 'no_show')                 AS no_show,
            COUNT(*) FILTER (WHERE status = 'completed')               AS completed,
            COUNT(*) FILTER (WHERE status IN ('scheduled','confirmed')) AS upcoming
        FROM appointments
        WHERE clinic_id    = :clinic_id
          AND scheduled_at >= :start_date
          AND scheduled_at <  :end_date
          {doctor_filter}
    """)
    params: dict = {
        "clinic_id": str(clinic_id),
        "start_date": start_date,
        "end_date": end_date,
    }
    if doctor_id:
        params["doctor_id"] = str(doctor_id)
    row = (await db.execute(sql, params)).fetchone()
    return dict(row._mapping) if row else {}


async def query_appointments_by_specialty(
    db: AsyncSession,
    clinic_id: UUID,
    start_date: date,
    end_date: date,
    doctor_id: UUID | None = None,
) -> list[dict]:
    """Branş bazlı randevu sayıları."""
    doctor_filter = "AND a.doctor_id = :doctor_id" if doctor_id else ""
    sql = text(f"""
        SELECT
            d.specialty,
            COUNT(*)                                         AS total,
            COUNT(*) FILTER (WHERE a.status = 'cancelled')  AS cancelled,
            COUNT(*) FILTER (WHERE a.status = 'no_show')    AS no_show,
            COUNT(*) FILTER (WHERE a.status = 'completed')  AS completed
        FROM appointments a
        JOIN doctors d ON d.id = a.doctor_id
        WHERE a.clinic_id    = :clinic_id
          AND a.scheduled_at >= :start_date
          AND a.scheduled_at <  :end_date
          {doctor_filter}
        GROUP BY d.specialty
        ORDER BY total DESC
    """)
    params: dict = {
        "clinic_id": str(clinic_id),
        "start_date": start_date,
        "end_date": end_date,
    }
    if doctor_id:
        params["doctor_id"] = str(doctor_id)
    result = await db.execute(sql, params)
    return [dict(row._mapping) for row in result.fetchall()]


# ── Inventory Waste Report ─────────────────────────────────────────────────


async def query_high_waste_materials(
    db: AsyncSession,
    clinic_id: UUID,
) -> list[dict]:
    """is_high_waste = TRUE olan tüm cycle_material kayıtları."""
    sql = text("""
        SELECT
            id,
            qr_id,
            name,
            category,
            start_date,
            end_date,
            expected_lifespan,
            actual_lifespan,
            end_reason,
            waste_note
        FROM cycle_materials
        WHERE clinic_id    = :clinic_id
          AND is_high_waste = TRUE
        ORDER BY created_at DESC
    """)
    result = await db.execute(sql, {"clinic_id": str(clinic_id)})
    return [dict(row._mapping) for row in result.fetchall()]


async def query_waste_by_category(
    db: AsyncSession,
    clinic_id: UUID,
) -> list[dict]:
    """Kategori bazlı israf özeti."""
    sql = text("""
        SELECT
            COALESCE(category, 'Kategori Yok')  AS category,
            COUNT(*)                             AS total_cycles,
            COUNT(*) FILTER (WHERE is_high_waste) AS high_waste_count,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE is_high_waste)
                / NULLIF(COUNT(*), 0), 1
            )                                    AS waste_rate_pct,
            ROUND(AVG(actual_lifespan), 1)       AS avg_actual_lifespan,
            ROUND(AVG(expected_lifespan), 1)     AS avg_expected_lifespan
        FROM cycle_materials
        WHERE clinic_id = :clinic_id
          AND end_date IS NOT NULL
        GROUP BY category
        ORDER BY high_waste_count DESC
    """)
    result = await db.execute(sql, {"clinic_id": str(clinic_id)})
    return [dict(row._mapping) for row in result.fetchall()]


# ── Doctor Performance ─────────────────────────────────────────────────────


async def query_doctor_performance(
    db: AsyncSession,
    clinic_id: UUID,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """
    Hekim başına:
      - Toplam randevu
      - Tamamlanan randevu
      - İptal oranı
      - No-show oranı
      - Tekrar gelen hasta sayısı (birden fazla randevu olan hasta)
    """
    sql = text("""
        WITH appts AS (
            SELECT
                d.id            AS doctor_id,
                d.full_name     AS doctor_name,
                d.specialty,
                a.id            AS appt_id,
                a.patient_id,
                a.status
            FROM appointments a
            JOIN doctors d ON d.id = a.doctor_id
            WHERE a.clinic_id    = :clinic_id
              AND a.scheduled_at >= :start_date
              AND a.scheduled_at <  :end_date
        ),
        loyal AS (
            SELECT doctor_id, COUNT(DISTINCT patient_id) AS loyal_patients
            FROM (
                SELECT doctor_id, patient_id
                FROM appts
                GROUP BY doctor_id, patient_id
                HAVING COUNT(*) > 1
            ) sub
            GROUP BY doctor_id
        )
        SELECT
            appts.doctor_id,
            appts.doctor_name,
            appts.specialty,
            COUNT(appts.appt_id)                                              AS total,
            COUNT(appts.appt_id) FILTER (WHERE appts.status = 'completed')   AS completed,
            COUNT(appts.appt_id) FILTER (WHERE appts.status = 'cancelled')   AS cancelled,
            COUNT(appts.appt_id) FILTER (WHERE appts.status = 'no_show')     AS no_show,
            ROUND(
                100.0 * COUNT(appts.appt_id) FILTER (WHERE appts.status = 'cancelled')
                / NULLIF(COUNT(appts.appt_id), 0), 1
            )                                                                  AS cancel_rate_pct,
            ROUND(
                100.0 * COUNT(appts.appt_id) FILTER (WHERE appts.status = 'completed')
                / NULLIF(COUNT(appts.appt_id), 0), 1
            )                                                                  AS completion_rate_pct,
            COALESCE(loyal.loyal_patients, 0)                                  AS loyal_patient_count
        FROM appts
        LEFT JOIN loyal ON loyal.doctor_id = appts.doctor_id
        GROUP BY appts.doctor_id, appts.doctor_name, appts.specialty, loyal.loyal_patients
        ORDER BY completion_rate_pct DESC NULLS LAST
    """)
    result = await db.execute(sql, {
        "clinic_id": str(clinic_id),
        "start_date": start_date,
        "end_date": end_date,
    })
    return [dict(row._mapping) for row in result.fetchall()]


# ── Expiring Cycles (Süresi Dolmak Üzere) ────────────────────────────────


async def query_expiring_cycles(
    db: AsyncSession,
    clinic_id: UUID,
) -> list[dict]:
    """
    Beklenen ömrünün %90'ını doldurmuş, hala aktif olan QR malzeme kayıtları.
    actual_lifespan / expected_lifespan >= 0.9 kriter olarak kullanılır.
    """
    sql = text("""
        SELECT
            id,
            qr_id,
            shelf_code,
            name,
            category,
            start_date,
            expected_lifespan,
            actual_lifespan,
            ROUND(
                100.0 * actual_lifespan / NULLIF(expected_lifespan, 0), 1
            ) AS lifespan_used_pct
        FROM cycle_materials
        WHERE clinic_id       = :clinic_id
          AND is_active       = TRUE
          AND expected_lifespan IS NOT NULL
          AND actual_lifespan  IS NOT NULL
          AND actual_lifespan::float / NULLIF(expected_lifespan, 0) >= 0.9
        ORDER BY lifespan_used_pct DESC
    """)
    result = await db.execute(sql, {"clinic_id": str(clinic_id)})
    return [dict(row._mapping) for row in result.fetchall()]


# ── Treatment Aggregator (Tedavi Sayaçları) ───────────────────────────────


async def query_treatment_counts(
    db: AsyncSession,
    clinic_id: UUID,
    start_date: date,
    end_date: date,
    doctor_id: UUID | None = None,
    group_by: str = "month",   # day | week | month | year
) -> list[dict]:
    """
    Randevu notlarından tedavi türlerini gruplandırır.
    Dönem (Günlük/Haftalık/Aylık/Yıllık) bazında sayısal özet döner.
    """
    # group_by değerini whitelist ile doğrula
    valid_groups = {"day", "week", "month", "year"}
    if group_by not in valid_groups:
        group_by = "month"

    doctor_filter = "AND doctor_id = :doctor_id" if doctor_id else ""
    params: dict = {
        "clinic_id": str(clinic_id),
        "start_date": start_date,
        "end_date": end_date,
    }
    if doctor_id:
        params["doctor_id"] = str(doctor_id)

    sql = text(f"""
        SELECT
            DATE_TRUNC('{group_by}', scheduled_at)::date        AS period,
            COUNT(*) FILTER (WHERE status = 'completed')        AS total_completed,
            COUNT(*) FILTER (WHERE status = 'completed' AND treatment_type = 'dolgu')       AS dolgu,
            COUNT(*) FILTER (WHERE status = 'completed' AND treatment_type = 'kanal')       AS kanal,
            COUNT(*) FILTER (WHERE status = 'completed' AND treatment_type = 'implant')     AS implant,
            COUNT(*) FILTER (WHERE status = 'completed' AND treatment_type = 'kron')        AS kron,
            COUNT(*) FILTER (WHERE status = 'completed' AND treatment_type = 'cekim')       AS cekim,
            COUNT(*) FILTER (WHERE status = 'completed' AND treatment_type = 'protez')      AS protez,
            COUNT(*) FILTER (WHERE status = 'completed' AND treatment_type = 'ortodonti')   AS ortodonti,
            COUNT(*) FILTER (WHERE status = 'completed' AND treatment_type = 'temizlik')    AS temizlik,
            COUNT(*) FILTER (WHERE status = 'completed' AND treatment_type = 'beyazlatma')  AS beyazlatma
        FROM appointments
        WHERE clinic_id    = :clinic_id
          AND scheduled_at >= :start_date
          AND scheduled_at <  :end_date
          {doctor_filter}
        GROUP BY DATE_TRUNC('{group_by}', scheduled_at)
        ORDER BY period ASC
    """)
    result = await db.execute(sql, params)
    return [dict(row._mapping) for row in result.fetchall()]


async def query_treatment_totals(
    db: AsyncSession,
    clinic_id: UUID,
    start_date: date,
    end_date: date,
    doctor_id: UUID | None = None,
) -> dict:
    """
    Dönem içi kümülatif tedavi toplamları (grafik header kartları için).
    """
    doctor_filter = "AND doctor_id = :doctor_id" if doctor_id else ""
    params: dict = {
        "clinic_id": str(clinic_id),
        "start_date": start_date,
        "end_date": end_date,
    }
    if doctor_id:
        params["doctor_id"] = str(doctor_id)

    sql = text(f"""
        SELECT
            COUNT(*) FILTER (WHERE status = 'completed') AS total_completed,
            COUNT(*) FILTER (WHERE status = 'completed' AND treatment_type = 'dolgu')       AS dolgu,
            COUNT(*) FILTER (WHERE status = 'completed' AND treatment_type = 'kanal')       AS kanal,
            COUNT(*) FILTER (WHERE status = 'completed' AND treatment_type = 'implant')     AS implant,
            COUNT(*) FILTER (WHERE status = 'completed' AND treatment_type = 'kron')        AS kron,
            COUNT(*) FILTER (WHERE status = 'completed' AND treatment_type = 'cekim')       AS cekim,
            COUNT(*) FILTER (WHERE status = 'completed' AND treatment_type = 'protez')      AS protez,
            COUNT(*) FILTER (WHERE status = 'completed' AND treatment_type = 'ortodonti')   AS ortodonti,
            COUNT(*) FILTER (WHERE status = 'completed' AND treatment_type = 'temizlik')    AS temizlik
        FROM appointments
        WHERE clinic_id    = :clinic_id
          AND scheduled_at >= :start_date
          AND scheduled_at <  :end_date
          {doctor_filter}
    """)
    row = (await db.execute(sql, params)).fetchone()
    return dict(row._mapping) if row else {}


# ── Per-Doctor Treatment Breakdown (Sahip görünümü) ───────────────────────

async def query_treatments_by_doctor(
    db: AsyncSession,
    clinic_id: UUID,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """
    Klinik içindeki her hekim için tedavi türü bazlı sayılar.
    Sadece sahip (owner) rolü için; tüm doktorları tek sorguda döner.
    """
    sql = text("""
        SELECT
            d.id            AS doctor_id,
            d.full_name     AS doctor_name,
            d.specialty,
            COUNT(*) FILTER (WHERE a.status = 'completed')                              AS total_completed,
            COUNT(*) FILTER (WHERE a.status = 'completed' AND a.treatment_type = 'dolgu')       AS dolgu,
            COUNT(*) FILTER (WHERE a.status = 'completed' AND a.treatment_type = 'kanal')       AS kanal,
            COUNT(*) FILTER (WHERE a.status = 'completed' AND a.treatment_type = 'implant')     AS implant,
            COUNT(*) FILTER (WHERE a.status = 'completed' AND a.treatment_type = 'kron')        AS kron,
            COUNT(*) FILTER (WHERE a.status = 'completed' AND a.treatment_type = 'cekim')       AS cekim,
            COUNT(*) FILTER (WHERE a.status = 'completed' AND a.treatment_type = 'protez')      AS protez,
            COUNT(*) FILTER (WHERE a.status = 'completed' AND a.treatment_type = 'ortodonti')   AS ortodonti,
            COUNT(*) FILTER (WHERE a.status = 'completed' AND a.treatment_type = 'temizlik')    AS temizlik
        FROM doctors d
        LEFT JOIN appointments a
            ON a.doctor_id  = d.id
           AND a.clinic_id  = :clinic_id
           AND a.scheduled_at >= :start_date
           AND a.scheduled_at <  :end_date
        WHERE d.clinic_id = :clinic_id
        GROUP BY d.id, d.full_name, d.specialty
        ORDER BY total_completed DESC, d.full_name ASC
    """)
    result = await db.execute(sql, {
        "clinic_id": str(clinic_id),
        "start_date": start_date,
        "end_date": end_date,
    })
    return [dict(row._mapping) for row in result.fetchall()]


async def query_inventory_category_summary(
    db: AsyncSession,
    clinic_id: UUID,
) -> list[dict]:
    """Kategori bazında stok özeti — pasta grafik için."""
    sql = text("""
        SELECT
            COALESCE(category, 'Kategorizasyon Yok') AS category,
            COUNT(*)                                  AS item_count,
            COUNT(*) FILTER (WHERE quantity <= min_stock_level) AS low_stock_count,
            ROUND(COALESCE(SUM(quantity * cost_per_unit), 0)::numeric, 2)::float AS total_value,
            ROUND(COALESCE(SUM(quantity), 0)::numeric, 2)::float AS total_quantity
        FROM inventory_items
        WHERE clinic_id = :clinic_id
        GROUP BY category
        ORDER BY total_value DESC NULLS LAST, item_count DESC
    """)
    result = await db.execute(sql, {"clinic_id": str(clinic_id)})
    return [dict(row._mapping) for row in result.fetchall()]


# ── Inventory Consumption (Hareket Geçmişi) ───────────────────────────────

async def query_inventory_consumption(
    db: AsyncSession,
    clinic_id: UUID,
    start_date: date,
    end_date: date,
    group_by: str = "month",
) -> list[dict]:
    """
    Dönem bazlı stok hareketleri.
    delta > 0 = alım/ekleme, delta < 0 = tüketim/çıkış.
    Her dönem için item bazında toplam alım ve tüketim döner.
    """
    valid_groups = {"day", "week", "month", "year"}
    if group_by not in valid_groups:
        group_by = "month"

    sql = text(f"""
        SELECT
            DATE_TRUNC('{group_by}', adj.created_at)::date  AS period,
            ii.name                                          AS item_name,
            COALESCE(ii.category, 'Kategorizasyon Yok')     AS category,
            ii.unit,
            ROUND(SUM(adj.delta) FILTER (WHERE adj.delta > 0)::numeric, 2)::float
                                                             AS total_in,
            ROUND(ABS(SUM(adj.delta) FILTER (WHERE adj.delta < 0))::numeric, 2)::float
                                                             AS total_out,
            ROUND(SUM(adj.delta)::numeric, 2)::float         AS net_delta,
            COUNT(*) FILTER (WHERE adj.delta > 0)            AS in_count,
            COUNT(*) FILTER (WHERE adj.delta < 0)            AS out_count
        FROM inventory_adjustments adj
        JOIN inventory_items ii
            ON ii.id = adj.item_id
        WHERE adj.clinic_id   = :clinic_id
          AND adj.created_at >= :start_date
          AND adj.created_at <  :end_date
        GROUP BY
            DATE_TRUNC('{group_by}', adj.created_at),
            ii.name, ii.category, ii.unit
        ORDER BY period ASC, total_out DESC NULLS LAST
    """)
    result = await db.execute(sql, {
        "clinic_id": str(clinic_id),
        "start_date": start_date,
        "end_date": end_date,
    })
    return [dict(row._mapping) for row in result.fetchall()]


async def query_inventory_consumption_totals(
    db: AsyncSession,
    clinic_id: UUID,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Dönem toplamı — kalem bazında en çok tüketilen/alınan."""
    sql = text("""
        SELECT
            ii.name                                          AS item_name,
            COALESCE(ii.category, 'Kategorizasyon Yok')     AS category,
            ii.unit,
            ROUND(COALESCE(SUM(adj.delta) FILTER (WHERE adj.delta > 0), 0)::numeric, 2)::float
                                                             AS total_in,
            ROUND(ABS(COALESCE(SUM(adj.delta) FILTER (WHERE adj.delta < 0), 0))::numeric, 2)::float
                                                             AS total_out,
            ROUND(COALESCE(SUM(adj.delta), 0)::numeric, 2)::float
                                                             AS net_delta,
            COUNT(*) FILTER (WHERE adj.delta > 0)            AS in_count,
            COUNT(*) FILTER (WHERE adj.delta < 0)            AS out_count
        FROM inventory_adjustments adj
        JOIN inventory_items ii
            ON ii.id = adj.item_id
        WHERE adj.clinic_id   = :clinic_id
          AND adj.created_at >= :start_date
          AND adj.created_at <  :end_date
        GROUP BY ii.name, ii.category, ii.unit
        ORDER BY total_out DESC NULLS LAST, total_in DESC NULLS LAST
    """)
    result = await db.execute(sql, {
        "clinic_id": str(clinic_id),
        "start_date": start_date,
        "end_date": end_date,
    })
    return [dict(row._mapping) for row in result.fetchall()]
