FROM python:3.9-slim

WORKDIR /app

# Install FFmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY worker/ /app/worker
COPY shared/ /app/shared

# Create upload directory
RUN mkdir -p /app/uploads

ENV PYTHONPATH=/app

CMD ["python", "-m", "worker.app.main"]
