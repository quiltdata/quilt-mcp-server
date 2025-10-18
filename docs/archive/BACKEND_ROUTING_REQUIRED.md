# Backend Team: MCP Server Routing Configuration Required

## 🚨 CRITICAL: Routing Not Configured

**Status:**
- ✅ Frontend: Generating enhanced JWT tokens correctly (4,084 bytes, 32 buckets, 24 permissions)
- ✅ MCP Server: Deployed, healthy, listening on port 8000 (Task Definition Rev 70)
- ✅ JWT Config: Secrets match perfectly between frontend and server
- ❌ **ROUTING: `/mcp` path returns 405 Method Not Allowed (HTML, not JSON)**

**Root Cause:** The ALB/nginx/API Gateway is **NOT routing `/mcp*` to the MCP server target group**

---

## 🎯 What Needs to Be Done

Configure the routing layer to forward requests from:
```
https://demo.quiltdata.com/mcp → MCP Server (port 8000)
```

---

## 🔍 Current Infrastructure

**MCP Server (ECS Service):**
- Cluster: `sales-prod`
- Service: `sales-prod-mcp-server-production`
- Task Definition: `quilt-mcp-server:70`
- Container Port: `8000`
- Protocol: `HTTP`
- Health Check: `GET /healthz` (returning 200 OK ✅)

**Load Balancer:**
- ALB DNS: `sales--LoadB-nGDYylEerIKm-1431252539.us-east-1.elb.amazonaws.com`
- Target Group: `sales-prod-mcp-server`
- Target Port: `8000`

**Public Endpoint:**
- Domain: `demo.quiltdata.com`
- Path: `/mcp` (currently returns 405 ❌)

---

## 📋 Required Configuration

### Step 1: Identify the Routing Layer

**Question:** What's handling `https://demo.quiltdata.com`?

Check for:
- [ ] CloudFront distribution pointing to ALB
- [ ] ALB listener rules directly
- [ ] Nginx reverse proxy
- [ ] API Gateway
- [ ] Other proxy/CDN

### Step 2: Add MCP Routing Rule

**Based on what you find:**

#### If Using ALB Listener Rules (Most Likely):

```bash
# Check current rules
aws elbv2 describe-rules \
  --listener-arn <your-listener-arn> \
  --region us-east-1

# Add new rule for /mcp
aws elbv2 create-rule \
  --listener-arn <your-listener-arn> \
  --priority 10 \
  --conditions Field=path-pattern,Values='/mcp*' \
  --actions Type=forward,TargetGroupArn=<mcp-target-group-arn> \
  --region us-east-1
```

#### If Using CloudFormation/CDK:

Add to your ALB listener rules:

```yaml
MCPRoutingRule:
  Type: AWS::ElasticLoadBalancingV2::ListenerRule
  Properties:
    ListenerArn: !Ref HTTPSListener
    Priority: 10
    Conditions:
      - Field: path-pattern
        Values:
          - '/mcp*'
    Actions:
      - Type: forward
        TargetGroupArn: !Ref MCPServerTargetGroup
```

#### If Using Terraform:

```hcl
resource "aws_lb_listener_rule" "mcp_routing" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 10

  condition {
    path_pattern {
      values = ["/mcp*"]
    }
  }

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.mcp_server.arn
  }
}
```

#### If Using Nginx:

Add to nginx config (e.g., `/etc/nginx/sites-available/demo.quiltdata.com`):

```nginx
# MCP Server proxy
location /mcp {
    # Forward to ALB or directly to ECS service
    proxy_pass http://sales--LoadB-nGDYylEerIKm-1431252539.us-east-1.elb.amazonaws.com;
    # OR if using service discovery:
    # proxy_pass http://sales-prod-mcp-server.local:8000;
    
    # Required headers
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # CRITICAL: Pass through all headers including Authorization
    proxy_pass_request_headers on;
    
    # Support MCP protocol (JSON-RPC over HTTP)
    proxy_set_header Content-Type application/json;
    
    # SSE support for streaming responses
    proxy_set_header Connection '';
    proxy_buffering off;
    proxy_cache off;
    chunked_transfer_encoding off;
    
    # Timeouts
    proxy_connect_timeout 60s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;
    
    # CORS for frontend
    add_header 'Access-Control-Allow-Origin' '*' always;
    add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS' always;
    add_header 'Access-Control-Allow-Headers' 'Authorization, Content-Type, mcp-protocol-version, mcp-session-id' always;
    
    # Handle OPTIONS preflight
    if ($request_method = 'OPTIONS') {
        return 204;
    }
}
```

Then reload nginx:
```bash
sudo nginx -t && sudo nginx -s reload
```

---

## 🧪 Testing the Routing

### Test 1: Health Check (No Auth Required)

```bash
curl https://demo.quiltdata.com/mcp/healthz
```

**Expected:**
```json
{
  "status": "ok",
  "timestamp": 1727650000,
  "mcp_tools_count": 97,
  "transport": "sse"
}
```

**Current (broken):**
```html
<html>... 405 Method Not Allowed
```

### Test 2: MCP Tools List (Requires JWT)

```bash
# Get JWT from browser console first:
# await window.__dynamicAuthManager.getCurrentToken()

curl -X POST https://demo.quiltdata.com/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <paste-jwt-here>" \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-1",
    "method": "tools/list"
  }'
```

**Expected:**
```json
{
  "jsonrpc": "2.0",
  "id": "test-1",
  "result": {
    "tools": [
      {"name": "auth_status", ...},
      {"name": "bucket_objects_list", ...},
      ...97 tools total...
    ]
  }
}
```

### Test 3: Direct ALB Test (From Within VPC)

```bash
# If you can access from within the VPC:
curl -X POST http://sales--LoadB-nGDYylEerIKm-1431252539.us-east-1.elb.amazonaws.com/mcp/healthz

# Should return JSON health status
```

---

## 📊 Current Route Analysis

### Check Existing Routes

```bash
# If using ALB, check current listener rules:
aws elbv2 describe-listeners \
  --load-balancer-arn <your-alb-arn> \
  --region us-east-1

aws elbv2 describe-rules \
  --listener-arn <listener-arn> \
  --region us-east-1 \
  | grep -A 5 "PathPattern"
```

Look for patterns like:
- `/graphql` → GraphQL server
- `/api/*` → API server  
- `/mcp*` → **MISSING** (needs to be added)

---

## 🔧 Implementation Steps

### Step-by-Step Guide

1. **Find the ALB:**
   ```bash
   aws elbv2 describe-load-balancers \
     --region us-east-1 \
     --query "LoadBalancers[?DNSName=='sales--LoadB-nGDYylEerIKm-1431252539.us-east-1.elb.amazonaws.com']"
   ```

2. **Find the HTTPS Listener:**
   ```bash
   aws elbv2 describe-listeners \
     --load-balancer-arn <alb-arn-from-step-1> \
     --region us-east-1 \
     --query "Listeners[?Port==\`443\`]"
   ```

3. **Find the MCP Target Group ARN:**
   ```bash
   aws elbv2 describe-target-groups \
     --region us-east-1 \
     --query "TargetGroups[?TargetGroupName=='sales-prod-mcp-server'].TargetGroupArn" \
     --output text
   ```

4. **Create the Routing Rule:**
   ```bash
   aws elbv2 create-rule \
     --listener-arn <listener-arn-from-step-2> \
     --priority 10 \
     --conditions Field=path-pattern,Values='/mcp*' \
     --actions Type=forward,TargetGroupArn=<target-group-arn-from-step-3> \
     --region us-east-1
   ```

5. **Verify the Rule:**
   ```bash
   aws elbv2 describe-rules \
     --listener-arn <listener-arn> \
     --region us-east-1 \
     | grep -B 2 -A 10 "mcp"
   ```

6. **Test Immediately:**
   ```bash
   curl https://demo.quiltdata.com/mcp/healthz
   # Should return JSON, not HTML
   ```

---

## 🏗️ Infrastructure as Code Examples

### Terraform Module

```hcl
# Add to your existing Terraform configuration
resource "aws_lb_listener_rule" "mcp_server" {
  listener_arn = data.aws_lb_listener.https.arn
  priority     = 10

  condition {
    path_pattern {
      values = ["/mcp*"]
    }
  }

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.mcp_server.arn
  }

  tags = {
    Name        = "mcp-server-routing"
    Environment = "production"
    Service     = "quilt-mcp-server"
  }
}
```

### CloudFormation

```yaml
MCPRoutingRule:
  Type: AWS::ElasticLoadBalancingV2::ListenerRule
  Properties:
    ListenerArn: !Ref HTTPSListener
    Priority: 10
    Conditions:
      - Field: path-pattern
        PathPatternConfig:
          Values:
            - '/mcp*'
    Actions:
      - Type: forward
        ForwardConfig:
          TargetGroups:
            - TargetGroupArn: !Ref MCPServerTargetGroup
              Weight: 1
```

### CDK (TypeScript)

```typescript
// Add to your ALB listener
listener.addTargetGroups('MCPServerRoute', {
  priority: 10,
  conditions: [
    elbv2.ListenerCondition.pathPatterns(['/mcp*'])
  ],
  targetGroups: [mcpServerTargetGroup]
});
```

---

## ⚠️ Important Notes

1. **Priority Number:**
   - Choose a priority that doesn't conflict with existing rules
   - Lower number = higher priority
   - Check existing rules first to avoid conflicts

2. **Path Pattern:**
   - Use `/mcp*` to catch all subpaths
   - Includes `/mcp`, `/mcp/healthz`, `/mcp/tools/list`, etc.

3. **HTTPS vs HTTP:**
   - Public endpoint: HTTPS (demo.quiltdata.com)
   - ALB → MCP Server: Can be HTTP (internal VPC)
   - Ensure ALB listener is on port 443 for HTTPS

4. **Health Checks:**
   - Target group should have health check: `GET /healthz`
   - Already configured ✅
   - Should show healthy in target group

---

## 🚀 Expected Timeline

**Estimated time:** 5-10 minutes
1. Add ALB listener rule (2 min)
2. Wait for rule to propagate (1-2 min)
3. Test routing (1 min)
4. Verify end-to-end (2 min)

**Once configured:**
- Frontend tests will immediately pass ✅
- No frontend changes needed
- No MCP server restart needed
- Just refresh browser and tests will work

---

## 🔍 Diagnostic Commands

### Check if route exists:
```bash
aws elbv2 describe-rules \
  --listener-arn <listener-arn> \
  --region us-east-1 \
  | grep -i "mcp"
```

### Check target group health:
```bash
aws elbv2 describe-target-health \
  --target-group-arn <mcp-target-group-arn> \
  --region us-east-1
```

Expected: Target should show `healthy`

### Test from within VPC:
```bash
# SSH into any EC2 instance in the VPC and run:
curl http://sales--LoadB-nGDYylEerIKm-1431252539.us-east-1.elb.amazonaws.com/mcp/healthz
```

---

## 📊 Before vs After

### Before (Current - Broken)
```
User → https://demo.quiltdata.com/mcp
  ↓
ALB (no route for /mcp)
  ↓
❌ 405 Method Not Allowed (default behavior)
```

### After (Fixed)
```
User → https://demo.quiltdata.com/mcp
  ↓
ALB Listener Rule (path=/mcp*)
  ↓
Target Group (sales-prod-mcp-server)
  ↓
ECS Task (port 8000)
  ↓
✅ MCP Server responds with JSON
```

---

## 🆘 Need Help Finding the Configuration?

Run these commands to locate your infrastructure:

```bash
# 1. Find the ALB
aws elbv2 describe-load-balancers \
  --region us-east-1 \
  --query "LoadBalancers[?DNSName=='sales--LoadB-nGDYylEerIKm-1431252539.us-east-1.elb.amazonaws.com']" \
  | grep LoadBalancerArn

# 2. Find HTTPS listener (port 443)
aws elbv2 describe-listeners \
  --load-balancer-arn <alb-arn-from-above> \
  --region us-east-1 \
  --query "Listeners[?Port==\`443\`]" \
  | grep ListenerArn

# 3. Check existing rules
aws elbv2 describe-rules \
  --listener-arn <listener-arn-from-above> \
  --region us-east-1 \
  --output table

# 4. Find MCP target group
aws elbv2 describe-target-groups \
  --region us-east-1 \
  --names sales-prod-mcp-server \
  | grep TargetGroupArn

# 5. Verify target is healthy
aws elbv2 describe-target-health \
  --target-group-arn <target-group-arn-from-above> \
  --region us-east-1
```

---

## ✅ Verification After Configuration

### Test 1: Health Check
```bash
curl https://demo.quiltdata.com/mcp/healthz
```
Should return JSON (not HTML 405)

### Test 2: Tools List (with JWT)
```bash
curl -X POST https://demo.quiltdata.com/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJ..." \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/list"}'
```
Should return list of 97 tools

### Test 3: Frontend Integration
Ask frontend to re-run their test suite - all tests should pass:
- ✅ Get Current Buckets
- ✅ Enhanced Token Generator
- ✅ Permission Validation
- ✅ Bucket Discovery Validation
- ✅ Complete Auth Flow

---

## 🚨 URGENT: This is Blocking Production

**Impact:**
- Frontend is fully implemented and working
- MCP server is deployed and healthy
- JWT authentication is configured correctly
- **But users can't access MCP tools because routing isn't configured**

**ETA:** This should take **5-10 minutes** to fix once you locate the routing configuration.

---

## 📞 Questions?

If you need help:
1. Share the output of the diagnostic commands above
2. Tell me what routing layer you're using (ALB/nginx/CloudFront/etc.)
3. Share existing routing configuration for other services (e.g., `/graphql`)

I can provide exact commands/config based on your infrastructure.

---

## 🎯 Bottom Line

**Everything is ready except the routing configuration.**

Once `/mcp` is routed to the MCP server target group:
- All frontend tests will pass immediately ✅
- JWT authentication will work end-to-end ✅
- Users can access all 97 MCP tools ✅

**This is the ONLY blocker to production.** 🚀
