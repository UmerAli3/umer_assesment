import csv
import statistics

FIELDS = ["timeStamp", "elapsed", "label", "responseCode", "responseMessage",
          "threadName", "dataType", "success", "bytes", "sentBytes",
          "grpThreads", "allThreads"]

rows = []
with open("results/results.jtl") as f:
    reader = csv.reader(f)
    for r in reader:
        row = dict(zip(FIELDS, r))
        rows.append(row)

print(f"Total samples: {len(rows)}\n")


def pct(sorted_vals, p):
    if not sorted_vals:
        return 0
    k = (len(sorted_vals) - 1) * (p / 100)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def summarize(label, subset):
    elapsed = sorted(int(r["elapsed"]) for r in subset)
    errors = sum(1 for r in subset if r["success"] != "true")
    n = len(subset)
    ts = [int(r["timeStamp"]) for r in subset]
    duration_s = (max(ts) - min(ts)) / 1000.0 if len(ts) > 1 else 1
    throughput = n / duration_s if duration_s > 0 else 0

    print(f"--- {label} ---")
    print(f"  Samples:      {n}")
    print(f"  Errors:       {errors} ({errors/n*100:.2f}%)")
    print(f"  Throughput:   {throughput:.2f} req/s")
    print(f"  Average (ms): {statistics.mean(elapsed):.1f}")
    print(f"  Median  (ms): {statistics.median(elapsed):.1f}")
    print(f"  P90     (ms): {pct(elapsed, 90):.1f}")
    print(f"  P95     (ms): {pct(elapsed, 95):.1f}")
    print(f"  P99     (ms): {pct(elapsed, 99):.1f}")
    print(f"  Min     (ms): {min(elapsed)}")
    print(f"  Max     (ms): {max(elapsed)}")
    print()
    return {
        "label": label, "samples": n, "errors": errors, "error_pct": round(errors/n*100, 2),
        "throughput": round(throughput, 2), "avg_ms": round(statistics.mean(elapsed), 1),
        "median_ms": round(statistics.median(elapsed), 1),
        "p90_ms": round(pct(elapsed, 90), 1), "p95_ms": round(pct(elapsed, 95), 1),
        "p99_ms": round(pct(elapsed, 99), 1), "min_ms": min(elapsed), "max_ms": max(elapsed)
    }


overall = summarize("OVERALL (all endpoints combined)", rows)

labels = sorted(set(r["label"] for r in rows))
per_endpoint = []
for lbl in labels:
    subset = [r for r in rows if r["label"] == lbl]
    per_endpoint.append(summarize(lbl, subset))

import json
with open("results/summary_stats.json", "w") as f:
    json.dump({"overall": overall, "per_endpoint": per_endpoint}, f, indent=2)
print("Saved to results/summary_stats.json")
