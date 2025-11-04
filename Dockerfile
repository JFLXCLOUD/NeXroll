# NeXroll Docker Image
# Multi-stage build for optimized image size
# This Dockerfile is for GitHub Actions builds (repository root context)

# Stage 1: Build frontend
FROM node:18-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy frontend package files
COPY frontend/package*.json ./
RUN npm ci --only=production

# Copy frontend source
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime
FROM python:3.11-slim

LABEL maintainer="JFLXCLOUD"
LABEL description="NeXroll - Advanced Preroll Management for Plex and Jellyfin"
LABEL version="1.7.0"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    NEXROLL_DB_DIR=/app/data

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ffprobe \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy backend requirements and install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./backend/

# Create version.py (since it's not in git)
RUN echo "__version__ = '1.7.0'" > version.py && \
    echo "def get_version():" >> version.py && \
    echo "    return __version__" >> version.py

# Copy built frontend from previous stage
COPY --from=frontend-builder /app/frontend/build ./frontend/build

# Create data directories
RUN mkdir -p /app/data/prerolls \
    && mkdir -p /app/data/logs \
    && mkdir -p /app/data/db \
    && mkdir -p /app/data/thumbnails

# Create non-root user
RUN useradd -m -u 1000 nexroll && \
    chown -R nexroll:nexroll /app

USER nexroll

# Expose port
EXPOSE 9393

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9393/system/version')" || exit 1

# Start command
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "9393"]
