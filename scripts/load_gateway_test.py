import concurrent.futures
import statistics
import time
import urllib.error
import urllib.request

TESTS = [
    ("auth_health", "http://localhost:8081/api/auth/health", 200, 300, 40),
    ("integration_health", "http://localhost:8081/api/integration/health", 200, 300, 40),
]


def fetch(url: str, timeout: float = 5.0):
    t0 = time.perf_counter()
    status = 0
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            status = r.getcode()
    except urllib.error.HTTPError as e:
        status = e.code
    except Exception:
        status = 0
    latency = time.perf_counter() - t0
    return status, latency


for name, url, expected_status, total, workers in TESTS:
    start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(fetch, url) for _ in range(total)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    elapsed = time.perf_counter() - start

    statuses = [s for s, _ in results]
    latencies = [l for _, l in results]

    ok = sum(1 for s in statuses if s == expected_status)
    fail = len(statuses) - ok
    lat_sorted = sorted(latencies)

    def pct(p: float):
        idx = min(len(lat_sorted) - 1, int(len(lat_sorted) * p))
        return lat_sorted[idx] * 1000

    print(f"[{name}]")
    print(f"total={total} workers={workers}")
    print(f"ok={ok} fail={fail}")
    print(f"elapsed_sec={elapsed:.3f}")
    print(f"rps={total/elapsed:.2f}")
    print(f"lat_avg_ms={statistics.fmean(latencies)*1000:.2f}")
    print(f"lat_p50_ms={pct(0.50):.2f}")
    print(f"lat_p95_ms={pct(0.95):.2f}")
    print(f"lat_p99_ms={pct(0.99):.2f}")
    print()
