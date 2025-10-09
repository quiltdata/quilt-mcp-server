# Multi-MCP Architecture Analysis

## The Challenge

Run both Quilt MCP and Benchling MCP servers with:
- **Different authentication**: JWT tokens (Quilt) vs API keys (Benchling)
- **Different permission models**: User-specific Quilt access vs shared/user Benchling keys
- **Scalability**: Multiple users, potentially different access levels
- **Maintainability**: Independent updates, debugging, monitoring

## Architecture Options

### Option 1: Separate Containers (Recommended ✅)

**Architecture**:
```
┌─────────────────────────────────────────────────────────┐
│                     API Gateway / ALB                    │
│                  (Route by path prefix)                  │
└─────────────────┬───────────────────────┬────────────────┘
                  │                       │
         /quilt/* │                       │ /benchling/*
                  │                       │
        ┌─────────▼─────────┐   ┌────────▼──────────┐
        │  Quilt MCP Server  │   │ Benchling MCP     │
        │   (ECS Task 1)     │   │   (ECS Task 2)    │
        │                    │   │                   │
        │  Auth: JWT tokens  │   │  Auth: API keys   │
        │  Port: 3000        │   │  Port: 3001       │
        └────────────────────┘   └───────────────────┘
```

**Pros**:
- ✅ **Independent scaling**: Scale each MCP based on its load
- ✅ **Independent deployment**: Update Quilt without touching Benchling
- ✅ **Failure isolation**: Benchling crash doesn't affect Quilt
- ✅ **Clear permission boundaries**: Each service manages its own auth
- ✅ **Independent monitoring**: Separate logs, metrics, alarms
- ✅ **Resource allocation**: Different CPU/memory for each service
- ✅ **Technology flexibility**: Can use different languages/frameworks

**Cons**:
- ❌ More infrastructure (2 ECS services, 2 task definitions)
- ❌ Slightly higher cost (2 containers vs 1)
- ❌ More complex routing configuration

**Routing Setup**:
```yaml
# ALB Listener Rules
/quilt/*     → Target Group 1 (Quilt MCP)
/benchling/* → Target Group 2 (Benchling MCP)

# OR use subdomains:
quilt.example.com     → Quilt MCP
benchling.example.com → Benchling MCP
```

**Implementation Complexity**: Medium
**Operational Overhead**: Medium
**Best For**: Production environments, teams that need independent scaling/deployment

---

### Option 2: Single Container with Multiple Processes

**Architecture**:
```
┌─────────────────────────────────────────────────────────┐
│                    Docker Container                      │
│  ┌───────────────────────────────────────────────────┐  │
│  │            Supervisor / Process Manager           │  │
│  └─────┬──────────────────────────────────┬──────────┘  │
│        │                                   │             │
│  ┌─────▼──────────┐              ┌────────▼─────────┐  │
│  │ Quilt MCP      │              │ Benchling MCP     │  │
│  │ Process        │              │ Process           │  │
│  │ Port: 3000     │              │ Port: 3001        │  │
│  └────────────────┘              └───────────────────┘  │
│                                                          │
│  + Nginx/HAProxy for internal routing                   │
└──────────────────────────────────────────────────────────┘
```

**Pros**:
- ✅ Single container to manage
- ✅ Shared base image (smaller total size)
- ✅ Can share common dependencies
- ✅ Simpler deployment (one task definition)

**Cons**:
- ❌ **Coupled lifecycle**: Both services restart together
- ❌ **Shared resources**: CPU/memory contention
- ❌ **Failure cascade**: One service crash can affect the other
- ❌ **Complex orchestration**: Need supervisor (supervisord, PM2, etc.)
- ❌ **Harder debugging**: Logs intermingled
- ❌ **Can't scale independently**
- ❌ **Update complexity**: Can't update one without restarting both

**Implementation Complexity**: High
**Operational Overhead**: High
**Best For**: Development/testing only, NOT recommended for production

---

### Option 3: Unified MCP Server (Single Codebase)

**Architecture**:
```
┌─────────────────────────────────────────────────────────┐
│              Unified MCP Server                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │            Request Handler                        │  │
│  │     (Auth middleware: JWT + API key support)      │  │
│  └─────┬──────────────────────────────────┬──────────┘  │
│        │                                   │             │
│  ┌─────▼──────────┐              ┌────────▼─────────┐  │
│  │ Quilt Module   │              │ Benchling Module  │  │
│  │ (auth, search, │              │ (entries,         │  │
│  │  packaging,    │              │  schemas, etc)    │  │
│  │  etc.)         │              │                   │  │
│  └────────────────┘              └───────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

**Pros**:
- ✅ **Single server**: One service to monitor/deploy
- ✅ **Shared code**: Auth helpers, utilities, error handling
- ✅ **Cross-service features**: Quilt packages can reference Benchling data
- ✅ **Simplified client**: One connection, one set of tools
- ✅ **Unified observability**: Single log stream, metrics dashboard

**Cons**:
- ❌ **Tight coupling**: Changes require full rebuild/test of both
- ❌ **Monolithic growth**: Codebase becomes complex over time
- ❌ **Testing complexity**: Need to test both Quilt and Benchling scenarios
- ❌ **Can't scale independently**
- ❌ **Deployment risk**: Bug in Benchling code affects Quilt users
- ❌ **Permission complexity**: Need to handle two auth schemes in one place

**Implementation Complexity**: Very High
**Operational Overhead**: Medium
**Best For**: Tight integration scenarios, shared data workflows

---

## Authentication & Permission Management

### Current Authentication Flows

#### Quilt MCP (JWT-based)
```python
# Client sends JWT in request
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...

# Server extracts JWT and validates
token = request.headers.get("Authorization").split("Bearer ")[1]
jwt_payload = verify_jwt(token)

# JWT contains:
{
  "user_id": "user@example.com",
  "catalog_url": "https://example.quiltdata.com",
  "aws_credentials": {
    "access_key_id": "...",
    "secret_access_key": "...",
    "session_token": "..."
  },
  "scopes": ["read:packages", "write:packages"]
}

# Each user has unique JWT → unique AWS credentials
```

#### Benchling MCP (API Key-based)
```python
# Client sends API key in request
X-Benchling-API-Key: sk_1234567890abcdef...

# OR as Basic Auth
Authorization: Basic base64(api_key:)

# Server uses API key for all Benchling requests
headers = {"X-Benchling-API-Key": api_key}
response = requests.get("https://api.benchling.com/v2/entries", headers=headers)

# API key maps to:
# - Specific Benchling user OR
# - Service account with specific permissions
```

### Permission Models Comparison

| Aspect | Quilt (JWT) | Benchling (API Key) |
|--------|-------------|---------------------|
| **Granularity** | Per-user, per-request | Per-key (could be shared) |
| **Expiration** | Short-lived (hours) | Long-lived (until revoked) |
| **Rotation** | Automatic (new JWT per login) | Manual |
| **Audit Trail** | User ID in every request | API key ID (if user keys) |
| **Credential Storage** | Client-side only | Could be server-side |
| **AWS Access** | Embedded in JWT | N/A |

### Option A: User-Specific API Keys (Recommended ✅)

**Architecture**:
```
User 1 → JWT (Quilt) + API Key 1 (Benchling personal key)
User 2 → JWT (Quilt) + API Key 2 (Benchling personal key)
User 3 → JWT (Quilt) + API Key 3 (Benchling personal key)
```

**How It Works**:
1. User logs into Quilt → receives JWT
2. User provides their Benchling API key (personal/user key)
3. MCP server receives both credentials in each request:
   ```
   Authorization: Bearer <quilt-jwt>
   X-Benchling-API-Key: <user-benchling-key>
   ```
4. Server uses JWT for Quilt operations, API key for Benchling operations

**Pros**:
- ✅ **Proper audit trail**: Each user's actions tracked separately
- ✅ **Principle of least privilege**: Users have only their permissions
- ✅ **Clear accountability**: Know who did what in both systems
- ✅ **No shared secrets**: Each user manages their own credentials

**Cons**:
- ❌ Users must manage two credentials
- ❌ Benchling key rotation requires user action
- ❌ More complex client setup

**Implementation**:
```python
# MCP Server
async def handle_benchling_request(request):
    # Extract both credentials
    jwt_token = extract_jwt(request)
    benchling_key = request.headers.get("X-Benchling-API-Key")
    
    # Validate both
    quilt_user = validate_jwt(jwt_token)
    benchling_client = BenchlingClient(api_key=benchling_key)
    
    # Use appropriate credential for each service
    if action.startswith("quilt_"):
        return await quilt_operation(jwt_token, action, params)
    elif action.startswith("benchling_"):
        return await benchling_operation(benchling_client, action, params)
```

### Option B: Shared Service Account Key

**Architecture**:
```
All Users → JWT (Quilt, unique per user) + Shared API Key (Benchling service account)
```

**How It Works**:
1. MCP server stores single Benchling API key (service account)
2. Users only provide JWT (Quilt)
3. All Benchling requests use shared key
4. Server logs user ID from JWT for audit

**Pros**:
- ✅ **Simpler for users**: Only need Quilt JWT
- ✅ **Centralized key rotation**: Admin controls Benchling key
- ✅ **Easier setup**: One-time Benchling key configuration

**Cons**:
- ❌ **Lost audit trail**: All Benchling actions appear from service account
- ❌ **Over-privileged**: Service account needs union of all user permissions
- ❌ **Security risk**: Compromised MCP = all Benchling access
- ❌ **No user-level controls**: Can't restrict individual users in Benchling

**Implementation**:
```python
# Environment variable
BENCHLING_SERVICE_KEY = os.environ.get("BENCHLING_API_KEY")

async def handle_benchling_request(request):
    jwt_token = extract_jwt(request)
    quilt_user = validate_jwt(jwt_token)
    
    # Use shared key but log user
    logger.info(f"User {quilt_user['user_id']} accessing Benchling")
    benchling_client = BenchlingClient(api_key=BENCHLING_SERVICE_KEY)
    
    return await benchling_operation(benchling_client, action, params)
```

### Option C: Hybrid with Key Vault

**Architecture**:
```
User → JWT (Quilt) → MCP → AWS Secrets Manager → User's Benchling Key
```

**How It Works**:
1. Store each user's Benchling API key in AWS Secrets Manager
2. Key stored as: `benchling/user/{user_email}/api_key`
3. MCP extracts user ID from JWT
4. MCP fetches that user's Benchling key from Secrets Manager
5. Use fetched key for Benchling operations

**Pros**:
- ✅ **User-specific access**: Each user has their own permissions
- ✅ **Centralized rotation**: Admin can rotate keys without user action
- ✅ **Secure storage**: Keys never in client code
- ✅ **Audit trail**: AWS logs key access

**Cons**:
- ❌ **Complex setup**: Need Secrets Manager integration
- ❌ **Latency**: Extra fetch on each request (can cache)
- ❌ **Cost**: Secrets Manager API calls
- ❌ **Initial provisioning**: Need to populate secrets for each user

**Implementation**:
```python
import boto3

secrets_client = boto3.client('secretsmanager')

async def get_user_benchling_key(user_email: str) -> str:
    """Fetch user's Benchling API key from Secrets Manager."""
    secret_name = f"benchling/user/{user_email}/api_key"
    response = secrets_client.get_secret_value(SecretId=secret_name)
    return response['SecretString']

async def handle_benchling_request(request):
    jwt_token = extract_jwt(request)
    quilt_user = validate_jwt(jwt_token)
    
    # Fetch user's Benchling key
    benchling_key = await get_user_benchling_key(quilt_user['user_id'])
    benchling_client = BenchlingClient(api_key=benchling_key)
    
    return await benchling_operation(benchling_client, action, params)
```

---

## Recommended Architecture

### For Production: Separate Containers + User-Specific Keys

**Infrastructure**:
```yaml
# docker-compose.yml (or ECS equivalent)
services:
  quilt-mcp:
    image: quilt-mcp-server:latest
    ports:
      - "3000:3000"
    environment:
      - FASTMCP_TRANSPORT=http
      - FASTMCP_HOST=0.0.0.0
      - FASTMCP_PORT=3000
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
  
  benchling-mcp:
    image: benchling-mcp-server:latest
    ports:
      - "3001:3001"
    environment:
      - FASTMCP_TRANSPORT=http
      - FASTMCP_HOST=0.0.0.0
      - FASTMCP_PORT=3001
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G

  # Optional: API Gateway / Reverse Proxy
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - quilt-mcp
      - benchling-mcp
```

**Routing (nginx.conf)**:
```nginx
http {
    upstream quilt_backend {
        server quilt-mcp:3000;
    }
    
    upstream benchling_backend {
        server benchling-mcp:3001;
    }
    
    server {
        listen 80;
        
        # Route by path prefix
        location /quilt/ {
            proxy_pass http://quilt_backend/;
            proxy_set_header Authorization $http_authorization;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }
        
        location /benchling/ {
            proxy_pass http://benchling_backend/;
            proxy_set_header X-Benchling-API-Key $http_x_benchling_api_key;
            proxy_set_header Authorization $http_authorization;
        }
    }
}
```

**Client Usage**:
```javascript
// Quilt operations
fetch('https://mcp.example.com/quilt/mcp', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${quiltJWT}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    method: 'tools/call',
    params: {
      name: 'mcp_quilt-mcp-server_search',
      arguments: { action: 'unified_search', params: { query: 'csv' } }
    }
  })
});

// Benchling operations
fetch('https://mcp.example.com/benchling/mcp', {
  method: 'POST',
  headers: {
    'X-Benchling-API-Key': userBenchlingKey,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    method: 'tools/call',
    params: {
      name: 'mcp_benchling_entries_list',
      arguments: { folder_id: 'lib_abc123' }
    }
  })
});
```

---

## ECS Task Configuration

### Separate Tasks (Recommended)

```json
{
  "family": "quilt-mcp-server",
  "taskRoleArn": "arn:aws:iam::ACCOUNT:role/QuiltMCPTaskRole",
  "executionRoleArn": "arn:aws:iam::ACCOUNT:role/ECSExecutionRole",
  "networkMode": "awsvpc",
  "cpu": "2048",
  "memory": "4096",
  "containerDefinitions": [{
    "name": "quilt-mcp",
    "image": "850787717197.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:latest",
    "portMappings": [{ "containerPort": 3000, "protocol": "tcp" }],
    "environment": [
      { "name": "FASTMCP_TRANSPORT", "value": "http" },
      { "name": "FASTMCP_HOST", "value": "0.0.0.0" },
      { "name": "FASTMCP_PORT", "value": "3000" }
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/quilt-mcp-server",
        "awslogs-region": "us-east-1",
        "awslogs-stream-prefix": "quilt"
      }
    }
  }]
}
```

```json
{
  "family": "benchling-mcp-server",
  "taskRoleArn": "arn:aws:iam::ACCOUNT:role/BenchlingMCPTaskRole",
  "executionRoleArn": "arn:aws:iam::ACCOUNT:role/ECSExecutionRole",
  "networkMode": "awsvpc",
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [{
    "name": "benchling-mcp",
    "image": "YOUR_ECR/benchling-mcp-server:latest",
    "portMappings": [{ "containerPort": 3001, "protocol": "tcp" }],
    "environment": [
      { "name": "FASTMCP_TRANSPORT", "value": "http" },
      { "name": "FASTMCP_HOST", "value": "0.0.0.0" },
      { "name": "FASTMCP_PORT", "value": "3001" }
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/benchling-mcp-server",
        "awslogs-region": "us-east-1",
        "awslogs-stream-prefix": "benchling"
      }
    }
  }]
}
```

### ALB Configuration

```bash
# Create target groups
aws elbv2 create-target-group \
  --name quilt-mcp-tg \
  --protocol HTTP \
  --port 3000 \
  --vpc-id vpc-xxx \
  --target-type ip \
  --health-check-path /health

aws elbv2 create-target-group \
  --name benchling-mcp-tg \
  --protocol HTTP \
  --port 3001 \
  --vpc-id vpc-xxx \
  --target-type ip \
  --health-check-path /health

# Create listener rules
aws elbv2 create-rule \
  --listener-arn arn:aws:elasticloadbalancing:... \
  --priority 10 \
  --conditions Field=path-pattern,Values='/quilt/*' \
  --actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:.../quilt-mcp-tg

aws elbv2 create-rule \
  --listener-arn arn:aws:elasticloadbalancing:... \
  --priority 20 \
  --conditions Field=path-pattern,Values='/benchling/*' \
  --actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:.../benchling-mcp-tg
```

---

## Security Considerations

### JWT Token Handling
- ✅ Validate signature using Quilt's public key
- ✅ Check expiration timestamps
- ✅ Verify audience and issuer claims
- ✅ Extract AWS credentials securely
- ✅ Never log full JWT tokens

### API Key Handling
- ✅ Never log API keys (mask in logs)
- ✅ Use HTTPS only (never HTTP)
- ✅ Implement rate limiting per key
- ✅ Support key rotation without downtime
- ✅ Store in environment variables or Secrets Manager

### Network Security
- ✅ VPC with private subnets for containers
- ✅ Security groups restrict inbound to ALB only
- ✅ ALB terminates SSL/TLS
- ✅ Use AWS WAF for DDoS protection
- ✅ Enable VPC Flow Logs

---

## Monitoring & Observability

### Metrics to Track

**Per-Service**:
- Request count
- Error rate (4xx, 5xx)
- Latency (p50, p95, p99)
- Active connections
- Memory usage
- CPU utilization

**Authentication**:
- JWT validation failures
- API key validation failures
- Token expiration errors
- Rate limit hits

**Business Metrics**:
- Quilt operations per user
- Benchling operations per user
- Cross-service workflows

### CloudWatch Dashboards

```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "title": "Quilt MCP Requests",
        "metrics": [
          ["AWS/ECS", "RequestCount", {"Service": "quilt-mcp"}]
        ]
      }
    },
    {
      "type": "metric",
      "properties": {
        "title": "Benchling MCP Requests",
        "metrics": [
          ["AWS/ECS", "RequestCount", {"Service": "benchling-mcp"}]
        ]
      }
    }
  ]
}
```

---

## Migration Path

### Phase 1: Deploy Benchling MCP Standalone
1. Build Benchling MCP Docker image
2. Create ECS task definition
3. Deploy to ECS with separate target group
4. Test with direct API calls

### Phase 2: Configure Routing
1. Set up ALB listener rules
2. Configure path-based routing
3. Test routing to both services
4. Verify authentication flows

### Phase 3: Client Integration
1. Update clients to use path prefixes
2. Add Benchling API key configuration
3. Test cross-service workflows
4. Monitor and optimize

### Phase 4: Production Rollout
1. Gradual rollout (canary deployment)
2. Monitor error rates and latency
3. Set up alarms and runbooks
4. Train support team

---

## Cost Estimate

### Option 1 (Separate Containers):
- **Quilt MCP**: t3.medium (2 vCPU, 4GB) = ~$30/month
- **Benchling MCP**: t3.small (2 vCPU, 2GB) = ~$15/month
- **ALB**: ~$20/month + data transfer
- **Total**: ~$65/month + data transfer

### Option 2 (Single Container):
- **Combined**: t3.medium (2 vCPU, 4GB) = ~$30/month
- **ALB**: ~$20/month + data transfer
- **Total**: ~$50/month + data transfer

**Savings**: ~$15/month, but loss of flexibility worth much more in operational efficiency.

---

## Conclusion

**Recommended Architecture**: **Separate Containers + User-Specific API Keys**

**Why**:
1. **Scalability**: Scale each service independently
2. **Reliability**: Failure isolation between services
3. **Security**: Clear permission boundaries, proper audit trail
4. **Maintainability**: Update/debug one service without affecting other
5. **Observability**: Clear metrics and logs per service
6. **Flexibility**: Can swap/upgrade either service independently

**When to Consider Unified**:
- Heavy cross-service data flows (e.g., Benchling data → Quilt packages)
- Need atomic transactions across both systems
- Tight budget constraints (saves ~$15/month)
- Small user base (<10 users)

**Next Steps**:
1. Review Benchling MCP codebase structure
2. Create Dockerfile for Benchling MCP
3. Set up ECS task definition
4. Configure ALB routing
5. Test authentication flows
6. Deploy to staging
7. Production rollout

