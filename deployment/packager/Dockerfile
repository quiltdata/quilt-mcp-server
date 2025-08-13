# syntax=docker/dockerfile:1
# Unified Docker image for both local development and Lambda deployment
ARG BASE_IMAGE=ghcr.io/astral-sh/uv:python3.11-bookworm
ARG LAMBDA_MODE=false

# Use Lambda base image when LAMBDA_MODE=true
FROM public.ecr.aws/lambda/python:3.11 as lambda-base
FROM ghcr.io/astral-sh/uv:python3.11-bookworm as dev-base

# Select the appropriate base
FROM ${BASE_IMAGE} as base

# Common setup for both modes
WORKDIR ${LAMBDA_MODE:+/var/task}${LAMBDA_MODE:-/app}

# Install system dependencies (conditional for different bases)
RUN if [ "$LAMBDA_MODE" = "false" ]; then \
        apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates && rm -rf /var/lib/apt/lists/*; \
    fi

# Copy project files
COPY pyproject.toml uv.lock* ./
COPY src/ ./src/

# Install uv if not available (Lambda base doesn't have it)
RUN if ! command -v uv >/dev/null 2>&1; then pip install uv; fi

# Install dependencies to system Python (no venv for Lambda compatibility)
RUN uv pip install --system --no-cache-dir \
    fastmcp mcp quilt3 boto3 botocore pydantic

# Copy source code to the correct location for Lambda imports
RUN cp -r src/* ./

# Default commands for different modes
EXPOSE 8000
CMD if [ "$LAMBDA_MODE" = "true" ]; then \
        exec "$_HANDLER"; \
    else \
        exec python -m quilt_mcp.server; \
    fi
