# syntax=docker/dockerfile:1

# --- Backend runtime stage ---
FROM python:3.12-slim

ARG APP_VERSION=dev
ARG VERSION=dev
LABEL org.opencontainers.image.title="NeXroll" \
      org.opencontainers.image.description="NeXroll preroll management system" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NEXROLL_PORT=9393 \
    NEXROLL_DB_DIR=/data \
    NEXROLL_PREROLL_PATH=/data/prerolls \
    NEXROLL_SECRETS_DIR=/data \
    PLEX_URL="" \
    JELLYFIN_URL="" \
    TZ=UTC

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        tzdata \
        build-essential \
        rustc \
        cargo \
        pkg-config && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app/NeXroll

# Install Python deps (use root requirements.txt with all dependencies)
COPY requirements.txt /app/NeXroll/requirements.txt
RUN pip install --no-cache-dir -r /app/NeXroll/requirements.txt

# Copy backend
COPY NeXroll/backend /app/NeXroll/backend

# Copy version.py
COPY NeXroll/version.py /app/NeXroll/version.py

# Copy CHANGELOG
COPY NeXroll/CHANGELOG.md /app/NeXroll/CHANGELOG.md

# Copy pre-built frontend assets (built locally before Docker build)
COPY NeXroll/frontend/build /app/NeXroll/frontend/build

# Prepare persistent data volume
RUN mkdir -p /data /data/prerolls

VOLUME ["/data"]

EXPOSE 9393

# Healthcheck: FastAPI health endpoint
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -fsS http://localhost:${NEXROLL_PORT:-9393}/health || exit 1

# Start Uvicorn
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${NEXROLL_PORT:-9393}"]
