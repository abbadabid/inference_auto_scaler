import httpx
import time
import random
import os
import csv
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor

# ── Config ───────────────────────────────────────────────────────────────────
DISPATCHER_URL = "http://127.0.0.1:64826/predict"
WORKLOAD_FILE  = "workload.txt"
IMAGE_DIR      = "./test_images"
RESULTS_FILE   = "hpa90_results.csv"
REPLICAS_FILE  = RESULTS_FILE.replace("results", "replicas")  # e.g. replicas_hpa90.csv

# ── Load workload ─────────────────────────────────────────────────────────────
with open(WORKLOAD_FILE) as f:
    WORKLOAD = [int(x) for x in f.read().split()]

# ── Load images ───────────────────────────────────────────────────────────────
images = [
    os.path.join(IMAGE_DIR, f)
    for f in os.listdir(IMAGE_DIR)
    if f.endswith((".jpg", ".jpeg", ".JPEG"))
]

if not images:
    raise RuntimeError(f"No images found in {IMAGE_DIR}")

print(f"Loaded {len(images)} images from {IMAGE_DIR}")

# ── Replica tracking (background thread) ─────────────────────────────────────
replica_records = []
_stop_tracking = threading.Event()

def _get_replicas():
    try:
        out = subprocess.check_output(
            ["kubectl", "get", "deployment", "resnet-deployment",
             "-o", "jsonpath={.status.readyReplicas}"],
            stderr=subprocess.DEVNULL
        )
        val = out.decode().strip()
        return int(val) if val else 0
    except Exception:
        return 0

def _track_replicas(start_time):
    while not _stop_tracking.is_set():
        elapsed = round(time.time() - start_time)
        replica_records.append({"second": elapsed, "replicas": _get_replicas()})
        time.sleep(5)  # sample every 5 seconds

# ── Single request function ───────────────────────────────────────────────────
def send_request(second: int) -> dict:
    image_path = random.choice(images)
    t_start = time.time()
    try:
        with open(image_path, "rb") as img:
            r = httpx.post(
                DISPATCHER_URL,
                files={"image": img},
                timeout=60
            )
        latency = time.time() - t_start
        return {
            "second": second,
            "latency": latency,
            "status": r.status_code
        }
    except Exception as e:
        latency = time.time() - t_start
        return {
            "second": second,
            "latency": latency,
            "status": f"error: {str(e)}"
        }

# ── Main loop ─────────────────────────────────────────────────────────────────
results = []
all_futures = []

print(f"Starting load test: {len(WORKLOAD)} seconds, "
      f"max {max(WORKLOAD)} rps, total ~{sum(WORKLOAD)} requests")
print(f"Targeting: {DISPATCHER_URL}\n")

test_start = time.time()
tracker = threading.Thread(target=_track_replicas, args=(test_start,), daemon=True)
tracker.start()

with ThreadPoolExecutor(max_workers=150) as executor:
    for second, target_rps in enumerate(WORKLOAD):
        t_second_start = time.time()

        for _ in range(target_rps):
            all_futures.append(executor.submit(send_request, second))

        elapsed = time.time() - t_second_start
        sleep_time = 1.0 - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)

        print(f"[s={second:>3}] rps={target_rps:>2} dispatched")

    print("\nAll requests dispatched! Waiting for responses...")
    for f in all_futures:
        results.append(f.result())

_stop_tracking.set()

# ── Calculate results ─────────────────────────────────────────────────────────
successful = [r for r in results if r["status"] == 200]
failed = [r for r in results if r["status"] != 200]
successful_latencies = [r["latency"] for r in successful]

print(f"\n--- Final Results ---")
print(f"Total requests:  {len(results)}")
print(f"Successful:      {len(successful)}")
print(f"Failed:          {len(failed)}")

if successful_latencies:
    sorted_lat = sorted(successful_latencies)
    p50 = sorted_lat[int(len(sorted_lat) * 0.50) - 1]
    p99 = sorted_lat[int(len(sorted_lat) * 0.99) - 1]
    avg = sum(successful_latencies) / len(successful_latencies)
    print(f"Average latency: {avg:.3f}s")
    print(f"P50 latency:     {p50:.3f}s")
    print(f"P99 latency:     {p99:.3f}s")

if failed:
    print(f"\nFailed request reasons:")
    reasons = {}
    for r in failed:
        reasons[r["status"]] = reasons.get(r["status"], 0) + 1
    for reason, count in reasons.items():
        print(f"  {reason}: {count}")

# ── Save latency results ──────────────────────────────────────────────────────
with open(RESULTS_FILE, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["second", "latency", "status"])
    writer.writeheader()
    writer.writerows(results)
print(f"Latency results saved to {RESULTS_FILE}")

# ── Save replica records ──────────────────────────────────────────────────────
with open(REPLICAS_FILE, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["second", "replicas"])
    writer.writeheader()
    writer.writerows(replica_records)
print(f"Replica records saved to {REPLICAS_FILE}")
