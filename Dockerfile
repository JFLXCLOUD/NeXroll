# syntax=docker/dockerfile:1

# --- Build stage: compile Python wheels with native deps ---
FROM python:3.12-slim AS builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        rustc \
        cargo \
        pkg-config && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# --- PO-token provider build stage (bgutil) ---
# Builds the YouTube Proof-of-Origin token server. This is what gets NeX-Up past
# YouTube's "Sign in to confirm you're not a bot" wall. node:22 + bookworm keeps
# it glibc-compatible with the python:3.12-slim runtime so we can copy node and
# the (native-canvas) node_modules across stages. node:22 (>=22.12) is required
# because the provider's jsdom stack pulls an ESM-only @exodus/bytes that is
# loaded via require(); on Node <22.12 that crashes the server at startup with
# ERR_REQUIRE_ESM. Keep BGUTIL_VERSION in sync with the bgutil-ytdlp-pot-provider
# pin in requirements.txt.
FROM node:22-bookworm-slim AS potoken
ARG BGUTIL_VERSION=1.3.1
# ca-certificates is required for the HTTPS git clone below (the slim node image
# ships without it, so the clone fails with "server certificate verification
# failed"). git pulls the provider; the rest are a fallback toolchain in case
# node-canvas has no prebuilt binary for this arch and builds from source.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git python3 build-essential pkg-config \
        libcairo2-dev libpango1.0-dev libjpeg-dev libgif-dev librsvg2-dev && \
    rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch ${BGUTIL_VERSION} \
        https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /opt/bgutil-provider && \
    cd /opt/bgutil-provider/server && \
    npm install --no-audit --no-fund && \
    npx tsc

# --- Jellyfin plugin build stage ---
# Builds the NeXroll Intros (Jellyfin) plugin zip so the running container can
# serve it for download from the Connect page (/jellyfin/plugin/download). Kept
# self-contained so the image always ships the plugin matching this build.
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS pluginbuild
WORKDIR /pluginsrc
COPY Plugins/NeXroll.Jellyfin/ ./
RUN apt-get update && apt-get install -y --no-install-recommends zip && \
    rm -rf /var/lib/apt/lists/* && \
    dotnet publish NeXroll.Jellyfin.csproj -c Release -o publish && \
    mkdir -p /out && \
    zip -j /out/NeXroll.Jellyfin.zip publish/NeXroll.Jellyfin.dll meta.json thumb.png

# --- Runtime stage: slim image without build tools ---
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
    RADARR_URL="" \
    SONARR_URL="" \
    TZ=UTC

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        unzip \
        tzdata \
        # DejaVu + Liberation fonts so FFmpeg drawtext can render extended-Latin
        # glyphs (German umlauts ä/ö/ü, accents, etc.) in generated prerolls /
        # Coming Soon lists. Without a real fontfile, drawtext falls back to a
        # built-in font with poor coverage and umlauts render as garbage.
        fonts-dejavu-core \
        fonts-liberation && \
    # Remove ncurses binaries (CVE-2025-69720) — not used by NeXroll
    dpkg --remove --force-depends ncurses-base ncurses-bin 2>/dev/null || true && \
    rm -rf /var/lib/apt/lists/*

# Install Deno (required for yt-dlp YouTube extraction)
RUN curl -fsSL https://deno.land/install.sh | sh && \
    ln -s /root/.deno/bin/deno /usr/local/bin/deno

# YouTube PO-token provider: copy the Node runtime + the prebuilt bgutil server
# from the potoken stage, and install the shared libs its native `canvas`
# dependency links against. The backend (backend/nexup_potoken.py) launches
# `node build/main.js` from NEXROLL_BGUTIL_DIR so yt-dlp can mint PO tokens.
COPY --from=potoken /usr/local/bin/node /usr/local/bin/node
COPY --from=potoken /opt/bgutil-provider /opt/bgutil-provider
RUN apt-get update && apt-get install -y --no-install-recommends \
        libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libjpeg62-turbo \
        libgif7 librsvg2-2 libpixman-1-0 libfontconfig1 && \
    rm -rf /var/lib/apt/lists/*
ENV NEXROLL_BGUTIL_DIR=/opt/bgutil-provider/server

WORKDIR /app/NeXroll

# Install pre-built Python wheels (no compiler needed)
COPY --from=builder /wheels /wheels
COPY requirements.txt /app/NeXroll/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --no-index --find-links=/wheels -r /app/NeXroll/requirements.txt && \
    rm -rf /wheels

# Copy backend
COPY NeXroll/backend /app/NeXroll/backend

# Copy version.py
COPY NeXroll/version.py /app/NeXroll/version.py

# Copy CHANGELOG
COPY NeXroll/CHANGELOG.md /app/NeXroll/CHANGELOG.md

# Copy audio assets for Coming Soon generator
COPY docs/lefty-blue-wednesday-main-version-36162-02-38.mp3 /app/docs/lefty-blue-wednesday-main-version-36162-02-38.mp3

# Copy pre-built frontend assets (built locally before Docker build)
COPY NeXroll/frontend/build /app/NeXroll/frontend/build

# Jellyfin plugin package, served for download from the Connect page
COPY --from=pluginbuild /out/NeXroll.Jellyfin.zip /app/plugins/NeXroll.Jellyfin.zip

# Prepare persistent data volume
RUN mkdir -p /data /data/prerolls

VOLUME ["/data"]

EXPOSE 9393

# Healthcheck: FastAPI health endpoint
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -fsS http://localhost:${NEXROLL_PORT:-9393}/health || exit 1

# Start Uvicorn
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${NEXROLL_PORT:-9393}"]
