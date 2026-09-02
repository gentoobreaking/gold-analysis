# ─────────────────────────────────────────────────────────────────────────────
# Backend Dockerfile — FastAPI / uvicorn
# Multi-stage build: deps → runtime
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Dependencies ────────────────────────────────────────────────────
FROM python:3.12-alpine AS deps

# Install build tools required for compiling Python packages
RUN apk add --no-cache \
    build-base \
    gcc \
    musl-dev \
    libffi-dev \
    postgresql-dev \
    curl

WORKDIR /app

# Copy only lock file + pyproject for layer caching
COPY pyproject.toml uv.lock* ./

# Install uv (binary download, no shell hooks needed)
# Then sync locked dependencies into /app/.venv
# Install uv via official installer script
RUN UV_VERSION=0.4.0 \
    && curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" -o /tmp/uv-install.sh \
    && sh /tmp/uv-install.sh \
    && rm /tmp/uv-install.sh \
    && /root/.cargo/bin/uv venv /app/.venv --python 3.12 \
    && /root/.cargo/bin/uv sync --frozen --no-dev

# ── Stage 2: Runtime image ───────────────────────────────────────────────────
FROM python:3.12-alpine AS runtime

# Create non-root user for security
RUN addgroup -S -g 1000 appgroup && \
    adduser -D -S -u 1000 -G appgroup appuser && \
    apk add --no-cache \
        libpq \
        libgomp \
        libstdc++ \
        curl

# Copy virtualenv from deps stage
COPY --from=deps /app/.venv /app/.venv

# Copy application source
COPY . .

# Ensure the venv is used
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

# Run as non-root
USER appuser

EXPOSE 8000

# Health check: hit the /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["curl", "-f", "http://localhost:8000/health"]

# Launch uvicorn (no reload — use --host 0.0.0.0 for container)
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
