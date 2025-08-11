# syntax=docker/dockerfile:1
# Lambda-compatible build (x86_64 Linux)
ARG TARGETPLATFORM=linux/amd64
FROM --platform=$TARGETPLATFORM ghcr.io/astral-sh/uv:python3.11-bookworm

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml uv.lock* ./
COPY quilt/ ./quilt/
COPY *.py ./

# Install dependencies to system Python (no venv for Lambda compatibility)
RUN uv pip install --system --no-cache-dir \
    fastmcp mcp quilt3 boto3 botocore pydantic

EXPOSE 8000
CMD ["python", "-m", "quilt"]
