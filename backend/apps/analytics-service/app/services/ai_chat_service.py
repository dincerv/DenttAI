from __future__ import annotations

import asyncio
import json
import os
import re
from urllib import request as urllib_request
from typing import TypedDict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings


class UsageMeta(TypedDict):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float


MODEL_PRICING_PER_1M: dict[str, tuple[float, float]] = {
    # (input_usd, output_usd) per 1M tokens
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1-mini": (0.40, 1.60),
    "gemini-1.5-flash": (0.35, 1.05),
    "gemini-1.5-pro": (3.50, 10.50),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.30, 2.50),
}


def _estimate_tokens(text_value: str) -> int:
    if not text_value:
        return 0
    return max(1, len(text_value) // 4)


def _estimate_cost_usd(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    input_cost, output_cost = MODEL_PRICING_PER_1M.get(model_name, (0.0, 0.0))
    usd = (prompt_tokens / 1_000_000) * input_cost + (completion_tokens / 1_000_000) * output_cost
    return round(usd, 6)


def _safe_float(value: object) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _env_first(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return default


def _resolve_provider() -> str:
    return _env_first(
        "ANALYTICS_AI_PROVIDER",
        "AI_PROVIDER",
        default=getattr(settings, "AI_PROVIDER", "gemini"),
    ).lower()


def _resolve_gemini_api_key() -> str:
    return _env_first(
        "ANALYTICS_GEMINI_API_KEY",
        "GEMINI_API_KEY",
        default=getattr(settings, "GEMINI_API_KEY", ""),
    )


def _resolve_openai_api_key() -> str:
    return _env_first(
        "ANALYTICS_OPENAI_API_KEY",
        "OPENAI_API_KEY",
        default=getattr(settings, "OPENAI_API_KEY", ""),
    )


async def _build_context(db: AsyncSession) -> dict:
    appointments_row = (
        await db.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total_30d,
                    COUNT(*) FILTER (WHERE status = 'completed') AS completed_30d,
                    COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled_30d,
                    COUNT(*) FILTER (WHERE status = 'no_show') AS no_show_30d,
                    COUNT(*) FILTER (WHERE status IN ('scheduled', 'confirmed')) AS upcoming_30d
                FROM appointments
                WHERE scheduled_at >= NOW() - INTERVAL '30 day'
                """
            )
        )
    ).mappings().first() or {}

    waitlist_row = (
        await db.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (WHERE is_active = TRUE) AS active_waitlist,
                    COUNT(*) AS total_waitlist,
                    COALESCE(AVG(priority), 0) AS avg_priority
                FROM waitlist
                """
            )
        )
    ).mappings().first() or {}

    inventory_row = (
        await db.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total_items,
                    COUNT(*) FILTER (WHERE quantity <= min_stock_level) AS low_stock_items,
                    COALESCE(SUM(quantity * COALESCE(cost_per_unit, 0)), 0) AS stock_value
                FROM inventory_items
                """
            )
        )
    ).mappings().first() or {}

    low_stock_rows = (
        await db.execute(
            text(
                """
                SELECT name, quantity, min_stock_level, unit
                FROM inventory_items
                WHERE quantity <= min_stock_level
                ORDER BY (min_stock_level - quantity) DESC
                LIMIT 8
                """
            )
        )
    ).mappings().all()

    top_stock_rows = (
        await db.execute(
            text(
                """
                SELECT name, quantity, min_stock_level, unit
                FROM inventory_items
                ORDER BY quantity DESC, name ASC
                LIMIT 8
                """
            )
        )
    ).mappings().all()

    doctor_treatments = (
        await db.execute(
            text(
                """
                SELECT
                    d.full_name AS doctor_name,
                    COALESCE(a.treatment_type, 'belirtilmemis') AS treatment_type,
                    COUNT(*) AS count
                FROM appointments a
                JOIN doctors d ON d.id = a.doctor_id
                WHERE a.status = 'completed'
                  AND a.scheduled_at >= NOW() - INTERVAL '30 day'
                GROUP BY d.full_name, COALESCE(a.treatment_type, 'belirtilmemis')
                ORDER BY count DESC
                LIMIT 20
                """
            )
        )
    ).mappings().all()

    patient_treatments = (
        await db.execute(
            text(
                """
                SELECT
                    p.full_name AS patient_name,
                    COALESCE(a.treatment_type, 'belirtilmemis') AS treatment_type,
                    COUNT(*) AS count
                FROM appointments a
                JOIN patients p ON p.id = a.patient_id
                WHERE a.status = 'completed'
                  AND a.scheduled_at >= NOW() - INTERVAL '30 day'
                GROUP BY p.full_name, COALESCE(a.treatment_type, 'belirtilmemis')
                ORDER BY count DESC
                LIMIT 20
                """
            )
        )
    ).mappings().all()

    tomorrow_row = (
        await db.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE status IN ('scheduled', 'confirmed')) AS upcoming,
                    COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                    COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled,
                    COUNT(*) FILTER (WHERE status = 'no_show') AS no_show
                FROM appointments
                WHERE scheduled_at >= date_trunc('day', NOW()) + INTERVAL '1 day'
                  AND scheduled_at < date_trunc('day', NOW()) + INTERVAL '2 day'
                """
            )
        )
    ).mappings().first() or {}

    today_row = (
        await db.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE status IN ('scheduled', 'confirmed')) AS upcoming,
                    COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                    COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled,
                    COUNT(*) FILTER (WHERE status = 'no_show') AS no_show
                FROM appointments
                WHERE scheduled_at >= date_trunc('day', NOW())
                  AND scheduled_at < date_trunc('day', NOW()) + INTERVAL '1 day'
                """
            )
        )
    ).mappings().first() or {}

    return {
        "appointments_30d": {
            "total": int(appointments_row.get("total_30d", 0) or 0),
            "completed": int(appointments_row.get("completed_30d", 0) or 0),
            "cancelled": int(appointments_row.get("cancelled_30d", 0) or 0),
            "no_show": int(appointments_row.get("no_show_30d", 0) or 0),
            "upcoming": int(appointments_row.get("upcoming_30d", 0) or 0),
        },
        "appointments_today": {
            "total": int(today_row.get("total", 0) or 0),
            "upcoming": int(today_row.get("upcoming", 0) or 0),
            "completed": int(today_row.get("completed", 0) or 0),
            "cancelled": int(today_row.get("cancelled", 0) or 0),
            "no_show": int(today_row.get("no_show", 0) or 0),
        },
        "appointments_tomorrow": {
            "total": int(tomorrow_row.get("total", 0) or 0),
            "upcoming": int(tomorrow_row.get("upcoming", 0) or 0),
            "completed": int(tomorrow_row.get("completed", 0) or 0),
            "cancelled": int(tomorrow_row.get("cancelled", 0) or 0),
            "no_show": int(tomorrow_row.get("no_show", 0) or 0),
        },
        "waitlist": {
            "active": int(waitlist_row.get("active_waitlist", 0) or 0),
            "total": int(waitlist_row.get("total_waitlist", 0) or 0),
            "avg_priority": round(_safe_float(waitlist_row.get("avg_priority")), 2),
        },
        "inventory": {
            "total_items": int(inventory_row.get("total_items", 0) or 0),
            "low_stock_items": int(inventory_row.get("low_stock_items", 0) or 0),
            "stock_value": round(_safe_float(inventory_row.get("stock_value")), 2),
            "critical_items": [dict(r) for r in low_stock_rows],
            "top_stock_items": [dict(r) for r in top_stock_rows],
        },
        "doctor_treatments_top": [dict(r) for r in doctor_treatments],
        "patient_treatments_top": [dict(r) for r in patient_treatments],
    }


def _normalize(text_value: str) -> str:
    value = (text_value or "").strip().lower()
    value = value.replace("\u0131", "i")
    value = value.replace("\u0130", "i")
    value = value.replace("\u00e7", "c").replace("\u00c7", "c")
    value = value.replace("\u011f", "g").replace("\u011e", "g")
    value = value.replace("\u00f6", "o").replace("\u00d6", "o")
    value = value.replace("\u015f", "s").replace("\u015e", "s")
    value = value.replace("\u00fc", "u").replace("\u00dc", "u")
    return value


def _infer_intent(question: str) -> str:
    q = _normalize(question)

    if re.fullmatch(r"[a-z]{1,4}", q):
        return "unknown"

    if any(k in q for k in ("selam", "merhaba", "hello", "hi")):
        return "greeting"

    if any(k in q for k in ("hangi malzemeden alm", "ne almal", "satin al", "siparis", "stok al")):
        return "inventory_buy"

    if any(k in q for k in ("en cok", "daha cok var", "stokta en fazla", "en fazla", "en yuksek stok")):
        return "inventory_most"

    if ("yarin" in q or "yarin " in q) and ("randevu" in q) and any(k in q for k in ("kac", "sayi", "sayisi", "var")):
        return "appointment_tomorrow"

    if ("bugun" in q) and ("randevu" in q) and any(k in q for k in ("kac", "sayi", "sayisi", "var")):
        return "appointment_today"

    if any(k in q for k in ("kac randevu", "randevu sayisi", "toplam randevu")):
        return "appointment_count"

    if any(k in q for k in ("iptal", "no-show", "noshow", "gelmedi", "gelmeme", "aksiyon oner")):
        return "cancel_noshow"

    if any(k in q for k in ("yedek liste", "waitlist")):
        return "waitlist"

    if any(k in q for k in ("hekim", "doktor", "tedavi dagilim", "performans")):
        return "doctor_treatment"

    return "summary"


def _rate(value: int, total: int) -> float:
    return (value / total * 100.0) if total else 0.0


def _rule_based_answer(question: str, context: dict) -> str:
    ap = context["appointments_30d"]
    ap_today = context["appointments_today"]
    ap_tomorrow = context["appointments_tomorrow"]
    wl = context["waitlist"]
    inv = context["inventory"]
    cancel_rate = _rate(ap["cancelled"], ap["total"])
    no_show_rate = _rate(ap["no_show"], ap["total"])
    completion_rate = _rate(ap["completed"], ap["total"])
    intent = _infer_intent(question)

    top_stock = inv.get("top_stock_items", [])
    critical = inv.get("critical_items", [])

    if intent == "greeting":
        return (
            "Merhaba. Klinik durumunu kisaca ozetleyeyim:\n"
            f"- Son 30 gunde {ap['total']} randevu var (tamamlanan {ap['completed']}, iptal {ap['cancelled']}, no-show {ap['no_show']}).\n"
            f"- Envanterde {inv['total_items']} urun var, bunlarin {inv['low_stock_items']} tanesi kritik seviyede.\n"
            "Isterseniz stok, randevu, yedek liste veya hekim performansi odakli detay analiz yapabilirim."
        )

    if intent == "inventory_most":
        if not top_stock:
            return "Envanter verisi bulunamadi."
        top = top_stock[0]
        top3 = top_stock[:3]
        top3_text = ", ".join(
            f"{r.get('name')} ({r.get('quantity')} {r.get('unit')})" for r in top3
        )
        return (
            f"Stokta en fazla bulunan malzeme: {top.get('name')} ({top.get('quantity')} {top.get('unit')}).\n"
            f"Ilk 3: {top3_text}."
        )

    if intent == "inventory_buy":
        if not critical:
            return "Su an kritik seviyede malzeme gorunmuyor; acil satin alma ihtiyaci yok."
        ranked: list[tuple[int, dict]] = []
        for row in critical:
            gap = int((_safe_float(row.get("min_stock_level")) - _safe_float(row.get("quantity"))))
            ranked.append((gap, row))
        ranked.sort(key=lambda x: x[0], reverse=True)
        top_buy = ranked[:3]
        lines = ["Oncelikli satin alma listesi:"]
        for gap, row in top_buy:
            lines.append(
                f"- {row.get('name')}: mevcut {row.get('quantity')} {row.get('unit')}, min {row.get('min_stock_level')} (onerilen ek alim: ~{max(gap, 1)} {row.get('unit')})."
            )
        return "\n".join(lines)

    if intent == "appointment_count":
        return (
            f"Son 30 gunde toplam {ap['total']} randevu var.\n"
            f"- Tamamlanan: {ap['completed']} (%{completion_rate:.1f})\n"
            f"- Iptal: {ap['cancelled']} (%{cancel_rate:.1f})\n"
            f"- No-show: {ap['no_show']} (%{no_show_rate:.1f})\n"
            f"- Yaklasan: {ap['upcoming']}"
        )

    if intent == "appointment_tomorrow":
        return (
            "Yarin randevu ozeti:\n"
            f"- Toplam: {ap_tomorrow['total']}\n"
            f"- Planli/Onayli: {ap_tomorrow['upcoming']}\n"
            f"- Tamamlanan: {ap_tomorrow['completed']}\n"
            f"- Iptal: {ap_tomorrow['cancelled']}\n"
            f"- No-show: {ap_tomorrow['no_show']}"
        )

    if intent == "appointment_today":
        return (
            "Bugun randevu ozeti:\n"
            f"- Toplam: {ap_today['total']}\n"
            f"- Planli/Onayli: {ap_today['upcoming']}\n"
            f"- Tamamlanan: {ap_today['completed']}\n"
            f"- Iptal: {ap_today['cancelled']}\n"
            f"- No-show: {ap_today['no_show']}"
        )

    if intent == "cancel_noshow":
        lines = [
            "Iptal/No-show analizi (son 30 gun):",
            f"- Iptal orani: %{cancel_rate:.1f}",
            f"- No-show orani: %{no_show_rate:.1f}",
        ]
        if cancel_rate == 0 and no_show_rate == 0:
            lines.append("- Sistemde iptal/no-show kaydi gorunmuyor. Veri senkronu veya status map kontrolu yapmanizi oneririm.")
        elif cancel_rate + no_show_rate >= 20:
            lines.append("- Oran yuksek. Yedek listeyi otomatiklestirin, 24 saat once hatirlatma ve ayni gun teyit akisi ekleyin.")
        else:
            lines.append("- Oran yonetilebilir seviyede. Kritik gun/saat bazli segment analizine gecerek daha fazla dusurebilirsiniz.")
        return "\n".join(lines)

    if intent == "waitlist":
        return (
            "Yedek liste ozeti:\n"
            f"- Aktif kayit: {wl['active']}\n"
            f"- Toplam kayit: {wl['total']}\n"
            f"- Ortalama oncelik: {wl['avg_priority']}\n"
            "Not: Iptal/no-show randevularinda otomatik doldurma tetigi acik degilse aktif etmenizi oneririm."
        )

    if intent == "doctor_treatment":
        top_doc = context.get("doctor_treatments_top", [])
        if not top_doc:
            return "Hekim tedavi dagilimi icin son 30 gunde tamamlanan tedavi kaydi gorunmuyor."
        sample = top_doc[:3]
        sample_text = ", ".join(
            f"{r.get('doctor_name')} - {r.get('treatment_type')} ({r.get('count')})" for r in sample
        )
        return f"Hekim bazli ilk kayitlar: {sample_text}. Detayli karsilastirma isterseniz hekim adi verin."

    if intent == "unknown":
        return (
            "Sorunuzu anlayamadim. Asagidaki formatlarda sorabilirsiniz:\n"
            "- 'Hangi malzemeden daha cok var?'\n"
            "- 'Hangi malzemeden almaliyim?'\n"
            "- 'Kac randevu var?'\n"
            "- 'Iptal/no-show oranini yorumla'"
        )

    lines = [
        "Klinik ozeti:",
        f"- Randevu (30 gun): {ap['total']} | tamamlanan {ap['completed']} | iptal {ap['cancelled']} | no-show {ap['no_show']}",
        f"- Yedek liste: aktif {wl['active']}, toplam {wl['total']}",
        f"- Envanter: {inv['total_items']} urun, kritik stok {inv['low_stock_items']}, stok degeri {inv['stock_value']:.2f} TRY",
    ]
    if critical:
        c = critical[0]
        lines.append(
            f"- Kritik stok adayi: {c.get('name')} ({c.get('quantity')} {c.get('unit')} / min {c.get('min_stock_level')})"
        )
    lines.append("Isterseniz soruyu daha spesifik yazin; dogrudan sayisal cevap verebilirim.")
    return "\n".join(lines)


def _call_openai_sync(question: str, context: dict) -> tuple[str, UsageMeta]:
    api_key = _resolve_openai_api_key()
    payload = {
        "model": settings.OPENAI_MODEL,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Sen bir klinik is analisti AI asistanisin. "
                    "Yanitlari Turkce ve kisa/eyleme donuk ver. "
                    "Sadece verilen klinik verisini kullan."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Kullanici sorusu: {question}\n\n"
                    f"Klinik veri ozeti (JSON): {json.dumps(context, ensure_ascii=True)}"
                ),
            },
        ],
    }

    req = urllib_request.Request(
        url="https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    with urllib_request.urlopen(req, timeout=settings.OPENAI_TIMEOUT_SECONDS) as resp:
        raw = resp.read().decode("utf-8")
    parsed = json.loads(raw)
    answer = parsed["choices"][0]["message"]["content"].strip()
    usage = parsed.get("usage") or {}
    prompt_tokens = int(usage.get("prompt_tokens") or _estimate_tokens(question + json.dumps(context, ensure_ascii=True)))
    completion_tokens = int(usage.get("completion_tokens") or _estimate_tokens(answer))
    total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
    return answer, {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost_usd": _estimate_cost_usd(settings.OPENAI_MODEL, prompt_tokens, completion_tokens),
    }


def _call_gemini_sync(question: str, context: dict) -> tuple[str, UsageMeta]:
    api_key = _resolve_gemini_api_key()
    prompt = (
        "Sen bir klinik is analisti AI asistanisin. "
        "Yanitlari Turkce ve kisa/eyleme donuk ver. "
        "Sadece verilen klinik verisini kullan.\n\n"
        f"Kullanici sorusu: {question}\n\n"
        f"Klinik veri ozeti (JSON): {json.dumps(context, ensure_ascii=True)}"
    )

    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
        },
    }

    model = (settings.GEMINI_MODEL or "gemini-2.5-pro").strip()
    if model.startswith("models/"):
        model = model.split("/", 1)[1]
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        f"?key={api_key}"
    )

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
        raise RuntimeError("Gemini did not return any candidate")

    parts = candidates[0].get("content", {}).get("parts", [])
    text_parts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")]
    if not text_parts:
        raise RuntimeError("Gemini response has no text")
    answer = "\n".join(text_parts).strip()
    usage = parsed.get("usageMetadata") or {}
    prompt_tokens = int(usage.get("promptTokenCount") or _estimate_tokens(question + json.dumps(context, ensure_ascii=True)))
    completion_tokens = int(usage.get("candidatesTokenCount") or _estimate_tokens(answer))
    total_tokens = int(usage.get("totalTokenCount") or (prompt_tokens + completion_tokens))
    return answer, {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost_usd": _estimate_cost_usd(settings.GEMINI_MODEL, prompt_tokens, completion_tokens),
    }


async def answer_clinic_question(question: str, db: AsyncSession) -> tuple[str, str, bool, UsageMeta]:
    context = await _build_context(db)

    provider = _resolve_provider()
    gemini_api_key = _resolve_gemini_api_key()
    openai_api_key = _resolve_openai_api_key()

    if provider == "gemini":
        if not gemini_api_key:
            return _rule_based_answer(question, context), "rule-based", True, {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
            }
        try:
            answer, usage = await asyncio.to_thread(_call_gemini_sync, question, context)
            return answer, settings.GEMINI_MODEL, False, usage
        except Exception:
            return _rule_based_answer(question, context), "rule-based", True, {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
            }

    if not openai_api_key:
        return _rule_based_answer(question, context), "rule-based", True, {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
        }

    try:
        answer, usage = await asyncio.to_thread(_call_openai_sync, question, context)
        return answer, settings.OPENAI_MODEL, False, usage
    except Exception:
        return _rule_based_answer(question, context), "rule-based", True, {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
        }
