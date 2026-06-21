"""Concurrency / Performance Test for Face Check-in System"""
import requests
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "http://120.27.120.99:8080"

# Get fresh token before running
def get_token():
    r = requests.post(f"{BASE}/api/auth/login", json={"username":"admin","password":"Test512"}, timeout=10)
    return r.json()["access_token"]

TOKEN = get_token()
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

RESULTS = {}

def bench(name, func, concurrency, count):
    """Run func `count` times with `concurrency` workers. Measure latency & throughput."""
    print(f"\n[Bench] {name} (concurrency={concurrency}, total={count})")
    latencies = []
    errors = 0
    start = time.time()

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(func) for _ in range(count)]
        for f in as_completed(futures):
            try:
                lat, ok = f.result()
                latencies.append(lat)
                if not ok: errors += 1
            except:
                errors += 1

    elapsed = time.time() - start
    qps = count / elapsed if elapsed > 0 else 0

    latencies.sort()
    p50 = latencies[int(len(latencies) * 0.5)] if latencies else 0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0
    avg = statistics.mean(latencies) if latencies else 0

    result = {
        "concurrency": concurrency, "total": count, "errors": errors,
        "elapsed_s": round(elapsed, 2), "qps": round(qps, 1),
        "latency_avg_ms": round(avg * 1000, 1),
        "latency_p50_ms": round(p50 * 1000, 1),
        "latency_p95_ms": round(p95 * 1000, 1),
        "latency_p99_ms": round(p99 * 1000, 1),
    }
    RESULTS[name] = result

    print(f"  Elapsed: {elapsed:.2f}s  QPS: {qps:.1f}  Errors: {errors}")
    print(f"  Latency: avg={avg*1000:.0f}ms  p50={p50*1000:.0f}ms  p95={p95*1000:.0f}ms  p99={p99*1000:.0f}ms")
    return result

# ── Test Scenarios ──

def health_check():
    t0 = time.time()
    r = requests.get(f"{BASE}/api/health", timeout=10)
    return time.time() - t0, r.status_code == 200

def get_statistics():
    t0 = time.time()
    r = requests.get(f"{BASE}/api/admin/statistics", headers=HEADERS, timeout=10)
    return time.time() - t0, r.status_code == 200

def list_users():
    t0 = time.time()
    r = requests.get(f"{BASE}/api/admin/users", headers=HEADERS, timeout=10)
    return time.time() - t0, r.status_code == 200

def generate_qr():
    t0 = time.time()
    r = requests.post(f"{BASE}/api/qr/generate", headers=HEADERS,
                      json={"type":"checkin","location_id":1}, timeout=10)
    return time.time() - t0, r.status_code == 200

def get_sessions():
    t0 = time.time()
    r = requests.get(f"{BASE}/api/admin/sessions/active", headers=HEADERS, timeout=10)
    return time.time() - t0, r.status_code == 200

def check_status():
    t0 = time.time()
    r = requests.get(f"{BASE}/api/check/status?user_id=2", timeout=10)
    return time.time() - t0, r.status_code == 200

print("=" * 65)
print("FACE CHECK-IN -- CONCURRENCY TEST")
print(f"Target: {BASE}")
print("=" * 65)

# Light: 10 concurrent, 50 requests
bench("Health (light)", health_check, 10, 50)
bench("Statistics (light)", get_statistics, 10, 50)
bench("List Users (light)", list_users, 10, 50)
bench("Check Status (light)", check_status, 10, 50)
bench("Generate QR (light)", generate_qr, 10, 50)
bench("List Sessions (light)", get_sessions, 10, 50)

# Medium: 50 concurrent, 200 requests
bench("Health (medium)", health_check, 50, 200)
bench("Statistics (medium)", get_statistics, 50, 200)
bench("List Sessions (medium)", get_sessions, 50, 200)

# Heavy: 100 concurrent, 500 requests
bench("Health (heavy)", health_check, 100, 500)
bench("Check Status (heavy)", check_status, 100, 500)

# ── Summary ──
print("\n" + "=" * 85)
print("CONCURRENCY TEST SUMMARY")
print("=" * 85)
print(f"{'Scenario':<30} {'Conc':>5} {'Total':>6} {'Errors':>6} {'QPS':>8} {'Avg(ms)':>8} {'P95(ms)':>8} {'P99(ms)':>8}")
print("-" * 85)
for name, r in RESULTS.items():
    print(f"{name:<30} {r['concurrency']:>5} {r['total']:>6} {r['errors']:>6} {r['qps']:>8.1f} {r['latency_avg_ms']:>8.1f} {r['latency_p95_ms']:>8.1f} {r['latency_p99_ms']:>8.1f}")

# Save
import json
with open(r"D:\test\concurrency_results.json", "w", encoding="utf-8") as f:
    json.dump(RESULTS, f, ensure_ascii=False, indent=2)
print("\nResults saved to D:\\test\\concurrency_results.json")
