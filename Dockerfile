# syntax=docker/dockerfile:1.6

FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder
WORKDIR /app

# Copy project metadata and lockfile first for better caching
COPY pyproject.toml uv.lock ./
COPY Makefile make.dev make.deploy ./
# Copy metadata files required by setuptools (referenced in pyproject.toml)
COPY README.md LICENSE.txt ./

# Install build dependencies required for native extensions (e.g., pybigwig)
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        libcurl4-openssl-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies without the project itself for better layer caching
# This layer only rebuilds if pyproject.toml, uv.lock, or metadata files change
RUN uv sync --frozen --no-dev --no-install-project

# Copy source and supporting files after dependencies are installed
# Changes to application code won't invalidate the dependency layer
COPY src ./src
COPY scripts ./scripts
COPY docs ./docs
COPY spec ./spec

# Install the project itself (fast since dependencies are already installed)
RUN uv sync --frozen --no-dev

FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    FASTMCP_TRANSPORT=http \
    FASTMCP_HOST=0.0.0.0 \
    FASTMCP_PORT=8000

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        curl \
        libcurl4 \
        zlib1g \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment and application code
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/pyproject.toml /app/pyproject.toml

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["quilt-mcp"]
