# ============================================================
# Multi-stage Dockerfile — SuperAgente IA Pro
# Stage 1: builder (install deps + compile)
# Stage 2: runtime slim (no pip, no gcc, minimal attack surface)
# ============================================================

# ---------- Stage 1: Builder ----------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

ARG PIP_TRUSTED_HOSTS=""

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates gcc libpq-dev && \
    update-ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN set -eux; \
    trusted_args=""; \
    for host in $PIP_TRUSTED_HOSTS; do trusted_args="$trusted_args --trusted-host $host"; done; \
    pip install --no-cache-dir --prefix=/install $trusted_args -r requirements.txt

# ---------- Stage 2: Runtime ----------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates libpq5 curl && \
    update-ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# UID/GID fijos alineados con k8s/helm/superagente/values.yaml (runAsUser/fsGroup).
RUN addgroup --system --gid 10001 appgroup \
    && adduser --system --uid 10001 --ingroup appgroup appuser

COPY --from=builder /install /usr/local
COPY . .

RUN python scripts/generate_static_css.py 2>/dev/null || true && \
    mkdir -p /app/data /app/generated_images /app/logs /app/.streamlit/static && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -f http://127.0.0.1:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
