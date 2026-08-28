FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV PYTHONUNBUFFERED=1 \
    CACHE_DIR=/app/.cache \
    PYTHONDONTWRITEBYTECODE=1

RUN mkdir -p /app/.cache

EXPOSE 8000

# Single worker: in-process SWR cache is not shared across workers.
HEALTHCHECK --interval=30s --timeout=8s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/api/ready || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-keep-alive", "75"]
