"""
LLM Service — OpenAI Integration for NLP Tasks

Uses:
- Appointment reminder response parsing (accept/decline/reschedule)
- Patient feedback analysis (severity classification)
- Waitlist offer personalization (context-aware messaging)
- FAQ search augmentation (semantic understanding)
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import json
import os
from urllib import request as urllib_request
from typing import Any
from enum import Enum

import openai
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Maximum concurrent OpenAI calls to avoid rate-limit storms.
# All coroutines in the same process share this semaphore.
_openai_semaphore = asyncio.Semaphore(5)

# Module-level async Redis client (lazy-initialised once per process).
_redis_client: "redis.asyncio.Redis | None" = None  # type: ignore[name-defined]


async def _get_redis() -> "redis.asyncio.Redis":  # type: ignore[name-defined]
    global _redis_client
    if _redis_client is None:
        import redis.asyncio as aioredis  # type: ignore[import]

        url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        _redis_client = aioredis.from_url(url, decode_responses=True)
    return _redis_client


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS & TYPES
# ═══════════════════════════════════════════════════════════════════════════════

class ResponseType(str, Enum):
    """Patient message response classification."""
    CONFIRM = "confirm"  # Hasta randevuya geleceğini doğruladı
    CANCEL = "cancel"  # Hasta iptal etmek istiyor
    RESCHEDULE = "reschedule"  # Başka zaman ister
    QUESTION = "question"  # Soruyorum var
    OTHER = "other"  # Sınıflandırılamayan


class FeedbackSeverityClass(str, Enum):
    """Feedback severity AI classification."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ═══════════════════════════════════════════════════════════════════════════════
# LLM SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

class LLMService:
    """
    OpenAI GPT integration for NLP tasks.
    
    Model: gpt-4-turbo (or gpt-3.5-turbo for cost efficiency)
    Temperature: 0.0-0.3 (deterministic, not creative)
    """
    
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo", provider: str = "openai"):
        """
        Initialize LLM service.

        Args:
            api_key: OpenAI API key
            model: Model name (gpt-4, gpt-3.5-turbo, etc.)
        """
        self.model = model
        self.provider = (provider or "openai").strip().lower()
        self.api_key = api_key
        # Per-instance async client — only needed for OpenAI provider.
        self._client = AsyncOpenAI(api_key=api_key, timeout=30.0) if self.provider == "openai" else None
    
    async def classify_appointment_response(
        self,
        patient_message: str,
        appointment_details: str,
        clinic_name: str,
        language: str = "en",
    ) -> dict[str, Any]:
        """
        Classify patient's WhatsApp response to appointment reminder.
        
        Returns:
        {
            "type": "confirm|cancel|reschedule|question|other",
            "confidence": 0.0-1.0,
            "reason": "explanation",
            "extracted_date": "2026-05-25" (if reschedule),
            "extracted_time": "14:30" (if reschedule),
        }
        """
        prompt = f"""
Analyze patient's WhatsApp response to appointment reminder.

Appointment Details:
{appointment_details}

Patient's Message (in {language}):
"{patient_message}"

Clinic: {clinic_name}

Classify the response as one of:
1. "confirm" - Patient confirmed they will attend
2. "cancel" - Patient wants to cancel
3. "reschedule" - Patient wants to reschedule
4. "question" - Patient is asking a question
5. "other" - Cannot classify

Respond in JSON format:
{{
    "type": "confirm|cancel|reschedule|question|other",
    "confidence": 0.0-1.0,
    "reason": "brief explanation",
    "extracted_date": "YYYY-MM-DD or null",
    "extracted_time": "HH:MM or null"
}}

Only JSON, no markdown.
"""
        
        try:
            response = await self._call_openai(prompt)
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return {
                "type": "other",
                "confidence": 0.0,
                "reason": "Parsing error",
            }
    
    async def classify_feedback_severity(
        self,
        feedback_message: str,
        feedback_type: str,
        context: str = "",
        language: str = "en",
    ) -> dict[str, Any]:
        """
        Classify patient feedback severity.
        
        Returns:
        {
            "severity": "low|medium|high|critical",
            "requires_immediate_action": bool,
            "suggested_action": "contact patient|prescribe antibiotics|refer specialist|etc",
            "confidence": 0.0-1.0,
        }
        """
        prompt = f"""
Analyze patient post-op feedback severity and urgency.

Feedback Type: {feedback_type}
Patient's Message (in {language}):
"{feedback_message}"

Additional Context:
{context}

Classify severity as one of:
1. "low" - Minor issue, typically self-resolving
2. "medium" - Manageable with OTC medication
3. "high" - Requires doctor consultation
4. "critical" - Emergency-level complication

Respond in JSON:
{{
    "severity": "low|medium|high|critical",
    "requires_immediate_action": true/false,
    "suggested_action": "brief action recommendation",
    "confidence": 0.0-1.0
}}

Only JSON.
"""
        
        try:
            response = await self._call_openai(prompt)
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"Feedback classification error: {e}")
            return {
                "severity": "medium",  # Default to safe level
                "requires_immediate_action": True,
                "suggested_action": "review with doctor",
                "confidence": 0.0,
            }
    
    async def generate_waitlist_offer_message(
        self,
        patient_name: str,
        doctor_name: str,
        appointment_date: str,
        appointment_time: str,
        clinic_name: str,
        language: str = "tr",  # Turkish by default
    ) -> str:
        """
        Generate personalized waitlist offer message.
        
        Returns: Conversation-ready message (without WhatsApp template structure)
        """
        prompt = f"""
Generate a friendly, brief WhatsApp message to offer a cancellation slot to a patient.

Patient: {patient_name}
Doctor: {doctor_name}
Date: {appointment_date}
Time: {appointment_time}
Clinic: {clinic_name}
Language: {language}

Requirements:
- Professional but warm tone
- Under 160 characters (WhatsApp best practice)
- Include appointment details
- Include quick yes/no buttons reference

Message (plain text, no markdown):
"""
        
        try:
            response = await self._call_openai(prompt)
            return response.strip()
        except Exception as e:
            logger.error(f"Failed to generate offer message: {e}")
            # Fallback message
            return f"Merhaba {patient_name}, {appointment_date} {appointment_time}'de {doctor_name} ile randevunuz boş. Kabul ediyor musunuz?"
    
    async def generate_appointment_confirmation_message(
        self,
        patient_name: str,
        doctor_name: str,
        appointment_date: str,
        appointment_time: str,
        clinic_name: str,
        language: str = "tr",
    ) -> str:
        """
        Generate a short, friendly WhatsApp message asking the patient if they
        can attend their upcoming appointment.  Patient should reply YES/EVET or NO/HAYIR.
        """
        prompt = f"""
Generate a short, warm WhatsApp reminder message for a dental patient asking if they can attend their appointment.

Patient: {patient_name}
Doctor: {doctor_name}
Date: {appointment_date}
Time: {appointment_time}
Clinic: {clinic_name}
Language: {language}

Requirements:
- Max 200 characters
- Friendly, professional tone
- Ask if they can attend (yes/evet or no/hayir)
- Mention date and time

Plain text only, no markdown, no JSON:
"""
        try:
            response = await self._call_openai(prompt, max_tokens=200, cache_ttl=300)
            return response.strip()
        except Exception as e:
            logger.error(f"Failed to generate confirmation message: {e}")
            return (
                f"Merhaba {patient_name}! {appointment_date} {appointment_time}'deki "
                f"{doctor_name} randevunuza gelebilecek misiniz? "
                f"Evet/Hayır yazarak yanıtlayabilirsiniz."
            )

    async def generate_feedback_solution_message(
        self,
        patient_name: str,
        patient_complaint: str,
        severity: str,
        faqs: list[dict],
        clinic_name: str,
        language: str = "tr",
    ) -> str:
        """
        Given a patient complaint after treatment, generate a helpful solution/advice
        message to send back via WhatsApp.

        Args:
            faqs: List of relevant FAQ dicts (each has 'question', 'answer' keys)
        """
        faq_context = ""
        if faqs:
            faq_lines = [f"- S: {f.get('question','')}\n  C: {f.get('answer','')}" for f in faqs[:3]]
            faq_context = "Relevant clinic FAQs:\n" + "\n".join(faq_lines)

        prompt = f"""
You are a dental clinic assistant. A patient has reported a complaint after their treatment.
Write a concise, helpful WhatsApp reply offering advice.

Patient: {patient_name}
Complaint: "{patient_complaint}"
Severity: {severity}
Clinic: {clinic_name}
Language: {language}

{faq_context}

Guidelines:
- Be empathetic and professional
- Severity "low"/"medium": provide practical home-care advice based on FAQs
- Severity "high"/"critical": recommend calling the clinic immediately
- Max 300 characters
- Never diagnose, never prescribe medications by name
- End with clinic name

Plain text only, no markdown:
"""
        try:
            response = await self._call_openai(prompt, max_tokens=300, cache_ttl=300)
            return response.strip()
        except Exception as e:
            logger.error(f"Failed to generate solution message: {e}")
            if severity in ("high", "critical"):
                return (
                    f"Merhaba {patient_name}, şikayetiniz için lütfen kliniğimizi arayın. "
                    f"Sizinle en kısa sürede ilgilenelim. — {clinic_name}"
                )
            return (
                f"Merhaba {patient_name}, bildirdiğiniz şikayet için teşekkürler. "
                f"İyileşme sürecinizde ağrı kesici kullanabilir, "
                f"sorun devam ederse kliniğimizi arayabilirsiniz. — {clinic_name}"
            )

    async def parse_faq_query(
        self,
        query: str,
        language: str = "en",
    ) -> dict[str, Any]:
        """
        Parse patient FAQ query to extract intent and entities.
        
        Returns:
        {
            "intent": "diagnosis|treatment|post_op|payment|schedule|etc",
            "main_topics": ["pain", "swelling", "infection"],
            "urgency": "low|medium|high",
            "language_detected": "tr|en",
        }
        """
        prompt = f"""
Analyze patient's FAQ query.

Query (in {language}):
"{query}"

Extract:
1. Intent: why are they asking?
2. Main topics mentioned
3. Urgency level
4. Detected language

Response (JSON only):
{{
    "intent": "diagnosis|treatment|post_op|payment|schedule|emergency|other",
    "main_topics": ["topic1", "topic2"],
    "urgency": "low|medium|high",
    "language_detected": "en|tr|etc"
}}
"""
        
        try:
            response = await self._call_openai(prompt)
            return json.loads(response)
        except Exception as e:
            logger.error(f"FAQ parsing error: {e}")
            return {
                "intent": "other",
                "main_topics": [],
                "urgency": "medium",
                "language_detected": language,
            }
    
    def _call_gemini_sync(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 500,
    ) -> str:
        """Blocking Gemini call (wrapped with asyncio.to_thread by caller)."""
        model = (self.model or "gemini-1.5-flash").strip()
        if model.startswith("models/"):
            model = model.split("/", 1)[1]

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            f"?key={self.api_key}"
        )
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "You are a helpful dental clinic assistant. "
                                "Respond in valid JSON format.\n\n"
                                f"{prompt}"
                            )
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        req = urllib_request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib_request.urlopen(req, timeout=30.0) as resp:
            raw = resp.read().decode("utf-8")

        parsed = json.loads(raw)
        candidates = parsed.get("candidates") or []
        if not candidates:
            raise OpenAIError("Gemini did not return candidates")

        parts = candidates[0].get("content", {}).get("parts", [])
        text_parts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")]
        if not text_parts:
            raise OpenAIError("Gemini response has no text")

        return "\n".join(text_parts).strip()

    async def _call_openai(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 500,
        cache_ttl: int = 3600,
    ) -> str:
        """
        Call OpenAI API with:
        - Semaphore (max 5 concurrent calls per process)
        - Redis response cache (identical prompts served from cache)
        - 30 s network timeout (set on AsyncOpenAI client)

        Raises:
            OpenAIRateLimitError: On 429 responses
            OpenAIError: On other API failures
        """
        # Cache key = SHA-256 of model:prompt (truncated to 32 hex chars)
        cache_key = "llm:" + hashlib.sha256(
            f"{self.provider}:{self.model}:{prompt}".encode()
        ).hexdigest()[:32]

        try:
            redis = await _get_redis()
            cached = await redis.get(cache_key)
            if cached:
                logger.debug("LLM cache hit: %s", cache_key)
                return cached
        except Exception as exc:
            logger.warning("Redis cache read failed (proceeding without cache): %s", exc)

        async with _openai_semaphore:
            try:
                if self.provider == "gemini":
                    result = await asyncio.to_thread(
                        self._call_gemini_sync,
                        prompt,
                        temperature,
                        max_tokens,
                    )
                else:
                    if self._client is None:
                        raise OpenAIError("OpenAI client is not initialized")
                    response = await self._client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a helpful dental clinic assistant. Respond in valid JSON format.",
                            },
                            {
                                "role": "user",
                                "content": prompt,
                            },
                        ],
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    result = response.choices[0].message.content or ""

            except openai.RateLimitError as exc:
                logger.error("OpenAI rate limit: %s", exc)
                raise OpenAIRateLimitError(f"Rate limited: {exc}") from exc
            except openai.APIError as exc:
                logger.error("OpenAI API error: %s", exc)
                raise OpenAIError(f"API call failed: {exc}") from exc
            except Exception as exc:
                logger.error("%s API error: %s", self.provider.upper(), exc)
                raise OpenAIError(f"{self.provider} API call failed: {exc}") from exc

        try:
            redis = await _get_redis()
            await redis.set(cache_key, result, ex=cache_ttl)
        except Exception as exc:
            logger.warning("Redis cache write failed: %s", exc)

        return result


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR HANDLING
# ═══════════════════════════════════════════════════════════════════════════════

class OpenAIError(Exception):
    """OpenAI API error."""
    pass


class OpenAIRateLimitError(OpenAIError):
    """OpenAI rate limit exceeded."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# FACTORY FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def get_llm_service(model: str | None = None) -> LLMService:
    """
    Factory function to initialize LLM service.

    Uses LLM_PROVIDER + LLM_MODEL from settings for WhatsApp patient AI.
    Pass an explicit model to override (e.g., in tests).
    """
    import os
    from app.core.config import settings

    provider = (getattr(settings, "LLM_PROVIDER", "openai") or "openai").strip().lower()
    selected_model = model or getattr(settings, "LLM_MODEL", None)

    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not configured in environment")
        if not selected_model:
            selected_model = getattr(settings, "GEMINI_MODEL", "gemini-1.5-flash")
        return LLMService(api_key=api_key, model=selected_model, provider="gemini")

    api_key = os.getenv("OPENAI_API_KEY") or settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError("OPENAI_API_KEY not configured in environment")
    if not selected_model:
        selected_model = settings.OPENAI_MODEL

    return LLMService(api_key=api_key, model=selected_model, provider="openai")


__all__ = [
    "LLMService",
    "ResponseType",
    "FeedbackSeverityClass",
    "OpenAIError",
    "OpenAIRateLimitError",
    "get_llm_service",
]
