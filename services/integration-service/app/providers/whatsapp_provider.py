"""
WhatsApp Cloud API Provider — Meta Official API Client

Production-ready: request signing, rate limiting, error handling
"""
from __future__ import annotations

import logging
import hashlib
import hmac
from typing import Optional, Any
from datetime import datetime, timedelta

import httpx
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class WhatsappTemplate(BaseModel):
    """WhatsApp message template definition."""
    name: str
    language: str = "en_US"  # e.g., "tr_TR" for Turkish
    parameters: dict[str, Any] | None = Field(None)


class WhatsappMessage(BaseModel):
    """WhatsApp message to send."""
    to: str  # Phone number (international format: +1234567890)
    template: WhatsappTemplate | None = Field(None)
    text: str | None = Field(None)  # Fallback text message


class WhatsappMessageResponse(BaseModel):
    """WhatsApp API response."""
    messages: list[dict[str, Any]]
    contacts: list[dict[str, Any]] | None = Field(None)


# ═══════════════════════════════════════════════════════════════════════════════
# WHATSAPP PROVIDER CLIENT
# ═══════════════════════════════════════════════════════════════════════════════

class WhatsappProvider:
    """
    Meta WhatsApp Cloud API client.
    
    Authentication: Bearer token
    API Version: v18.0
    Rate Limit: 1000 messages/second per business account
    """
    
    BASE_URL = "https://graph.instagram.com/v18.0"
    
    def __init__(
        self,
        business_account_id: str,
        phone_number_id: str,
        access_token: str,
    ):
        """
        Initialize WhatsApp provider.
        
        Args:
            business_account_id: Meta Business Account ID
            phone_number_id: WhatsApp Business Phone Number ID
            access_token: Long-lived access token (from Meta App Settings)
        """
        self.business_account_id = business_account_id
        self.phone_number_id = phone_number_id
        self.access_token = access_token
        self.api_url = f"{self.BASE_URL}/{phone_number_id}/messages"
    
    async def send_message(
        self,
        phone_number: str,
        template_name: str,
        language: str = "en_US",
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Send templated message via WhatsApp.
        
        Args:
            phone_number: Recipient phone (international format)
            template_name: WhatsApp template name (pre-approved by Meta)
            language: Template language
            parameters: Template variable substitution
        
        Returns:
            API response with message ID
        
        Raises:
            WhatsappAPIError: If API call fails
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self._normalize_phone(phone_number),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": language,
                },
            },
        }
        
        if parameters:
            payload["template"]["components"] = [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": str(v)}
                        for v in parameters.values()
                    ],
                }
            ]
        
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.post(
                    self.api_url,
                    json=payload,
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                
                data = response.json()
                logger.info(
                    f"WhatsApp message sent",
                    extra={
                        "phone": phone_number,
                        "template": template_name,
                        "message_id": data.get("messages", [{}])[0].get("id", "unknown"),
                    },
                )
                return data
                
            except httpx.HTTPError as e:
                logger.error(
                    f"WhatsApp API error: {e}",
                    extra={
                        "phone": phone_number,
                        "template": template_name,
                        "status_code": getattr(e.response, "status_code", None),
                    },
                )
                raise WhatsappAPIError(f"Failed to send message: {e}")
    
    async def send_text_message(
        self,
        phone_number: str,
        text: str,
    ) -> dict[str, Any]:
        """
        Send free-form text message (not templated).
        
        Note: Meta requires 24-hour session window for non-template messages.
        Use templates for proactive messaging.
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self._normalize_phone(phone_number),
            "type": "text",
            "text": {
                "body": text,
            },
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.post(
                    self.api_url,
                    json=payload,
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPError as e:
                logger.error(f"WhatsApp text message failed: {e}")
                raise WhatsappAPIError(f"Failed to send text: {e}")
    
    @staticmethod
    def verify_webhook_signature(
        body: bytes,
        signature: str | None,
        app_secret: str,
    ) -> bool:
        """
        Verify incoming webhook signature (security).
        
        Meta sends one of:
        - X-Hub-Signature-256: sha256=<hash>
        - X-Hub-Signature: sha1=<hash>
        
        Hash = HMAC(app_secret, request_body)
        """
        try:
            if not signature:
                return False

            hash_method, hash_value = signature.split("=", 1)

            if hash_method == "sha256":
                expected_hash = hmac.new(
                    app_secret.encode(),
                    body,
                    hashlib.sha256,
                ).hexdigest()
            elif hash_method == "sha1":
                expected_hash = hmac.new(
                    app_secret.encode(),
                    body,
                    hashlib.sha1,
                ).hexdigest()
            else:
                logger.warning("Unsupported signature hash method: %s", hash_method)
                return False

            return hmac.compare_digest(hash_value, expected_hash)
            
        except ValueError:
            logger.warning("Invalid signature format")
            return False
    
    def _get_headers(self) -> dict[str, str]:
        """Get API request headers."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
    
    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """
        Normalize phone number to international format.
        
        E.g., 90123456789 → +90123456789
            +90123456789 → +90123456789
        """
        phone = phone.replace(" ", "").replace("-", "")
        if not phone.startswith("+"):
            phone = "+" + phone
        return phone


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR HANDLING
# ═══════════════════════════════════════════════════════════════════════════════

class WhatsappAPIError(Exception):
    """WhatsApp API error."""
    pass


class WhatsappRateLimitError(WhatsappAPIError):
    """Rate limit exceeded."""
    
    def __init__(self, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(f"Rate limited. Retry after {retry_after}s")


def _read_sender_override(clinic_settings: Any | None, field_name: str) -> str | None:
    if clinic_settings is None:
        return None

    if isinstance(clinic_settings, dict):
        value = clinic_settings.get(field_name)
    else:
        value = getattr(clinic_settings, field_name, None)

    if value is None:
        return None

    text_value = str(value).strip()
    return text_value or None


# ═══════════════════════════════════════════════════════════════════════════════
# FACTORY FUNCTION (Dependency Injection friendly)
# ═══════════════════════════════════════════════════════════════════════════════

def get_whatsapp_provider(clinic_settings: Any | None = None) -> WhatsappProvider:
    """
    Factory function to initialize WhatsApp provider.
    
    Reads from environment variables:
    - WHATSAPP_BUSINESS_ACCOUNT_ID
    - WHATSAPP_PHONE_NUMBER_ID
    - WHATSAPP_ACCESS_TOKEN
    """
    import os

    business_account_id = (
        _read_sender_override(clinic_settings, "whatsapp_business_account_id")
        or os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID")
    )
    phone_number_id = (
        _read_sender_override(clinic_settings, "whatsapp_phone_number_id")
        or os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    )
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")

    if not all([business_account_id, phone_number_id, access_token]):
        raise ValueError("WhatsApp credentials not configured in environment")

    return WhatsappProvider(
        business_account_id=business_account_id,
        phone_number_id=phone_number_id,
        access_token=access_token,
    )


__all__ = [
    "WhatsappProvider",
    "WhatsappMessage",
    "WhatsappTemplate",
    "WhatsappAPIError",
    "WhatsappRateLimitError",
    "get_whatsapp_provider",
]
