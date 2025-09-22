<!-- markdownlint-disable MD013 -->
# Analysis - Isolate quilt3 Dependency

**GitHub Issue**: #155 "[isolate quilt3](https://github.com/quiltdata/quilt-mcp-server/issues/155)"
**Requirements Reference**: [01-requirements.md](./01-requirements.md)

## Current Architecture Analysis

### 1. Core Dependencies and Architecture

#### 1.1 Primary Dependency Structure

- **Entry Point**: `src/main.py` → `quilt_mcp.utils.run_server()`
- **Core Framework**: FastMCP server with 84+ registered tools
- **Critical Dependency**: `quilt3>=5.6.0` is deeply integrated throughout the codebase
- **Authentication Layer**: Relies on `quilt3.logged_in()` and `quilt3.get_boto3_session()`
- **Configuration**: Uses `quilt3.config()` for catalog discovery and setup

#### 1.2 Current Deployment Patterns

1. **Local Development Environment**:
   - Uses `quilt3 login` for authentication
   - Relies on local filesystem for configuration storage
   - Requires user interaction for browser-based auth flow

2. **DXT (Desktop Extension) Environment**:
   - Bundled deployment with `src/deploy/dxt_main.py`
   - Still depends on local quilt3 installation and auth
   - Bootstrap process in `src/deploy/bootstrap.py` installs quilt3

3. **Remote Stack Environment** (Target):
   - Currently **not implemented**
   - Would need to work without local filesystem access
   - Cannot use quilt3's interactive authentication mechanisms

### 2. quilt3 Integration Points

#### 2.1 Authentication and Session Management

**File**: `src/quilt_mcp/utils.py` (lines 179-228)

```python
def get_s3_client(use_quilt_auth: bool = True):
    if use_quilt_auth:
        if hasattr(quilt3, "logged_in") and quilt3.logged_in():
            if hasattr(quilt3, "get_boto3_session"):
                session = quilt3.get_boto3_session()
                return session.client("s3")
    return boto3.client("s3")  # Fallback
```

**Analysis**:

- Primary authentication pathway through quilt3
- Fallback to boto3 already exists but needs enhancement
- STS client follows identical pattern

#### 2.2 Catalog Configuration and Discovery

**File**: `src/quilt_mcp/tools/auth.py` (lines 52-84, 101-126)

```python
def _get_catalog_info() -> dict[str, Any]:
    logged_in_url = quilt3.logged_in()
    config = quilt3.config()
    # Extracts navigator_url, registry_url from config
```

**Analysis**:

- Catalog discovery entirely dependent on quilt3 configuration
- No alternative mechanism for remote stack environments
- Configuration stored in quilt3's local filesystem locations

#### 2.3 Package Operations

**File**: `src/quilt_mcp/tools/packages.py` (lines 27-54)

```python
def packages_list(registry: str = DEFAULT_REGISTRY, ...):
    with suppress_stdout():
        pkgs = list(quilt3.list_packages(registry=normalized_registry))
```

**Analysis**:

- Direct quilt3 API usage for package discovery
- Heavy integration in package search, browsing, creation operations
- Affects 15+ tool modules

#### 2.4 Stack Service Integration

**File**: `src/quilt_mcp/tools/stack_buckets.py` (lines 12-50)

```python
def get_stack_buckets() -> List[str]:
    stack_buckets = _get_stack_buckets_via_graphql()  # Uses quilt3 session
    # Fallback to permission discovery
```

**Analysis**:

- Stack discovery depends on quilt3 GraphQL session
- Indicates existing higher-performance stack services
- Fallback mechanisms already partially implemented

#### 2.5 GraphQL Service Access

**File**: `src/quilt_mcp/tools/graphql.py` (lines 15-34)

```python
def _get_graphql_endpoint():
    import quilt3
    session = quilt3.session.get_session()
    registry_url = quilt3.session.get_registry_url()
    graphql_url = urljoin(registry_url.rstrip("/") + "/", "graphql")
    return session, graphql_url
```

**Analysis**:

- GraphQL endpoint discovery and authenticated session from quilt3
- Critical for stack service access in enterprise deployments
- No alternative authentication mechanism for stack services

### 3. Current System Constraints and Limitations

#### 3.1 Authentication Constraints

1. **Local Filesystem Dependency**: quilt3 stores authentication tokens in `~/.config/quilt/`
2. **Interactive Authentication**: `quilt3 login` requires browser interaction
3. **Single Authentication Model**: No provision for service-to-service authentication
4. **Session Management**: No mechanism for long-lived service credentials

#### 3.2 Configuration Constraints

1. **Static Configuration**: quilt3 config stored locally, not environment-aware
2. **Catalog Discovery**: Hardcoded reliance on quilt3's navigator_url configuration
3. **Registry Detection**: No programmatic way to determine stack registry endpoints
4. **Environment Detection**: No mechanism to detect deployment context (local vs stack)

#### 3.3 Service Access Constraints

1. **GraphQL Authentication**: Only works with quilt3 authenticated sessions
2. **Stack Service Discovery**: Limited fallback mechanisms for service endpoint discovery
3. **Permission Management**: Tied to quilt3's AWS credential management
4. **Cross-Bucket Operations**: Depends on quilt3's stack bucket discovery

### 4. Current Codebase Patterns and Conventions

#### 4.1 Error Handling Patterns

- Extensive use of try/catch with graceful fallbacks
- Pattern: attempt quilt3 operation, fallback to boto3/AWS direct
- Standardized error response format via `format_error_response()`

#### 4.2 Tool Registration Architecture

- Auto-discovery of tool modules in `src/quilt_mcp/tools/`
- Function introspection for MCP tool registration
- Modular architecture with clear separation of concerns

#### 4.3 Authentication Abstraction

- Existing `use_quilt_auth` parameter in utility functions
- Client factory pattern for S3/STS clients
- Conditional import pattern for quilt3 dependencies

#### 4.4 Configuration Management

- Environment variable pattern via `os.getenv()` in constants
- Default values with environment overrides
- Static configuration for known test environments

### 5. Technical Debt and Refactoring Opportunities

#### 5.1 Existing Abstraction Violations

1. **Direct quilt3 Imports**: 72 files directly import and use quilt3 APIs
2. **Scattered Authentication Logic**: Authentication checks duplicated across modules
3. **Hard-coded Assumptions**: Catalog URLs and registry endpoints assumed to come from quilt3
4. **Missing Interfaces**: No abstraction layer between tools and backend services

#### 5.2 Code Quality Observations

1. **Good**: Existing fallback patterns show awareness of dependency issues
2. **Good**: Modular tool architecture supports selective enablement
3. **Challenge**: Deep integration makes clean separation difficult
4. **Challenge**: No current testing of quilt3-free operation modes

### 6. Gap Analysis: Current State vs Requirements

#### 6.1 Local Development Environment

✅ **Current State**: Fully functional with quilt3 authentication

- All 84+ tools working
- Complete package management capabilities
- Full search and discovery features

#### 6.2 Stack Deployment Environment

❌ **Current State**: Not supported

- **Gap 1**: No authentication mechanism for stack deployment
- **Gap 2**: No catalog configuration without quilt3
- **Gap 3**: No service endpoint discovery for stack services
- **Gap 4**: No environment detection mechanism
- **Gap 5**: No abstraction layer for backend service selection

#### 6.3 Consistent Interface Requirement

⚠️ **Current State**: Partially achievable

- **Achievable**: Same MCP tool interface can be maintained
- **Challenge**: Some tools may need feature degradation in stack mode
- **Challenge**: Different authentication models may require different capabilities

### 7. Architectural Challenges and Design Considerations

#### 7.1 Authentication Architecture Challenges

1. **Dual Authentication Models**: Local (quilt3) vs Stack (service credentials)
2. **Credential Management**: How to securely handle stack service credentials
3. **Session Lifecycle**: Different session patterns for local vs remote environments
4. **Permission Discovery**: How to determine capabilities without quilt3's introspection

#### 7.2 Service Discovery Challenges

1. **Endpoint Configuration**: How to discover stack service endpoints without quilt3
2. **Registry Detection**: How to determine package registries in stack environment
3. **Bucket Discovery**: How to find stack buckets without GraphQL session
4. **Catalog Configuration**: How to configure catalog access without quilt3.config()

#### 7.3 Feature Parity Challenges

1. **Search Capabilities**: Stack may have different/better search services
2. **Package Operations**: Different APIs for package management in stack
3. **Metadata Access**: Stack services may provide enhanced metadata
4. **Performance Trade-offs**: Stack services may be faster but have different capabilities

#### 7.4 Testing and Validation Challenges

1. **Environment Simulation**: How to test stack mode without actual stack deployment
2. **Authentication Testing**: How to test different auth modes safely
3. **Feature Coverage**: Ensuring all tools work in both environments
4. **Integration Testing**: Validating service discovery and endpoint resolution

### 8. Current Implementation Strengths

#### 8.1 Architectural Strengths

1. **Modular Design**: Tool modules can be selectively enabled/disabled
2. **Fallback Patterns**: Existing patterns for graceful degradation
3. **Abstraction Readiness**: Client factory functions already parameterized
4. **Error Handling**: Robust error handling with informative messages

#### 8.2 Code Quality Strengths

1. **Type Annotations**: Strong typing throughout codebase
2. **Documentation**: Comprehensive docstrings and tool descriptions
3. **Testing Framework**: Solid pytest foundation with AWS integration
4. **Dependency Management**: Clean dependency specification in pyproject.toml

### 9. Summary of Analysis Findings

#### 9.1 Core Challenge

The MCP server is **deeply integrated** with quilt3, with authentication, configuration, and service discovery all depending on quilt3's local filesystem and interactive authentication model. This makes stack deployment impossible without significant architectural changes.

#### 9.2 Key Architectural Decisions Needed

1. **Authentication Strategy**: How to handle dual authentication models
2. **Configuration Management**: How to manage catalog/stack configuration
3. **Service Abstraction**: How to abstract backend service access
4. **Environment Detection**: How to automatically detect deployment context
5. **Feature Compatibility**: Which features are available in each environment

#### 9.3 Implementation Complexity

- **High**: Deep integration requires careful refactoring across 70+ files
- **Medium**: Existing fallback patterns provide foundation for abstraction
- **Low**: Tool interface can remain unchanged with proper abstraction layer

The analysis reveals that while the challenge is significant due to deep quilt3 integration, the existing codebase has architectural patterns that can be leveraged for a clean separation. The key is creating proper abstraction layers while maintaining the existing tool interface contract.
