# Dockerfile - Unified single container for OpenOutreach
# This single Dockerfile builds and runs everything: frontend, backend, Django, LinkedIn automation

# ── Stage 1: Build frontend ────────────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend-build
COPY frontend/package*.json ./
RUN npm ci || npm install
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Build dependencies (Python) ────────────────────────────────────────
FROM python:3.12-slim-bookworm AS deps

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN pip install uv

COPY ./requirements /requirements
ARG BUILD_ENV=production
RUN uv pip install --system -r /requirements/${BUILD_ENV}.txt

# ── Stage 3: Runtime (combined) ─────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS runtime

# Install Node.js for running Next.js
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && rm -rf /var/lib/apt/lists/*

# Install nginx for serving frontend
RUN apt-get update && apt-get install -y --no-install-recommends nginx && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from the build stage
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Create nginx directories with proper ownership for ubuntu user
RUN mkdir -p /var/lib/nginx/body /var/lib/nginx/proxy /var/cache/nginx /run/nginx && \
    chown -R ubuntu:ubuntu /var/lib/nginx /var/cache/nginx /run/nginx && \
    chmod -R 755 /var/lib/nginx /var/cache/nginx /run/nginx

# Install Playwright Chromium
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers
ENV EDITOR=nano
RUN playwright install --with-deps chromium

# Install VNC stack
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gosu xvfb x11vnc python3-websockify curl nano \
    && curl -fsSL https://github.com/novnc/noVNC/archive/refs/tags/v1.6.0.tar.gz \
        | tar -xz -C /opt \
    && mv /opt/noVNC-1.6.0 /opt/noVNC \
    && cp /opt/noVNC/vnc.html /opt/noVNC/index.html \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 ubuntu

# Copy frontend build
COPY --from=frontend-builder /frontend-build/.next /app/frontend/.next
COPY --from=frontend-builder /frontend-build/node_modules /app/frontend/node_modules

# Copy frontend package.json for serve scripts
COPY frontend/package*.json /app/frontend/

# Copy application code
ARG APP_HOME=/app
WORKDIR ${APP_HOME}

COPY ./compose/linkedin/entrypoint /entrypoint
COPY ./compose/linkedin/start /start
COPY ./nginx.conf /etc/nginx/conf.d/default.conf

# Setup nginx to run on port 3000
RUN sed -i 's/listen 80/listen 3000/g' /etc/nginx/conf.d/default.conf && \
    sed -i 's/server_name _/server_name localhost/g' /etc/nginx/conf.d/default.conf

RUN sed -i 's/\r$//g' /entrypoint /start && chmod +x /entrypoint /start

COPY --chown=ubuntu:ubuntu . ${APP_HOME}

# Create directories and set permissions
RUN chown ubuntu:ubuntu ${APP_HOME} && \
    mkdir -p /app/data /app/openoutreach/media /app/staticfiles && \
    chmod -R 755 /app/data /app/openoutreach/media /app/staticfiles

# Expose ports for frontend (3000) and VNC (6080, 5900)
EXPOSE 3000 6080 5900

ENTRYPOINT ["/entrypoint"]
CMD ["/start"]