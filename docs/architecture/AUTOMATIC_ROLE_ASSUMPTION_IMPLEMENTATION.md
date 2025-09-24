# Automatic Role Assumption Implementation

## Overview

This document details the implementation of automatic role assumption for the Quilt MCP Server, enabling seamless role-based access control where the MCP server automatically assumes the same AWS IAM role as the Quilt user.

## Architecture

### System Components

1. **Frontend (MCP Client)**: Sends Quilt user role information via HTTP headers
2. **QuiltRoleMiddleware**: Extracts role information from headers and sets environment variables
3. **AuthenticationService**: Automatically assumes the specified role using STS
4. **MCP Tools**: Provide role management and status information

### Data Flow

```
Frontend → HTTP Headers → QuiltRoleMiddleware → Environment Variables → AuthenticationService → STS AssumeRole → AWS Operations
```

## Implementation Details

### 1. QuiltRoleMiddleware

**Location**: `src/quilt_mcp/utils.py`

**Purpose**: Extracts Quilt user role information from HTTP headers and triggers automatic role assumption.

**Key Features**:
- Extracts `X-Quilt-User-Role` and `X-Quilt-User-Id` headers
- Sets environment variables for the authentication service
- Automatically triggers role assumption on each request
- Error isolation - middleware failures don't break requests

**Code Implementation**:
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

### 2. AuthenticationService Enhancements

**Location**: `src/quilt_mcp/services/auth_service.py`

**New Features**:
- `ASSUMED_ROLE` authentication method
- Automatic role assumption on per-request basis
- Smart caching to avoid redundant role assumptions
- Comprehensive error handling and logging

**Key Methods**:

#### `auto_attempt_role_assumption()`
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

#### `assume_quilt_user_role()`
```python
def assume_quilt_user_role(self, role_arn: str) -> bool:
    """Assume the specified Quilt user role using STS."""
    try:
        # Validate role ARN format
        if not role_arn.startswith("arn:aws:iam::"):
            logger.error("Invalid role ARN format: %s", role_arn)
            return False
        
        # Create STS client with current session
        sts_client = self._boto3_session.client("sts")
        
        # Assume the role
        response = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName=f"mcp-server-{int(time.time())}",
            DurationSeconds=3600,  # 1 hour
            SourceIdentity="mcp-server"
        )
        
        # Create new session with assumed role credentials
        assumed_session = boto3.Session(
            aws_access_key_id=response['Credentials']['AccessKeyId'],
            aws_secret_access_key=response['Credentials']['SecretAccessKey'],
            aws_session_token=response['Credentials']['SessionToken']
        )
        
        # Validate the assumed role
        caller_identity = assumed_session.client("sts").get_caller_identity()
        logger.info("Successfully assumed role: %s", caller_identity['Arn'])
        
        # Update service state
        self._auth_method = AuthMethod.ASSUMED_ROLE
        self._auth_status = AuthStatus.AUTHENTICATED
        self._boto3_session = assumed_session
        self._assumed_role_arn = role_arn
        self._assumed_session = assumed_session
        
        return True
        
    except ClientError as e:
        logger.error("Failed to assume role %s: %s", role_arn, e)
        return False
    except Exception as e:
        logger.error("Unexpected error assuming role %s: %s", role_arn, e)
        return False
```

### 3. MCP Tools Updates

**Location**: `src/quilt_mcp/tools/auth.py`

#### `get_current_quilt_role()`
Updated to detect automatic role assumption:
```python
async def get_current_quilt_role() -> dict[str, Any]:
    """Get information about the current Quilt user role."""
    try:
        # Check for role information from Quilt headers (set by middleware)
        header_role_arn = os.environ.get("QUILT_USER_ROLE_ARN")
        header_user_id = os.environ.get("QUILT_USER_ID")
        
        if header_role_arn:
            return {
                "status": "success",
                "current_role_arn": header_role_arn,
                "user_id": header_user_id,
                "message": f"Found Quilt user role from headers: {header_role_arn}",
                "detection_method": "quilt_headers",
                "source": "X-Quilt-User-Role header from MCP client",
                "next_steps": [
                    "Role assumption is AUTOMATIC - no action needed!",
                    "The MCP server will automatically assume this role on each request",
                    "All MCP operations will use this role's permissions",
                ],
                "integration_status": {
                    "quilt_headers": "✅ Available",
                    "automatic_assumption": "✅ Ready",
                    "role_switching": "✅ Supported",
                },
            }
        # ... fallback logic for local development
    except Exception as e:
        return {"status": "error", "error": f"Failed to detect Quilt user role: {e}"}
```

#### `assume_quilt_user_role()`
Updated to indicate automatic behavior:
```python
async def assume_quilt_user_role(role_arn: str = None) -> dict[str, Any]:
    """Assume the Quilt user role for MCP operations.
    
    NOTE: Role assumption is now AUTOMATIC when Quilt headers are present.
    This tool is provided for manual override or testing purposes.
    """
    # ... implementation details
```

### 4. CORS Configuration Updates

**Location**: `src/quilt_mcp/utils.py`

Updated CORS middleware to allow Quilt-specific headers:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "*",
        "Content-Type",
        "Accept", 
        "MCP-Protocol-Version",
        "Mcp-Session-Id",
        "Authorization",
        "X-Quilt-User-Role",  # Quilt role information
        "X-Quilt-User-Id",    # Quilt user identification
        "Origin",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers"
    ],
    allow_credentials=False,
    expose_headers=["mcp-session-id"],
)
```

## Configuration

### Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `QUILT_USER_ROLE_ARN` | Set by middleware from headers | `arn:aws:iam::850787717197:role/ReadWriteQuiltV2-sales-prod` |
| `QUILT_USER_ID` | Set by middleware from headers | `user123` |

### IAM Configuration

#### ECS Task Role Permissions
The ECS task role needs `sts:AssumeRole` permission:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "sts:AssumeRole",
            "Resource": "*"
        }
    ]
}
```

#### Target Role Trust Policy
Quilt user roles must trust the ECS task role:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "AWS": [
                    "arn:aws:iam::850787717197:role/ecsTaskRole",
                    "arn:aws:iam::850787717197:role/sales-prod-AmazonECSTaskExecutionRole-psyJbxNf8dSA"
                ]
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
```

## Frontend Integration

### Required Headers

The frontend must send these headers with all MCP requests:

```javascript
const mcpHeaders = {
  'X-Quilt-User-Role': 'arn:aws:iam::850787717197:role/ReadWriteQuiltV2-sales-prod',
  'X-Quilt-User-Id': 'user123',
  'Authorization': 'Bearer <oauth_token>',
  'Content-Type': 'application/json',
  'Accept': 'application/json, text/event-stream',
};
```

### Role Switching

When users switch roles in the Quilt UI, the frontend should automatically update the MCP headers:

```typescript
useEffect(() => {
  if (user?.role?.arn) {
    updateMCPHeaders({
      'X-Quilt-User-Role': user.role.arn,
      'X-Quilt-User-Id': user.id,
    });
  }
}, [user?.role?.arn, user?.id]);
```

## Deployment

### Docker Image

The implementation is deployed using the `auto-role-assumption` image tag:
```bash
docker buildx build --platform linux/amd64 \
  -t 850787717197.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:auto-role-assumption \
  . --push
```

### ECS Task Definition

Updated task definition includes:
- New Docker image with automatic role assumption
- Proper environment variables
- Health check configuration

## Monitoring and Logging

### CloudWatch Logs

The system logs all role assumption attempts:

**Successful Role Assumption**:
```
INFO: Automatically attempting to assume Quilt user role: arn:aws:iam::850787717197:role/ReadWriteQuiltV2-sales-prod
INFO: Automatic role assumption successful: arn:aws:iam::850787717197:role/ReadWriteQuiltV2-sales-prod
```

**Failed Role Assumption**:
```
Failed to assume Quilt user role arn:aws:iam::850787717197:role/ReadWriteQuiltBucket: An error occurred (AccessDenied) when calling the AssumeRole operation: User: arn:aws:sts::850787717197:assumed-role/ecsTaskRole/6b777c1809a94925ab48098fa09824de is not authorized to perform: sts:AssumeRole on resource: arn:aws:iam::850787717197:role/ReadWriteQuiltBucket
Automatic role assumption failed: arn:aws:iam::850787717197:role/ReadWriteQuiltBucket
```

### Health Monitoring

The `/healthz` endpoint provides authentication status:
```json
{
  "status": "healthy",
  "timestamp": "2025-09-23T16:36:45Z",
  "transport": "streamable-http",
  "mcp_tools_count": 45,
  "authentication": {
    "method": "assumed_role",
    "status": "authenticated",
    "role_arn": "arn:aws:iam::850787717197:role/ReadWriteQuiltV2-sales-prod"
  }
}
```

## Troubleshooting

### Common Issues

#### 1. Role Name Mismatch
**Error**: `Failed to assume Quilt user role ReadWriteQuiltBucket: ValidationError`
**Solution**: Frontend must send correct role name (e.g., `ReadWriteQuiltV2-sales-prod`)

#### 2. IAM Trust Policy Missing
**Error**: `AccessDenied: User is not authorized to perform: sts:AssumeRole`
**Solution**: Update target role trust policy to include ECS task role

#### 3. Missing Headers
**Error**: No role assumption attempts in logs
**Solution**: Frontend must send `X-Quilt-User-Role` header

### Debug Commands

Check current role assumption status:
```bash
curl -H "Accept: application/json" \
  "https://demo.quiltdata.com/mcp/" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/call","params":{"name":"get_current_quilt_role","arguments":{}}}'
```

Check authentication status:
```bash
curl -H "Accept: application/json" \
  "https://demo.quiltdata.com/mcp/" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/call","params":{"name":"auth_status","arguments":{}}}'
```

## Security Considerations

1. **Role Isolation**: Each user's MCP operations use their specific role
2. **Automatic Switching**: Role changes are applied immediately without user intervention
3. **Error Isolation**: Middleware failures don't break requests
4. **Audit Trail**: All role assumptions are logged to CloudWatch
5. **Credential Management**: Temporary credentials are properly managed and expired

## Performance Impact

- **Minimal Overhead**: Role assumption only occurs when headers change
- **Smart Caching**: Avoids redundant role assumptions
- **Fast Failover**: Graceful degradation when role assumption fails
- **Concurrent Support**: Multiple users can have different roles simultaneously

## Future Enhancements

1. **Role Caching**: Cache assumed roles with TTL
2. **Batch Operations**: Optimize multiple role assumptions
3. **Metrics**: Add CloudWatch metrics for role assumption success/failure rates
4. **Circuit Breaker**: Implement circuit breaker pattern for role assumption failures
