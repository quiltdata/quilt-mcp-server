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
COPY --from=builder /app/scripts /app/scripts

# Make scripts executable
RUN chmod +x /app/scripts/healthcheck.py /app/scripts/start.sh

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Docker health check using Python script
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python /app/scripts/healthcheck.py --timeout 4

CMD ["/app/scripts/start.sh"]
