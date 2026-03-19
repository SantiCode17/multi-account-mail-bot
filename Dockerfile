# ── Stage 1: Install dependencies ───────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Production image ──────────────────────────────────
FROM python:3.11-slim

LABEL maintainer="SantiCode17"
LABEL description="Inbox Bridge — Multi-Account Email Monitor Bot"

# Install curl for healthcheck probe (lightweight)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user matching typical host UID (1000) for volume permissions
ARG UID=1000
ARG GID=1000
RUN groupadd -g ${GID} inboxbridge && useradd -u ${UID} -g inboxbridge -d /app -s /sbin/nologin inboxbridge

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# Create runtime directories and set ownership
RUN mkdir -p data logs config/credentials \
    && chown -R inboxbridge:inboxbridge /app

# Switch to non-root user
USER inboxbridge

# Expose health-check port
EXPOSE 8080

# Health check — Docker restarts the container if this fails
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://127.0.0.1:8080/health || exit 1

# Ensure Python output is sent straight to the container logs
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Graceful shutdown: Python receives SIGTERM from Docker
STOPSIGNAL SIGTERM

CMD ["python", "run.py"]
