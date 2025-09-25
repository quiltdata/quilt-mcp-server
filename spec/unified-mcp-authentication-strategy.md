# Unified MCP Authentication Strategy

## Executive Summary

This document outlines a comprehensive strategy for unifying authentication across Quilt's MCP server to support both web clients (browser-based) and desktop clients (Claude Desktop, Cursor, VS Code) using a single remote AWS-hosted MCP server. The strategy addresses current authentication failures and provides a clear implementation plan.

## Current State Analysis

### Authentication Methods Currently Implemented

1. **Web Clients (Browser)**
   - **Method**: JWT Bearer Token Authentication
   - **Flow**: Frontend → Authorization Header → MCP Server → JWT Validation → AWS Operations
   - **Status**: Partially working, some tools fail authentication
   - **Issues**: Inconsistent JWT claim processing, permission mapping gaps

2. **Desktop Clients (Claude, Cursor, VS Code)**
   - **Method**: Quilt3 OAuth2 + AWS Role Assumption
   - **Flow**: Desktop → quilt3 login → MCP Server → AWS Role Assumption → AWS Operations
   - **Status**: Working for local development, inconsistent for remote server
   - **Issues**: Role assumption not working reliably with remote server

3. **Hybrid/ECS Deployment**
   - **Method**: IAM Task Role + Header-based Role Switching
   - **Flow**: Headers → Role Assumption → AWS Operations
   - **Status**: Working in production
   - **Issues**: Not accessible to desktop clients

## Tool Categories & Authentication Requirements

### 1. S3 Bucket Operations
**Tools**: `bucket_objects_list`, `bucket_object_info`, `bucket_object_text`, `bucket_object_fetch`, `bucket_objects_put`, `bucket_object_link`

**Authentication Requirements**:
- **Web**: JWT with S3 permissions (`s3:ListBucket`, `s3:GetObject`, `s3:PutObject`)
- **Desktop**: AWS credentials with S3 permissions
- **Unified**: Both should use same AWS credentials/role

### 2. Package Operations
**Tools**: `package_create`, `package_update`, `package_delete`, `package_browse`, `package_contents_search`, `package_diff`, `create_package_enhanced`

**Authentication Requirements**:
- **Web**: JWT with package-level permissions
- **Desktop**: AWS credentials + Quilt registry access
- **Unified**: AWS credentials + Quilt API access

### 3. Athena/Glue Operations
**Tools**: `athena_query_execute`, `athena_databases_list`, `athena_tables_list`, `athena_table_schema`, `athena_workgroups_list`, `athena_query_history`

**Authentication Requirements**:
- **Web**: JWT with Athena/Glue permissions
- **Desktop**: AWS credentials with Athena/Glue permissions
- **Unified**: AWS credentials with proper IAM policies

### 4. Search Operations
**Tools**: `unified_search`, `packages_search`

**Authentication Requirements**:
- **Web**: JWT with search permissions
- **Desktop**: Quilt API access
- **Unified**: Quilt API access (no AWS required)

### 5. Permission Operations
**Tools**: `aws_permissions_discover`, `bucket_access_check`, `bucket_recommendations_get`

**Authentication Requirements**:
- **Web**: JWT with permission discovery access
- **Desktop**: AWS credentials with IAM read permissions
- **Unified**: AWS credentials with IAM read permissions

## Proposed Unified Authentication Strategy

### Core Principle: AWS Credentials as Single Source of Truth

Instead of maintaining separate authentication paths, all tools should use AWS credentials as the primary authentication method, with JWT tokens serving as a credential source for AWS operations.

### 1. Authentication Flow Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Client    │    │  Desktop Client │    │   MCP Server    │
│   (Browser)     │    │ (Claude/Cursor) │    │   (AWS ECS)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │ JWT Token             │ quilt3 login          │
         │ (Authorization)       │ (OAuth2)              │
         ▼                       ▼                       │
┌─────────────────┐    ┌─────────────────┐               │
│  Quilt Frontend │    │  Quilt Desktop  │               │
│  (JWT Issuer)   │    │  (AWS Creds)    │               │
└─────────────────┘    └─────────────────┘               │
         │                       │                       │
         │ Extract AWS Role      │ Direct AWS Creds      │
         ▼                       ▼                       │
┌─────────────────┐    ┌─────────────────┐               │
│  AWS Role ARN   │    │  AWS Credentials│               │
│  (from JWT)     │    │  (from quilt3)  │               │
└─────────────────┘    └─────────────────┘               │
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼
                    ┌─────────────────┐
                    │  AWS Operations │
                    │  (S3, Athena,   │
                    │   Glue, IAM)    │
                    └─────────────────┘
```

### 2. Unified Authentication Service

Create a single `UnifiedAuthService` that:

1. **Detects client type** (web vs desktop) from request context
2. **Extracts AWS credentials** from either JWT or quilt3 session
3. **Creates boto3 sessions** with appropriate credentials
4. **Provides consistent interface** to all tools

### 3. JWT Token Enhancement

Enhance JWT tokens to include:
- **AWS Role ARN**: Primary role for AWS operations
- **AWS Credentials**: Temporary credentials (if available)
- **Permission Mapping**: Direct mapping to AWS permissions
- **Client Type**: Web vs desktop indicator

### 4. Desktop Client Integration

Modify desktop clients to:
- **Use remote MCP server** instead of local
- **Pass quilt3 credentials** via MCP protocol
- **Support credential refresh** for long-running sessions

## Implementation Plan

### Phase 1: JWT Token Enhancement (Week 1)

**Objective**: Enhance JWT tokens to include AWS role information

**Tasks**:
1. **Modify Quilt Frontend** to include AWS role ARN in JWT tokens
2. **Update JWT validation** in MCP server to extract role information
3. **Implement role assumption** from JWT tokens
4. **Test web client authentication** with enhanced tokens

**Deliverables**:
- Enhanced JWT token structure
- Updated bearer auth service
- Working web client authentication

### Phase 2: Unified Authentication Service (Week 2)

**Objective**: Create single authentication service for all client types

**Tasks**:
1. **Create UnifiedAuthService** class
2. **Implement client type detection** (web vs desktop)
3. **Implement credential extraction** from multiple sources
4. **Create boto3 session factory** with proper credentials
5. **Update all tools** to use unified service

**Deliverables**:
- UnifiedAuthService implementation
- Updated tool authentication patterns
- Consistent AWS credential handling

### Phase 3: Desktop Client Integration (Week 3)

**Objective**: Enable desktop clients to use remote MCP server

**Tasks**:
1. **Modify MCP server** to accept quilt3 credentials
2. **Implement credential passing** via MCP protocol
3. **Add credential refresh** mechanism
4. **Update desktop client configuration** for remote server
5. **Test desktop client authentication**

**Deliverables**:
- Remote MCP server support for desktop clients
- Updated desktop client configurations
- Working desktop client authentication

### Phase 4: Tool-Specific Authentication (Week 4)

**Objective**: Implement tool-specific authentication patterns

**Tasks**:
1. **Categorize tools** by authentication requirements
2. **Implement permission mapping** for each category
3. **Add tool-specific validation** logic
4. **Create authentication helpers** for common patterns
5. **Test all tool categories** with both client types

**Deliverables**:
- Tool-specific authentication patterns
- Permission mapping system
- Comprehensive test coverage

## Technical Implementation Details

### 1. Unified Authentication Service

```python
class UnifiedAuthService:
    """Unified authentication service for all MCP client types."""
    
    def __init__(self):
        self.client_type = None
        self.aws_credentials = None
        self.quilt_api_token = None
        
    def authenticate_request(self, request_context: dict) -> AuthResult:
        """Authenticate request from any client type."""
        client_type = self._detect_client_type(request_context)
        
        if client_type == "web":
            return self._authenticate_web_client(request_context)
        elif client_type == "desktop":
            return self._authenticate_desktop_client(request_context)
        else:
            return self._authenticate_hybrid_client(request_context)
    
    def get_aws_session(self, service: str) -> boto3.Session:
        """Get boto3 session for AWS service."""
        return boto3.Session(
            aws_access_key_id=self.aws_credentials.access_key,
            aws_secret_access_key=self.aws_credentials.secret_key,
            aws_session_token=self.aws_credentials.session_token,
            region_name=self.aws_credentials.region
        ).client(service)
    
    def get_quilt_api_client(self) -> QuiltAPIClient:
        """Get Quilt API client with proper authentication."""
        return QuiltAPIClient(token=self.quilt_api_token)
```

### 2. Enhanced JWT Token Structure

```json
{
  "sub": "user123",
  "exp": 1640995200,
  "iat": 1640908800,
  "permissions": ["s3:ListBucket", "s3:GetObject"],
  "buckets": ["quilt-sandbox-bucket", "quilt-sales-prod"],
  "roles": ["ReadWriteQuiltV2-sales-prod"],
  "aws_role_arn": "arn:aws:iam::123456789012:role/ReadWriteQuiltV2-sales-prod",
  "aws_credentials": {
    "access_key_id": "AKIA...",
    "secret_access_key": "...",
    "session_token": "...",
    "expiration": "2023-12-31T23:59:59Z"
  },
  "client_type": "web",
  "scope": "mcp:read mcp:write"
}
```

### 3. Tool Authentication Pattern

```python
def _check_unified_authorization(tool_name: str, tool_args: dict) -> dict:
    """Unified authorization check for all tools."""
    try:
        # Get unified auth service
        auth_service = get_unified_auth_service()
        
        # Authenticate request
        auth_result = auth_service.authenticate_request(get_request_context())
        
        if not auth_result.success:
            return {"authorized": False, "error": auth_result.error}
        
        # Check tool-specific permissions
        if not auth_service.authorize_tool(tool_name, tool_args, auth_result):
            return {"authorized": False, "error": f"Tool {tool_name} not authorized"}
        
        # Return success with user info
        return {
            "authorized": True,
            "user_info": auth_result.user_info,
            "aws_session": auth_service.get_aws_session,
            "quilt_api": auth_service.get_quilt_api_client
        }
        
    except Exception as e:
        logger.error("Unified authorization failed: %s", e)
        return {"authorized": False, "error": f"Authorization failed: {str(e)}"}
```

## Security Considerations

### 1. Credential Management
- **JWT tokens** should have short expiration times (1 hour)
- **AWS credentials** should be refreshed automatically
- **Session tokens** should be rotated regularly
- **Credential storage** should be encrypted at rest

### 2. Permission Validation
- **Principle of least privilege** - users get only what they need
- **Tool-level permissions** - each tool has specific requirements
- **Bucket-level access** - users can only access authorized buckets
- **Audit logging** - all authentication events are logged

### 3. Network Security
- **HTTPS only** - all communication encrypted
- **CORS configuration** - proper origin restrictions
- **Rate limiting** - prevent abuse
- **Request validation** - validate all inputs

## Testing Strategy

### 1. Unit Tests
- **Authentication service** methods
- **JWT token** parsing and validation
- **Permission mapping** logic
- **Tool authorization** checks

### 2. Integration Tests
- **Web client** authentication flow
- **Desktop client** authentication flow
- **AWS service** integration
- **Quilt API** integration

### 3. End-to-End Tests
- **Complete user workflows** with both client types
- **Permission enforcement** across all tools
- **Error handling** and recovery
- **Performance** under load

## Success Metrics

### 1. Authentication Success Rate
- **Web clients**: >95% successful authentication
- **Desktop clients**: >95% successful authentication
- **Tool access**: >90% successful tool execution

### 2. Performance Metrics
- **Authentication time**: <500ms
- **Tool execution time**: <2s average
- **Error rate**: <1% of requests

### 3. User Experience
- **Setup time**: <5 minutes for new users
- **Error messages**: Clear and actionable
- **Documentation**: Complete and up-to-date

## Migration Strategy

### 1. Backward Compatibility
- **Existing clients** continue to work
- **Gradual migration** to new authentication
- **Feature flags** for new functionality
- **Rollback capability** if issues arise

### 2. Rollout Plan
- **Phase 1**: Internal testing with enhanced JWT
- **Phase 2**: Beta testing with select users
- **Phase 3**: Gradual rollout to all users
- **Phase 4**: Full migration and cleanup

### 3. Monitoring and Alerting
- **Authentication failures** monitored
- **Performance metrics** tracked
- **Error rates** alerted
- **User feedback** collected

## Conclusion

This unified authentication strategy provides a clear path forward for supporting both web and desktop MCP clients with a single remote server. By using AWS credentials as the single source of truth and implementing a unified authentication service, we can eliminate the current authentication inconsistencies while maintaining security and performance.

The phased implementation approach ensures minimal disruption to existing users while providing a clear migration path to the new system. The comprehensive testing strategy and monitoring plan ensure the solution is robust and reliable.

**Next Steps**:
1. Review and approve this strategy document
2. Begin Phase 1 implementation (JWT token enhancement)
3. Set up monitoring and testing infrastructure
4. Create detailed implementation tickets for each phase
