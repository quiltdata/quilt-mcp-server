<!-- markdownlint-disable MD013 -->
# Phase 1 Design: Authentication Status (Tracer Bullet)

## Overview

This document defines the technical architecture and implementation strategy for Phase 1 of the Quilt3 isolation project - implementing the `auth_status` feature as a tracer bullet to establish the complete isolation pattern.

## Reference Documents

- **Phase Definition**: [04-phases.md](./04-phases.md) - Phase 1 specifications
- **Target Architecture**: [03-specifications.md](./03-specifications.md) - Desired end state goals
- **Current Analysis**: [02-analysis.md](./02-analysis.md) - Current system constraints

## Design Goals

### Primary Objectives

1. **Establish Complete Isolation Pattern**: Prove the full stack isolation works end-to-end
2. **Minimal Viable Implementation**: Implement the simplest, safest feature first
3. **Pattern Validation**: Validate architectural decisions with real implementation
4. **Foundation for Scaling**: Create reusable patterns for subsequent phases

### Success Criteria

- Users can configure isolated Quilt3 connection
- `auth_status` tool works independently of global quilt3 state
- Complete test coverage across all architectural layers
- MCP Inspector shows working tool with proper error handling

## Architecture Design

### Layer 1: Configuration System (`src/quilt_mcp/config/`)

#### `quilt3.py` - Isolated Configuration Class

**Design Decision**: Create a dedicated configuration class that encapsulates all Quilt3 connection parameters without depending on global quilt3 state.

```python
# Conceptual interface - DO NOT IMPLEMENT
class Quilt3Config:
    def __init__(self, registry_url: str, catalog_url: Optional[str] = None)
    def validate(self) -> ConfigValidationResult
    def to_dict(self) -> Dict[str, Any]
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Quilt3Config"
```

**Key Design Principles**:

- Immutable configuration objects
- Self-validating with clear error messages
- Serializable for testing and debugging
- No dependency on quilt3 global state

**Configuration Sources** (in priority order):

1. Explicit MCP tool parameters
2. Environment variables (`QUILT_REGISTRY_URL`, `QUILT_CATALOG_URL`)
3. Default registry detection from catalog configuration

### Layer 2: Operation Implementation (`src/quilt_mcp/operations/quilt3/`)

#### `auth.py` - Authentication Operations

**Design Decision**: Complete rewrite of authentication logic with strict isolation from global quilt3 state.

**Core Operation Interface**:

```python
# Conceptual interface - DO NOT IMPLEMENT
def check_auth_status(config: Quilt3Config) -> AuthStatusResult
```

**Implementation Strategy**:

1. **Isolated Client Creation**: Create quilt3 client instances with explicit configuration
2. **Stateless Operations**: Each operation receives complete configuration context
3. **Comprehensive Error Handling**: Catch and categorize all possible failure modes
4. **Structured Results**: Return typed result objects, not raw quilt3 responses

**Error Categorization**:

- Configuration errors (invalid URLs, missing credentials)
- Network errors (connectivity, timeouts)
- Authentication errors (invalid tokens, expired credentials)
- Authorization errors (insufficient permissions)

### Layer 3: MCP API Integration (`src/quilt_mcp/api/`)

#### `quilt3.py` - MCP Tool Definitions

**Design Decision**: Create clean MCP tool interfaces that abstract away implementation complexity.

**Tool Definition Strategy**:

- Clear parameter schemas with validation
- Comprehensive documentation in tool descriptions
- Consistent error response formatting
- Optional parameters with sensible defaults

**Response Standardization**:

```python
# Conceptual structure - DO NOT IMPLEMENT
{
    "success": bool,
    "data": Optional[Dict[str, Any]],
    "error": Optional[ErrorInfo],
    "metadata": Dict[str, Any]  # execution context, timing, etc.
}
```

### Layer 4: Core Adapter (`src/quilt_mcp/`)

#### `server.py` - Tool Registration and Routing

**Design Decision**: Centralized tool registration with configuration dependency injection.

**Configuration Management Strategy**:

1. Load configuration from multiple sources (see Layer 1)
2. Validate configuration at startup
3. Inject validated configuration into operation handlers
4. Handle configuration errors gracefully with helpful messages

**Tool Registration Pattern**:

- Declarative tool registration using decorators or registration functions
- Automatic parameter validation using configuration schema
- Consistent error handling across all tools

## Implementation Strategy

### Configuration Layer Implementation

1. **Create Base Configuration Classes**:
   - Abstract base for all configuration types
   - Validation framework with typed errors
   - Serialization/deserialization support

2. **Implement Quilt3Config**:
   - Registry URL validation (S3 bucket format)
   - Catalog URL validation (HTTP/HTTPS)
   - Environment variable integration
   - Default value resolution

3. **Configuration Loading Pipeline**:
   - Priority-based configuration resolution
   - Environment variable parsing
   - Validation with actionable error messages

### Operation Layer Implementation

1. **Establish Operation Base Classes**:
   - Standard operation interface pattern
   - Result type definitions
   - Error handling framework

2. **Implement Authentication Operations**:
   - Create isolated quilt3 client instances
   - Check authentication status without side effects
   - Comprehensive error detection and categorization
   - Structured result formatting

### API Layer Implementation

1. **Create MCP Tool Framework**:
   - Tool registration utilities
   - Parameter validation framework
   - Response standardization

2. **Implement Authentication Tools**:
   - `auth_status` tool definition
   - Parameter schema validation
   - Documentation and examples

### Adapter Layer Implementation

1. **Enhance Server Architecture**:
   - Configuration injection system
   - Tool registration framework
   - Error handling middleware

2. **Integration Points**:
   - Configuration loading at startup
   - Tool handler registration
   - Error response formatting

## Integration Points

### Configuration → Operations

- Configuration objects passed explicitly to all operations
- No global state dependencies
- Clear configuration validation errors

### Operations → API

- Typed result objects from operations
- Standardized error information
- Consistent response formatting

### API → Server

- Tool registration with configuration injection
- Centralized error handling
- Request/response logging for debugging

## Testing Strategy

### Configuration Testing

- Valid/invalid configuration scenarios
- Environment variable integration
- Default value resolution
- Error message clarity

### Operation Testing

- Authentication success/failure scenarios
- Network error simulation
- Configuration error handling
- Result object validation

### Integration Testing

- End-to-end MCP tool execution
- Configuration loading pipeline
- Error propagation through all layers
- MCP Inspector compatibility

## Risk Mitigation

### Configuration Isolation Risks

- **Risk**: Accidental dependency on global quilt3 state
- **Mitigation**: Explicit configuration injection, no global imports

### Operation Reliability Risks

- **Risk**: Inconsistent error handling across operations
- **Mitigation**: Standardized error categorization framework

### API Consistency Risks

- **Risk**: Inconsistent response formats across tools
- **Mitigation**: Response standardization utilities

### Integration Complexity Risks

- **Risk**: Complex configuration loading logic
- **Mitigation**: Simple, testable configuration pipeline

## Implementation Guidelines

### Code Organization

```tree
src/quilt_mcp/
├── config/
│   ├── __init__.py          # Configuration framework
│   ├── base.py              # Base configuration classes
│   └── quilt3.py            # Quilt3-specific configuration
├── operations/
│   └── quilt3/
│       ├── __init__.py      # Operation framework
│       ├── base.py          # Base operation classes
│       └── auth.py          # Authentication operations
├── api/
│   ├── __init__.py          # API framework
│   └── quilt3.py            # Quilt3 MCP tool definitions
└── server.py                # Enhanced server with configuration injection
```

### Development Sequence

1. **Configuration Framework**: Base classes and validation
2. **Quilt3 Configuration**: Specific implementation with env var support
3. **Operation Framework**: Base classes and result types
4. **Authentication Operations**: Isolated auth status checking
5. **API Framework**: Tool registration and response standardization
6. **Authentication Tools**: MCP tool definitions
7. **Server Integration**: Configuration injection and tool registration

### Quality Standards

- **Test Coverage**: 100% coverage for all new code
- **Type Safety**: Full type annotations with mypy validation
- **Documentation**: Comprehensive docstrings and examples
- **Error Handling**: Clear, actionable error messages

## Success Validation

### Functional Validation

1. **Configuration Loading**: All configuration sources work correctly
2. **Auth Status Check**: Successfully detects authentication state
3. **Error Handling**: Proper error categorization and reporting
4. **MCP Integration**: Tool appears and works in MCP Inspector

### Technical Validation

1. **Isolation Proof**: No dependencies on global quilt3 state
2. **Test Coverage**: 100% coverage across all layers
3. **Type Safety**: mypy passes without errors
4. **Performance**: Auth check completes within reasonable time

### Integration Validation

1. **End-to-End Flow**: Configuration → Operation → API → Response
2. **Error Propagation**: Errors properly bubble up through layers
3. **MCP Compatibility**: Works correctly with MCP Inspector
4. **Documentation**: Clear examples for users

## Next Phase Preparation

This phase establishes the foundational patterns that will be reused in subsequent phases:

- Configuration injection pattern for new Quilt3 operations
- Operation base classes for consistent implementation
- API standardization for uniform tool interfaces
- Testing patterns for comprehensive coverage

The success of this tracer bullet validates the entire isolation architecture and provides confidence for implementing more complex operations in future phases.
