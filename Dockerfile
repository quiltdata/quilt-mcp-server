# Use the official AWS Lambda Python base image from Amazon ECR
FROM --platform=linux/amd64 public.ecr.aws/lambda/python:3.11

# Set environment variables for Lambda
ENV PYTHONPATH="${LAMBDA_TASK_ROOT}"

# Copy requirements and install dependencies
COPY pyproject.toml uv.lock* ./

# Install uv for dependency management  
RUN pip install --no-cache-dir uv

# Install dependencies with explicit platform
RUN uv pip install --system --no-cache-dir \
    fastmcp mcp quilt3 boto3 botocore pydantic

# Copy the application code to Lambda task root
COPY src/ ${LAMBDA_TASK_ROOT}/

# Ensure the handler module is importable
RUN python -c "import quilt_mcp.server; print('Handler module imported successfully')"

# Set the CMD to the handler function
CMD ["quilt_mcp.server.handler"]