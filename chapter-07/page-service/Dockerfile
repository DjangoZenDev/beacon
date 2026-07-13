# Beacon v0.7 — Page Service Dockerfile
#
# Minimal Python Docker image for the page-service gRPC server.
# Multi-stage build keeps the final image small.

FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies for grpcio.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime stage ──────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /install /usr/local

COPY page-service/ ./page-service/
COPY core/ ./core/
COPY beacon/ ./beacon/
COPY manage.py .

ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=beacon.settings

EXPOSE 50051

CMD ["python", "page-service/server.py"]
