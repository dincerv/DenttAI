"""
WhatsApp smoke test — W1/W2/W3 adımları
Kullanım:
  python scripts_smoke_whatsapp.py
"""
import os, sys, json
import urllib.request, urllib.parse, urllib.error

API = os.environ.get("API_URL", "https://denttai-production.up.railway.app")

def request(method, path, token=None, body=None):
    url = API + path
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

# ── W0: Health ────────────────────────────────────────────
print("W0 /health ...", end=" ")
status, body = request("GET", "/health")
assert status == 200, f"FAIL: {status}"
print(f"OK  {body}")

# ── W1: Login (owner) ─────────────────────────────────────
print("W1 login ...", end=" ")
CLINIC_CODE  = os.environ.get("CLINIC_CODE",  "80C791")
OWNER_EMAIL  = os.environ.get("OWNER_EMAIL",  "admin@demo.com")
OWNER_PASS   = os.environ.get("OWNER_PASS",   "Admin1234")
status, body = request("POST", "/api/auth/login", body={
    "email": OWNER_EMAIL, "password": OWNER_PASS, "clinic_code": CLINIC_CODE
})
assert status == 200, f"FAIL: {status} {body}"
token = body["access_token"]
print(f"OK  (token ...{token[-12:]})")

# ── W2: WhatsApp health ───────────────────────────────────
print("W2 /api/integration/whatsapp/health/whatsapp ...", end=" ")
status, body = request("GET", "/api/integration/whatsapp/health/whatsapp", token=token)
print(f"{'OK' if status == 200 else 'FAIL'}  {status}  {body}")

# ── W3: Clinic settings GET ───────────────────────────────
print("W3 GET /api/integration/whatsapp/clinic-settings ...", end=" ")
status, body = request("GET", "/api/integration/whatsapp/clinic-settings", token=token)
print(f"{'OK' if status == 200 else 'FAIL'}  {status}  is_whatsapp_enabled={body.get('is_whatsapp_enabled')}")

# ── W4: Webhook verify token ──────────────────────────────
VERIFY_TOKEN = os.environ.get("WHATSAPP_WEBHOOK_VERIFY_TOKEN", "")
if VERIFY_TOKEN:
    print("W4 webhook verify ...", end=" ")
    qs = urllib.parse.urlencode({
        "hub.mode": "subscribe",
        "hub.verify_token": VERIFY_TOKEN,
        "hub.challenge": "12345",
    })
    status, body = request("GET", f"/api/whatsapp/webhook?{qs}")
    print(f"{'OK challenge=12345' if body == 12345 else 'FAIL'}  {status}  {body}")
else:
    print("W4 SKIP — WHATSAPP_WEBHOOK_VERIFY_TOKEN env yok")

# ── W5: WhatsApp send (numara varsa) ─────────────────────
PHONE = os.environ.get("TEST_PHONE", "")
ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
if PHONE and ACCESS_TOKEN:
    print(f"W5 send message → {PHONE} ...", end=" ")
    status, body = request("POST", "/api/integration/whatsapp/whatsapp-messages/send", token=token, body={
        "phone_number": PHONE,
        "message_type": "text",
        "content": "DentAI Flow smoke test — bu mesajı aldıysanız sistem çalışıyor.",
    })
    print(f"{'OK' if status == 202 else 'FAIL'}  {status}  {body}")
else:
    print("W5 SKIP — TEST_PHONE veya WHATSAPP_ACCESS_TOKEN env yok")

print("\n✅ Smoke bitti.")
