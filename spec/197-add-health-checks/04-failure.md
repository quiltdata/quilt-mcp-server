<!-- markdownlint-disable MD013 -->
# MCP Server ECS Deployment Analysis

## Current Situation

The CloudFormation stack `tf-dev-mcp-server` is hanging during deployment. The stack is stuck and not completing the deployment process.

## Stack Information

- **Stack Name**: `tf-dev-mcp-server`
- **Region**: `us-east-2`
- **CloudFormation Stack**: [Stack](https://us-east-2.console.aws.amazon.com/cloudformation/home?region=us-east-2#/stacks/resources?eventsView=graph&filteringStatus=active&filteringText=&stackId=arn%3Aaws%3Acloudformation%3Aus-east-2%3A712023778557%3Astack%2Ftf-dev-mcp-server%2Fc2e45ad0-98c5-11f0-9e38-025c47bc4a51&viewNested=true)
- **ECS Logs**: [Logs](https://us-east-2.console.aws.amazon.com/ecs/v2/clusters/tf-dev-mcp-server/services/tf-dev-mcp-server-mcp-server/logs?region=us-east-2)

## Container Configuration Analysis

### Location

- **Configuration File**: `/Users/ernest/GitHub/deployment/t4/template/containers.py`
- **Function**: `make_mcp_server_container()` (lines 480-571)
- **Docker Image**: `712023778557.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:latest`

### Key Configuration Elements

#### 1. Environment Variables

- Standard T4 integration variables (AWS region, stack ID, etc.)
- Service discovery URLs for registry and S3 proxy
- Database connection (`SQLALCHEMY_DATABASE_URI`)
- Search service integration (`ES_ENDPOINT`)
- MCP-specific configuration:
  - `MCP_PORT`: "8080"
  - `FASTMCP_TRANSPORT`: "http"
  - `FASTMCP_HOST`: "0.0.0.0"
  - `FASTMCP_PORT`: "8080"
  - Debug flags enabled (`DEBUG=1`, `MCP_LOG_LEVEL=DEBUG`)

#### 2. Health Check Configuration

```python
"HealthCheck": ecs.HealthCheck(
    Command=[
        "CMD-SHELL",
        "curl -f --max-time 5 http://localhost:8080/health || exit 1",
    ],
    Interval=30,  # Check every 30 seconds
    Timeout=10,  # 10 second timeout
    Retries=5,  # More retries for stability
    StartPeriod=120,  # 2 minutes for initial startup
),
```

#### 3. Resource Allocation

```python
"Memory": 1024,  # 1GB memory reservation
"MemoryReservation": 512,  # 512MB soft limit
"Cpu": 256,  # 0.25 vCPU
```

#### 4. Volume Mounts

- `/tmp/` - mcp-tmp volume
- `/var/log/` - mcp-logs volume for debugging
- ECS exec volumes if enabled

#### 5. Container Settings

- `ReadonlyRootFilesystem`: False (for debugging)
- `InitProcessEnabled`: True (for better signal handling)
- `StopTimeout`: 30 seconds

## Identified Issues

### Issue 1: Health Check Configuration

**Previous Configuration** (lines 530-540):

- Used verbose curl output (`-v`) with complex piping
- Command: `curl -v -f --max-time 4 http://localhost:8080/health 2>&1 | tee /tmp/health.log || (cat /tmp/health.log >&2 && exit 1)`
- This could cause the health check to fail or behave unpredictably

**Current Configuration** (after fix):

- Simplified to: `curl -f --max-time 5 http://localhost:8080/health || exit 1`
- Increased intervals and start period for stability

### Issue 2: Port Configuration

- Both `MCP_PORT` and `FASTMCP_PORT` set to "8080"
- Override attempt from default FastMCP port 8000 to 8080
- Potential binding conflicts if application expects different ports

### Issue 3: Debug Mode Complexity

When debug is enabled (lines 554-568):

- Executes complex bash command with multiple echo statements
- Could fail silently if any part of the command fails
- Makes troubleshooting harder

### Issue 4: Resource Constraints

**Previous**: No explicit resource allocation
**Current**: Added memory and CPU reservations to ensure adequate resources

## Potential Root Causes for Hanging

1. **Health Check Failures**: Container might be starting but failing health checks, causing ECS to repeatedly restart it
2. **Port Binding Issues**: Application might not be binding to the expected port (8080)
3. **Startup Time**: Container might need more time than the 120-second start period
4. **Resource Starvation**: Without explicit resource allocation, container might not have enough memory/CPU
5. **Application Crash Loop**: The MCP server application itself might be crashing on startup

## Next Steps for Debugging

1. **Check ECS Task Logs**:
   - Review the actual container logs in CloudWatch
   - Look for startup errors or crash messages
   - Check if the health endpoint is responding

2. **Verify Docker Image**:
   - Ensure `quilt-mcp-server:latest` image exists in ECR
   - Verify the image can run locally with the same environment variables

3. **ECS Service Events**:
   - Check ECS service events for task placement failures
   - Look for resource allocation issues
   - Review task stop reasons

4. **Network Configuration**:
   - Verify security groups allow health check traffic
   - Check if the service can reach required dependencies (database, S3, etc.)

5. **Simplify Configuration**:
   - Remove debug mode complexity
   - Start with minimal configuration and add features incrementally
   - Consider increasing health check grace period further

## Applied Fixes

1. ✅ Simplified health check command
2. ✅ Added resource reservations (Memory: 1GB, CPU: 0.25 vCPU)
3. ✅ Increased health check intervals and start period
4. ⏳ Debug command simplification (pending)

## Recommendations

1. **Immediate Actions**:
   - Deploy with simplified health check
   - Monitor CloudWatch logs during deployment
   - Check ECS task stop reasons

2. **Follow-up Actions**:
   - Test the Docker image locally with production-like environment
   - Consider implementing a simpler health endpoint that doesn't depend on all services
   - Add more detailed logging during startup
   - Consider using ECS Exec to debug running containers

3. **Long-term Improvements**:
   - Implement proper health check that validates actual service functionality
   - Add metrics and monitoring for container startup time
   - Document required environment variables and dependencies
   - Create a staging environment for testing deployments
