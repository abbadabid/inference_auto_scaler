from fastapi import FastAPI, UploadFile, File
from fastapi.responses import Response
import requests
import cv2
import base64
import json
import numpy as np
import asyncio
import time
from collections import deque
from prometheus_client import Gauge, Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = FastAPI()

# Resnet service URL (Kubernetes DNS)
RESNET_URL = "http://resnet-service:8001/infer"

# Queue to store incoming requests
request_queue = asyncio.Queue()

# Metrics storage
latencies = deque(maxlen=100) #p99 is calculated from this
total_requests_count = 0

# Prometheus metrics
QUEUE_LENGTH = Gauge("dispatcher_queue_length", "Number of requests in queue")
TOTAL_REQUESTS = Counter("dispatcher_total_requests", "Total number of requests received")
LATENCY_HISTOGRAM = Histogram("dispatcher_request_latency_seconds", "Request latency in seconds")
P99_LATENCY = Gauge("dispatcher_p99_latency_seconds", "99th percentile latency in seconds")

@app.post("/predict")
async def predict(image: UploadFile = File(...)):
    global total_requests_count

    # Read and preprocess image
    contents = await image.read()
    img_array = np.frombuffer(contents, np.uint8)
    im = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    im = cv2.resize(im, dsize=(256, 256), interpolation=cv2.INTER_CUBIC)
    encoded = base64.b64encode(cv2.imencode(".jpeg", im)[1].tobytes()).decode("utf-8")

    # Create a future to get result back
    future = asyncio.get_event_loop().create_future()

    # Add to queue
    await request_queue.put((encoded, future))
    QUEUE_LENGTH.set(request_queue.qsize())
    TOTAL_REQUESTS.inc()
    total_requests_count += 1

    # Wait for result
    result = await future
    return result

# Background worker that processes queue
async def worker():
    while True:
        if not request_queue.empty():
            encoded, future = await request_queue.get()
            QUEUE_LENGTH.set(request_queue.qsize())

            start = time.perf_counter()
            try:
                response = requests.post(
                    RESNET_URL,
                    data=json.dumps({"data": encoded})
                )
                latency = time.perf_counter() - start
                latencies.append(latency)

                # Update Prometheus metrics
                LATENCY_HISTOGRAM.observe(latency)
                if latencies:
                    sorted_latencies = sorted(latencies)
                    p99_index = max(0, int(len(sorted_latencies) * 0.99) - 1)
                    p99 = sorted_latencies[p99_index]
                    P99_LATENCY.set(p99)

                future.set_result(response.json())
            except Exception as e:
                future.set_exception(e)
        else:
            await asyncio.sleep(0.01)

# JSON metrics endpoint (for autoscaler)
@app.get("/metrics/json")
async def get_metrics_json():
    sorted_lat = sorted(latencies)
    p99_index = max(0, int(len(sorted_lat) * 0.99) - 1)
    p99 = sorted_lat[p99_index] if sorted_lat else 0
    return {
        "queue_length": request_queue.qsize(),
        "total_requests": total_requests_count,
        "p99_latency": round(p99, 3)
    }

# Prometheus metrics endpoint
@app.get("/metrics")
async def get_metrics_prometheus():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

@app.on_event("startup")
async def startup_event():
    # Start 7 parallel workers to process queue
    for _ in range(7):
        asyncio.create_task(worker())

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)