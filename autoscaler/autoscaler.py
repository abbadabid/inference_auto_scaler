import time
import requests
from kubernetes import client, config

# Load in-cluster config
config.load_incluster_config()
apps_v1 = client.AppsV1Api()

# Configuration
DISPATCHER_METRICS_URL = "http://dispatcher-service:5000/metrics/json"
DEPLOYMENT_NAME = "resnet-deployment"
NAMESPACE = "default"
MIN_REPLICAS = 1
MAX_REPLICAS = 6
INTERVAL = 2

# Thresholds
SCALE_UP_QUEUE_THRESHOLD = 2
SCALE_UP_LATENCY_THRESHOLD = 0.45   # scale up if p99 > 0.45s
SCALE_DOWN_LATENCY_THRESHOLD = 0.35  # scale down if p99 < 0.3s

# Cooldown tracking
last_scale_up_time = 0
last_scale_down_time = 0
SCALE_UP_COOLDOWN = 15    # wait 15s before scaling up again
SCALE_DOWN_COOLDOWN = 30  # wait 30s before scaling down again

def get_realtime_metrics():
    try:
        response = requests.get(DISPATCHER_METRICS_URL, timeout=5)
        data = response.json()
        return data.get("queue_length", 0), data.get("p99_latency", 0.0)
    except Exception as e:
        print(f"Failed to fetch metrics from dispatcher: {e}")
        return 0, 0.0

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
        print(f"P99 latency: {p99_latency}s")
        print(f"Current replicas: {current_replicas}")

        # ── Scale UP logic ──────────────────────────────
        if queue_length > SCALE_UP_QUEUE_THRESHOLD or p99_latency > SCALE_UP_LATENCY_THRESHOLD:
            if now - last_scale_up_time > SCALE_UP_COOLDOWN:
                # Aggressive scale up for heavy load
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
              p99_latency < SCALE_DOWN_LATENCY_THRESHOLD and 
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