import time
import requests
from kubernetes import client, config

# Load in-cluster config
config.load_incluster_config()
apps_v1 = client.AppsV1Api()

# Configuration
PROMETHEUS_URL      = "http://prometheus-kube-prometheus-prometheus.monitoring:9090"
DISPATCHER_FALLBACK = "http://dispatcher-service:5000/metrics/json"
DEPLOYMENT_NAME     = "resnet-deployment"
NAMESPACE           = "default"
MIN_REPLICAS        = 1
MAX_REPLICAS        = 6
INTERVAL            = 5  # check every 5s; fallback to dispatcher when Prometheus is slow

# Thresholds
SCALE_UP_QUEUE_THRESHOLD    = 2
SCALE_UP_LATENCY_THRESHOLD  = 0.45  # scale up if p99 > 0.45s
SCALE_DOWN_LATENCY_THRESHOLD = 0.35  # scale down if p99 < 0.35s

# Cooldown tracking
last_scale_up_time   = 0
last_scale_down_time = 0
SCALE_UP_COOLDOWN    = 15  # wait 15s before scaling up again
SCALE_DOWN_COOLDOWN  = 30  # wait 30s before scaling down again

def query_prometheus(promql):
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": promql},
            timeout=5
        )
        result = response.json()["data"]["result"]
        if result:
            return float(result[0]["value"][1])
        return 0.0
    except Exception as e:
        print(f"Prometheus query error ({promql}): {e}")
        return None  # signals fetch failure

def get_realtime_metrics():
    queue_length = query_prometheus("dispatcher_queue_length")
    p99_latency  = query_prometheus("dispatcher_p99_latency_seconds")

    # Fallback to dispatcher /metrics/json when Prometheus is unavailable
    if queue_length is None or p99_latency is None:
        try:
            response = requests.get(DISPATCHER_FALLBACK, timeout=3)
            data = response.json()
            print("Using dispatcher fallback for metrics")
            return data.get("queue_length", 0), data.get("p99_latency", 0.0)
        except Exception as e:
            print(f"Dispatcher fallback also failed: {e}")
            return None, None

    return queue_length, p99_latency

def get_current_replicas():
    try:
        deployment = apps_v1.read_namespaced_deployment(
            name=DEPLOYMENT_NAME,
            namespace=NAMESPACE
        )
        return deployment.spec.replicas
    except Exception as e:
        print(f"Failed to get replicas: {e}")
        return 1

def scale_deployment(replicas):
    try:
        replicas = max(MIN_REPLICAS, min(MAX_REPLICAS, replicas))
        apps_v1.patch_namespaced_deployment_scale(
            name=DEPLOYMENT_NAME,
            namespace=NAMESPACE,
            body={"spec": {"replicas": replicas}}
        )
        print(f"Scaled to {replicas} replicas")
    except Exception as e:
        print(f"Failed to scale: {e}")

def autoscaler_loop():
    global last_scale_up_time, last_scale_down_time

    while True:
        queue_length, p99_latency = get_realtime_metrics()
        current_replicas = get_current_replicas()
        now = time.time()

        print(f"\n--- Autoscaler Check ---")
        print(f"Queue length: {queue_length}")
        print(f"P99 latency: {p99_latency if p99_latency is None else f'{p99_latency}s'}")
        print(f"Current replicas: {current_replicas}")

        # Skip scaling if both sources failed
        if queue_length is None or p99_latency is None:
            print("Skipping scaling decision: metrics unavailable")
            time.sleep(INTERVAL)
            continue

        # ── Scale UP logic ──────────────────────────────
        if queue_length > SCALE_UP_QUEUE_THRESHOLD or p99_latency > SCALE_UP_LATENCY_THRESHOLD:
            if now - last_scale_up_time > SCALE_UP_COOLDOWN:
                if p99_latency > 1.0 or queue_length > 5:
                    target_replicas = current_replicas + 3
                else:
                    target_replicas = current_replicas + 1

                target_replicas = max(MIN_REPLICAS, min(MAX_REPLICAS, target_replicas))

                if target_replicas > current_replicas:
                    print(f"Scaling UP: {current_replicas} → {target_replicas}")
                    scale_deployment(target_replicas)
                    last_scale_up_time = now
                else:
                    print("Already at MAX replicas")
            else:
                remaining = int(SCALE_UP_COOLDOWN - (now - last_scale_up_time))
                print(f"Scale up cooldown: {remaining}s remaining")

        # ── Scale DOWN logic ────────────────────────────
        elif (queue_length == 0 and
              0 < p99_latency < SCALE_DOWN_LATENCY_THRESHOLD and
              current_replicas > MIN_REPLICAS):
            if now - last_scale_down_time > SCALE_DOWN_COOLDOWN:
                target_replicas = current_replicas - 1
                print(f"Scaling DOWN: {current_replicas} → {target_replicas}")
                scale_deployment(target_replicas)
                last_scale_down_time = now
            else:
                remaining = int(SCALE_DOWN_COOLDOWN - (now - last_scale_down_time))
                print(f"Scale down cooldown: {remaining}s remaining")

        else:
            print("No scaling needed")

        time.sleep(INTERVAL)

if __name__ == '__main__':
    print("Starting Autoscaler...")
    autoscaler_loop()
