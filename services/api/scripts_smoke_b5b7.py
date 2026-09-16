from app.routers.webhook import router as wr
from app.core.broker import _handle_appointment_completed
import asyncio

paths = []
for r in wr.routes:
    paths.append(getattr(r, "path", None) or str(r))
print("webhook routes:", paths)
assert any("/webhook" in str(p) for p in paths)
asyncio.run(_handle_appointment_completed({}))
print("broker+webhook OK")
