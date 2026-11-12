# ============================================================
# استشراف المستقبل (Istishraf) - Production Cloud Dockerfile
# Compatible with Hugging Face Spaces (Free 16GB RAM), Render,
# Railway, Koyeb, and Self-Hosted Docker
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
    PORT=7860 \
    HOME=/home/user

# libgomp1 is required by PyTorch CPU runtime on Debian slim
RUN apt-get update && \
    apt-get install -y --no-install-recommends libgomp1 && \
    rm -rf /var/lib/apt/lists/* && \
    useradd -m -u 1000 user

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

# Ensure writable directories for non-root containers (e.g. Hugging Face Spaces uid=1000)
RUN mkdir -p /app/backend/uploads /app/backend/logs /home/user/.cache && \
    touch /app/.env && \
    chown -R 1000:1000 /app /home/user && \
    chmod -R 775 /app /home/user

USER user
EXPOSE 7860

# Single gthread process (-w 1 --threads 16) preserves in-memory TaskManager,
# SimulationRunner, and live Config state across concurrent user requests.
CMD ["sh", "-c", "gunicorn --chdir /app/backend -w 1 --threads 16 --timeout 300 -b 0.0.0.0:${PORT:-7860} 'app:create_app()'"]
