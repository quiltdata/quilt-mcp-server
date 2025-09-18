<!-- markdownlint-disable MD013 -->
# Specifications - Isolate quilt3 Dependency

**GitHub Issue**: #155 "[isolate quilt3](https://github.com/quiltdata/quilt-mcp-server/issues/155)"
**Requirements Reference**: [01-requirements.md](./01-requirements.md)
**Analysis Reference**: [02-analysis.md](./02-analysis.md)

## 1. System Architecture Goals

### 1.1 Dual Environment Support

The MCP server shall operate seamlessly in two distinct deployment environments:

1. **Local Development Environment**
   - Uses quilt3 authentication and configuration
   - Maintains full backward compatibility with existing workflows
   - Supports interactive authentication via `quilt3 login`

2. **Stack Deployment Environment**
   - Operates without quilt3 dependencies
   - Uses stack-native service authentication
   - Accesses enhanced stack services directly

### 1.2 Abstraction Layer Architecture

Create a service abstraction layer that isolates quilt3 knowledge from MCP tools:

1. **Service Interface Layer**: MCP tools interact only with well-defined service interfaces
2. **Implementation Layer**: Backend implementations handle quilt3 vs stack service decisions
3. **Configuration Layer**: Environment-aware configuration management
4. **Authentication Layer**: Dual authentication pathway management

### 1.3 Consistent Tool Interface

All 84+ MCP tools shall maintain identical interfaces and behavior patterns across both environments, with feature parity where technically feasible.

## 2. Service Abstraction Specifications

### 2.1 AWS Client Service Interface

**Purpose**: Provide authenticated AWS clients for S3 and STS operations

**Interface Contract**:

```python
def get_s3_client(use_quilt_auth: bool = True) -> S3Client
def get_sts_client(use_quilt_auth: bool = True) -> STSClient
```

**Behavior Specifications**:

1. **Local Environment**: Use quilt3 session-based authentication when available
2. **Stack Environment**: Use environment-provided credentials (IAM roles, service accounts)
3. **Fallback Strategy**: Gracefully degrade to boto3 default credential chain
4. **Error Handling**: Provide actionable error messages for authentication failures

### 2.2 Catalog Information Service Interface

**Purpose**: Provide catalog configuration and discovery capabilities

**Interface Contract**:

```python
def get_catalog_info() -> dict[str, Any]
def get_registry_url() -> str
def get_navigator_url() -> str
```

**Behavior Specifications**:

1. **Local Environment**: Extract configuration from quilt3.config()
2. **Stack Environment**: Use environment variables or stack service discovery
3. **Configuration Keys**: `navigator_url`, `registry_url`, `default_bucket`
4. **Validation**: Ensure returned URLs are accessible and valid

### 2.3 GraphQL Service Interface

**Purpose**: Provide authenticated access to Quilt catalog GraphQL endpoints

**Interface Contract**:

```python
def get_graphql_session() -> Tuple[Session, str]
def execute_graphql_query(query: str, variables: dict) -> dict
```

**Behavior Specifications**:

1. **Local Environment**: Use quilt3 authenticated session and endpoint discovery
2. **Stack Environment**: Use stack service authentication and direct endpoint access
3. **Session Management**: Handle session lifecycle and token refresh
4. **Error Handling**: Provide specific error messages for authentication and network issues

### 2.4 Package Operations Service Interface

**Purpose**: Provide package management capabilities across both environments

**Interface Contract**:

```python
def list_packages(registry: str) -> Iterator[PackageInfo]
def get_package_info(package_name: str, registry: str) -> PackageInfo
def create_package(package_name: str, **kwargs) -> PackageResult
```

**Behavior Specifications**:

1. **Local Environment**: Use quilt3 package APIs directly
2. **Stack Environment**: Use stack package management APIs
3. **Performance**: Stack environment should leverage enhanced stack performance
4. **Feature Parity**: Maintain consistent package operation results

## 3. Environment Detection and Configuration

### 3.1 Environment Detection Strategy

**Automatic Detection Criteria**:

1. **Stack Environment Indicators**:
   - Presence of stack-specific environment variables
   - Availability of stack service endpoints
   - IAM role-based authentication context

2. **Local Environment Indicators**:
   - Presence of quilt3 configuration files
   - Valid quilt3 authentication state
   - Local filesystem access patterns

### 3.2 Configuration Management

**Configuration Sources (Priority Order)**:

1. **Environment Variables**: Override all other sources
2. **Stack Service Discovery**: For stack deployments
3. **quilt3 Configuration**: For local environments
4. **Default Values**: Fallback configuration

**Required Configuration Parameters**:

- `QUILT_CATALOG_URL`: Catalog base URL
- `QUILT_REGISTRY_URL`: Package registry URL
- `QUILT_GRAPHQL_ENDPOINT`: GraphQL service endpoint
- `QUILT_DEFAULT_BUCKET`: Default S3 bucket for operations

## 4. Authentication Architecture

### 4.1 Dual Authentication Pathways

**Local Authentication Pathway**:

- Uses quilt3.logged_in() for authentication state
- Leverages quilt3.get_boto3_session() for AWS credentials
- Maintains compatibility with existing `quilt3 login` workflows

**Stack Authentication Pathway**:

- Uses IAM roles or service account credentials
- Accesses stack services with service-to-service authentication
- No dependency on local filesystem or interactive authentication

### 4.2 Authentication State Management

**Authentication Validation**:

- Verify authentication state before critical operations
- Provide clear authentication status reporting
- Handle authentication refresh and expiration

**Error Handling**:

- Distinguish between authentication and authorization failures
- Provide actionable guidance for authentication setup
- Support graceful degradation when authentication is partial

## 5. Integration Points and API Contracts

### 5.1 Tool Integration Requirements

**MCP Tool Modifications**:

1. Tools shall use service interface functions exclusively
2. No direct quilt3 imports permitted in tool modules
3. All AWS operations shall use abstracted client functions
4. Configuration access shall use abstracted configuration functions

**Backward Compatibility**:

1. Existing tool function signatures remain unchanged
2. Tool behavior remains consistent across environments
3. Error messages maintain existing format and detail level

### 5.2 Service Discovery Integration

**Stack Service Discovery**:

- Automatic discovery of available stack services
- Dynamic endpoint configuration based on environment
- Health checking and failover capabilities

**Local Service Integration**:

- Seamless integration with existing quilt3 workflows
- Preservation of local development capabilities
- Support for offline development scenarios

## 6. Quality Gates and Validation Criteria

### 6.1 Functional Validation Gates

**Environment Compatibility**:

1. All tools function correctly in local environment (existing behavior)
2. All tools function correctly in stack environment (new requirement)
3. Authentication works correctly in both environments
4. Configuration discovery works correctly in both environments

**Feature Parity Validation**:

1. Core package operations maintain identical results
2. Search functionality provides equivalent capabilities
3. Metadata access maintains consistency
4. Performance meets or exceeds current benchmarks

### 6.2 Integration Validation Gates

**Authentication Integration**:

1. Local authentication maintains existing workflows
2. Stack authentication integrates with IAM/service accounts
3. Authentication failures provide actionable error messages
4. Authentication state is correctly reported across all tools

**Configuration Integration**:

1. Environment detection works automatically
2. Configuration override via environment variables
3. Fallback configuration provides reasonable defaults
4. Configuration validation prevents runtime errors

### 6.3 Quality Assurance Gates

**Code Quality Standards**:

1. Zero direct quilt3 imports in tool modules
2. All service interfaces properly abstracted
3. Comprehensive error handling in abstraction layer
4. Type safety maintained across all interfaces

**Testing Coverage Requirements**:

1. Unit tests for all service interface implementations
2. Integration tests for both environment scenarios
3. End-to-end tests for critical user workflows
4. Performance benchmarks for both environments

## 7. Success Criteria and Measurable Outcomes

### 7.1 Primary Success Metrics

**Deployment Capability**:

1. MCP server successfully deploys in stack environment without quilt3
2. All 84+ tools remain functional in stack deployment
3. Authentication works seamlessly in both environments
4. Configuration discovery works without manual intervention

**Performance Criteria**:

1. Local environment performance matches or exceeds current performance
2. Stack environment leverages enhanced stack service performance
3. Authentication latency remains within acceptable bounds
4. Memory usage remains within current resource constraints

### 7.2 User Experience Metrics

**Developer Experience**:

1. Local development workflow remains unchanged
2. Tool behavior is consistent across environments
3. Error messages provide clear guidance for environment-specific issues
4. Documentation clearly explains environment differences

**Operations Experience**:

1. Stack deployment requires no additional configuration steps
2. Authentication setup is automated for stack environment
3. Monitoring and logging provide environment-specific visibility
4. Troubleshooting procedures work for both environments

## 8. Architectural Constraints and Design Principles

### 8.1 Design Principles

**Separation of Concerns**:

1. Tools focus on business logic, not infrastructure concerns
2. Service interfaces abstract environment-specific implementation
3. Configuration management is centralized and environment-aware
4. Authentication is abstracted from service access patterns

**Graceful Degradation**:

1. Fallback mechanisms for all critical operations
2. Progressive enhancement based on available capabilities
3. Clear communication of reduced functionality when applicable
4. No silent failures or undefined behavior states

### 8.2 Implementation Constraints

**Compatibility Requirements**:

1. Maintain backward compatibility with existing local workflows
2. Preserve existing tool interfaces and behavior patterns
3. Support incremental rollout and testing strategies
4. Enable environment-specific feature toggles when necessary

**Dependency Management**:

1. quilt3 remains optional dependency for stack deployments
2. Core functionality available without quilt3 installation
3. Clear dependency boundaries between environments
4. Minimal additional dependencies for abstraction layer

## 9. Technical Uncertainties and Risk Assessment

### 9.1 Authentication Integration Risks

**Risk**: Stack service authentication complexity

- **Impact**: High - Authentication failures break all functionality
- **Mitigation**: Comprehensive testing with actual stack service accounts

**Risk**: Session management differences between environments

- **Impact**: Medium - May cause intermittent authentication failures
- **Mitigation**: Robust session lifecycle management and error handling

### 9.2 Performance and Compatibility Risks

**Risk**: Stack service API differences from quilt3 APIs

- **Impact**: High - Could break tool functionality or degrade performance
- **Mitigation**: Careful API mapping and comprehensive integration testing

**Risk**: Configuration discovery failures in stack environment

- **Impact**: Medium - Tools may not find required services or endpoints
- **Mitigation**: Multiple discovery mechanisms with comprehensive fallbacks

### 9.3 Implementation Complexity Risks

**Risk**: Deep quilt3 integration requires extensive refactoring

- **Impact**: High - Risk of introducing regressions in local environment
- **Mitigation**: Incremental implementation with comprehensive test coverage

**Risk**: Environment detection may be unreliable

- **Impact**: Medium - Wrong environment assumptions could cause failures
- **Mitigation**: Multiple detection criteria with explicit override capabilities

## 10. Validation and Testing Strategy

### 10.1 Environment Simulation Strategy

**Local Environment Testing**:

1. Maintain existing test suite for local environment functionality
2. Add tests for new abstraction layer with quilt3 backend
3. Verify backward compatibility with existing authentication flows
4. Performance regression testing for abstraction overhead

**Stack Environment Testing**:

1. Mock stack service implementations for unit testing
2. Integration testing with actual stack service endpoints
3. Authentication testing with service account credentials
4. End-to-end workflow testing in simulated stack environment

### 10.2 Quality Assurance Process

**Code Review Requirements**:

1. All changes reviewed for proper abstraction boundaries
2. No direct quilt3 usage permitted in tool modules
3. Error handling patterns consistently applied
4. Documentation updated for environment-specific behavior

**Integration Testing Protocol**:

1. Both environments tested for each tool modification
2. Authentication scenarios tested across both environments
3. Configuration discovery tested with various environment setups
4. Performance benchmarking for both environments maintained

This specification defines the desired end state architecture that enables the MCP server to operate in both local development and stack deployment environments while maintaining consistent tool interfaces and behavior patterns. The success of this architecture depends on proper abstraction of quilt3 dependencies behind well-defined service interfaces that can be implemented differently for each environment.
