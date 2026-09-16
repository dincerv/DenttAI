"""
Global Exception Handler — Hide stack traces from client responses

Tüm unhandled exception'ları yakalar ve genel bir hata mesajı döndürür.
Ayrıntılı hata bilgisi (stack trace) yalnızca sunucu loglarına yazılır.

Kullanım (main.py'de):
    from shared.exception_handler import setup_global_exception_handler
    setup_global_exception_handler(app, logger)
"""
import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


def setup_global_exception_handler(app: FastAPI, logger: logging.Logger = None) -> None:
    """
    FastAPI app'a global exception handler ekle.
    
    Args:
        app: FastAPI uygulaması
        logger: Optional logging instance. Eğer None ise logging.getLogger() kullanılır
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """
        Tüm unhandled exception'ları yakala ve genel bir hata mesajı döndür.
        
        ⚠️ Stack trace'i yalnızca sunucu loglarına yaz (client'a gösterme!)
        """
        # Log tam error bilgisini (internal use only)
        logger.error(
            f"Unhandled exception in {request.method} {request.url}",
            exc_info=True,
            extra={
                "client_host": request.client.host if request.client else None,
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
            }
        )
        
        # Client'a genel bir hata mesajı döndür (stack trace yok!)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal server error. Please contact support if the problem persists.",
                "error_id": request.headers.get("x-request-id", "unknown")
            },
        )
    
    return app
