<!-- markdownlint-disable MD013 -->
# Phase 1 Design: Foundation & Infrastructure

**Issue Reference**: GitHub Issue #233 - get-resource tool
**Branch**: `233-get-resource-tool`
**Phase**: 1 of 3
**Status**: Design

## References

This design implements Phase 1 based on:

- **Specifications**: [03-specifications.md](./03-specifications.md) - Desired end state and technical contracts
- **Analysis**: [02-analysis.md](./02-analysis.md) - Current codebase patterns and challenges
- **Requirements**: [01-requirements.md](./01-requirements.md) - User stories and acceptance criteria

## Phase 1 Objectives

Phase 1 establishes the foundational infrastructure for the `get_resource` tool without implementing the full feature set. This phase focuses on:

1. **Type System Foundation**: Define all response models and type definitions
2. **Resource Registry System**: Implement the core URI-to-function mapping infrastructure
3. **ResourceManager Class**: Create the central orchestrator for resource access
4. **Testing Infrastructure**: Establish comprehensive test harness and benchmarking framework
5. **Integration Points**: Validate integration with existing FastMCP and resource systems

**Success Criteria**:

- ✅ All response models defined and tested
- ✅ Resource registry infrastructure operational with 5+ representative resources
- ✅ ResourceManager class handles static URIs correctly
- ✅ Test harness validates data consistency against real resources
- ✅ Performance benchmarking framework in place
- ✅ No modifications to existing resource definitions

## 1. Technical Architecture

### 1.1 Module Structure

```
src/quilt_mcp/tools/
  resource_access.py          # Main tool implementation
    - get_resource()          # Tool function (FastMCP-compatible)
    - ResourceManager         # Core orchestrator class
    - Resource registry       # URI-to-function mapping

src/quilt_mcp/models/
  responses.py                # Extended with resource tool responses
    - GetResourceSuccess      # Success response model
    - GetResourceError        # Error response model
    - ResourceMetadata        # Discovery mode metadata
    - ResourceDefinition      # Registry entry type

tests/unit/tools/
  test_resource_access.py     # Unit tests for tool
  test_resource_registry.py   # Registry validation tests

tests/integration/
  test_resource_parity.py     # Data consistency validation
  test_resource_performance.py # Performance benchmarks
```

**Design Decision**: Single module for Phase 1, potential split in Phase 2+ if complexity warrants.

### 1.2 Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Client (Legacy)                      │
└───────────────────────┬─────────────────────────────────────┘
                        │ Tool Protocol
                        │ get_resource(uri="auth://status")
                        ▼
┌─────────────────────────────────────────────────────────────┐
│               get_resource() Tool Function                  │
│  1. Validate URI parameter                                  │
│  2. Route to ResourceManager                                │
│  3. Wrap result in GetResourceSuccess/Error                 │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                   ResourceManager                           │
│  1. Lookup URI in registry (static O(1) dict)              │
│  2. Extract ResourceDefinition                              │
│  3. Call service function with auth context                 │
│  4. Deserialize result to dict                              │
│  5. Return structured data                                  │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              Service Functions (Existing)                   │
│  Examples:                                                  │
│  - auth_status() → dict                                     │
│  - catalog_info() → dict                                    │
│  - admin_users_list() → Pydantic model                      │
└─────────────────────────────────────────────────────────────┘
```

**Key Design Principle**: ResourceManager is a pure orchestrator - it does NOT implement business logic, only routing and serialization.

### 1.3 Authentication Context Flow

```
User Authenticates → quilt3.config stores credentials
                           ↓
              quilt_mcp.runtime_context.get_runtime_config()
                           ↓
                 ┌─────────┴──────────┐
                 │                    │
          Resource Function    get_resource Tool
          (Existing)           (New)
                 │                    │
                 └─────────┬──────────┘
                           │
                   Service Functions
                   (auth context implicit)
```

**Design Decision**: Zero additional authentication plumbing. Tool inherits auth context automatically through existing runtime_context mechanism.

## 2. Type Definitions and Response Models

### 2.1 Response Models (Extension to models/responses.py)

```python
# ============================================================================
# Resource Access Tool Responses
# ============================================================================

class ResourceMetadata(BaseModel):
    """Metadata for a single resource in discovery mode."""

    uri: str = Field(..., description="Resource URI pattern (may contain {variables})")
    name: str = Field(..., description="Human-readable resource name")
    description: str = Field(..., description="Functional description")
    is_template: bool = Field(..., description="True if URI contains template variables")
    template_variables: list[str] = Field(
        default_factory=list,
        description="List of variable names in URI (empty if not templated)"
    )
    requires_admin: bool = Field(..., description="True if admin privileges required")
    category: str = Field(..., description="Resource category (auth, admin, etc.)")


class GetResourceSuccess(SuccessResponse):
    """Successful resource access response."""

    uri: str = Field(..., description="The resolved URI (expanded if templated)")
    resource_name: str = Field(..., description="Human-readable name of the resource")
    data: dict[str, Any] = Field(..., description="The actual resource data")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the data was retrieved"
    )
    mime_type: str = Field(default="application/json", description="Resource MIME type")


class GetResourceError(ErrorResponse):
    """Failed resource access response."""

    # Inherits: success, error, cause, possible_fixes, suggested_actions
    valid_uris: Optional[list[str]] = Field(
        default=None,
        description="Available URIs (for invalid URI errors)"
    )
```

**Design Decisions**:

1. **Inheritance from Base Models**: Reuse `SuccessResponse` and `ErrorResponse` for consistency
2. **DictAccessibleModel**: Both inherit dict-like access for backward compatibility
3. **Field Descriptions**: Comprehensive docstrings for auto-generated API documentation
4. **Datetime Handling**: Use `datetime` type with auto-serialization via FastMCP

**Phase 1 Scope**: Define all models, test serialization, validate FastMCP compatibility.

### 2.2 ResourceDefinition Type (Internal)

```python
# Internal type for registry entries (not exposed in tool responses)
from typing import Callable, TypedDict

class ResourceDefinition(TypedDict):
    """Definition of a single resource in the registry."""

    uri: str                          # URI pattern (may contain {variables})
    name: str                         # Human-readable name
    description: str                  # Functional description
    service_function: Callable[..., Any]  # Function to invoke
    is_async: bool                    # Whether service function is async
    is_template: bool                 # Whether URI contains variables
    template_variables: list[str]     # Variable names (empty if not templated)
    requires_admin: bool              # Whether admin privileges required
    category: str                     # Resource category
    parameter_mapping: dict[str, str] # URI variable → function parameter (for templates)
```

**Design Decision**: Use TypedDict for internal registry to maintain type safety without runtime overhead.

## 3. ResourceManager Class Design

### 3.1 Class Structure

```python
class ResourceManager:
    """Manages resource URI routing and service function invocation.

    This class provides a centralized orchestrator for:
    - URI validation and lookup
    - Static URI dispatching (O(1) dict lookup)
    - Template URI expansion (Phase 2+)
    - Service function invocation with proper async handling
    - Result serialization and error handling

    Design Principle: Pure orchestrator - no business logic, only routing.
    """

    def __init__(self, registry: dict[str, ResourceDefinition]):
        """Initialize with resource registry.

        Args:
            registry: URI → ResourceDefinition mapping
        """
        self._registry = registry
        self._static_uris = {
            uri: defn for uri, defn in registry.items()
            if not defn["is_template"]
        }
        # Template URIs handled in Phase 2

    async def get_resource(self, uri: Optional[str]) -> dict[str, Any]:
        """Retrieve resource data by URI.

        Args:
            uri: Resource URI or None/empty for discovery mode

        Returns:
            Resource data dict (to be wrapped in GetResourceSuccess/Error)

        Raises:
            ValueError: Invalid URI format
            KeyError: URI not found in registry
            RuntimeError: Service function execution failed
        """
        # Implementation details below

    async def get_discovery_data(self) -> dict[str, list[ResourceMetadata]]:
        """Generate discovery mode response.

        Returns:
            Dict mapping category → list of ResourceMetadata
        """
        # Implementation details below

    async def _invoke_service_function(
        self,
        defn: ResourceDefinition,
        params: dict[str, Any]
    ) -> dict[str, Any]:
        """Invoke service function and deserialize result.

        Args:
            defn: Resource definition
            params: Parameters for service function (empty for Phase 1)

        Returns:
            Deserialized result as dict
        """
        # Implementation details below
```

**Design Decisions**:

1. **Separate Static URIs**: Pre-filter static URIs for O(1) lookup performance
2. **Async-First Design**: All methods async to match FastMCP pattern
3. **Exception-Based Errors**: Raise specific exceptions, tool wrapper converts to error responses
4. **Dependency Injection**: Registry passed in constructor for testability

### 3.2 Static URI Dispatch Implementation

```python
async def get_resource(self, uri: Optional[str]) -> dict[str, Any]:
    """Retrieve resource data by URI (Phase 1: static URIs only)."""

    # Discovery mode
    if uri is None or uri == "":
        return await self.get_discovery_data()

    # Validate URI format
    if not uri or "://" not in uri:
        raise ValueError(f"Invalid URI format: {uri}")

    # Static URI lookup (Phase 1)
    if uri not in self._static_uris:
        raise KeyError(f"Resource URI not recognized: {uri}")

    # Get definition and invoke service function
    defn = self._static_uris[uri]
    result = await self._invoke_service_function(defn, params={})

    return {
        "uri": uri,
        "resource_name": defn["name"],
        "data": result,
        "mime_type": "application/json",
    }
```

**Phase 1 Scope**:

- ✅ Static URI lookup (17 resources)
- ❌ Template URI expansion (deferred to Phase 2)
- ✅ Discovery mode
- ✅ Basic error handling

### 3.3 Service Function Invocation

```python
async def _invoke_service_function(
    self,
    defn: ResourceDefinition,
    params: dict[str, Any]
) -> dict[str, Any]:
    """Invoke service function and deserialize result."""

    func = defn["service_function"]

    # Handle async vs sync functions
    if defn["is_async"]:
        result = await func(**params)
    else:
        # Run sync functions in thread pool
        result = await asyncio.to_thread(func, **params)

    # Deserialize Pydantic models to dict
    if hasattr(result, "model_dump"):
        return result.model_dump()

    # Already a dict
    if isinstance(result, dict):
        return result

    # Fallback: attempt to convert to dict
    try:
        return dict(result)
    except (TypeError, ValueError) as e:
        raise RuntimeError(f"Unable to serialize result: {e}")
```

**Design Decisions**:

1. **Async/Sync Handling**: Use `asyncio.to_thread()` for sync functions (matches resource pattern)
2. **Pydantic Deserialization**: Use `.model_dump()` for consistent dict conversion
3. **Fallback Logic**: Attempt dict conversion as last resort
4. **Error Propagation**: Wrap serialization failures in RuntimeError

### 3.4 Discovery Mode Implementation

```python
async def get_discovery_data(self) -> dict[str, list[ResourceMetadata]]:
    """Generate discovery mode response."""

    # Group resources by category
    by_category: dict[str, list[ResourceMetadata]] = {}

    for uri, defn in self._registry.items():
        metadata = ResourceMetadata(
            uri=uri,
            name=defn["name"],
            description=defn["description"],
            is_template=defn["is_template"],
            template_variables=defn["template_variables"],
            requires_admin=defn["requires_admin"],
            category=defn["category"],
        )

        if metadata.category not in by_category:
            by_category[metadata.category] = []

        by_category[metadata.category].append(metadata)

    # Sort within each category by URI
    for category in by_category:
        by_category[category].sort(key=lambda m: m.uri)

    return by_category
```

**Design Decision**: Pre-compute discovery data at runtime (not cached in Phase 1) for simplicity. Can optimize with caching in Phase 2 if needed.

## 4. Resource Registry Design

### 4.1 Registry Construction

**Phase 1 Approach**: Manual registry with 5 representative resources to validate architecture.

**Representative Resources Selected**:

1. `auth://status` (static, auth category, returns dict)
2. `auth://catalog/info` (static, auth category, returns dict)
3. `admin://users` (static, admin category, requires admin, returns Pydantic model)
4. `permissions://discover` (static, permissions category, returns dict)
5. `metadata://templates/standard` (template, metadata category - validates registry structure only, full impl in Phase 2)

**Selection Rationale**:

- Covers 3 different categories (auth, admin, permissions)
- Mix of return types (dict, Pydantic model)
- Includes admin-only resource (tests authorization)
- Includes one template resource (validates registry structure)
- All have existing service functions

### 4.2 Registry Implementation

```python
# In resource_access.py

from quilt_mcp.services.auth_metadata import (
    auth_status,
    catalog_info,
)
from quilt_mcp.services.governance_service import admin_users_list
from quilt_mcp.services.permissions_service import discover_permissions
from quilt_mcp.services.metadata_service import get_metadata_template

# Build resource registry (Phase 1: 5 representative resources)
RESOURCE_REGISTRY: dict[str, ResourceDefinition] = {
    "auth://status": {
        "uri": "auth://status",
        "name": "Auth Status",
        "description": "Check authentication status and catalog configuration",
        "service_function": auth_status,
        "is_async": False,
        "is_template": False,
        "template_variables": [],
        "requires_admin": False,
        "category": "auth",
        "parameter_mapping": {},
    },
    "auth://catalog/info": {
        "uri": "auth://catalog/info",
        "name": "Catalog Info",
        "description": "Get catalog configuration details",
        "service_function": catalog_info,
        "is_async": False,
        "is_template": False,
        "template_variables": [],
        "requires_admin": False,
        "category": "auth",
        "parameter_mapping": {},
    },
    "admin://users": {
        "uri": "admin://users",
        "name": "Admin Users List",
        "description": "List all users in the Quilt registry with their roles and status (requires admin privileges)",
        "service_function": admin_users_list,
        "is_async": True,  # Note: This is an async function
        "is_template": False,
        "template_variables": [],
        "requires_admin": True,
        "category": "admin",
        "parameter_mapping": {},
    },
    "permissions://discover": {
        "uri": "permissions://discover",
        "name": "Permissions Discovery",
        "description": "Discover AWS permissions for current user/role",
        "service_function": discover_permissions,
        "is_async": False,
        "is_template": False,
        "template_variables": [],
        "requires_admin": False,
        "category": "permissions",
        "parameter_mapping": {},
    },
    # Template resource (structure only, full impl in Phase 2)
    "metadata://templates/{template}": {
        "uri": "metadata://templates/{template}",
        "name": "Metadata Template",
        "description": "Get specific metadata template by name",
        "service_function": get_metadata_template,
        "is_async": False,
        "is_template": True,
        "template_variables": ["template"],
        "requires_admin": False,
        "category": "metadata",
        "parameter_mapping": {"template": "name"},
    },
}
```

**Phase 1 Validation**:

- ✅ Registry structure correct
- ✅ All service functions importable
- ✅ Async/sync flags accurate
- ✅ Admin flags correct
- ✅ Categories consistent

**Phase 2 Expansion**: Add remaining 14 resources following same pattern.

### 4.3 Registry Validation

```python
def validate_registry(registry: dict[str, ResourceDefinition]) -> None:
    """Validate registry structure and consistency.

    Raises:
        ValueError: Registry validation failed
    """
    for uri, defn in registry.items():
        # Validate URI matches definition URI
        if uri != defn["uri"]:
            raise ValueError(f"URI mismatch: key={uri}, defn={defn['uri']}")

        # Validate service function is callable
        if not callable(defn["service_function"]):
            raise ValueError(f"Service function not callable: {uri}")

        # Validate template consistency
        has_braces = "{" in uri
        if defn["is_template"] != has_braces:
            raise ValueError(f"Template flag inconsistent with URI: {uri}")

        # Validate template variables
        if defn["is_template"] and not defn["template_variables"]:
            raise ValueError(f"Template URI missing variable list: {uri}")

        # Validate parameter mapping for templates
        if defn["is_template"]:
            for var in defn["template_variables"]:
                if var not in defn["parameter_mapping"]:
                    raise ValueError(f"Template variable not in parameter mapping: {var} in {uri}")

# Validate at module initialization
validate_registry(RESOURCE_REGISTRY)
```

**Design Decision**: Fail-fast validation at module initialization to catch registry errors immediately.

## 5. Tool Function Implementation

### 5.1 Tool Wrapper Function

```python
# In resource_access.py

async def get_resource(uri: str = "") -> GetResourceSuccess | GetResourceError:
    """Access MCP resource data via tool interface for legacy clients.

    This tool provides compatibility with legacy MCP clients (Claude Desktop, Cursor)
    that lack native support for the MCP resources protocol. It exposes all server
    resources through a tool interface with identical data structures.

    Discovery Mode:
        Call without arguments (or with empty string) to list all available resources:

        >>> get_resource()
        >>> get_resource("")

        Returns organized list of all 19 resources with metadata including:
        - URI patterns (with template variables if applicable)
        - Human-readable names and descriptions
        - Admin privilege requirements
        - Resource categories

    Resource Access:
        Provide a resource URI to access specific resource data:

        >>> get_resource("auth://status")
        >>> get_resource("auth://catalog/info")
        >>> get_resource("admin://users")  # Requires admin privileges

    Template Resources (Phase 2+):
        Some resources use template URIs with variables:

        >>> get_resource("metadata://templates/standard")
        >>> get_resource("workflow://workflows/{id}/status")

    Available Resource Categories:
        - auth: Authentication and catalog status
        - permissions: AWS permissions discovery
        - admin: User management and configuration (requires admin)
        - athena: Database schema exploration
        - metadata: Package metadata templates
        - workflow: Workflow tracking and status
        - tabulator: Bucket and table listings

    Args:
        uri: Resource URI or empty string for discovery mode.
             Format: scheme://path (e.g., "auth://status")
             Template variables: {variable} (e.g., "metadata://templates/{template}")

    Returns:
        GetResourceSuccess: Resource data or discovery listing
        GetResourceError: Error with actionable guidance

    Error Handling:
        All errors include:
        - Error type classification
        - Human-readable error message
        - Suggested recovery actions
        - Valid URI list (for invalid URI errors)

    Performance:
        - Discovery mode: <500ms
        - Static resources: <10% overhead vs direct resource access
        - Template resources: <100ms additional parsing (Phase 2+)

    Authentication:
        Uses same authentication context as resources protocol.
        No additional configuration required.
        Admin-only resources return clear authorization errors.

    Examples:
        Discovery mode:
        >>> result = get_resource()
        >>> print(result["data"]["auth"])  # List auth resources

        Static resource access:
        >>> result = get_resource("auth://status")
        >>> print(result["data"]["authenticated"])

        Error handling:
        >>> result = get_resource("invalid://uri")
        >>> if not result["success"]:
        ...     print(result["suggested_actions"])
    """
    # Initialize resource manager (Phase 1: singleton pattern simple)
    manager = ResourceManager(RESOURCE_REGISTRY)

    try:
        # Get resource data
        data = await manager.get_resource(uri)

        # Wrap in success response
        return GetResourceSuccess(
            uri=uri,
            resource_name=data.get("resource_name", "Available Resources"),
            data=data.get("data", data),
            timestamp=datetime.utcnow(),
            mime_type=data.get("mime_type", "application/json"),
        )

    except ValueError as e:
        # Invalid URI format
        return GetResourceError(
            error="InvalidURI",
            cause=str(e),
            suggested_actions=[
                "Call get_resource() with no arguments to see all available resources.",
                "Verify the URI scheme and path are correct.",
                "Check for typos in the URI.",
            ],
            valid_uris=list(RESOURCE_REGISTRY.keys()),
        )

    except KeyError as e:
        # URI not found
        return GetResourceError(
            error="InvalidURI",
            cause=f"Resource URI not recognized: {uri}",
            suggested_actions=[
                "Call get_resource() with no arguments to see all available resources.",
                f"Similar URIs: {_get_similar_uris(uri, RESOURCE_REGISTRY)}",
                "Check for typos in the URI.",
            ],
            valid_uris=list(RESOURCE_REGISTRY.keys()),
        )

    except RuntimeError as e:
        # Service function execution error
        error_msg = str(e)

        # Check for authorization errors
        if "Unauthorized" in error_msg or "403" in error_msg or "401" in error_msg:
            return GetResourceError(
                error="Unauthorized",
                cause=f"Resource '{uri}' requires admin privileges.",
                suggested_actions=[
                    "Contact your Quilt administrator to request admin access.",
                    "Check your current permissions using get_resource('auth://status').",
                    "Use get_resource() to see resources available to all users.",
                ],
            )

        # Generic execution error
        return GetResourceError(
            error="ResourceExecutionError",
            cause=f"Failed to retrieve resource '{uri}': {error_msg}",
            suggested_actions=[
                "Verify you have network connectivity to AWS services.",
                "Check authentication status using get_resource('auth://status').",
                "Retry the operation if this was a transient failure.",
                "Contact support if the problem persists.",
            ],
        )

    except Exception as e:
        # Unexpected error
        return GetResourceError(
            error="UnexpectedError",
            cause=f"Unexpected error: {type(e).__name__}: {e}",
            suggested_actions=[
                "This is an unexpected error. Please report to maintainers.",
                "Include the error message and URI in your report.",
            ],
        )


def _get_similar_uris(uri: str, registry: dict[str, ResourceDefinition]) -> str:
    """Find similar URIs for typo suggestions (simple implementation)."""
    # Phase 1: Simple prefix matching
    # Phase 2+: Could use Levenshtein distance

    if "://" not in uri:
        return "No suggestions available"

    scheme = uri.split("://")[0]
    similar = [u for u in registry.keys() if u.startswith(f"{scheme}://")]

    if not similar:
        return "No similar URIs found"

    return ", ".join(similar[:3])
```

**Design Decisions**:

1. **Comprehensive Docstring**: 100+ lines following reStructuredText format for excellent IDE/API docs
2. **Error Handling Strategy**: Catch-and-convert exceptions to error responses
3. **Manager Initialization**: Simple singleton pattern for Phase 1 (can optimize later)
4. **Similar URI Suggestions**: Basic prefix matching (can enhance in Phase 2)

## 6. Testing Infrastructure

### 6.1 Unit Test Strategy

**Test File**: `tests/unit/tools/test_resource_access.py`

**Test Categories**:

1. **Response Model Tests**
   - Serialization/deserialization
   - Dict-like access compatibility
   - Pydantic validation

2. **ResourceManager Tests**
   - Static URI lookup
   - Discovery mode data structure
   - Service function invocation
   - Error handling (invalid URI, not found, execution error)

3. **Registry Validation Tests**
   - Registry structure validation
   - Template consistency checks
   - Service function callability

4. **Tool Function Tests**
   - Success response wrapping
   - Error response conversion
   - Discovery mode trigger
   - Authorization error handling

**Example Test Structure**:

```python
import pytest
from unittest.mock import AsyncMock, patch
from quilt_mcp.tools.resource_access import (
    get_resource,
    ResourceManager,
    RESOURCE_REGISTRY,
)
from quilt_mcp.models.responses import GetResourceSuccess, GetResourceError


class TestResponseModels:
    """Test response model serialization and compatibility."""

    def test_get_resource_success_model(self):
        """Test GetResourceSuccess model structure."""
        response = GetResourceSuccess(
            uri="auth://status",
            resource_name="Auth Status",
            data={"authenticated": True},
        )

        assert response.success is True
        assert response.uri == "auth://status"
        assert response["uri"] == "auth://status"  # Dict-like access
        assert "authenticated" in response.data

    def test_get_resource_error_model(self):
        """Test GetResourceError model structure."""
        response = GetResourceError(
            error="InvalidURI",
            cause="Resource not found",
            suggested_actions=["Check URI format"],
            valid_uris=["auth://status"],
        )

        assert response.success is False
        assert response.error == "InvalidURI"
        assert len(response.suggested_actions) > 0


class TestResourceManager:
    """Test ResourceManager core functionality."""

    @pytest.fixture
    def manager(self):
        """Create ResourceManager with test registry."""
        return ResourceManager(RESOURCE_REGISTRY)

    @pytest.mark.asyncio
    async def test_static_uri_lookup(self, manager):
        """Test static URI lookup returns correct data."""
        result = await manager.get_resource("auth://status")

        assert "uri" in result
        assert "resource_name" in result
        assert "data" in result
        assert result["uri"] == "auth://status"

    @pytest.mark.asyncio
    async def test_invalid_uri_raises_key_error(self, manager):
        """Test invalid URI raises KeyError."""
        with pytest.raises(KeyError):
            await manager.get_resource("invalid://uri")

    @pytest.mark.asyncio
    async def test_discovery_mode(self, manager):
        """Test discovery mode returns all resources."""
        result = await manager.get_discovery_data()

        assert isinstance(result, dict)
        assert "auth" in result
        assert len(result["auth"]) >= 2  # At least auth://status and auth://catalog/info


class TestToolFunction:
    """Test get_resource tool function."""

    @pytest.mark.asyncio
    async def test_discovery_mode_empty_string(self):
        """Test discovery mode with empty string."""
        result = await get_resource("")

        assert isinstance(result, GetResourceSuccess)
        assert result.success is True
        assert "data" in result.model_dump()

    @pytest.mark.asyncio
    async def test_static_resource_success(self):
        """Test successful static resource access."""
        result = await get_resource("auth://status")

        assert isinstance(result, GetResourceSuccess)
        assert result.uri == "auth://status"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_invalid_uri_returns_error(self):
        """Test invalid URI returns error response."""
        result = await get_resource("invalid://uri")

        assert isinstance(result, GetResourceError)
        assert result.success is False
        assert result.error == "InvalidURI"
        assert len(result.suggested_actions) > 0
        assert result.valid_uris is not None
```

**Phase 1 Test Coverage Goal**: >90% code coverage for all Phase 1 components.

### 6.2 Integration Test Strategy

**Test File**: `tests/integration/test_resource_parity.py`

**Purpose**: Validate data consistency between tool and resource access

**Test Approach**:

```python
import pytest
from quilt_mcp.tools.resource_access import get_resource
from quilt_mcp.resources import _serialize_result
from quilt_mcp.services.auth_metadata import auth_status


class TestResourceParity:
    """Validate tool returns identical data to resource protocol."""

    @pytest.mark.asyncio
    async def test_auth_status_parity(self):
        """Test auth://status returns same data as resource."""
        # Get data via tool
        tool_result = await get_resource("auth://status")
        tool_data = tool_result.data

        # Get data via direct service call (simulating resource)
        service_result = auth_status()

        # Deserialize if Pydantic model
        if hasattr(service_result, "model_dump"):
            service_data = service_result.model_dump()
        else:
            service_data = service_result

        # Compare data structures
        assert tool_data == service_data, \
            f"Data mismatch:\nTool: {tool_data}\nService: {service_data}"

    @pytest.mark.asyncio
    async def test_all_static_resources_parity(self):
        """Test all static resources for data consistency."""
        static_uris = [
            "auth://status",
            "auth://catalog/info",
            "permissions://discover",
        ]

        for uri in static_uris:
            result = await get_resource(uri)
            assert result.success is True, f"Resource {uri} failed: {result}"
            assert "data" in result.model_dump(), f"No data in {uri} response"
```

**Phase 1 Integration Test Coverage**: 4 static resources (auth x2, permissions x1, admin x1)

### 6.3 Performance Benchmark Framework

**Test File**: `tests/integration/test_resource_performance.py`

**Purpose**: Validate tool overhead stays within 10% budget

**Benchmark Approach**:

```python
import pytest
import time
from statistics import mean, stdev
from quilt_mcp.tools.resource_access import get_resource
from quilt_mcp.services.auth_metadata import auth_status


class TestResourcePerformance:
    """Benchmark tool performance vs direct service calls."""

    @pytest.mark.asyncio
    async def test_static_uri_overhead(self):
        """Measure overhead of tool vs direct service call."""
        iterations = 100

        # Benchmark direct service calls
        service_times = []
        for _ in range(iterations):
            start = time.perf_counter()
            result = auth_status()
            elapsed = time.perf_counter() - start
            service_times.append(elapsed)

        # Benchmark tool calls
        tool_times = []
        for _ in range(iterations):
            start = time.perf_counter()
            result = await get_resource("auth://status")
            elapsed = time.perf_counter() - start
            tool_times.append(elapsed)

        # Calculate overhead
        service_mean = mean(service_times)
        tool_mean = mean(tool_times)
        overhead_pct = ((tool_mean - service_mean) / service_mean) * 100

        print(f"\nService: {service_mean*1000:.2f}ms (±{stdev(service_times)*1000:.2f}ms)")
        print(f"Tool: {tool_mean*1000:.2f}ms (±{stdev(tool_times)*1000:.2f}ms)")
        print(f"Overhead: {overhead_pct:.1f}%")

        # Assert overhead within budget
        assert overhead_pct < 10.0, \
            f"Tool overhead {overhead_pct:.1f}% exceeds 10% budget"

    @pytest.mark.asyncio
    async def test_discovery_mode_performance(self):
        """Validate discovery mode completes within 500ms."""
        iterations = 10
        times = []

        for _ in range(iterations):
            start = time.perf_counter()
            result = await get_resource("")
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        avg_time = mean(times)
        print(f"\nDiscovery mode: {avg_time*1000:.2f}ms (±{stdev(times)*1000:.2f}ms)")

        assert avg_time < 0.5, \
            f"Discovery mode took {avg_time*1000:.2f}ms, exceeds 500ms budget"
```

**Phase 1 Benchmark Coverage**: 4 static resources + discovery mode

## 7. Integration Points

### 7.1 FastMCP Integration

**Registration Method**: Auto-discovery via `get_tool_modules()`

**Validation Steps**:

1. Verify tool appears in MCP introspection
2. Test tool invocation via FastMCP server
3. Validate response serialization through FastMCP
4. Confirm compatibility with stdio, HTTP, SSE transports

**Integration Test**:

```python
@pytest.mark.asyncio
async def test_fastmcp_registration():
    """Test tool registers correctly with FastMCP."""
    from quilt_mcp.main import mcp

    # Get tool list from MCP server
    tools = mcp.list_tools()
    tool_names = [t.name for t in tools]

    assert "get_resource" in tool_names, "get_resource tool not registered"

    # Verify tool schema
    tool = next(t for t in tools if t.name == "get_resource")
    assert "uri" in tool.inputSchema["properties"]
    assert tool.inputSchema["properties"]["uri"]["type"] == "string"
```

### 7.2 Resource System Integration

**Contract**: Read-only dependency on resources module

**Validation**:

- ✅ No modifications to `resources.py`
- ✅ No modifications to service function signatures
- ✅ No dependencies added to resources module
- ✅ Can import service functions directly

**Integration Test**:

```python
def test_resource_system_unchanged():
    """Verify resources module unchanged by tool implementation."""
    from quilt_mcp import resources

    # Verify key resources still defined
    assert hasattr(resources, "register_resources")

    # Verify can still import service functions
    from quilt_mcp.services.auth_metadata import auth_status
    assert callable(auth_status)
```

### 7.3 Service Layer Integration

**Service Functions Used in Phase 1**:

1. `quilt_mcp.services.auth_metadata.auth_status`
2. `quilt_mcp.services.auth_metadata.catalog_info`
3. `quilt_mcp.services.governance_service.admin_users_list`
4. `quilt_mcp.services.permissions_service.discover_permissions`
5. `quilt_mcp.services.metadata_service.get_metadata_template` (structure only)

**Integration Validation**:

```python
def test_service_function_imports():
    """Verify all Phase 1 service functions importable."""
    from quilt_mcp.services.auth_metadata import auth_status, catalog_info
    from quilt_mcp.services.governance_service import admin_users_list
    from quilt_mcp.services.permissions_service import discover_permissions
    from quilt_mcp.services.metadata_service import get_metadata_template

    # Verify all callable
    assert all(callable(f) for f in [
        auth_status,
        catalog_info,
        admin_users_list,
        discover_permissions,
        get_metadata_template,
    ])
```

## 8. Technology Choices and Justifications

### 8.1 AsyncIO for Service Function Invocation

**Choice**: Use `asyncio.to_thread()` for sync functions

**Alternatives Considered**:
- Run sync functions directly (simpler but blocks event loop)
- Use `concurrent.futures.ThreadPoolExecutor` (more complex, no benefit)

**Justification**:
- Matches existing pattern in `resources.py`
- Non-blocking for FastMCP async event loop
- Simple API, no additional dependencies
- Consistent with Python 3.12+ best practices

### 8.2 TypedDict for Registry Definitions

**Choice**: Use `TypedDict` for `ResourceDefinition`

**Alternatives Considered**:
- Pydantic model (runtime validation overhead)
- NamedTuple (less flexible for optional fields)
- Plain dict (no type safety)

**Justification**:
- Type safety with zero runtime overhead
- Perfect for internal data structures
- Excellent IDE support and type checking
- No serialization concerns (internal only)

### 8.3 Manual Registry for Phase 1

**Choice**: Manually construct registry for Phase 1

**Alternatives Considered**:
- Dynamic introspection of `resources.py` (complex, fragile)
- Parse `mcp-list.csv` (additional dependency)
- Code generation from resource definitions (over-engineering)

**Justification**:
- Simple and explicit
- Easy to validate and test
- Allows incremental addition of resources
- Clear upgrade path to automation in Phase 2+

### 8.4 Exception-Based Error Handling

**Choice**: Raise exceptions from ResourceManager, convert in tool function

**Alternatives Considered**:
- Return Result[T, E] type (requires additional dependency)
- Return error responses directly (couples manager to response models)
- Use Try/Except in every manager method (repetitive)

**Justification**:
- Clear separation of concerns (manager = routing, tool = response wrapping)
- Standard Python pattern
- Easy to test (can test exceptions separately)
- Consistent with existing codebase patterns

## 9. Risks and Mitigation

### 9.1 Phase 1-Specific Risks

**Risk: Service Function Signature Changes**

- **Impact**: High - Registry parameter mappings could become invalid
- **Likelihood**: Low - Service functions are stable
- **Mitigation**:
  - Comprehensive integration tests validate service calls
  - CI fails if service imports break
  - Type hints on service functions provide early warning

**Risk: Response Model Serialization Issues**

- **Impact**: Medium - Tool responses might not serialize correctly through FastMCP
- **Likelihood**: Medium - FastMCP serialization can be finicky
- **Mitigation**:
  - Extensive unit tests for response models
  - Integration tests through actual FastMCP server
  - Follow established response model patterns

**Risk: Authentication Context Not Propagated**

- **Impact**: High - Admin resources would fail incorrectly
- **Likelihood**: Low - Runtime context is well-established
- **Mitigation**:
  - Test with both authenticated and unauthenticated states
  - Test admin resources explicitly
  - Validate error messages match resource behavior

### 9.2 Technical Debt Accepted in Phase 1

**Debt Item 1: Manual Registry**
- **Debt**: Registry must be manually updated when resources added
- **Cost**: Maintenance burden, risk of drift
- **Payoff Date**: Phase 3 (automation)
- **Justification**: Allows validation of architecture before investing in automation

**Debt Item 2: No Template URI Support**
- **Debt**: Template resources not fully functional
- **Cost**: Limited feature set, requires Phase 2
- **Payoff Date**: Phase 2 (template implementation)
- **Justification**: Validates architecture with simpler static case first

**Debt Item 3: Simple Manager Initialization**
- **Debt**: New ResourceManager created on each tool call
- **Cost**: Minor performance overhead
- **Payoff Date**: Phase 2 (singleton or caching)
- **Justification**: Simplifies Phase 1, overhead negligible, can optimize later

## 10. Success Criteria and Validation

### 10.1 Phase 1 Success Criteria

**Functional Criteria**:

1. ✅ All response models defined and tested
2. ✅ ResourceManager handles 4 static resources correctly
3. ✅ Discovery mode returns complete metadata for 5 resources
4. ✅ Tool function wraps responses correctly
5. ✅ Error handling covers all Phase 1 error cases
6. ✅ Integration with FastMCP validated

**Quality Criteria**:

1. ✅ Unit test coverage >90%
2. ✅ Integration tests pass for all 4 static resources
3. ✅ Performance benchmarks within budget (<10% overhead)
4. ✅ No regressions in existing resource functionality
5. ✅ Lint and type checks pass
6. ✅ Documentation complete

**Process Criteria**:

1. ✅ All tests pass in CI
2. ✅ Code review completed
3. ✅ Phase 1 design approved
4. ✅ Ready for Phase 2 design

### 10.2 Validation Checklist

- [ ] Response models defined in `models/responses.py`
- [ ] Response model unit tests pass
- [ ] ResourceManager class implemented
- [ ] ResourceManager unit tests pass
- [ ] Registry constructed with 5 resources
- [ ] Registry validation tests pass
- [ ] Tool function implemented with comprehensive docstring
- [ ] Tool function unit tests pass
- [ ] Integration tests validate data parity (4 resources)
- [ ] Performance benchmarks within budget
- [ ] FastMCP registration validated
- [ ] Service layer integration validated
- [ ] Manual testing in Claude Desktop successful
- [ ] All quality gates pass
- [ ] Phase 1 checklist completed

### 10.3 Ready for Phase 2 Criteria

**Prerequisites for Phase 2**:

1. ✅ Phase 1 merged to main branch
2. ✅ All Phase 1 tests passing in CI
3. ✅ Phase 1 design patterns validated
4. ✅ Performance baseline established
5. ✅ No blocking issues identified

**Phase 2 Preparation**:

- Document lessons learned from Phase 1
- Identify optimization opportunities
- Plan template URI implementation strategy
- Design remaining resource additions

## 11. Future Considerations

### 11.1 Phase 2 Preview

**Phase 2 Objectives**:

1. Implement template URI expansion and variable extraction
2. Add remaining 14 resources to registry
3. Optimize ResourceManager (singleton, caching)
4. Enhance error messages with fuzzy URI matching
5. Complete integration test coverage (19/19 resources)

**Phase 2 Dependencies**:

- Phase 1 architecture validated
- Performance baseline established
- Template parsing strategy decided

### 11.2 Extensibility Considerations

**Architecture Extensibility**:

- Registry structure supports easy addition of new resources
- ResourceManager can be extended with new dispatch strategies
- Response models can add optional fields without breaking clients
- Error handling framework supports new error types

**Future Enhancement Hooks**:

- Registry could be generated from resource introspection
- Discovery mode could cache results
- Performance monitoring could be instrumented
- Batch resource access could reuse infrastructure

---

## Appendix A: File Changes Summary

### Files to Create

1. `src/quilt_mcp/tools/resource_access.py` (~300 lines)
   - ResourceManager class
   - Resource registry (5 entries)
   - get_resource() tool function

2. `tests/unit/tools/test_resource_access.py` (~400 lines)
   - Response model tests
   - ResourceManager tests
   - Registry validation tests
   - Tool function tests

3. `tests/integration/test_resource_parity.py` (~200 lines)
   - Data consistency tests (4 resources)

4. `tests/integration/test_resource_performance.py` (~150 lines)
   - Performance benchmarks

### Files to Modify

1. `src/quilt_mcp/models/responses.py` (~80 lines added)
   - GetResourceSuccess model
   - GetResourceError model
   - ResourceMetadata model
   - ResourceDefinition TypedDict

### Files to Validate (No Changes)

1. `src/quilt_mcp/resources.py` - Ensure no modifications
2. `src/quilt_mcp/services/*.py` - Verify service functions unchanged

---

## Appendix B: Testing Checklist

### Unit Tests

- [ ] Response model serialization
- [ ] Response model dict-like access
- [ ] ResourceManager static URI lookup
- [ ] ResourceManager discovery mode
- [ ] ResourceManager service invocation (sync)
- [ ] ResourceManager service invocation (async)
- [ ] ResourceManager error handling (invalid URI)
- [ ] ResourceManager error handling (not found)
- [ ] Registry validation (structure)
- [ ] Registry validation (template consistency)
- [ ] Tool function success response
- [ ] Tool function error response
- [ ] Tool function discovery mode
- [ ] Tool function authorization errors

### Integration Tests

- [ ] auth://status parity test
- [ ] auth://catalog/info parity test
- [ ] permissions://discover parity test
- [ ] admin://users parity test (with auth)
- [ ] FastMCP registration test
- [ ] Service layer integration test

### Performance Tests

- [ ] Static URI overhead benchmark
- [ ] Discovery mode performance benchmark
- [ ] Service function invocation benchmark

### Manual Tests

- [ ] Claude Desktop: Discovery mode
- [ ] Claude Desktop: Static resource access
- [ ] Claude Desktop: Invalid URI error
- [ ] Claude Desktop: Tool documentation visible

---

**Document Status**: ✅ Complete - Ready for Human Review

**Approval Gate**: Human review required before proceeding to episodes breakdown (07-phase1-episodes.md)
