"""
RAG (Retrieval-Augmented Generation) Service

Hasta geri bildirimine bağlı olarak ClinicFAQ tablosundan relevant bilgiyi çekerek
OpenAI sistem promptlarına enjekte eden servis.

- Anahtar kelime tabanlı FAQ arama
- Semantik sıralama (ilgililik skorlaması)
- Prompt context builders (AI sistem mesajına FAQ'ları embed etme)
"""

from __future__ import annotations

import logging
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.whatsapp import ClinicFaq
from app.schemas_whatsapp import ClinicFaqResponse

logger = logging.getLogger(__name__)


class RAGService:
    """
    Retrieval-Augmented Generation motor.
    
    ClinicFAQ'lardan relevant bilgiyi çekerek, LLM'in sistem promptlarına
    klinik-onaylı yanıtlar vermesini sağlar.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search_relevant_faqs(
        self,
        clinic_id: UUID,
        patient_message: str,
        limit: int = 3,
    ) -> list[ClinicFaqResponse]:
        """
        Hasta mesajından relevant SSS'leri ara.
        
        Args:
            clinic_id: Klinik ID
            patient_message: Hastanın mesajı (örn: "Ağrım var", "Kanamam durmadı")
            limit: Döndürülecek max SSS sayısı
            
        Returns:
            Relevans sırası ile ClinicFaqResponse listesi
        """
        from app.services.whatsapp_service import ClinicFaqService
        
        service = ClinicFaqService(self.db)
        faqs = await service.search_by_keywords(clinic_id, patient_message, limit)
        
        logger.info(
            f"RAG search: clinic_id={clinic_id}, found {len(faqs)} FAQs "
            f"for message: {patient_message[:100]}"
        )
        
        return faqs

    def build_system_prompt_with_rag(
        self,
        base_prompt: str,
        faqs: list[ClinicFaqResponse],
        clinic_name: str,
    ) -> str:
        """
        Temel sistem promptuna RAG context'i enjekte et.
        
        Args:
            base_prompt: Asıl sistem promptu ("Sen klinik AI asistanısın...")
            faqs: Relevant ClinicFaq'lar
            clinic_name: Klinik adı
            
        Returns:
            RAG embedded sistem promptu
        """
        if not faqs:
            return base_prompt

        faq_context = "\n".join(
            [
                f"Soru: {faq.question}\nCevap: {faq.answer}\nKategori: {faq.category}"
                for faq in faqs
            ]
        )

        enhanced_prompt = f"""{base_prompt}

───────────────────────────────────────────────────────────────
🏥 KLINIK UZMAN BİLGİSİ ({clinic_name}):

Aşağıdaki SSS'ler tedavi sonrası sık sorulan konular ve klinik onaylı cevaplardır.
Lütfen hasta sorularına yanıt verirken bu bilgileri kullan:

{faq_context}

───────────────────────────────────────────────────────────────

KURALLAR:
1. Hastaya verdiğin tavsiyeler SADECE yukarıdaki klinik onaylı bilgilere dayalı olmalıdır
2. Eğer soru SSS'lerde yoksa "Bu konu hakkında daha detaylı bilgi için doktorunuzla görüşün" de
3. Acil durum belirtileri görürsen (aşırı kanama, şiddetli ağrı) derhal doktora yönlendir
4. Her zaman klinik adını ({clinic_name}) referans al
"""
        return enhanced_prompt

    def extract_severity_from_faq_context(
        self,
        patient_message: str,
        faqs: list[ClinicFaqResponse],
    ) -> dict:
        """
        FAQ context'ine bakarak hasta mesajının severity'sini tahmin et.
        
        Args:
            patient_message: Hastanın mesajı
            faqs: Relevant FAQ'lar
            
        Returns:
            {
                "likely_severity": "low" | "medium" | "high" | "critical",
                "confidence": 0.0-1.0,
                "faq_match": boolean (FAQ'da bu konu varsa True)
            }
        """
        keywords_critical = {
            "aşırı kanama", "durduramıyorum", "şuur kaybı", "bayıldım",
            "yüksek ateş", "şiddetli ağrı", "çene açamıyorum",
            "kalp çarpıntısı", "nefes alamıyorum", "acil",
        }
        keywords_high = {"kanama", "ağrı", "şişme", "morluk"}
        keywords_medium = {"rahatsızlık", "hafif", "biraz"}

        message_lower = patient_message.lower()
        
        # Severity detection
        if any(kw in message_lower for kw in keywords_critical):
            severity = "critical"
            confidence = 0.95
        elif any(kw in message_lower for kw in keywords_high):
            severity = "high"
            confidence = 0.85
        elif any(kw in message_lower for kw in keywords_medium):
            severity = "medium"
            confidence = 0.70
        else:
            severity = "low"
            confidence = 0.50

        # FAQ match
        faq_match = any(kw in message_lower for faq in faqs for kw in faq.question.lower().split())

        return {
            "likely_severity": severity,
            "confidence": confidence,
            "faq_match": faq_match,
        }

    def build_doctor_alert_message(
        self,
        patient_name: str,
        patient_message: str,
        appointment_date: str,
        doctor_name: str,
        severity: str,
        faqs: list[ClinicFaqResponse] | None = None,
    ) -> str:
        """
        Doktora acil durum uyarısı mesajı oluştur.
        
        Args:
            patient_name: Hasta adı
            patient_message: Hastanın şikayeti
            appointment_date: Tedavi tarihi
            doctor_name: Hekim adı
            severity: Ciddiyet seviyesi (low/medium/high/critical)
            faqs: İlgili FAQ'lar (opsiyonel)
            
        Returns:
            Doktor için WhatsApp uyarı mesajı
        """
        emoji_map = {
            "low": "ℹ️",
            "medium": "⚠️",
            "high": "🔴",
            "critical": "🚨",
        }
        emoji = emoji_map.get(severity, "ℹ️")

        message = f"""{emoji} HASTA TAKİP UYARISI

Doktor: {doctor_name}
Hasta: {patient_name}
Tedavi tarihi: {appointment_date}
Ciddiyet: {severity.upper()}

Şikayet: "{patient_message}"
"""
        if faqs:
            message += f"\nKlinik SSS önerisi (AI tarafından seçilmiş):\n"
            for faq in faqs[:2]:  # Top 2 FAQs
                message += f"- {faq.question}\n  → {faq.answer[:100]}...\n"

        message += f"\nLütfen hastaya kontrol etmek için ulaşın."

        return message
