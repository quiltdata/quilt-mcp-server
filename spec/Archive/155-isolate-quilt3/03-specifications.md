<!-- markdownlint-disable MD013 -->
# Specifications - Isolate quilt3 Dependency

**GitHub Issue**: #155 "[isolate quilt3](https://github.com/quiltdata/quilt-mcp-server/issues/155)"
**Requirements Reference**: [01-requirements.md](./01-requirements.md)
**Analysis Reference**: [02-analysis.md](./02-analysis.md)

## 1. System Architecture Goals

### 1.1 Simplified Abstraction Layer

Create a single, centralized abstraction layer that isolates all quilt3 API usage:

1. **Centralized quilt3 Access**: All quilt3 imports and API calls consolidated into one abstraction module
2. **Single Service Interface**: One unified interface that handles all quilt3 operations
3. **Tool Isolation**: MCP tools interact only with the abstraction layer, never directly with quilt3
4. **Future-Ready Design**: Architecture prepared for eventual backend swapping without additional complexity

### 1.2 Current Implementation Strategy

#### Phase 1: Centralization (This Specification)

- Consolidate all quilt3 usage behind a single abstraction layer
- Remove direct quilt3 imports from all MCP tools
- Maintain identical functionality and interfaces

#### Future Phases: Backend Flexibility

- The centralized abstraction enables future backend implementations
- Potential for stack-native services or alternative implementations
- Foundation for deployment environment flexibility

### 1.3 Design Principles

1. **Single Point of Control**: All quilt3 operations flow through one abstraction layer
2. **Zero Direct Dependencies**: MCP tools have no direct quilt3 imports or API calls
3. **Transparent Operation**: Tools function identically, abstraction is invisible to users
4. **Maintainable Architecture**: Clear separation of concerns for future evolution

## 2. Centralized Abstraction Layer Specification

### 2.1 QuiltService - Single Abstraction Interface

**Purpose**: Centralize all quilt3 API access behind a unified interface

**Core Interface**:

```python
class QuiltService:
    """Centralized abstraction for all quilt3 operations"""

    # Authentication & Configuration
    def get_auth_status(self) -> dict[str, Any]
    def get_catalog_info(self) -> dict[str, Any]
    def get_registry_url(self) -> str
    def get_navigator_url(self) -> str

    # AWS Client Access
    def get_s3_client(self) -> S3Client
    def get_sts_client(self) -> STSClient

    # GraphQL Operations
    def execute_graphql_query(self, query: str, variables: dict) -> dict

    # Package Operations
    def list_packages(self, registry: str) -> Iterator[PackageInfo]
    def get_package(self, package_name: str, registry: str) -> Package
    def create_package(self, package_name: str, **kwargs) -> PackageResult

    # S3 Operations
    def list_bucket_objects(self, bucket: str, **kwargs) -> dict
    def get_object_info(self, s3_uri: str) -> dict
    def fetch_object_data(self, s3_uri: str, **kwargs) -> bytes

    # Search Operations
    def search_packages(self, query: str, **kwargs) -> dict
    def search_bucket_objects(self, bucket: str, query: str, **kwargs) -> dict
```

### 2.2 Implementation Strategy

**Single Module Design**:

- All quilt3 imports contained in `quilt_mcp/services/quilt_service.py`
- One class (`QuiltService`) handles all quilt3 operations
- All MCP tools import and use only this service class

**Current Implementation Approach**:

- Use quilt3 APIs directly within the service implementation
- Maintain all existing functionality and behavior
- Preserve error handling and authentication patterns
- No environment detection or backend switching in initial implementation

## 3. Service Integration Requirements

### 3.1 Tool Integration Pattern

**Migration Strategy**:

1. Replace direct quilt3 imports with `QuiltService` imports
2. Replace quilt3 API calls with equivalent service method calls
3. Maintain identical tool interfaces and behavior

**Example Migration Pattern**:

```python
# Before: Direct quilt3 usage
import quilt3
session, endpoint = quilt3.get_api_session()

# After: Service abstraction
from quilt_mcp.services.quilt_service import QuiltService
service = QuiltService()
session, endpoint = service.get_graphql_session()
```

### 3.2 Configuration Access

**Simplified Configuration**:

- Service handles all quilt3 configuration access internally
- Tools access configuration through service methods only
- No direct quilt3.config() calls in tool modules

**Configuration Methods**:

- `service.get_catalog_info()` - replaces `quilt3.config()`
- `service.get_registry_url()` - centralized registry access
- `service.get_navigator_url()` - centralized navigator access

## 4. Quality Gates and Success Criteria

### 4.1 Implementation Requirements

**Zero Direct quilt3 Usage**:

1. No direct quilt3 imports in any MCP tool module
2. All quilt3 operations flow through `QuiltService` only
3. Service module is the single point of quilt3 dependency

**Functional Equivalence**:

1. All existing tool functionality preserved exactly
2. Error handling patterns maintained
3. Performance characteristics preserved
4. Tool interfaces remain unchanged

### 4.2 Validation Criteria

**Code Quality Gates**:

- Static analysis confirms no quilt3 imports in tool modules
- All tool tests pass without modification
- Service module provides complete API coverage
- Type safety maintained across all interfaces

**Integration Testing**:

- All 84+ MCP tools function identically through service layer
- Authentication workflows preserved
- Configuration access patterns maintained
- Error scenarios handled consistently

## 5. Implementation Phases

### 5.1 Phase 1: Create QuiltService (Current)

**Deliverables**:

1. Implement `QuiltService` class with complete API coverage
2. Migrate core authentication and configuration tools
3. Establish testing patterns for service layer
4. Document migration patterns for remaining tools

**Success Criteria**:

- `QuiltService` handles all identified quilt3 operations
- Core tools (auth, config) successfully migrated
- All existing functionality preserved
- Test coverage maintained at 100%

### 5.2 Phase 2: Migrate All Tools

**Deliverables**:

1. Migrate all 84+ MCP tools to use `QuiltService`
2. Remove all direct quilt3 imports from tool modules
3. Validate functional equivalence across all tools
4. Update documentation and examples

**Success Criteria**:

- Zero direct quilt3 imports in tool modules
- All tools pass existing test suites
- Performance benchmarks maintained
- Complete API migration documented

### 5.3 Future Phases: Backend Flexibility

**Potential Enhancements** (Not in Current Scope):

- Environment detection and backend switching
- Stack-native service implementations
- Performance optimization for deployment environments
- Enhanced error handling for different backends

## 6. Architecture Benefits

### 6.1 Immediate Benefits

**Simplified Maintenance**:

- Single point of quilt3 dependency management
- Centralized error handling and authentication patterns
- Easier debugging and troubleshooting
- Consistent API usage patterns across all tools

**Future Flexibility**:

- Foundation for backend swapping without tool changes
- Enables deployment environment optimization
- Supports gradual migration to alternative implementations
- Clean separation of concerns for easier testing

### 6.2 Long-term Strategic Value

**Deployment Options**:

- Preparation for stack environments without quilt3 dependency
- Foundation for performance-optimized backends
- Support for different authentication mechanisms
- Enables environment-specific feature optimization

**Development Efficiency**:

- Standardized patterns reduce implementation complexity
- Centralized quilt3 expertise in service layer
- Simplified onboarding for new developers
- Consistent error handling across all operations

This simplified specification focuses on the immediate goal of centralizing quilt3 access behind a single abstraction layer. This approach provides the foundation for future backend flexibility while maintaining all current functionality and significantly simplifying the migration effort.
