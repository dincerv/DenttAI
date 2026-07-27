"""
CSRF Protection Middleware — Prevent Cross-Site Request Forgery

Tüm POST, PATCH, DELETE, PUT isteklerinde X-CSRF-Token header'ını doğrular.
Token sunucuda session'da tutulur (httpOnly cookie'de).

Kullanım (main.py'de):
    from shared.csrf_protection import CSRFMiddleware
    app.add_middleware(CSRFMiddleware, secret="your-secret-key")
"""
import hmac
import hashlib
import secrets
from time import time
from typing import Callable

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF token doğrulama middleware'i.
    
    - GET/HEAD/OPTIONS: Token oluştur ve X-CSRF-Token header'ında döndür
    - POST/PATCH/DELETE/PUT: X-CSRF-Token header'ında token'ı doğrula
    """
    
    def __init__(self, app, secret: str = None):
        super().__init__(app)
        self.secret = secret or secrets.token_urlsafe(32)
        self.token_lifetime = 3600  # 1 hour
    
    def _generate_token(self) -> str:
        """CSRF token oluştur (timestamp + nonce + hmac)."""
        timestamp = str(int(time()))
        nonce = secrets.token_hex(8)
        message = f"{timestamp}:{nonce}".encode()
        signature = hmac.new(
            self.secret.encode(),
            message,
            hashlib.sha256
        ).hexdigest()
        return f"{timestamp}:{nonce}:{signature}"
    
    def _verify_token(self, token: str) -> bool:
        """CSRF token doğrula."""
        try:
            timestamp, nonce, signature = token.split(":")
            timestamp_int = int(timestamp)
            
            # Token süresini kontrol et
            if time() - timestamp_int > self.token_lifetime:
                return False
            
            # Signature'ı doğrula
            message = f"{timestamp}:{nonce}".encode()
            expected_signature = hmac.new(
                self.secret.encode(),
                message,
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
        except Exception:
            return False
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Request'i işle."""
        # Login endpoint should remain reachable even when client-side CSRF bootstrap fails.
        if request.method == "POST" and request.url.path.endswith("/auth/login"):
            return await call_next(request)

        # Bearer token authenticated API calls are not vulnerable to classic CSRF,
        # because Authorization header is not sent automatically by browsers.
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return await call_next(request)

        # Safe request methods (no CSRF check needed)
        if request.method in ("GET", "HEAD", "OPTIONS", "TRACE"):
            response = await call_next(request)
            # Token oluştur ve response header'na ekle
            token = self._generate_token()
            response.headers["X-CSRF-Token"] = token
            return response
        
        # State-changing methods (POST, PATCH, DELETE, PUT) — CSRF check
        if request.method in ("POST", "PATCH", "DELETE", "PUT"):
            # CSRF token doğrula
            csrf_token = request.headers.get("X-CSRF-Token", "").strip()

            if not csrf_token:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "CSRF token missing"},
                )

            if not self._verify_token(csrf_token):
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Invalid or expired CSRF token"},
                )

        response = await call_next(request)
        return response
