# syntax=docker/dockerfile:1
FROM --platform=linux/amd64 ghcr.io/astral-sh/uv:python3.11-bookworm

# Workdir
WORKDIR /app

# System deps (often none; add as needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates && rm -rf /var/lib/apt/lists/*

# Copy your project files
COPY pyproject.toml uv.lock* ./
COPY quilt/ ./quilt/
COPY weather/ ./weather/
COPY tests/ ./tests/
COPY *.py ./
COPY *.md ./
COPY *.json ./

# Install runtime dependencies directly to system Python (no venv)
# This ensures we use Python 3.11 throughout
RUN uv pip install --system --no-cache-dir fastmcp mcp quilt3 boto3 botocore pydantic

# Expose port if you run an HTTP/Streamable HTTP server
EXPOSE 8000

# Start your MCP server (adjust module/entrypoint)
CMD ["python", "-m", "quilt"]
