"""
AI-Powered Owner Insights Service

Proaktif klinik analizi: klinik sahibine otomatik içgörü ve öneri kartları üretir.
Smarter model (gpt-4o-mini / gemini-2.5-pro) kullanır — dashboard AI'ı.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any
from urllib import request as urllib_request
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── Veri toplama ──────────────────────────────────────────────────────────────

async def _gather_clinic_metrics(db: AsyncSession) -> dict[str, Any]:
    """Clinic için tüm önemli metrikleri tek sorguda topla."""
    now = datetime.utcnow()

    # --- Randevu istatistikleri ---
    appt_row = (await db.execute(text("""
        SELECT
            COUNT(*)                                                        AS total_30d,
            COUNT(*) FILTER (WHERE status = 'completed')                    AS completed_30d,
            COUNT(*) FILTER (WHERE status = 'cancelled')                    AS cancelled_30d,
            COUNT(*) FILTER (WHERE status = 'no_show')                      AS no_show_30d,
            COUNT(*) FILTER (WHERE status IN ('scheduled','confirmed'))      AS upcoming,
            ROUND(
                COUNT(*) FILTER (WHERE status = 'cancelled')::numeric
                / NULLIF(COUNT(*), 0) * 100, 1
            )                                                               AS cancel_rate_pct,
            ROUND(
                COUNT(*) FILTER (WHERE status = 'no_show')::numeric
                / NULLIF(COUNT(*), 0) * 100, 1
            )                                                               AS noshow_rate_pct
        FROM appointments
        WHERE scheduled_at >= NOW() - INTERVAL '30 day'
    """))).mappings().first() or {}

    # Önceki ay karşılaştırması
    appt_prev = (await db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE status = 'completed') AS completed_prev
        FROM appointments
        WHERE scheduled_at >= NOW() - INTERVAL '60 day'
          AND scheduled_at <  NOW() - INTERVAL '30 day'
    """))).mappings().first() or {}

    # --- Bekle listesi ---
    waitlist_row = (await db.execute(text("""
        SELECT COUNT(*) FILTER (WHERE is_active = TRUE) AS active
        FROM waitlist
    """))).mappings().first() or {}

    # --- Doktor performansı ---
    doctor_rows = (await db.execute(text("""
        SELECT
            d.full_name,
            COUNT(a.id)                                                 AS total,
            COUNT(a.id) FILTER (WHERE a.status = 'completed')          AS completed,
            COUNT(a.id) FILTER (WHERE a.status = 'no_show')            AS no_shows,
            ROUND(
                COUNT(a.id) FILTER (WHERE a.status = 'no_show')::numeric
                / NULLIF(COUNT(a.id), 0) * 100, 1
            )                                                           AS noshow_pct
        FROM doctors d
        LEFT JOIN appointments a
               ON a.doctor_id = d.id
              AND a.scheduled_at >= NOW() - INTERVAL '30 day'
        GROUP BY d.id, d.full_name
        ORDER BY completed DESC
        LIMIT 10
    """))).mappings().all()

    # --- Envanter kritik stok ---
    inv_low = (await db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE quantity <= min_stock_level) AS low_stock,
            COUNT(*) FILTER (WHERE quantity = 0)                AS out_of_stock
        FROM inventory_items
    """))).mappings().first() or {}

    # --- Hasta geri bildirim ---
    feedback_row = (await db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE is_resolved = FALSE)             AS open_count,
            COUNT(*) FILTER (WHERE severity IN ('high','critical') 
                             AND is_resolved = FALSE)               AS urgent_count
        FROM patient_feedback
        WHERE created_at >= NOW() - INTERVAL '30 day'
    """))).mappings().first() or {}

    # --- Pik saat analizi ---
    peak_rows = (await db.execute(text("""
        SELECT
            EXTRACT(HOUR FROM scheduled_at)::int AS hour,
            COUNT(*)                              AS count
        FROM appointments
        WHERE scheduled_at >= NOW() - INTERVAL '30 day'
          AND status = 'completed'
        GROUP BY 1
        ORDER BY count DESC
        LIMIT 3
    """))).mappings().all()

    return {
        "appointments": {
            "total_30d":        int(appt_row.get("total_30d") or 0),
            "completed_30d":    int(appt_row.get("completed_30d") or 0),
            "cancelled_30d":    int(appt_row.get("cancelled_30d") or 0),
            "no_show_30d":      int(appt_row.get("no_show_30d") or 0),
            "upcoming":         int(appt_row.get("upcoming") or 0),
            "cancel_rate_pct":  float(appt_row.get("cancel_rate_pct") or 0),
            "noshow_rate_pct":  float(appt_row.get("noshow_rate_pct") or 0),
            "completed_prev":   int(appt_prev.get("completed_prev") or 0),
        },
        "waitlist": {
            "active": int(waitlist_row.get("active") or 0),
        },
        "doctors": [
            {
                "name":       r["full_name"],
                "total":      int(r["total"] or 0),
                "completed":  int(r["completed"] or 0),
                "no_shows":   int(r["no_shows"] or 0),
                "noshow_pct": float(r["noshow_pct"] or 0),
            }
            for r in doctor_rows
        ],
        "inventory": {
            "low_stock":    int(inv_low.get("low_stock") or 0),
            "out_of_stock": int(inv_low.get("out_of_stock") or 0),
        },
        "feedback": {
            "open_count":   int(feedback_row.get("open_count") or 0),
            "urgent_count": int(feedback_row.get("urgent_count") or 0),
        },
        "peak_hours": [
            {"hour": int(r["hour"]), "count": int(r["count"])}
            for r in peak_rows
        ],
    }


# ── AI Çağrısı ────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "Sen bir klinik yönetim danışmanısın. Sana verilen klinik istatistiklerini analiz ederek, "
    "klinik sahibine 3-6 adet kısa, eyleme dönüştürülebilir öneri/içgörü kartı üreteceksin.\n\n"
    "Her kart JSON nesnesi olacak ve şu alanları içerecek:\n"
    "- category: 'appointment' | 'revenue' | 'patient' | 'inventory' | 'performance'\n"
    "- title: Kısa başlık (maks 60 karakter)\n"
    "- description: Açıklama (maks 200 karakter), sayısal veri içermeli\n"
    "- severity: 'info' | 'warning' | 'critical'\n"
    "  * critical: acil müdahale gerektiriyor\n"
    "  * warning: dikkat edilmeli\n"
    "  * info: iyi haber veya iyileştirme fırsatı\n"
    "- metric_label: İlgili metrik adı (örn: 'İptal Oranı')\n"
    "- metric_value: Metrik değeri (örn: '%22.5')\n"
    "- action: Önerilen aksiyon (maks 100 karakter)\n\n"
    "Yanıtını JSON dizisi olarak ver: [ {...}, {...}, ... ]\n"
    "Sadece JSON, başka hiçbir şey yok, markdown code fence kullanma."
)


def _call_openai_insights(metrics_json: str) -> list[dict]:
    payload = {
        "model": settings.OPENAI_MODEL,
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": f"Klinik metrikleri:\n{metrics_json}"},
        ],
    }
    req = urllib_request.Request(
        url="https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        },
        method="POST",
    )
    with urllib_request.urlopen(req, timeout=settings.OPENAI_TIMEOUT_SECONDS) as resp:
        raw = resp.read().decode("utf-8")
    text_out = json.loads(raw)["choices"][0]["message"]["content"].strip()
    return json.loads(text_out)


def _call_gemini_insights(metrics_json: str) -> list[dict]:
    full_prompt = f"{_SYSTEM_PROMPT}\n\nKlinik metrikleri:\n{metrics_json}"
    model = (settings.GEMINI_MODEL or "gemini-2.5-pro").strip()
    if model.startswith("models/"):
        model = model.split("/", 1)[1]
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        f"?key={settings.GEMINI_API_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {"temperature": 0.3},
    }
    req = urllib_request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib_request.urlopen(req, timeout=settings.OPENAI_TIMEOUT_SECONDS) as resp:
        raw = resp.read().decode("utf-8")
    parsed = json.loads(raw)
    candidates = parsed.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini returned no candidates")
    parts = candidates[0].get("content", {}).get("parts", [])
    text_out = "\n".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
    return json.loads(text_out)


async def _call_ai_insights(metrics_json: str) -> tuple[list[dict], str]:
    """AI modelini çağır, insight kartlarını döndür."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    model_used = ""
    loop = asyncio.get_event_loop()

    try:
        if settings.AI_PROVIDER == "openai" and settings.OPENAI_API_KEY:
            model_used = settings.OPENAI_MODEL
            with ThreadPoolExecutor(max_workers=1) as pool:
                cards = await loop.run_in_executor(
                    pool, lambda: _call_openai_insights(metrics_json)
                )
        elif settings.AI_PROVIDER == "gemini" and settings.GEMINI_API_KEY:
            model_used = settings.GEMINI_MODEL
            with ThreadPoolExecutor(max_workers=1) as pool:
                cards = await loop.run_in_executor(
                    pool, lambda: _call_gemini_insights(metrics_json)
                )
        else:
            return [], ""
    except Exception as exc:
        logger.error("AI insights HTTP call failed: %s", exc)
        return [], ""

    if not isinstance(cards, list):
        cards = []
    return cards, model_used


# ── Fallback statik insight ───────────────────────────────────────────────────

def _build_rule_based_insights(metrics: dict, now_str: str) -> list[dict]:
    """AI yokken ya da API key eksikken sayasal eşiklerle temel uyarılar üret."""
    insights: list[dict] = []
    appt = metrics.get("appointments", {})
    inv  = metrics.get("inventory", {})
    fb   = metrics.get("feedback", {})

    cancel_pct = appt.get("cancel_rate_pct", 0)
    if cancel_pct >= 30:
        insights.append({
            "category": "appointment",
            "title": "Yüksek İptal Oranı",
            "description": f"Son 30 günde iptal oranınız %{cancel_pct:.1f}. Ortalama sektör eşiği %15.",
            "severity": "critical",
            "metric_label": "İptal Oranı",
            "metric_value": f"%{cancel_pct:.1f}",
            "action": "Randevu onay mesajlarını aktif edin, bekleme listesi otomasyonunu gözden geçirin.",
            "generated_at": now_str,
        })
    elif cancel_pct >= 15:
        insights.append({
            "category": "appointment",
            "title": "İptal Oranı Dikkat Düzeyinde",
            "description": f"Son 30 günde iptal oranınız %{cancel_pct:.1f}.",
            "severity": "warning",
            "metric_label": "İptal Oranı",
            "metric_value": f"%{cancel_pct:.1f}",
            "action": "Hasta hatırlatma sıklığını artırın.",
            "generated_at": now_str,
        })

    if inv.get("out_of_stock", 0) > 0:
        insights.append({
            "category": "inventory",
            "title": "Stokta Olmayan Ürünler",
            "description": f"{inv['out_of_stock']} ürün sıfır stokta.",
            "severity": "critical",
            "metric_label": "Stoksuz Ürün",
            "metric_value": str(inv["out_of_stock"]),
            "action": "Stok siparişi verin.",
            "generated_at": now_str,
        })
    elif inv.get("low_stock", 0) > 0:
        insights.append({
            "category": "inventory",
            "title": "Düşük Stok Uyarısı",
            "description": f"{inv['low_stock']} ürün minimum stok seviyesinde veya altında.",
            "severity": "warning",
            "metric_label": "Düşük Stoklu Ürün",
            "metric_value": str(inv["low_stock"]),
            "action": "Kritik malzemeleri sipariş edin.",
            "generated_at": now_str,
        })

    if fb.get("urgent_count", 0) > 0:
        insights.append({
            "category": "patient",
            "title": "Acil Hasta Şikayeti",
            "description": f"{fb['urgent_count']} adet yüksek/kritik seviyede çözümsüz hasta şikayeti var.",
            "severity": "critical",
            "metric_label": "Acil Şikayet",
            "metric_value": str(fb["urgent_count"]),
            "action": "Hasta şikayetlerini hemen inceleyin.",
            "generated_at": now_str,
        })

    wl_active = metrics.get("waitlist", {}).get("active", 0)
    if wl_active > 5:
        insights.append({
            "category": "appointment",
            "title": "Dolu Bekleme Listesi",
            "description": f"{wl_active} aktif hasta bekleme listesinde.",
            "severity": "info",
            "metric_label": "Bekleyen Hasta",
            "metric_value": str(wl_active),
            "action": "Mevcut iptalleri bekleme listesine otomatik teklif etmeyi etkinleştirin.",
            "generated_at": now_str,
        })

    return insights


# ── Ana fonksiyon ─────────────────────────────────────────────────────────────

async def generate_clinic_insights(
    clinic_id: UUID,
    db: AsyncSession,
) -> dict[str, Any]:
    """
    Klinik sahibi için proaktif AI içgörü kartları üret.

    Returns:
        {
            "insights": [ InsightCard.to_dict(), ... ],
            "generated_at": ISO timestamp,
            "ai_powered": bool,
            "model_used": str,
        }
    """
    now_str = datetime.utcnow().isoformat()

    metrics = await _gather_clinic_metrics(db)

    ai_powered = False
    model_used = ""
    insights_raw: list[dict] = []

    if settings.OPENAI_API_KEY or settings.GEMINI_API_KEY:
        try:
            metrics_json = json.dumps(metrics, ensure_ascii=False, indent=2)
            insights_raw, model_used = await _call_ai_insights(metrics_json)
            if insights_raw:
                ai_powered = True
                # Inject generated_at into each card
                for card in insights_raw:
                    card.setdefault("generated_at", now_str)
        except Exception as exc:
            logger.error("AI insights call failed, falling back: %s", exc)
            insights_raw = []

    if not insights_raw:
        insights_raw = _build_rule_based_insights(metrics, now_str)

    return {
        "insights": insights_raw,
        "generated_at": now_str,
        "ai_powered": ai_powered,
        "model_used": model_used,
        "metrics_summary": {
            "total_appointments_30d":  metrics["appointments"]["total_30d"],
            "cancel_rate_pct":         metrics["appointments"]["cancel_rate_pct"],
            "noshow_rate_pct":         metrics["appointments"]["noshow_rate_pct"],
            "active_waitlist":         metrics["waitlist"]["active"],
            "low_stock_items":         metrics["inventory"]["low_stock"],
            "urgent_feedback":         metrics["feedback"]["urgent_count"],
        },
    }


__all__ = ["generate_clinic_insights"]
