# QuiltOps Architecture Documentation

## Overview

The QuiltOps abstraction layer represents a fundamental architectural shift from backend-specific operations to domain-driven operations. This design enables the Quilt MCP server to support multiple backends (quilt3 library, Platform GraphQL) while providing a unified interface for MCP tools.

## Architectural Principles

### 1. Domain-Driven Design
The architecture centers around Quilt domain concepts (packages, content, buckets) rather than backend-specific implementations.

### 2. Backend Abstraction
MCP tools interact with the QuiltOps interface, remaining completely isolated from backend implementation details.

### 3. Pluggable Backends
New backends can be added without changing the interface consumed by MCP tools.

### 4. Consistent Error Handling
All backends provide consistent error handling with domain-appropriate error messages.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        MCP Tools Layer                          │
├─────────────────────────────────────────────────────────────────┤
│  packages_list  │  package_browse  │  bucket_objects_list  │ ... │
└─────────────────┴──────────────────┴───────────────────────┴─────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    QuiltOps Interface                           │
├─────────────────────────────────────────────────────────────────┤
│  • search_packages()     • browse_content()                     │
│  • get_package_info()    • list_buckets()                       │
│  • get_content_url()                                            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   QuiltOpsFactory                               │
├─────────────────────────────────────────────────────────────────┤
│  Authentication Detection & Backend Selection                   │
│  • Detects quilt3 sessions                                      │
│  • Creates appropriate backend instance                         │
│  • Provides error handling for auth failures                    │
└─────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                ▼                               ▼
┌─────────────────────────┐         ┌─────────────────────────┐
│    Quilt3_Backend       │         │   Platform_Backend      │
│                         │         │     (Phase 2)           │
├─────────────────────────┤         ├─────────────────────────┤
│ • Uses quilt3 library   │         │ • Uses GraphQL API      │
│ • Session-based auth    │         │ • JWT token auth        │
│ • Direct S3 access      │         │ • Platform API access   │
└─────────────────────────┘         └─────────────────────────┘
                │                               │
                ▼                               ▼
┌─────────────────────────┐         ┌─────────────────────────┐
│     quilt3 Library      │         │  Platform GraphQL API  │
└─────────────────────────┘         └─────────────────────────┘
```

## Component Details

### MCP Tools Layer

**Responsibility:** Provide MCP tool implementations for client applications

**Key Characteristics:**
- Backend-agnostic implementations
- Work with domain objects only
- Use QuiltOpsFactory for backend access
- Handle domain exceptions appropriately

**Example Tool Structure:**
```python
def package_search_tool(query: str, registry: str):
    """MCP tool for package searching."""
    try:
        quilt_ops = QuiltOpsFactory.create()
        packages = quilt_ops.search_packages(query, registry)
        
        # Convert domain objects to MCP response format
        return {
            'packages': [asdict(pkg) for pkg in packages],
            'count': len(packages)
        }
    except AuthenticationError as e:
        return {'error': str(e), 'type': 'authentication'}
    except BackendError as e:
        return {'error': str(e), 'type': 'backend', 'context': e.context}
```

### QuiltOps Interface

**Responsibility:** Define domain-driven operations for Quilt functionality

**Key Characteristics:**
- Abstract base class with well-defined interface
- Domain-focused method signatures
- Consistent return types (domain objects)
- Comprehensive error handling specifications

**Interface Design:**
```python
class QuiltOps(ABC):
    @abstractmethod
    def search_packages(self, query: str, registry: str) -> List[Package_Info]:
        """Domain operation: search for packages"""
        pass
    
    @abstractmethod
    def get_package_info(self, package_name: str, registry: str) -> Package_Info:
        """Domain operation: get package details"""
        pass
    
    # ... other domain operations
```

### QuiltOpsFactory

**Responsibility:** Authentication detection and backend selection

**Key Characteristics:**
- Single entry point for QuiltOps creation
- Automatic authentication detection
- Backend selection based on available credentials
- Clear error messages for authentication failures

**Phase 1 Implementation:**
```python
class QuiltOpsFactory:
    @staticmethod
    def create() -> QuiltOps:
        # Phase 1: Only quilt3 session detection
        session_info = QuiltOpsFactory._detect_quilt3_session()
        if session_info:
            return Quilt3_Backend(session_info)
        
        raise AuthenticationError("No valid authentication found...")
```

**Phase 2 Implementation (Future):**
```python
class QuiltOpsFactory:
    @staticmethod
    def create() -> QuiltOps:
        # Priority 1: JWT authentication
        jwt_token = os.getenv("QUILT_JWT_TOKEN")
        if jwt_token:
            return Platform_Backend(jwt_token)
        
        # Priority 2: Quilt3 session
        session_info = QuiltOpsFactory._detect_quilt3_session()
        if session_info:
            return Quilt3_Backend(session_info)
        
        raise AuthenticationError("No valid authentication found...")
```

### Backend Implementations

#### Quilt3_Backend

**Responsibility:** Implement QuiltOps using quilt3 library

**Key Characteristics:**
- Direct integration with quilt3 Python library
- Session-based authentication
- Transformation from quilt3 objects to domain objects
- Comprehensive error handling with backend context

**Implementation Pattern:**
```python
class Quilt3_Backend(QuiltOps):
    def search_packages(self, query: str, registry: str) -> List[Package_Info]:
        try:
            # Use quilt3 library
            packages = quilt3.search(query, registry=registry)
            
            # Transform to domain objects
            return [self._transform_package(pkg) for pkg in packages]
            
        except Exception as e:
            # Transform to domain error
            raise BackendError(
                f"Quilt3 backend search failed: {str(e)}", 
                context={'query': query, 'registry': registry}
            )
    
    def _transform_package(self, quilt3_package) -> Package_Info:
        """Transform quilt3.Package to Package_Info domain object."""
        return Package_Info(
            name=quilt3_package.name,
            description=quilt3_package.description,
            tags=quilt3_package.tags or [],
            modified_date=quilt3_package.modified.isoformat(),
            registry=quilt3_package.registry,
            bucket=quilt3_package.bucket,
            top_hash=quilt3_package.top_hash
        )
```

#### Platform_Backend (Phase 2)

**Responsibility:** Implement QuiltOps using Platform GraphQL API

**Key Characteristics:**
- HTTP-based GraphQL API integration
- JWT token authentication
- Transformation from GraphQL responses to domain objects
- Platform-specific optimizations

## Data Flow

### Package Search Flow

```
1. MCP Tool calls packages_list(registry="s3://my-registry")
   │
   ▼
2. Tool creates QuiltOps via QuiltOpsFactory.create()
   │
   ▼
3. Factory detects quilt3 session → creates Quilt3_Backend
   │
   ▼
4. Tool calls quilt_ops.search_packages("", "s3://my-registry")
   │
   ▼
5. Quilt3_Backend calls quilt3.search("", registry="s3://my-registry")
   │
   ▼
6. Backend transforms quilt3.Package objects → Package_Info objects
   │
   ▼
7. Tool receives List[Package_Info] and converts to MCP response
   │
   ▼
8. MCP client receives JSON response with package data
```

### Error Flow

```
1. Backend operation fails (e.g., network timeout)
   │
   ▼
2. Backend catches exception and creates BackendError with context
   │
   ▼
3. BackendError propagates to MCP tool
   │
   ▼
4. Tool catches BackendError and creates appropriate MCP error response
   │
   ▼
5. MCP client receives structured error with remediation steps
```

## Authentication Architecture

### Phase 1: Quilt3 Session Only

```
┌─────────────────┐
│ QuiltOpsFactory │
└─────────┬───────┘
          │
          ▼
┌─────────────────┐    Yes    ┌─────────────────┐
│ quilt3.logged_in│ ────────▶ │ Quilt3_Backend  │
│ session check   │           └─────────────────┘
└─────────────────┘
          │
          │ No
          ▼
┌─────────────────┐
│ AuthenticationError │
│ "Run quilt3 login"  │
└─────────────────┘
```

### Phase 2: Multi-Backend Authentication (Future)

```
┌─────────────────┐
│ QuiltOpsFactory │
└─────────┬───────┘
          │
          ▼
┌─────────────────┐    Yes    ┌─────────────────┐
│ JWT Token Check │ ────────▶ │ Platform_Backend│
└─────────────────┘           └─────────────────┘
          │
          │ No
          ▼
┌─────────────────┐    Yes    ┌─────────────────┐
│ Quilt3 Session  │ ────────▶ │ Quilt3_Backend  │
│ Check           │           └─────────────────┘
└─────────────────┘
          │
          │ No
          ▼
┌─────────────────┐
│ AuthenticationError │
│ Multi-auth help     │
└─────────────────┘
```

## Testing Architecture

### Test Layer Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                    Integration Tests                             │
├─────────────────────────────────────────────────────────────────┤
│ • End-to-end workflows                                          │
│ • Server initialization                                         │
│ • Error handling and recovery                                   │
│ • Authentication scenarios                                      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Unit Tests                                 │
├─────────────────────────────────────────────────────────────────┤
│ Domain Objects │ QuiltOps Interface │ Backend Implementations   │
│ • Package_Info │ • Abstract methods │ • Quilt3_Backend         │
│ • Content_Info │ • Error handling   │ • Transformation logic   │
│ • Bucket_Info  │ • Type validation  │ • Error handling         │
└─────────────────────────────────────────────────────────────────┘
```

### Test Strategy

**Unit Tests:**
- Test individual components in isolation
- Mock external dependencies (quilt3, network calls)
- Focus on transformation logic and error handling
- Validate domain object creation and validation

**Integration Tests:**
- Test complete workflows end-to-end
- Test with real authentication (where possible)
- Validate error propagation through the stack
- Test server initialization and configuration

## Performance Considerations

### Backend Selection Performance

The QuiltOpsFactory performs authentication detection once per tool invocation:

```python
# Each tool call creates a new QuiltOps instance
def mcp_tool():
    quilt_ops = QuiltOpsFactory.create()  # Authentication detection happens here
    return quilt_ops.search_packages(...)
```

**Optimization Opportunities (Future):**
- Cache QuiltOps instances per session
- Implement connection pooling for Platform backend
- Add request batching for multiple operations

### Memory Usage

Domain objects are lightweight and designed for efficient memory usage:

```python
# Package_Info: ~200 bytes per instance
# Content_Info: ~150 bytes per instance  
# Bucket_Info: ~100 bytes per instance
```

**Large Dataset Handling:**
- Streaming support for large package listings
- Pagination support for content browsing
- Lazy loading for package metadata

## Security Architecture

### Authentication Security

**Phase 1 (Quilt3 Session):**
- Relies on quilt3 library's session management
- Session validation on backend creation
- No credential storage in QuiltOps layer

**Phase 2 (JWT Tokens):**
- JWT token validation and parsing
- Token expiration handling
- Secure token storage patterns

### Error Information Security

Error messages are designed to provide useful debugging information without exposing sensitive data:

```python
# Good - provides context without exposing credentials
"Quilt3 backend search failed: Access denied to registry 's3://private-registry'"

# Bad - would expose sensitive information
"Quilt3 backend search failed: Invalid AWS credentials: AKIA..."
```

## Extensibility

### Adding New Backends

To add a new backend implementation:

1. **Implement QuiltOps Interface:**
   ```python
   class NewBackend(QuiltOps):
       def search_packages(self, query: str, registry: str) -> List[Package_Info]:
           # Implementation specific to new backend
           pass
   ```

2. **Add Authentication Detection:**
   ```python
   # In QuiltOpsFactory
   def create() -> QuiltOps:
       # Check for new backend authentication
       if new_backend_auth_available():
           return NewBackend()
       # ... existing checks
   ```

3. **Implement Transformation Logic:**
   ```python
   def _transform_package(self, backend_package) -> Package_Info:
       # Transform backend-specific object to domain object
       return Package_Info(...)
   ```

### Adding New Domain Objects

To add new domain objects:

1. **Define Dataclass:**
   ```python
   @dataclass
   class NewDomainObject:
       field1: str
       field2: Optional[int]
   ```

2. **Add to QuiltOps Interface:**
   ```python
   @abstractmethod
   def new_operation(self) -> List[NewDomainObject]:
       pass
   ```

3. **Implement in All Backends:**
   ```python
   def new_operation(self) -> List[NewDomainObject]:
       # Backend-specific implementation
       pass
   ```

## Migration Path

### Phase 1 → Phase 2 Migration

The architecture is designed to support seamless migration from Phase 1 to Phase 2:

**No Interface Changes:**
- MCP tools continue using the same QuiltOps interface
- Domain objects remain unchanged
- Error handling patterns remain consistent

**Backend Addition:**
- Platform_Backend added alongside Quilt3_Backend
- QuiltOpsFactory updated to detect JWT authentication
- Authentication priority: JWT first, then quilt3 session

**Backward Compatibility:**
- Existing quilt3 session authentication continues to work
- No changes required in MCP tools
- Gradual migration path for users

## Monitoring and Observability

### Logging Strategy

**Factory Level:**
```python
logger.info("Authentication mode selected: quilt3")
logger.debug("Creating Quilt3_Backend with session info")
```

**Backend Level:**
```python
logger.debug("Searching packages with query: 'data' in registry: 's3://registry'")
logger.debug("Found 5 packages")
logger.error("Search failed: Network timeout", extra={'context': {...}})
```

**Tool Level:**
```python
logger.info("MCP tool 'packages_list' called with registry: 's3://registry'")
logger.debug("Returning 5 packages to MCP client")
```

### Metrics Collection

**Performance Metrics:**
- Operation execution time
- Backend selection time
- Authentication validation time
- Error rates by backend and operation

**Usage Metrics:**
- Most frequently used operations
- Backend usage distribution
- Error patterns and frequencies

## Deployment Considerations

### Environment Configuration

**Phase 1 Configuration:**
```bash
# Quilt3 session authentication (default)
# No additional environment variables required
# Authentication via: quilt3 login
```

**Phase 2 Configuration (Future):**
```bash
# JWT authentication
export QUILT_JWT_TOKEN="eyJ..."
export QUILT_PLATFORM_API_ENDPOINT="https://api.quiltdata.com/graphql"

# Fallback to quilt3 session if JWT not available
# Authentication priority: JWT → quilt3 session
```

### Container Deployment

The abstraction layer is designed to work in containerized environments:

```dockerfile
# Phase 1: Quilt3 session in container
FROM python:3.12
COPY . /app
WORKDIR /app
RUN pip install -e .

# Mount quilt3 credentials
VOLUME ["/root/.quilt"]

# Phase 2: JWT authentication in container
ENV QUILT_JWT_TOKEN=${JWT_TOKEN}
ENV QUILT_PLATFORM_API_ENDPOINT=${API_ENDPOINT}
```

## Future Enhancements

### Planned Features

**Caching Layer:**
- Cache frequently accessed package metadata
- Implement cache invalidation strategies
- Support for distributed caching

**Request Batching:**
- Batch multiple operations for efficiency
- Reduce network round trips
- Optimize for high-throughput scenarios

**Advanced Error Recovery:**
- Automatic retry with exponential backoff
- Circuit breaker pattern for failing backends
- Graceful degradation strategies

**Multi-Backend Operations:**
- Cross-backend package search
- Backend failover mechanisms
- Load balancing across backends

### Backward Compatibility Guarantee

The QuiltOps interface is designed to remain stable across all future enhancements:

- Domain objects will only receive additive changes
- Method signatures will remain unchanged
- Error handling patterns will remain consistent
- Migration paths will always be provided

This ensures that code written against the Phase 1 interface will continue to work in all future phases.