"""
Rate Limiting — Prevent brute force attacks on auth endpoints

Simple sliding window rate limiter (memory-based, good for single-instance deployments).
For distributed systems, use Redis-based limiter.

Kullanım (router'de):
    from shared.rate_limiter import rate_limit
    
    @router.post("/login")
    @rate_limit(max_requests=5, window_seconds=60)  # 5 requests per minute
    async def login(...):
        pass
"""
import time
from functools import wraps
from typing import Callable, Dict, Tuple
from collections import defaultdict

from fastapi import HTTPException, status, Request


# Global in-memory store: IP_address -> [(timestamp, count)]
_rate_limit_store: Dict[str, list] = defaultdict(list)

# Cleanup old entries every N seconds
_last_cleanup = time.time()


def _cleanup_old_entries() -> None:
    """Remove expired rate limit entries."""
    global _last_cleanup
    
    now = time.time()
    if now - _last_cleanup < 300:  # Cleanup every 5 minutes
        return
    
    _last_cleanup = now
    
    for ip in list(_rate_limit_store.keys()):
        # Keep only entries from last hour
        _rate_limit_store[ip] = [
            (ts, cnt) for ts, cnt in _rate_limit_store[ip]
            if now - ts < 3600
        ]
        if not _rate_limit_store[ip]:
            del _rate_limit_store[ip]


def rate_limit(max_requests: int = 10, window_seconds: int = 60):
    """
    Rate limit decorator for FastAPI endpoints.
    
    Args:
        max_requests: Maximum number of requests allowed in the window
        window_seconds: Time window in seconds
    
    Example:
        @router.post("/login")
        @rate_limit(max_requests=5, window_seconds=60)
        async def login(request: Request, data: LoginRequest):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract Request object
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if request is None and 'request' in kwargs:
                request = kwargs['request']
            
            if request is None:
                # If no request found, skip rate limiting
                return await func(*args, **kwargs)
            
            # Get client IP
            client_ip = request.client.host if request.client else "unknown"
            now = time.time()
            
            # Cleanup old entries
            _cleanup_old_entries()
            
            # Get request history for this IP
            history = _rate_limit_store[client_ip]
            
            # Remove entries outside the window
            history[:] = [(ts, cnt) for ts, cnt in history if now - ts < window_seconds]
            
            # Check if rate limit exceeded
            total_requests = sum(cnt for _, cnt in history)
            if total_requests >= max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded: {max_requests} requests per {window_seconds} seconds",
                    headers={"Retry-After": str(window_seconds)},
                )
            
            # Update history
            if history and history[-1][0] == now:
                # Same second, increment counter
                history[-1] = (now, history[-1][1] + 1)
            else:
                # New second
                history.append((now, 1))
            
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


class RateLimitMiddleware:
    """
    Middleware version of rate limiter (for global protection).
    
    Kullanım (main.py'de):
        from shared.rate_limiter import RateLimitMiddleware
        app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)
    """
    
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        self.app = app
        self.max_requests = max_requests
        self.window_seconds = window_seconds
    
    async def __call__(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        
        # Cleanup old entries
        _cleanup_old_entries()
        
        # Get request history for this IP
        history = _rate_limit_store[client_ip]
        
        # Remove entries outside the window
        history[:] = [
            (ts, cnt) for ts, cnt in history 
            if now - ts < self.window_seconds
        ]
        
        # Check if rate limit exceeded
        total_requests = sum(cnt for _, cnt in history)
        if total_requests >= self.max_requests:
            return HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded",
                headers={"Retry-After": str(self.window_seconds)},
            )
        
        # Update history
        if history and history[-1][0] == now:
            history[-1] = (now, history[-1][1] + 1)
        else:
            history.append((now, 1))
        
        return await self.app(request)
