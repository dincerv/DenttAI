import argparse
import asyncio
import hashlib
import hmac
import json
import time
from collections import Counter

import httpx

DEFAULT_BASE = "http://127.0.0.1:8005"
DEFAULT_SECRET = "dentai_webhook_secret_token"
DEFAULT_TOTAL = 120
DEFAULT_CONCURRENCY = 24


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Concurrent WhatsApp webhook load test")
    parser.add_argument("--base", default=DEFAULT_BASE, help="Base URL for the integration service")
    parser.add_argument("--secret", default=DEFAULT_SECRET, help="Webhook signing secret")
    parser.add_argument("--total", type=int, default=DEFAULT_TOTAL, help="Total number of requests")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY, help="Maximum concurrent requests")
    return parser.parse_args()


def build_body(i: int) -> str:
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": f"90555111{i:04d}",
                                    "id": f"wamid.load{i}",
                                    "timestamp": "1710000000",
                                    "text": {"body": "Merhaba, this is load test"},
                                }
                            ]
                        }
                    }
                ]
            }
        ],
    }
    return json.dumps(payload, separators=(",", ":"))


def signature(body: str, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()


async def run_load(base: str, secret: str, total: int, concurrency: int) -> None:
    timeout = httpx.Timeout(15.0, connect=5.0)
    limits = httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency)
    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        health = await client.get(f"{base}/health")
        csrf = health.headers.get("x-csrf-token", "")

        async def one(i: int):
            body = build_body(i)
            headers = {
                "X-CSRF-Token": csrf,
                "X-Hub-Signature-256": signature(body, secret),
                "Content-Type": "application/json",
            }
            async with sem:
                t0 = time.perf_counter()
                try:
                    r = await client.post(f"{base}/api/whatsapp/webhook", content=body, headers=headers)
                    return r.status_code, time.perf_counter() - t0
                except Exception:
                    return 0, time.perf_counter() - t0

        start = time.perf_counter()
        results = await asyncio.gather(*[one(i) for i in range(total)])
        elapsed = time.perf_counter() - start

    statuses = Counter([s for s, _ in results])
    lats = [lat for _, lat in results]
    lats_sorted = sorted(lats)

    def pct(p: float) -> float:
        idx = min(len(lats_sorted) - 1, int(len(lats_sorted) * p))
        return lats_sorted[idx]

    print(f"total={total}")
    print(f"concurrency={concurrency}")
    print(f"elapsed_sec={elapsed:.3f}")
    print(f"rps={total/elapsed:.2f}")
    print(f"status_counts={dict(statuses)}")
    print(f"lat_avg_ms={sum(lats)/len(lats)*1000:.1f}")
    print(f"lat_p50_ms={pct(0.50)*1000:.1f}")
    print(f"lat_p95_ms={pct(0.95)*1000:.1f}")
    print(f"lat_p99_ms={pct(0.99)*1000:.1f}")


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_load(args.base, args.secret, args.total, args.concurrency))
