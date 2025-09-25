# MCP Unified Authentication Implementation Specification

## Overview

This specification provides detailed implementation requirements for unifying authentication across Quilt's MCP server to support both web and desktop clients using a single remote AWS-hosted server.

## Current Problems

1. **Web clients fail authentication** - JWT tokens not properly processed for many tools
2. **Desktop clients can't use remote server** - quilt3 credentials not passed to remote MCP server
3. **Inconsistent authentication patterns** - Different tools use different auth methods
4. **Permission mapping gaps** - JWT claims don't map correctly to AWS permissions

## Solution Architecture

### Core Design Principles

1. **AWS Credentials as Single Source of Truth** - All tools use AWS credentials for AWS operations
2. **Unified Authentication Service** - Single service handles all client types
3. **Client Type Detection** - Automatic detection of web vs desktop clients
4. **Credential Abstraction** - Tools don't need to know about authentication details

### Authentication Flow

```
Client Request → UnifiedAuthService → AWS Credentials → Tool Execution
     ↓                    ↓                ↓              ↓
Web/Desktop         Detect Type      Extract Creds    Execute with
   Client           & Extract        from JWT/        AWS Session
                    Auth Info        quilt3
```

## Implementation Requirements

### 1. Unified Authentication Service

**File**: `src/quilt_mcp/services/unified_auth_service.py`

**Requirements**:
- Detect client type (web/desktop) from request context
- Extract AWS credentials from JWT tokens or quilt3 sessions
- Create boto3 sessions with proper credentials
- Provide consistent interface to all tools
- Handle credential refresh and expiration
- Support both temporary and permanent credentials

**Key Methods**:
```python
class UnifiedAuthService:
    def authenticate_request(self, request_context: dict) -> AuthResult
    def get_aws_session(self, service: str) -> boto3.Session
    def get_quilt_api_client(self) -> QuiltAPIClient
    def authorize_tool(self, tool_name: str, tool_args: dict, auth_result: AuthResult) -> bool
    def refresh_credentials(self) -> bool
```

### 2. Enhanced JWT Token Processing

**File**: `src/quilt_mcp/services/jwt_processor.py`

**Requirements**:
- Parse JWT tokens to extract AWS role information
- Handle both compressed and uncompressed JWT tokens
- Extract AWS credentials from JWT claims
- Validate JWT token expiration and signature
- Map JWT permissions to AWS permissions

**Key Methods**:
```python
class JWTProcessor:
    def extract_aws_role_arn(self, jwt_payload: dict) -> Optional[str]
    def extract_aws_credentials(self, jwt_payload: dict) -> Optional[AWSCredentials]
    def map_permissions_to_aws(self, jwt_permissions: list) -> list
    def validate_token_expiration(self, jwt_payload: dict) -> bool
```

### 3. Desktop Client Integration

**File**: `src/quilt_mcp/services/desktop_auth_service.py`

**Requirements**:
- Accept quilt3 credentials via MCP protocol
- Parse quilt3 authentication files
- Extract AWS credentials from quilt3 sessions
- Handle credential refresh for long-running sessions
- Support both local and remote MCP server usage

**Key Methods**:
```python
class DesktopAuthService:
    def parse_quilt3_credentials(self, credentials_data: dict) -> Quilt3Credentials
    def extract_aws_credentials(self, quilt3_creds: Quilt3Credentials) -> AWSCredentials
    def refresh_quilt3_credentials(self) -> bool
    def validate_credentials(self, credentials: Quilt3Credentials) -> bool
```

### 4. Tool Authentication Updates

**File**: `src/quilt_mcp/tools/auth_helpers.py`

**Requirements**:
- Replace existing `_check_authorization` functions
- Use unified authentication service
- Provide consistent error handling
- Support all tool categories
- Maintain backward compatibility

**Key Functions**:
```python
def check_unified_authorization(tool_name: str, tool_args: dict) -> dict
def get_aws_session_for_tool(tool_name: str) -> boto3.Session
def get_quilt_api_for_tool(tool_name: str) -> QuiltAPIClient
def validate_tool_permissions(tool_name: str, user_permissions: dict) -> bool
```

## Tool Category Implementation

### 1. S3 Bucket Operations

**Tools**: `bucket_objects_list`, `bucket_object_info`, `bucket_object_text`, `bucket_object_fetch`, `bucket_objects_put`, `bucket_object_link`

**Authentication Pattern**:
```python
def _check_s3_authorization(tool_name: str, tool_args: dict) -> dict:
    """S3-specific authorization check."""
    auth_result = check_unified_authorization(tool_name, tool_args)
    
    if not auth_result["authorized"]:
        return auth_result
    
    # Get AWS S3 client
    s3_client = auth_result["aws_session"]("s3")
    
    # Check bucket access
    bucket_name = tool_args.get("bucket_name")
    if bucket_name and not validate_bucket_access(bucket_name, auth_result["user_info"]["buckets"]):
        return {"authorized": False, "error": f"Access denied to bucket {bucket_name}"}
    
    return {
        "authorized": True,
        "s3_client": s3_client,
        "user_info": auth_result["user_info"]
    }
```

### 2. Package Operations

**Tools**: `package_create`, `package_update`, `package_delete`, `package_browse`, `package_contents_search`, `package_diff`, `create_package_enhanced`

**Authentication Pattern**:
```python
def _check_package_authorization(tool_name: str, tool_args: dict) -> dict:
    """Package-specific authorization check."""
    auth_result = check_unified_authorization(tool_name, tool_args)
    
    if not auth_result["authorized"]:
        return auth_result
    
    # Get both AWS and Quilt API clients
    s3_client = auth_result["aws_session"]("s3")
    quilt_api = auth_result["quilt_api"]
    
    # Check package permissions
    if not validate_package_permissions(tool_name, auth_result["user_info"]):
        return {"authorized": False, "error": f"Package operation {tool_name} not authorized"}
    
    return {
        "authorized": True,
        "s3_client": s3_client,
        "quilt_api": quilt_api,
        "user_info": auth_result["user_info"]
    }
```

### 3. Athena/Glue Operations

**Tools**: `athena_query_execute`, `athena_databases_list`, `athena_tables_list`, `athena_table_schema`, `athena_workgroups_list`, `athena_query_history`

**Authentication Pattern**:
```python
def _check_athena_authorization(tool_name: str, tool_args: dict) -> dict:
    """Athena/Glue-specific authorization check."""
    auth_result = check_unified_authorization(tool_name, tool_args)
    
    if not auth_result["authorized"]:
        return auth_result
    
    # Get AWS Athena and Glue clients
    athena_client = auth_result["aws_session"]("athena")
    glue_client = auth_result["aws_session"]("glue")
    
    # Check Athena permissions
    if not validate_athena_permissions(tool_name, auth_result["user_info"]):
        return {"authorized": False, "error": f"Athena operation {tool_name} not authorized"}
    
    return {
        "authorized": True,
        "athena_client": athena_client,
        "glue_client": glue_client,
        "user_info": auth_result["user_info"]
    }
```

### 4. Search Operations

**Tools**: `unified_search`, `packages_search`

**Authentication Pattern**:
```python
def _check_search_authorization(tool_name: str, tool_args: dict) -> dict:
    """Search-specific authorization check."""
    auth_result = check_unified_authorization(tool_name, tool_args)
    
    if not auth_result["authorized"]:
        return auth_result
    
    # Search operations only need Quilt API access
    quilt_api = auth_result["quilt_api"]
    
    return {
        "authorized": True,
        "quilt_api": quilt_api,
        "user_info": auth_result["user_info"]
    }
```

### 5. Permission Operations

**Tools**: `aws_permissions_discover`, `bucket_access_check`, `bucket_recommendations_get`

**Authentication Pattern**:
```python
def _check_permission_authorization(tool_name: str, tool_args: dict) -> dict:
    """Permission-specific authorization check."""
    auth_result = check_unified_authorization(tool_name, tool_args)
    
    if not auth_result["authorized"]:
        return auth_result
    
    # Get AWS IAM client for permission operations
    iam_client = auth_result["aws_session"]("iam")
    
    # Check IAM permissions
    if not validate_iam_permissions(tool_name, auth_result["user_info"]):
        return {"authorized": False, "error": f"Permission operation {tool_name} not authorized"}
    
    return {
        "authorized": True,
        "iam_client": iam_client,
        "user_info": auth_result["user_info"]
    }
```

## Configuration Requirements

### 1. Environment Variables

**New Variables**:
```bash
# Unified authentication
UNIFIED_AUTH_ENABLED=true
UNIFIED_AUTH_DEBUG=false

# JWT processing
JWT_AWS_ROLE_CLAIM=aws_role_arn
JWT_AWS_CREDS_CLAIM=aws_credentials
JWT_PERMISSION_MAPPING_FILE=configs/permission_mapping.json

# Desktop client support
DESKTOP_AUTH_ENABLED=true
QUILT3_CREDENTIALS_PATH=~/.quilt/auth.json
QUILT3_CREDENTIALS_REFRESH_INTERVAL=3600

# AWS credential refresh
AWS_CREDENTIAL_REFRESH_THRESHOLD=300
AWS_CREDENTIAL_CACHE_TTL=3600
```

### 2. Permission Mapping Configuration

**File**: `configs/permission_mapping.json`

```json
{
  "tool_permissions": {
    "bucket_objects_list": {
      "aws_permissions": ["s3:ListBucket", "s3:GetBucketLocation"],
      "quilt_permissions": ["bucket:read"],
      "required_services": ["s3"]
    },
    "package_create": {
      "aws_permissions": ["s3:PutObject", "s3:PutObjectAcl", "s3:ListBucket"],
      "quilt_permissions": ["package:write"],
      "required_services": ["s3", "quilt_api"]
    },
    "athena_query_execute": {
      "aws_permissions": ["athena:StartQueryExecution", "athena:GetQueryExecution", "athena:GetQueryResults"],
      "quilt_permissions": ["athena:execute"],
      "required_services": ["athena"]
    }
  },
  "role_mappings": {
    "ReadWriteQuiltV2-sales-prod": {
      "level": "write",
      "buckets": ["quilt-sandbox-bucket", "quilt-sales-prod"],
      "tools": ["bucket_objects_list", "package_create", "athena_query_execute"]
    }
  }
}
```

## Testing Requirements

### 1. Unit Tests

**File**: `tests/unit/test_unified_auth_service.py`

**Test Cases**:
- JWT token parsing and validation
- AWS credential extraction
- Client type detection
- Tool authorization logic
- Credential refresh mechanism
- Error handling and edge cases

### 2. Integration Tests

**File**: `tests/integration/test_unified_auth_integration.py`

**Test Cases**:
- Web client authentication flow
- Desktop client authentication flow
- AWS service integration
- Quilt API integration
- Tool execution with unified auth
- Permission enforcement

### 3. End-to-End Tests

**File**: `tests/e2e/test_unified_auth_e2e.py`

**Test Cases**:
- Complete user workflows
- Cross-client compatibility
- Performance under load
- Error recovery
- Security validation

## Migration Strategy

### 1. Backward Compatibility

- **Existing tools** continue to work with current authentication
- **Feature flag** to enable unified authentication
- **Gradual migration** of tools to new system
- **Rollback capability** if issues arise

### 2. Implementation Phases

**Phase 1**: Core unified authentication service
- Implement `UnifiedAuthService`
- Add JWT processing enhancements
- Create basic tool authentication helpers

**Phase 2**: Tool migration
- Migrate S3 bucket operations
- Migrate package operations
- Migrate Athena/Glue operations
- Migrate search operations
- Migrate permission operations

**Phase 3**: Desktop client integration
- Implement desktop authentication service
- Add credential passing via MCP protocol
- Update desktop client configurations

**Phase 4**: Testing and optimization
- Comprehensive testing
- Performance optimization
- Security validation
- Documentation updates

### 3. Rollout Plan

1. **Internal testing** with feature flag disabled
2. **Beta testing** with select users and tools
3. **Gradual rollout** to all tools and users
4. **Full migration** and cleanup of old code

## Security Requirements

### 1. Credential Security

- **JWT tokens** encrypted in transit and at rest
- **AWS credentials** stored securely with encryption
- **Credential rotation** implemented automatically
- **Access logging** for all authentication events

### 2. Permission Validation

- **Principle of least privilege** enforced
- **Tool-level permissions** validated
- **Bucket-level access** controlled
- **Audit trail** maintained

### 3. Network Security

- **HTTPS only** for all communication
- **CORS configuration** properly set
- **Rate limiting** implemented
- **Input validation** for all requests

## Performance Requirements

### 1. Response Times

- **Authentication**: <500ms
- **Tool execution**: <2s average
- **Credential refresh**: <1s
- **Error responses**: <100ms

### 2. Throughput

- **Concurrent requests**: 100+ per second
- **Credential caching**: 95%+ hit rate
- **Error rate**: <1% of requests
- **Availability**: 99.9% uptime

## Monitoring and Alerting

### 1. Metrics

- **Authentication success rate** by client type
- **Tool execution success rate** by category
- **Credential refresh frequency** and success rate
- **Error rates** by tool and client type

### 2. Alerts

- **Authentication failures** >5% in 5 minutes
- **Tool execution failures** >10% in 5 minutes
- **Credential refresh failures** >1% in 1 hour
- **Performance degradation** >2s average response time

### 3. Dashboards

- **Real-time authentication status**
- **Tool usage statistics**
- **Error rate trends**
- **Performance metrics**

## Documentation Requirements

### 1. API Documentation

- **Unified authentication service** API reference
- **Tool authentication patterns** guide
- **Client integration** examples
- **Troubleshooting** guide

### 2. User Documentation

- **Setup instructions** for both client types
- **Configuration examples** for different environments
- **Common issues** and solutions
- **Best practices** guide

### 3. Developer Documentation

- **Architecture overview** with diagrams
- **Implementation details** for each component
- **Testing guidelines** and examples
- **Contributing guidelines** for future development

## Success Criteria

### 1. Functional Requirements

- **Web clients** authenticate successfully 95%+ of the time
- **Desktop clients** authenticate successfully 95%+ of the time
- **All tools** work with both client types
- **Permission enforcement** works correctly

### 2. Performance Requirements

- **Authentication time** <500ms
- **Tool execution time** <2s average
- **Error rate** <1% of requests
- **Availability** 99.9% uptime

### 3. User Experience

- **Setup time** <5 minutes for new users
- **Error messages** clear and actionable
- **Documentation** complete and up-to-date
- **Support** responsive and helpful

## Implementation Checklist

### Phase 1: Core Service
- [ ] Create `UnifiedAuthService` class
- [ ] Implement JWT token processing
- [ ] Add AWS credential extraction
- [ ] Create tool authentication helpers
- [ ] Add unit tests for core service

### Phase 2: Tool Migration
- [ ] Migrate S3 bucket operations
- [ ] Migrate package operations
- [ ] Migrate Athena/Glue operations
- [ ] Migrate search operations
- [ ] Migrate permission operations
- [ ] Add integration tests

### Phase 3: Desktop Integration
- [ ] Implement desktop authentication service
- [ ] Add credential passing via MCP
- [ ] Update desktop client configs
- [ ] Add end-to-end tests

### Phase 4: Testing & Optimization
- [ ] Comprehensive testing suite
- [ ] Performance optimization
- [ ] Security validation
- [ ] Documentation updates
- [ ] Monitoring setup

## Conclusion

This specification provides a comprehensive implementation plan for unifying MCP authentication across web and desktop clients. The phased approach ensures minimal disruption while providing a clear path to a robust, secure, and performant solution.

**Next Steps**:
1. Review and approve this specification
2. Create implementation tickets for Phase 1
3. Set up development environment and testing infrastructure
4. Begin implementation of core unified authentication service
