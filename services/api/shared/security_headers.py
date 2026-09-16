"""
Security Headers Middleware — Add protective HTTP headers

Tüm response'lara aşağıdaki header'ları ekler:
- Strict-Transport-Security: HTTPS zorunluluğu
- X-Content-Type-Options: MIME type sniffing koruması
- X-Frame-Options: Clickjacking koruması
- Content-Security-Policy: XSS koruması
- X-XSS-Protection: Additional XSS protection

Kullanım (main.py'de):
    from shared.security_headers import SecurityHeadersMiddleware
    app.add_middleware(SecurityHeadersMiddleware)
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Callable


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # ⚠️ HSTS: Enforce HTTPS for 1 year
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # ⚠️ Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # ⚠️ Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # ⚠️ CSP: Only allow content from same origin
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        
        # ⚠️ Legacy XSS protection (for older browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # ⚠️ Referrer policy: Only send referrer to same-origin
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # ⚠️ Disable feature policy for untrusted features
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        return response
