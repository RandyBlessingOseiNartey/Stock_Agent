# StockAgent — one container serving the API and the built UI on one port.
# Works unchanged on Render, Google Cloud Run, Fly.io, Koyeb, or plain Docker.
#
#   docker build -t stockagent .
#   docker run --rm -p 8000:8000 --env-file .env stockagent

# ── Stage 1: build the frontend ─────────────────────────────────────
FROM node:22-slim AS frontend

WORKDIR /ui
# Copy manifests first so `npm ci` is cached until dependencies actually change.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build          # tsc -b && vite build → /ui/dist

# ── Stage 2: runtime ────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

# PYTHONUNBUFFERED keeps logs streaming to the platform's log viewer.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/app

WORKDIR /app

# requirements-deploy.txt is the slim runtime set: OpenBB core rather than
# openbb[all], and no streamlit/plotly/scipy/sklearn/statsmodels, none of which
# the server imports. ~290MB installed instead of ~795MB.
COPY requirements-deploy.txt ./
RUN pip install --no-cache-dir -r requirements-deploy.txt

# OpenBB assembles its static Python interface the first time it is imported.
# Doing it here bakes the result into the image, so container startup doesn't
# pay for it (~20s) on every cold start.
RUN python -c "import openbb" && python -c "from openbb import obb; print('openbb prebuilt:', bool(obb.equity))"

# Application code — the three feature packages plus the API layer.
COPY backend/ ./backend/
COPY deep_research/ ./deep_research/
COPY terminal/ ./terminal/
COPY chat/ ./chat/

# The built UI, served by FastAPI from this same app (see backend/main.py).
COPY --from=frontend /ui/dist ./backend/static

# Platforms inject $PORT (Cloud Run uses 8080, Render 10000); default for local.
ENV PORT=8000
EXPOSE 8000

# Single worker on purpose: each worker loads its own ~400MB of OpenBB and
# LangChain. Concurrency here is async, not process-based.
CMD ["sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
