# ============================================================
# استشراف المستقبل (Istishraf) - Production Cloud Dockerfile
# Builds unified Arabic Vue 3 PWA + Python Gunicorn API Server
# ============================================================

# 1) Build Frontend SPA & PWA
FROM node:20-slim AS frontend-builder
WORKDIR /build/frontend
COPY locales /build/locales
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

# 2) Production Python 3.12 Runtime (CPU-optimized, lightweight)
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5001

# libgomp1 is required by PyTorch CPU runtime on Debian slim
RUN apt-get update && \
    apt-get install -y --no-install-recommends libgomp1 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy locales & backend dependencies
COPY locales ./locales
COPY backend/requirements.txt ./backend/requirements.txt

# Install CPU-optimized packages + Gunicorn into system Python
RUN uv pip install --system --no-cache \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    --index-strategy unsafe-best-match \
    -r backend/requirements.txt

# Copy backend source and compiled frontend webroot
COPY backend ./backend
COPY --from=frontend-builder /build/frontend/webroot ./frontend/webroot

# Ensure persistent uploads directory exists
RUN mkdir -p /app/backend/uploads

EXPOSE 5001

# Single gthread process (-w 1 --threads 16) preserves in-memory TaskManager,
# SimulationRunner, and live Config state across concurrent user requests.
CMD ["sh", "-c", "gunicorn --chdir /app/backend -w 1 --threads 16 --timeout 300 -b 0.0.0.0:${PORT:-5001} 'app:create_app()'"]
