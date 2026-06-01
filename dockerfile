# Use a slim Python 3.11 image for a smaller footprint
FROM python:3.11-slim

# Install light system dependencies often needed by Torch/PIL
RUN apt-get update && apt-get install -y \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first to leverage Docker's cache
COPY requirements.txt .

# Install dependencies using the CPU-only PyTorch index
RUN pip install --no-cache-dir -r requirements.txt

# Copy your model_server.py and any other files
COPY . .

# Tell Docker that the container listens on port 8001
EXPOSE 8001

# Start the server
CMD ["python", "model_server.py"]