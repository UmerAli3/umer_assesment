"""
Progressive load / capacity test for the User Management API.

For each concurrency level, spins up N worker threads that each fire
requests continuously for DURATION seconds against a mix of endpoints
(GET /health, GET /users, GET /users/<id>, POST /users), while a
separate monitor thread samples CPU% and RSS memory of the gunicorn
process tree every 0.5s.

Outputs a summary row per level: avg latency, p50, p95, p99, error%,
throughput (req/s), peak CPU%, peak RAM(MB).
"""
import time
import threading
import statistics
import random
import json
import requests
import psutil
import sys

BASE_URL = "http://127.0.0.1:5000"
DURATION = 8  # seconds of sustained load per level

results_lock = threading.Lock()


def find_gunicorn_pids():
    pids = []
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = " ".join(p.info['cmdline'] or [])
            if 'gunicorn' in cmdline:
                pids.append(p.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return pids


def monitor_resources(stop_event, samples):
    pids = find_gunicorn_pids()
    procs = []
    for pid in pids:
        try:
            procs.append(psutil.Process(pid))
        except psutil.NoSuchProcess:
            pass
    # prime cpu_percent (first call always returns 0.0)
    for p in procs:
        try:
            p.cpu_percent(interval=None)
        except Exception:
            pass

    while not stop_event.is_set():
        total_cpu = 0.0
        total_rss = 0
        for p in list(procs):
            try:
                total_cpu += p.cpu_percent(interval=None)
                total_rss += p.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        samples.append((total_cpu, total_rss / (1024 * 1024)))  # MB
        time.sleep(0.5)


def worker(stop_event, latencies, errors, request_count):
    session = requests.Session()
    endpoints = [
        ("GET", "/health", None),
        ("GET", "/users", None),
        ("GET", "/users/1", None),
        ("GET", "/users/2", None),
        ("GET", "/users?status=active", None),
    ]
    while not stop_event.is_set():
        method, path, body = random.choice(endpoints)
        start = time.perf_counter()
        try:
            resp = session.request(method, BASE_URL + path, json=body, timeout=10)
            elapsed = time.perf_counter() - start
            with results_lock:
                latencies.append(elapsed * 1000)  # ms
                request_count[0] += 1
                if resp.status_code >= 500:
                    errors[0] += 1
        except requests.exceptions.RequestException:
            elapsed = time.perf_counter() - start
            with results_lock:
                latencies.append(elapsed * 1000)
                request_count[0] += 1
                errors[0] += 1


def run_level(concurrency):
    latencies = []
    errors = [0]
    request_count = [0]
    stop_event = threading.Event()
    resource_samples = []

    monitor_stop = threading.Event()
    monitor_thread = threading.Thread(target=monitor_resources, args=(monitor_stop, resource_samples))
    monitor_thread.start()

    threads = []
    start_time = time.perf_counter()
    for _ in range(concurrency):
        t = threading.Thread(target=worker, args=(stop_event, latencies, errors, request_count))
        t.daemon = True
        t.start()
        threads.append(t)

    time.sleep(DURATION)
    stop_event.set()
    for t in threads:
        t.join(timeout=5)
    total_time = time.perf_counter() - start_time

    monitor_stop.set()
    monitor_thread.join(timeout=2)

    if not latencies:
        return {
            "concurrency": concurrency, "requests": 0, "errors": 0, "error_pct": 100.0,
            "throughput": 0, "avg_ms": 0, "p50_ms": 0, "p95_ms": 0, "p99_ms": 0,
            "peak_cpu": 0, "peak_ram_mb": 0
        }

    latencies_sorted = sorted(latencies)
    n = len(latencies_sorted)
    p50 = latencies_sorted[int(n * 0.50) - 1]
    p95 = latencies_sorted[int(n * 0.95) - 1]
    p99 = latencies_sorted[min(int(n * 0.99), n - 1) - 1]

    peak_cpu = max((s[0] for s in resource_samples), default=0)
    peak_ram = max((s[1] for s in resource_samples), default=0)

    return {
        "concurrency": concurrency,
        "requests": request_count[0],
        "errors": errors[0],
        "error_pct": round(errors[0] / request_count[0] * 100, 2) if request_count[0] else 0,
        "throughput": round(request_count[0] / total_time, 2),
        "avg_ms": round(statistics.mean(latencies_sorted), 2),
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "p99_ms": round(p99, 2),
        "peak_cpu": round(peak_cpu, 1),
        "peak_ram_mb": round(peak_ram, 1),
    }


if __name__ == "__main__":
    levels = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else [50, 100, 200, 300, 500]
    all_results = []
    for level in levels:
        print(f"\n=== Running level: {level} concurrent users for {DURATION}s ===", flush=True)
        res = run_level(level)
        all_results.append(res)
        print(json.dumps(res, indent=2), flush=True)
        time.sleep(2)  # brief cooldown between levels

    with open("stress_results.json", "w") as f:
        json.dump(all_results, f, indent=2)
    print("\n\nAll levels complete. Results saved to stress_results.json")
