# Elastic ML Inference Autoscaler on Kubernetes

Autoscaling system for an image classification service (ResNet) on Minikube.
The custom autoscaler uses queue length and p99 latency (via Prometheus) to outperform Kubernetes HPA.

---

## System Components

### 1. ResNet Inference Service (`resnet/`)
- Containerized ML model that classifies images
- Each replica has CPU request and limit of 1
- Listens on port 8001, endpoint: `POST /infer`
- Image: `abbad470/resnet:latest`

### 2. Dispatcher (`dispatcher/`)
- Single entry point for all incoming requests
- Maintains an async queue — requests wait here until a resnet replica is free
- 7 background workers process the queue in parallel
- Exposes metrics:
  - `GET /metrics` — Prometheus format (scraped every 15s)
  - `GET /metrics/json` — JSON format (autoscaler fallback)
- Key metrics: `dispatcher_queue_length`, `dispatcher_p99_latency_seconds`
- Image: `abbad470/dispatcher:latest`

### 3. Custom Autoscaler (`autoscaler/`)
- Runs inside the cluster, checks metrics every 5 seconds
- Reads `dispatcher_queue_length` and `dispatcher_p99_latency_seconds` from Prometheus
- Falls back to `dispatcher/metrics/json` if Prometheus is unavailable
- Scales up if: `queue_length > 2` OR `p99_latency > 0.45s`
- Scales down if: `queue_length == 0` AND `0 < p99_latency < 0.35s`
- Min replicas: 1, Max replicas: 6
- Image: `abbad470/autoscaler:latest`

### 4. Prometheus + Grafana (`k8s/servicemonitor.yaml`)
- Installed via Helm (`kube-prometheus-stack`)
- Scrapes dispatcher metrics every 15 seconds
- ServiceMonitor configures the scrape target

### 5. Load Tester (`load_test.py`)
- Sends requests to the dispatcher following `workload.txt` (requests/second)
- Records client-side latency, replica count, and server-side p99 latency
- Outputs 3 CSV files per experiment

---

## Project Structure

```
├── resnet/               ResNet inference service
├── dispatcher/           Dispatcher server
├── autoscaler/           Custom autoscaler
├── k8s/
│   ├── deployment.yaml       All deployments and services
│   ├── autoscaler-rbac.yaml  RBAC permissions for autoscaler
│   ├── servicemonitor.yaml   Prometheus scrape config
│   ├── hpa-70.yaml           HPA at 70% CPU target
│   └── hpa-90.yaml           HPA at 90% CPU target
├── load_test.py          Load testing script
├── plot_results.py       Generates comparison plots
└── workload.txt          Requests/second workload pattern
```

---

## How to Run

### Prerequisites
- Minikube, kubectl, Docker, Helm installed
- Docker Hub account (or use existing images)

### 1. Start Minikube
```bash
minikube start
```

### 2. Deploy all components
```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/autoscaler-rbac.yaml
```

### 3. Install Prometheus
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace
```

### 4. Apply ServiceMonitor
```bash
kubectl apply -f k8s/servicemonitor.yaml
```

### 5. Verify all pods are running
```bash
kubectl get pods
kubectl get pods -n monitoring
```

---

## Running Experiments

### Experiment 1 — Custom Autoscaler
```bash
# Confirm HPA is deleted and autoscaler is running
kubectl get hpa                                          # must be empty
kubectl scale deployment autoscaler-deployment --replicas=1

# Get dispatcher URL
minikube service dispatcher-service --url

# Update DISPATCHER_URL and RESULTS_FILE="custom_autoscaler_results.csv" in load_test.py
python3 load_test.py
```

### Experiment 2 — HPA 70%
```bash
kubectl scale deployment autoscaler-deployment --replicas=0
kubectl scale deployment resnet-deployment --replicas=1
kubectl apply -f k8s/hpa-70.yaml
kubectl get hpa -w   # wait until TARGETS shows a real CPU%

# Update RESULTS_FILE="hpa70_autoscaler_results.csv" in load_test.py
python3 load_test.py

kubectl delete hpa resnet-hpa
```

### Experiment 3 — HPA 90%
```bash
kubectl scale deployment resnet-deployment --replicas=1
kubectl apply -f k8s/hpa-90.yaml
kubectl get hpa -w   # wait until TARGETS shows a real CPU%

# Update RESULTS_FILE="hpa90_autoscaler_results.csv" in load_test.py
python3 load_test.py

kubectl delete hpa resnet-hpa
```

### Generate Plots
```bash
python3 plot_results.py
# outputs: comparison.png
```

---

## Verifying Server-side Latency

```bash
# Port-forward Prometheus
kubectl port-forward -n monitoring \
  svc/prometheus-kube-prometheus-prometheus 9090:9090

# Open http://localhost:9090 and query:
# dispatcher_p99_latency_seconds
```

Server-side p99 latency remained below 0.5s throughout all experiments.

---

## Rebuilding Images (if code is changed)

```bash
# Dispatcher
cd dispatcher
docker build -t abbad470/dispatcher:latest .
docker push abbad470/dispatcher:latest
kubectl rollout restart deployment dispatcher-deployment

# Autoscaler
cd autoscaler
docker build -t abbad470/autoscaler:latest .
docker push abbad470/autoscaler:latest
kubectl rollout restart deployment autoscaler-deployment
```
