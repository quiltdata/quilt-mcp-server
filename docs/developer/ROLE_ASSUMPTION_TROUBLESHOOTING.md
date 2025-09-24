# Role Assumption Troubleshooting Guide

## Overview

This guide helps diagnose and resolve issues with the automatic role assumption system in the Quilt MCP Server.

## Quick Diagnostics

### 1. Check Current Status

```bash
# Check if role assumption is working
curl -H "Accept: application/json" \
  "https://demo.quiltdata.com/mcp/" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/call","params":{"name":"get_current_quilt_role","arguments":{}}}'
```

### 2. Check Authentication Status

```bash
curl -H "Accept: application/json" \
  "https://demo.quiltdata.com/mcp/" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/call","params":{"name":"auth_status","arguments":{}}}'
```

### 3. Check CloudWatch Logs

```bash
# Get recent logs
aws logs get-log-events \
  --log-group-name /ecs/mcp-server-production \
  --log-stream-name ecs/mcp-server/$(aws ecs list-tasks --cluster sales-prod --service-name sales-prod-mcp-server-production --query 'taskArns[0]' --output text | cut -d'/' -f3) \
  --query 'events[-20:].message' \
  --output text
```

## Common Issues and Solutions

### Issue 1: Role Name Mismatch

**Symptoms**:
- Logs show: `Failed to assume Quilt user role ReadWriteQuiltBucket: ValidationError`
- Frontend sends incorrect role name

**Diagnosis**:
```bash
# Check what roles are available
aws iam list-roles --query 'Roles[?contains(RoleName, `Quilt`)].{RoleName:RoleName,Arn:Arn}' --output table
```

**Solution**:
Update frontend to send correct role name:
- ❌ Wrong: `ReadWriteQuiltBucket`
- ✅ Correct: `ReadWriteQuiltV2-sales-prod`

**Frontend Fix**:
```javascript
// Update the role ARN in headers
const correctRoleArn = 'arn:aws:iam::850787717197:role/ReadWriteQuiltV2-sales-prod';
```

### Issue 2: IAM Trust Policy Missing

**Symptoms**:
- Logs show: `AccessDenied: User is not authorized to perform: sts:AssumeRole`
- Role assumption fails with permission error

**Diagnosis**:
```bash
# Check current trust policy
aws iam get-role --role-name ReadWriteQuiltV2-sales-prod --query 'Role.AssumeRolePolicyDocument' --output json
```

**Solution**:
Update trust policy to include ECS task role:
```bash
aws iam update-assume-role-policy --role-name ReadWriteQuiltV2-sales-prod --policy-document '{
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
}'
```

### Issue 3: Missing Headers

**Symptoms**:
- No role assumption attempts in logs
- `get_current_quilt_role()` returns "No Quilt user role ARN available"

**Diagnosis**:
Check if frontend is sending required headers:
```javascript
// Verify headers are being sent
console.log('MCP Headers:', {
  'X-Quilt-User-Role': request.headers['x-quilt-user-role'],
  'X-Quilt-User-Id': request.headers['x-quilt-user-id']
});
```

**Solution**:
Ensure frontend sends both headers:
```javascript
const mcpHeaders = {
  'X-Quilt-User-Role': user.role.arn,  // Full ARN, not just name
  'X-Quilt-User-Id': user.id,
  // ... other headers
};
```

### Issue 4: Invalid Role ARN Format

**Symptoms**:
- Logs show: `Invalid role ARN format`
- Role assumption fails before STS call

**Diagnosis**:
Check the role ARN format:
```bash
# Should start with arn:aws:iam::
echo $QUILT_USER_ROLE_ARN
```

**Solution**:
Ensure frontend sends full ARN:
- ❌ Wrong: `ReadWriteQuiltBucket`
- ✅ Correct: `arn:aws:iam::850787717197:role/ReadWriteQuiltV2-sales-prod`

### Issue 5: ECS Task Role Permissions

**Symptoms**:
- Logs show: `AccessDenied: User is not authorized to perform: sts:AssumeRole`
- ECS task role lacks permissions

**Diagnosis**:
```bash
# Check ECS task role permissions
aws iam get-role-policy --role-name ecsTaskRole --policy-name AssumeRolePolicy
```

**Solution**:
Add STS AssumeRole permission to ECS task role:
```bash
aws iam put-role-policy --role-name ecsTaskRole --policy-name AssumeRolePolicy --policy-document '{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "sts:AssumeRole",
      "Resource": "*"
    }
  ]
}'
```

## Log Analysis

### Successful Role Assumption

```
INFO: Automatically attempting to assume Quilt user role: arn:aws:iam::850787717197:role/ReadWriteQuiltV2-sales-prod
INFO: Automatic role assumption successful: arn:aws:iam::850787717197:role/ReadWriteQuiltV2-sales-prod
```

### Failed Role Assumption - Wrong Role Name

```
Failed to assume Quilt user role ReadWriteQuiltBucket: An error occurred (ValidationError) when calling the AssumeRole operation: ReadWriteQuiltBucket is invalid
Automatic role assumption failed: ReadWriteQuiltBucket
```

### Failed Role Assumption - Permission Denied

```
Failed to assume Quilt user role arn:aws:iam::850787717197:role/ReadWriteQuiltV2-sales-prod: An error occurred (AccessDenied) when calling the AssumeRole operation: User: arn:aws:sts::850787717197:assumed-role/ecsTaskRole/6b777c1809a94925ab48098fa09824de is not authorized to perform: sts:AssumeRole on resource: arn:aws:iam::850787717197:role/ReadWriteQuiltV2-sales-prod
Automatic role assumption failed: arn:aws:iam::850787717197:role/ReadWriteQuiltV2-sales-prod
```

### No Role Assumption Attempts

```
# No role assumption logs = missing headers
INFO: 127.0.0.1:54270 - "GET /healthz HTTP/1.1" 200 OK
INFO: 10.0.200.199:64300 - "POST /mcp/?t=1758664904222 HTTP/1.1" 200 OK
```

## Testing Commands

### Test Role Assumption Manually

```bash
# Test assuming a role manually
curl -H "Accept: application/json" \
  "https://demo.quiltdata.com/mcp/" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/call","params":{"name":"assume_quilt_user_role","arguments":{"role_arn":"arn:aws:iam::850787717197:role/ReadWriteQuiltV2-sales-prod"}}}'
```

### Test with Headers

```bash
# Test with role headers
curl -H "Accept: application/json" \
  -H "X-Quilt-User-Role: arn:aws:iam::850787717197:role/ReadWriteQuiltV2-sales-prod" \
  -H "X-Quilt-User-Id: test-user" \
  "https://demo.quiltdata.com/mcp/" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/call","params":{"name":"get_current_quilt_role","arguments":{}}}'
```

## Environment Verification

### Check ECS Task Definition

```bash
aws ecs describe-task-definition --task-definition quilt-mcp-server:23 --query 'taskDefinition.{taskRoleArn:taskRoleArn,containerDefinitions:containerDefinitions[0].image}' --output table
```

### Check ECS Service Status

```bash
aws ecs describe-services --cluster sales-prod --services sales-prod-mcp-server-production --query 'services[0].{status:status,runningCount:runningCount,desiredCount:desiredCount}' --output table
```

### Check Container Health

```bash
aws ecs describe-tasks --cluster sales-prod --tasks $(aws ecs list-tasks --cluster sales-prod --service-name sales-prod-mcp-server-production --query 'taskArns[0]' --output text) --query 'tasks[0].{lastStatus:lastStatus,healthStatus:healthStatus}' --output table
```

## Frontend Integration Checklist

### ✅ Required Headers

- [ ] `X-Quilt-User-Role`: Full AWS ARN (e.g., `arn:aws:iam::850787717197:role/ReadWriteQuiltV2-sales-prod`)
- [ ] `X-Quilt-User-Id`: User identifier

### ✅ Role Switching

- [ ] Headers update when user switches roles
- [ ] MCP client reconnects with new headers
- [ ] Role changes are reflected in MCP operations

### ✅ Error Handling

- [ ] Graceful handling of role assumption failures
- [ ] User feedback when permissions are insufficient
- [ ] Fallback behavior when headers are missing

## Performance Monitoring

### CloudWatch Metrics

Monitor these metrics for role assumption performance:
- Role assumption success rate
- Role assumption latency
- Failed role assumption count
- Concurrent role assumptions

### Log Patterns

Watch for these log patterns:
- `Automatic role assumption successful` - Good
- `Automatic role assumption failed` - Needs investigation
- `Already using the requested Quilt user role` - Efficient caching
- `No QUILT_USER_ROLE_ARN environment variable set` - Missing headers

## Recovery Procedures

### Reset Role Assumption

If role assumption gets stuck:
1. Check current role: `get_current_quilt_role()`
2. Manually assume correct role: `assume_quilt_user_role(role_arn)`
3. Verify: `auth_status()`

### Restart ECS Service

If persistent issues occur:
```bash
aws ecs update-service --cluster sales-prod --service sales-prod-mcp-server-production --force-new-deployment
```

### Clear Environment Variables

If environment variables are corrupted:
```bash
# Restart the container to clear environment variables
aws ecs update-service --cluster sales-prod --service sales-prod-mcp-server-production --force-new-deployment
```

## Contact Information

For additional support:
- Check CloudWatch logs for detailed error messages
- Review IAM permissions and trust policies
- Verify frontend header configuration
- Test with manual role assumption tools
