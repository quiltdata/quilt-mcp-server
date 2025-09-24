# syntax=docker/dockerfile:1.6

FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder
WORKDIR /app

# Copy project metadata and lockfile first for better caching
COPY pyproject.toml uv.lock ./
COPY Makefile make.dev make.deploy ./

# Install build dependencies required for native extensions (e.g., pybigwig)
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        libcurl4-openssl-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy source and supporting files
COPY src ./src
COPY scripts ./scripts
COPY docs ./docs
COPY spec ./spec

# Install project dependencies into a virtual environment
RUN uv sync --frozen --no-dev

FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    FASTMCP_TRANSPORT=http \
    FASTMCP_HOST=0.0.0.0 \
    FASTMCP_PORT=8000 \
    PYTHONPATH=/app/src:$PYTHONPATH

# Install runtime dependencies including curl for health checks
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        libcurl4 \
        zlib1g \
        curl \
        procps \
        net-tools \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment and application code
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/pyproject.toml /app/pyproject.toml
COPY --from=builder /app/spec/feature-docker-container /app/spec/feature-docker-container

# Add health check script
COPY <<'EOF' /app/healthcheck.sh
#!/bin/bash
set -e

# Log health check attempt
echo "[HEALTHCHECK] $(date -Iseconds) - Checking health on port ${FASTMCP_PORT:-8000}..." >&2

# Get the actual listening port
PORT=${FASTMCP_PORT:-8000}

# Check if process is running (look for python or main.py)
if ! pgrep -f "python.*main.py" > /dev/null && ! pgrep -f "quilt-mcp" > /dev/null; then
    echo "[HEALTHCHECK] $(date -Iseconds) - ERROR: MCP server process not running" >&2
    ps aux | grep python | head -5 >&2
    exit 1
fi

# Check if port is listening
if ! netstat -tln | grep -q ":${PORT}"; then
    echo "[HEALTHCHECK] $(date -Iseconds) - ERROR: Port ${PORT} not listening" >&2
    netstat -tln >&2
    exit 1
fi

# Perform actual health check with verbose curl
RESPONSE=$(curl -v -f -s -o /dev/null -w "%{http_code}" http://localhost:${PORT}/health 2>&1) || {
    EXIT_CODE=$?
    echo "[HEALTHCHECK] $(date -Iseconds) - ERROR: curl failed with exit code ${EXIT_CODE}" >&2
    echo "[HEALTHCHECK] Full curl output:" >&2
    curl -v http://localhost:${PORT}/health 2>&1 | sed 's/^/[HEALTHCHECK] /' >&2
    exit 1
}

echo "[HEALTHCHECK] $(date -Iseconds) - SUCCESS: Health check passed (HTTP ${RESPONSE})" >&2
exit 0
EOF

RUN chmod +x /app/healthcheck.sh

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Add startup wrapper script
COPY <<'EOF' /app/start.sh
#!/bin/bash
set -e

echo "[STARTUP] $(date -Iseconds) - Starting MCP server..." >&2
echo "[STARTUP] Environment variables:" >&2
env | grep -E "(FASTMCP|MCP|PORT|HOST)" | sort | sed 's/^/[STARTUP] /' >&2

echo "[STARTUP] Python path: $PYTHONPATH" >&2
echo "[STARTUP] Working directory: $(pwd)" >&2
echo "[STARTUP] Python version: $(python --version)" >&2

# Start the server with verbose output
echo "[STARTUP] Executing: python -u /app/src/main.py" >&2
exec python -u /app/src/main.py
EOF

RUN chmod +x /app/start.sh

# Docker health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD /app/healthcheck.sh

CMD ["/app/start.sh"]
