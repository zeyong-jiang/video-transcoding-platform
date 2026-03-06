FROM python:3.9-slim

WORKDIR /app

COPY api_gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api_gateway/ /app/api_gateway
COPY shared/ /app/shared

# Create upload directory
RUN mkdir -p /app/uploads

ENV PYTHONPATH=/app

CMD ["uvicorn", "api_gateway.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
