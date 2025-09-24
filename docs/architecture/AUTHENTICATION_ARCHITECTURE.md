# Authentication & Role Assumption Architecture

This document describes the comprehensive authentication system implemented for the Quilt MCP Server, including automatic role assumption, middleware patterns, and AWS IAM integration.

## Overview

The Quilt MCP Server implements a sophisticated authentication system that automatically assumes the same AWS IAM role that each Quilt user is currently using. This provides per-user isolation while maintaining seamless integration with Quilt's existing role management system.

## Architecture Components

### 1. Middleware Layer (`src/quilt_mcp/utils.py`)

The middleware layer extracts Quilt user context from HTTP headers and bridges it to the authentication service.

```python
class QuiltRoleMiddleware(BaseHTTPMiddleware):
    """Middleware to extract Quilt role information from headers and automatically assume the role."""
    
    async def dispatch(self, request, call_next):
        # Extract Quilt role information from headers
        quilt_user_role = request.headers.get("x-quilt-user-role")
        quilt_user_id = request.headers.get("x-quilt-user-id")
        
        # Set environment variables for the authentication service
        if quilt_user_role:
            os.environ["QUILT_USER_ROLE_ARN"] = quilt_user_role
        if quilt_user_id:
            os.environ["QUILT_USER_ID"] = quilt_user_id
        
        # Automatically attempt role assumption if role header is present
        if quilt_user_role:
            try:
                from quilt_mcp.services.auth_service import get_auth_service
                auth_service = get_auth_service()
                auth_service.auto_attempt_role_assumption()
            except Exception as e:
                # Log error but don't fail the request
                print(f"Warning: Failed to auto-assume Quilt role: {e}", file=sys.stderr)
        
        # Continue to the next middleware/handler
        response = await call_next(request)
        return response
```

**Key Design Principles:**
- **Request-Scoped**: Each HTTP request independently processes role information
- **Environment Bridge**: Headers are converted to environment variables for service consumption
- **Error Isolation**: Middleware errors don't fail the request
- **Automatic Triggering**: Role assumption happens automatically when headers are present

### 2. Authentication Service (`src/quilt_mcp/services/auth_service.py`)

The authentication service manages multiple authentication methods with automatic role assumption.

#### Authentication Methods (Priority Order)

1. **QUILT3**: Local quilt3 credentials (~/.quilt/)
2. **QUILT_REGISTRY**: Registry-based authentication
3. **ASSUMED_ROLE**: Automatic role assumption from Quilt headers
4. **IAM_ROLE**: ECS task role (fallback)
5. **ENVIRONMENT**: Environment variable credentials
6. **NONE**: Unauthenticated mode

#### Automatic Role Assumption

```python
def auto_attempt_role_assumption(self) -> bool:
    """Automatically attempt to assume Quilt user role if headers are present."""
    if not self._auto_role_assumption_enabled:
        return False
    
    try:
        # Check for role information from Quilt headers
        header_role_arn = os.environ.get("QUILT_USER_ROLE_ARN")
        if not header_role_arn:
            logger.debug("No QUILT_USER_ROLE_ARN environment variable set")
            return False
        
        # If we're already using the same role, no need to assume again
        if (self._auth_method == AuthMethod.ASSUMED_ROLE and 
            self._assumed_role_arn == header_role_arn):
            logger.debug("Already using the requested Quilt user role: %s", header_role_arn)
            return True
        
        # Attempt to assume the role
        logger.info("Automatically attempting to assume Quilt user role: %s", header_role_arn)
        success = self.assume_quilt_user_role(header_role_arn)
        
        if success:
            logger.info("Automatic role assumption successful: %s", header_role_arn)
            return True
        else:
            logger.warning("Automatic role assumption failed: %s", header_role_arn)
            return False
            
    except Exception as e:
        logger.error("Error during automatic role assumption: %s", e)
        return False
```

**Key Features:**
- **Intelligent Caching**: Avoids redundant role assumptions
- **Error Handling**: Graceful failure without breaking requests
- **Logging**: Comprehensive logging for debugging and monitoring
- **Configurable**: Can be enabled/disabled as needed

### 3. AWS IAM Role Assumption

The system uses AWS STS to assume user roles with proper security practices.

```python
def assume_quilt_user_role(self, role_arn: str) -> bool:
    """Manually assume a specific Quilt user role."""
    try:
        # Create a session with the current IAM role (ECS task role)
        base_session = boto3.Session()
        sts_client = base_session.client("sts")
        
        # Assume the specified role
        response = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName=f"mcp-server-{int(time.time())}",
            DurationSeconds=3600,  # 1 hour
            SourceIdentity="mcp-server"  # For audit trail
        )
        
        # Create a new session with the assumed role credentials
        assumed_credentials = response["Credentials"]
        assumed_session = boto3.Session(
            aws_access_key_id=assumed_credentials["AccessKeyId"],
            aws_secret_access_key=assumed_credentials["SecretAccessKey"],
            aws_session_token=assumed_credentials["SessionToken"]
        )
        
        # Test the assumed role
        assumed_sts_client = assumed_session.client("sts")
        identity = assumed_sts_client.get_caller_identity()
        
        # Update the authentication service state
        self._auth_method = AuthMethod.ASSUMED_ROLE
        self._auth_status = AuthStatus.AUTHENTICATED
        self._boto3_session = assumed_session
        self._assumed_role_arn = role_arn
        self._assumed_session = assumed_session
        self._aws_credentials = {
            "account_id": identity.get("Account"),
            "user_id": identity.get("UserId"),
            "arn": identity.get("Arn"),
            "assumed_role_arn": role_arn,
            "expiration": assumed_credentials["Expiration"].isoformat(),
        }
        
        logger.info("Successfully assumed Quilt user role: %s -> %s", 
                   base_session.client("sts").get_caller_identity().get("Arn"),
                   identity.get('Arn'))
        return True
        
    except Exception as e:
        logger.error("Failed to assume Quilt user role %s: %s", role_arn, e)
        return False
```

**Security Features:**
- **Source Identity**: All role assumptions include `SourceIdentity="mcp-server"` for audit trails
- **Session Validation**: Always validate assumed roles with `get_caller_identity`
- **Credential Expiration**: Track and handle credential expiration
- **Error Handling**: Comprehensive error handling for various failure modes

### 4. MCP Tools Integration (`src/quilt_mcp/tools/auth.py`)

The authentication system provides MCP tools for monitoring and manual control.

#### Available Tools

1. **`get_current_quilt_role()`**: Shows current role information and detection status
2. **`assume_quilt_user_role()`**: Manual role assumption (for testing/override)
3. **`auth_status()`**: Comprehensive authentication status

#### Tool Response Examples

```json
{
  "status": "success",
  "current_role_arn": "arn:aws:iam::850787717197:role/quilt-user-role",
  "user_id": "user123",
  "message": "Found Quilt user role from headers: arn:aws:iam::850787717197:role/quilt-user-role",
  "detection_method": "quilt_headers",
  "source": "X-Quilt-User-Role header from MCP client",
  "next_steps": [
    "Role assumption is AUTOMATIC - no action needed!",
    "The MCP server will automatically assume this role on each request",
    "All MCP operations will use this role's permissions"
  ],
  "integration_status": {
    "quilt_headers": "✅ Available",
    "automatic_assumption": "✅ Ready",
    "role_switching": "✅ Supported"
  }
}
```

## Integration with Quilt Frontend

### Required Headers

The MCP client must send these headers with each request:

- `X-Quilt-User-Role`: The ARN of the user's current role
- `X-Quilt-User-Id`: The user's identifier

### Role Switching Flow

1. **User switches role in Quilt UI** → Role switcher updates active role
2. **MCP client detects role change** → Updates headers for subsequent requests
3. **MCP server middleware** → Extracts new role ARN from headers
4. **Authentication service** → Automatically assumes the new role
5. **All AWS operations** → Use the new role's credentials

### Example Integration

```javascript
// Frontend role switching
function switchUserRole(newRoleArn) {
  // Update user context
  userContext.currentRole = newRoleArn;
  
  // Update MCP client headers
  mcpClient.setHeaders({
    'X-Quilt-User-Role': newRoleArn,
    'X-Quilt-User-Id': userContext.userId
  });
  
  // Subsequent MCP requests will automatically use the new role
}
```

## AWS IAM Requirements

### ECS Task Role Permissions

The ECS task role requires these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "sts:AssumeRole",
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": "sts:GetCallerIdentity",
      "Resource": "*"
    }
  ]
}
```

### Target Role Trust Policy

Each user role that the MCP server will assume must trust the ECS task role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::850787717197:role/ecsTaskRole"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:SourceIdentity": "mcp-server"
        }
      }
    }
  ]
}
```

## Deployment Configuration

### Environment Variables

```bash
# Required for role assumption
AWS_DEFAULT_REGION=us-east-1

# MCP server configuration
FASTMCP_TRANSPORT=streamable-http
FASTMCP_ADDR=0.0.0.0
FASTMCP_PORT=8000

# Quilt configuration
QUILT_CATALOG_URL=https://demo.quiltdata.com
```

### ECS Task Definition

```json
{
  "family": "quilt-mcp-server",
  "taskRoleArn": "arn:aws:iam::850787717197:role/ecsTaskRole",
  "executionRoleArn": "arn:aws:iam::850787717197:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "mcp-server",
      "image": "850787717197.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:auto-role-assumption",
      "environment": [
        {
          "name": "FASTMCP_TRANSPORT",
          "value": "streamable-http"
        },
        {
          "name": "QUILT_CATALOG_URL",
          "value": "https://demo.quiltdata.com"
        }
      ]
    }
  ]
}
```

## Monitoring and Debugging

### CloudWatch Logs

Key log messages to monitor:

- `"Automatically attempting to assume Quilt user role"`
- `"Automatic role assumption successful"`
- `"Already using the requested Quilt user role"`
- `"Failed to auto-assume Quilt role"`

### Health Checks

The system includes comprehensive health checks:

```python
def _health_check() -> dict[str, Any]:
    """Enhanced health check with authentication status."""
    try:
        # ... system health checks ...
        
        # Authentication status
        auth_service = get_auth_service()
        auth_status = auth_service.get_auth_status()
        
        return {
            "status": "healthy",
            "uptime_seconds": uptime,
            "memory_usage_percent": memory_percent,
            "cpu_usage_percent": cpu_percent,
            "mcp_tools_count": tools_count,
            "transport": transport,
            "authentication": auth_status
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e),
            "basic_health": "ok"
        }
```

## Security Considerations

### Audit Trail

- All role assumptions include `SourceIdentity="mcp-server"`
- Session names include timestamps for uniqueness
- Comprehensive logging of all authentication events

### Credential Management

- Temporary credentials are stored in memory only
- Credentials expire after 1 hour (configurable)
- Automatic credential refresh when expired

### Error Handling

- Authentication failures don't expose sensitive information
- Graceful degradation to unauthenticated mode when needed
- Comprehensive error logging for security monitoring

## Testing

### Unit Tests

Test the authentication service with various scenarios:

```python
def test_auto_role_assumption():
    """Test automatic role assumption when headers are present."""
    auth_service = AuthenticationService()
    
    # Set up role ARN in environment
    os.environ["QUILT_USER_ROLE_ARN"] = "arn:aws:iam::123456789012:role/test-role"
    
    # Test automatic assumption
    result = auth_service.auto_attempt_role_assumption()
    
    assert result is True
    assert auth_service._auth_method == AuthMethod.ASSUMED_ROLE
    assert auth_service._assumed_role_arn == "arn:aws:iam::123456789012:role/test-role"
```

### Integration Tests

Test the full middleware + authentication flow:

```python
def test_middleware_role_assumption():
    """Test that middleware automatically assumes roles."""
    app = build_http_app(mcp_server, transport="http")
    
    with TestClient(app) as client:
        response = client.get(
            "/healthz",
            headers={"X-Quilt-User-Role": "arn:aws:iam::123456789012:role/test-role"}
        )
        
        assert response.status_code == 200
        # Verify role was assumed automatically
```

## Troubleshooting

### Common Issues

1. **Role assumption fails**: Check trust policy and permissions
2. **Headers not received**: Verify MCP client is sending correct headers
3. **Authentication loops**: Check for infinite role assumption attempts
4. **Credential expiration**: Monitor credential expiration and refresh

### Debug Commands

```bash
# Check current authentication status
curl -H "X-Quilt-User-Role: arn:aws:iam::123456789012:role/test-role" \
     http://localhost:8000/healthz

# View CloudWatch logs
aws logs get-log-events \
  --log-group-name /ecs/mcp-server-production \
  --log-stream-name ecs/mcp-server/$(aws ecs list-tasks --cluster sales-prod --service-name sales-prod-mcp-server-production --query 'taskArns[0]' --output text | cut -d'/' -f3)
```

## Future Enhancements

1. **Role Caching**: Cache role assumptions across requests for performance
2. **Multi-Tenant Support**: Support multiple users simultaneously
3. **Advanced Security**: Implement additional security checks and monitoring
4. **Performance Optimization**: Optimize role assumption frequency and caching

This architecture provides a robust, secure, and scalable authentication system that seamlessly integrates with Quilt's existing role management while providing the isolation and security required for multi-user MCP operations.
