# Use official Python slim image for lightweight web server
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY pyproject.toml uv.lock* ./

# Install uv for dependency management  
RUN pip install --no-cache-dir uv

# Install dependencies
RUN uv pip install --system --no-cache-dir \
    fastmcp mcp quilt3 boto3 botocore pydantic

# Copy the application code
COPY app/quilt_mcp ./quilt_mcp/
COPY app/main.py ./

# Ensure the server module is importable
RUN python -c "import quilt_mcp.server; print('Server module imported successfully')"

# Expose the default port
EXPOSE 8000

# Health check - test if MCP server process is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f "python.*main.py" || exit 1

# Run the FastMCP server
CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8000"]