"""
Minimal cloud API gateway — Railway PORT uyumlu.
/api/auth/* → auth-service
/api/appointments|waitlist|patient-notes → appointment-service
"""
from __future__ import annotations

import os
from typing import Optional

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

AUTH = os.environ.get("AUTH_SERVICE_URL", "http://denttai.railway.internal:8080").rstrip("/")
APPT = os.environ.get(
    "APPOINTMENT_SERVICE_URL",
    "http://meticulous-rejoicing.railway.internal:8080",
).rstrip("/")

app = FastAPI(title="DentAI Cloud Gateway", docs_url=None, redoc_url=None)
client = httpx.AsyncClient(timeout=60.0, follow_redirects=False)


@app.on_event("shutdown")
async def _shutdown() -> None:
    await client.aclose()


@app.get("/health")
@app.get("/")
async def health():
    return {"status": "ok", "service": "gateway", "mode": "cloud-c1-proxy"}


async def _proxy(base: str, path: str, request: Request) -> Response:
    url = f"{base}{path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in {"host", "content-length", "connection"}
    }
    body = await request.body()
    try:
        upstream = await client.request(
            request.method,
            url,
            headers=headers,
            content=body,
        )
    except httpx.RequestError as e:
        return JSONResponse(
            status_code=502,
            content={"error": "upstream_unreachable", "detail": str(e), "target": base},
        )

    excluded = {"content-encoding", "transfer-encoding", "connection"}
    out_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in excluded}
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=out_headers,
    )


@app.api_route("/api/auth/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def auth_proxy(path: str, request: Request):
    # UI: /api/auth/login → auth: /auth/login ; health özel
    if path == "health":
        return await _proxy(AUTH, "/health", request)
    return await _proxy(AUTH, f"/auth/{path}", request)


@app.api_route("/api/auth", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def auth_root(request: Request):
    return await _proxy(AUTH, "/auth", request)


@app.api_route(
    "/api/appointments/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def appt_proxy(path: str, request: Request):
    if path == "health":
        return await _proxy(APPT, "/health", request)
    return await _proxy(APPT, f"/appointments/{path}", request)


@app.api_route("/api/appointments", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def appt_root(request: Request):
    return await _proxy(APPT, "/appointments", request)


@app.api_route("/api/waitlist/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
@app.api_route("/api/waitlist", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def waitlist_proxy(request: Request, path: Optional[str] = None):
    suffix = f"/waitlist/{path}" if path else "/waitlist"
    return await _proxy(APPT, suffix, request)


@app.api_route(
    "/api/patient-notes/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
@app.api_route("/api/patient-notes", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def notes_proxy(request: Request, path: Optional[str] = None):
    suffix = f"/patient-notes/{path}" if path else "/patient-notes"
    return await _proxy(APPT, suffix, request)
