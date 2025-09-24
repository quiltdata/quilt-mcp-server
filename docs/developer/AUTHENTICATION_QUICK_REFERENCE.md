# Authentication Quick Reference

Quick reference for implementing and troubleshooting the Quilt MCP Server authentication system.

## Architecture Overview

```
Quilt Frontend → MCP Client → MCP Server
     ↓              ↓            ↓
Role Switcher → X-Quilt-User-Role Header → Automatic Role Assumption
     ↓              ↓            ↓
User Role → STS AssumeRole → AWS Operations
```

## Key Components

### 1. Middleware (`src/quilt_mcp/utils.py`)

```python
class QuiltRoleMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Extract headers
        role_arn = request.headers.get("x-quilt-user-role")
        
        # Set environment variables
        if role_arn:
            os.environ["QUILT_USER_ROLE_ARN"] = role_arn
            
        # Auto-assume role
        if role_arn:
            auth_service.auto_attempt_role_assumption()
            
        return await call_next(request)
```

### 2. Authentication Service (`src/quilt_mcp/services/auth_service.py`)

```python
def auto_attempt_role_assumption(self) -> bool:
    role_arn = os.environ.get("QUILT_USER_ROLE_ARN")
    if role_arn and self._assumed_role_arn != role_arn:
        return self.assume_quilt_user_role(role_arn)
    return True
```

### 3. Role Assumption

```python
def assume_quilt_user_role(self, role_arn: str) -> bool:
    sts_client = boto3.Session().client("sts")
    response = sts_client.assume_role(
        RoleArn=role_arn,
        RoleSessionName=f"mcp-server-{int(time.time())}",
        DurationSeconds=3600,
        SourceIdentity="mcp-server"
    )
    # Create new session with assumed credentials
    # Validate and store session
```

## Required Headers

| Header | Description | Example |
|--------|-------------|---------|
| `X-Quilt-User-Role` | User's current role ARN | `arn:aws:iam::123456789012:role/user-role` |
| `X-Quilt-User-Id` | User identifier | `user123` |

## AWS IAM Setup

### ECS Task Role Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["sts:AssumeRole", "sts:GetCallerIdentity"],
      "Resource": "*"
    }
  ]
}
```

### Target Role Trust Policy

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

## MCP Tools

### Check Current Role

```python
# Returns current role information
result = await get_current_quilt_role()
```

### Manual Role Assumption

```python
# Manual override (usually not needed)
result = await assume_quilt_user_role("arn:aws:iam::123456789012:role/user-role")
```

### Authentication Status

```python
# Get comprehensive auth status
result = await auth_status()
```

## Frontend Integration

### JavaScript Example

```javascript
// Update MCP client headers when user switches role
function switchUserRole(newRoleArn) {
  mcpClient.setHeaders({
    'X-Quilt-User-Role': newRoleArn,
    'X-Quilt-User-Id': userContext.userId
  });
  
  // Subsequent MCP requests will automatically use new role
}
```

### React Hook Example

```javascript
function useMCPRoleSwitching() {
  const { currentRole, userId } = useAuth();
  
  useEffect(() => {
    if (currentRole && userId) {
      mcpClient.setHeaders({
        'X-Quilt-User-Role': currentRole,
        'X-Quilt-User-Id': userId
      });
    }
  }, [currentRole, userId]);
}
```

## Deployment

### Environment Variables

```bash
AWS_DEFAULT_REGION=us-east-1
FASTMCP_TRANSPORT=streamable-http
QUILT_CATALOG_URL=https://demo.quiltdata.com
```

### Docker Image

```bash
# Build and push
docker buildx build --platform linux/amd64 \
  -t 850787717197.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:auto-role-assumption \
  . --push
```

### ECS Deployment

```bash
# Register task definition
aws ecs register-task-definition --cli-input-json file://deploy/ecs-task-definition.json

# Update service
aws ecs update-service \
  --cluster sales-prod \
  --service sales-prod-mcp-server-production \
  --task-definition quilt-mcp-server:23 \
  --force-new-deployment
```

## Monitoring

### CloudWatch Logs

Key log patterns to monitor:

```bash
# Successful role assumption
"Automatic role assumption successful"

# Role already in use
"Already using the requested Quilt user role"

# Role assumption failed
"Automatic role assumption failed"

# Missing headers
"No QUILT_USER_ROLE_ARN environment variable set"
```

### Health Check

```bash
# Check server health and auth status
curl -H "X-Quilt-User-Role: arn:aws:iam::123456789012:role/test-role" \
     http://localhost:8000/healthz
```

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Role assumption fails | Missing trust policy | Add ECS task role to target role trust policy |
| Headers not received | MCP client not sending headers | Verify client sends `X-Quilt-User-Role` header |
| Infinite loops | Role assumption triggers more assumptions | Check middleware order and error handling |
| Credential expiration | Role sessions expire after 1 hour | Monitor expiration and implement refresh |

### Debug Commands

```bash
# Check ECS service status
aws ecs describe-services \
  --cluster sales-prod \
  --services sales-prod-mcp-server-production

# View recent logs
aws logs get-log-events \
  --log-group-name /ecs/mcp-server-production \
  --log-stream-name ecs/mcp-server/$(aws ecs list-tasks --cluster sales-prod --query 'taskArns[0]' --output text | cut -d'/' -f3)

# Test role assumption manually
aws sts assume-role \
  --role-arn "arn:aws:iam::123456789012:role/test-role" \
  --role-session-name "test-session"
```

### Debug MCP Tools

```python
# Check what role is detected
result = await get_current_quilt_role()
print(f"Current role: {result['current_role_arn']}")
print(f"Detection method: {result['detection_method']}")

# Check authentication status
result = await auth_status()
print(f"Auth method: {result['authentication_method']}")
print(f"Status: {result['authentication_status']}")
```

## Testing

### Unit Test Example

```python
def test_auto_role_assumption():
    auth_service = AuthenticationService()
    os.environ["QUILT_USER_ROLE_ARN"] = "arn:aws:iam::123456789012:role/test-role"
    
    result = auth_service.auto_attempt_role_assumption()
    assert result is True
    assert auth_service._auth_method == AuthMethod.ASSUMED_ROLE
```

### Integration Test Example

```python
def test_middleware_integration():
    app = build_http_app(mcp_server, transport="http")
    
    with TestClient(app) as client:
        response = client.get(
            "/healthz",
            headers={"X-Quilt-User-Role": "arn:aws:iam::123456789012:role/test-role"}
        )
        assert response.status_code == 200
```

## Security Checklist

- [ ] ECS task role has `sts:AssumeRole` permission
- [ ] Target roles trust the ECS task role
- [ ] All role assumptions include `SourceIdentity="mcp-server"`
- [ ] Credential expiration is tracked and handled
- [ ] Authentication failures are logged but don't expose sensitive data
- [ ] Middleware errors don't fail requests
- [ ] Role assumption is rate-limited to prevent abuse

## Performance Considerations

- Role assumption happens on each request with new headers
- Caching prevents redundant assumptions of the same role
- Credentials expire after 1 hour (configurable)
- Session validation adds minimal overhead
- Middleware processing is lightweight

## Future Enhancements

1. **Role Caching**: Cache role assumptions across requests
2. **Batch Operations**: Support multiple users simultaneously  
3. **Advanced Monitoring**: Enhanced metrics and alerting
4. **Performance Optimization**: Reduce role assumption frequency

This quick reference provides everything needed to understand, implement, and troubleshoot the authentication system.
