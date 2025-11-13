<!-- markdownlint-disable MD013 -->
# Phase 1 Episodes: Atomic Change Units

**Issue Reference**: GitHub Issue #233 - get-resource tool
**Branch**: `233-get-resource-tool`
**Phase**: 1 of 3
**Status**: Episodes Breakdown

## References

This episodes document breaks down Phase 1 implementation based on:

- **Design**: [06-phase1-design.md](./06-phase1-design.md) - Technical architecture and implementation strategy
- **Specifications**: [03-specifications.md](./03-specifications.md) - Desired end state and technical contracts
- **Phases**: [04-phases.md](./04-phases.md) - Phase 1 objectives and success criteria

## Episode Overview

Phase 1 is broken down into **7 atomic episodes**, each representing a single, testable, committable change. Each episode follows TDD (Test-Driven Development) cycle:

1. **Red**: Write failing tests first
2. **Green**: Implement minimum code to pass tests
3. **Refactor**: Improve code while keeping tests green
4. **Commit**: Push working episode to branch

**Episode Sequencing Strategy**:

- Foundation first (types, models)
- Core orchestration second (ResourceManager)
- Registry infrastructure third (validation, static resources)
- Tool wrapper fourth (integration point)
- Testing infrastructure last (validation and benchmarks)

## Episode 1: Response Models Foundation

**Objective**: Define all Pydantic response models for tool interface

**Success Criteria**:
- ✅ GetResourceSuccess model defined with all required fields
- ✅ GetResourceError model defined with all required fields
- ✅ ResourceMetadata model defined for discovery mode
- ✅ All models serialize/deserialize correctly
- ✅ Dict-like access compatibility validated
- ✅ Unit tests achieve >95% coverage for models

**TDD Cycle**:

### Red: Write Failing Tests

Create `tests/unit/models/test_resource_responses.py`:

```python
"""Tests for resource access response models."""

import pytest
from datetime import datetime
from quilt_mcp.models.responses import (
    GetResourceSuccess,
    GetResourceError,
    ResourceMetadata,
)


class TestGetResourceSuccess:
    """Test GetResourceSuccess model."""

    def test_create_success_response(self):
        """Test creating a valid success response."""
        response = GetResourceSuccess(
            uri="auth://status",
            resource_name="Auth Status",
            data={"authenticated": True, "catalog_url": "https://example.com"},
            timestamp=datetime.utcnow(),
            mime_type="application/json",
        )

        assert response.success is True
        assert response.uri == "auth://status"
        assert response.resource_name == "Auth Status"
        assert response.data["authenticated"] is True
        assert response.mime_type == "application/json"
        assert isinstance(response.timestamp, datetime)

    def test_dict_like_access(self):
        """Test dict-like access compatibility."""
        response = GetResourceSuccess(
            uri="auth://status",
            resource_name="Auth Status",
            data={"key": "value"},
        )

        # Dict-like access (from DictAccessibleModel)
        assert response["uri"] == "auth://status"
        assert response["data"]["key"] == "value"
        assert "resource_name" in response

    def test_model_dump_serialization(self):
        """Test model serialization to dict."""
        response = GetResourceSuccess(
            uri="auth://status",
            resource_name="Auth Status",
            data={"test": "data"},
        )

        dumped = response.model_dump()
        assert dumped["success"] is True
        assert dumped["uri"] == "auth://status"
        assert "timestamp" in dumped
        assert isinstance(dumped, dict)

    def test_default_mime_type(self):
        """Test default mime_type is application/json."""
        response = GetResourceSuccess(
            uri="auth://status",
            resource_name="Test",
            data={},
        )

        assert response.mime_type == "application/json"


class TestGetResourceError:
    """Test GetResourceError model."""

    def test_create_error_response(self):
        """Test creating a valid error response."""
        response = GetResourceError(
            error="InvalidURI",
            cause="Resource URI not recognized",
            suggested_actions=["Check URI format", "Call discovery mode"],
            valid_uris=["auth://status", "auth://catalog/info"],
        )

        assert response.success is False
        assert response.error == "InvalidURI"
        assert response.cause == "Resource URI not recognized"
        assert len(response.suggested_actions) == 2
        assert len(response.valid_uris) == 2

    def test_optional_valid_uris(self):
        """Test valid_uris is optional."""
        response = GetResourceError(
            error="ResourceExecutionError",
            cause="Service failed",
            suggested_actions=["Retry operation"],
        )

        assert response.valid_uris is None

    def test_dict_like_access(self):
        """Test dict-like access for error response."""
        response = GetResourceError(
            error="InvalidURI",
            cause="Test error",
            suggested_actions=["Action 1"],
        )

        assert response["error"] == "InvalidURI"
        assert response["success"] is False
        assert "suggested_actions" in response


class TestResourceMetadata:
    """Test ResourceMetadata model."""

    def test_create_static_resource_metadata(self):
        """Test metadata for static (non-template) resource."""
        metadata = ResourceMetadata(
            uri="auth://status",
            name="Auth Status",
            description="Check authentication status",
            is_template=False,
            template_variables=[],
            requires_admin=False,
            category="auth",
        )

        assert metadata.uri == "auth://status"
        assert metadata.is_template is False
        assert len(metadata.template_variables) == 0
        assert metadata.requires_admin is False
        assert metadata.category == "auth"

    def test_create_template_resource_metadata(self):
        """Test metadata for template resource."""
        metadata = ResourceMetadata(
            uri="metadata://templates/{template}",
            name="Metadata Template",
            description="Get specific metadata template",
            is_template=True,
            template_variables=["template"],
            requires_admin=False,
            category="metadata",
        )

        assert metadata.is_template is True
        assert metadata.template_variables == ["template"]
        assert "{template}" in metadata.uri

    def test_admin_resource_metadata(self):
        """Test metadata for admin-only resource."""
        metadata = ResourceMetadata(
            uri="admin://users",
            name="Admin Users List",
            description="List all users (requires admin)",
            is_template=False,
            template_variables=[],
            requires_admin=True,
            category="admin",
        )

        assert metadata.requires_admin is True
        assert metadata.category == "admin"

    def test_default_template_variables(self):
        """Test default empty list for template_variables."""
        metadata = ResourceMetadata(
            uri="auth://status",
            name="Test",
            description="Test resource",
            is_template=False,
            requires_admin=False,
            category="auth",
        )

        assert metadata.template_variables == []
```

**Expected Result**: All tests fail (models don't exist yet)

### Green: Implement Models

Add to `src/quilt_mcp/models/responses.py`:

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

**Expected Result**: All tests pass

### Refactor: Documentation and Type Hints

- Add comprehensive docstrings
- Verify type hints are complete
- Ensure consistent field ordering
- Validate inheritance from base models

### Commit

```bash
git add src/quilt_mcp/models/responses.py tests/unit/models/test_resource_responses.py
git commit -m "feat(models): add resource access response models

- Add GetResourceSuccess model for successful resource access
- Add GetResourceError model with actionable error guidance
- Add ResourceMetadata model for discovery mode
- Extend from existing SuccessResponse/ErrorResponse base models
- Include comprehensive unit tests with >95% coverage

Phase 1, Episode 1
"
```

**Dependencies**: None (foundation layer)
**Blocks**: Episodes 2-7 (all depend on response models)

---

## Episode 2: ResourceDefinition Type

**Objective**: Define internal TypedDict for registry entries

**Success Criteria**:
- ✅ ResourceDefinition TypedDict defined with all required fields
- ✅ Type hints accurate for service functions and mappings
- ✅ Validation function catches malformed definitions
- ✅ Unit tests validate type structure

**TDD Cycle**:

### Red: Write Failing Tests

Create `tests/unit/tools/test_resource_registry.py`:

```python
"""Tests for resource registry structure and validation."""

import pytest
from typing import get_type_hints
from quilt_mcp.tools.resource_access import (
    ResourceDefinition,
    validate_registry,
)


class TestResourceDefinitionType:
    """Test ResourceDefinition TypedDict structure."""

    def test_resource_definition_fields(self):
        """Test ResourceDefinition has all required fields."""
        # Get type hints from ResourceDefinition
        hints = get_type_hints(ResourceDefinition)

        required_fields = {
            "uri",
            "name",
            "description",
            "service_function",
            "is_async",
            "is_template",
            "template_variables",
            "requires_admin",
            "category",
            "parameter_mapping",
        }

        assert set(hints.keys()) == required_fields


class TestRegistryValidation:
    """Test registry validation function."""

    def test_valid_static_resource(self):
        """Test validation passes for valid static resource."""
        def mock_service():
            return {"test": "data"}

        registry = {
            "auth://status": {
                "uri": "auth://status",
                "name": "Auth Status",
                "description": "Test resource",
                "service_function": mock_service,
                "is_async": False,
                "is_template": False,
                "template_variables": [],
                "requires_admin": False,
                "category": "auth",
                "parameter_mapping": {},
            }
        }

        # Should not raise
        validate_registry(registry)

    def test_uri_mismatch_raises_error(self):
        """Test validation fails when key doesn't match uri."""
        def mock_service():
            return {}

        registry = {
            "auth://wrong": {
                "uri": "auth://correct",
                "name": "Test",
                "description": "Test",
                "service_function": mock_service,
                "is_async": False,
                "is_template": False,
                "template_variables": [],
                "requires_admin": False,
                "category": "auth",
                "parameter_mapping": {},
            }
        }

        with pytest.raises(ValueError, match="URI mismatch"):
            validate_registry(registry)

    def test_non_callable_service_function_raises_error(self):
        """Test validation fails for non-callable service function."""
        registry = {
            "auth://status": {
                "uri": "auth://status",
                "name": "Test",
                "description": "Test",
                "service_function": "not_callable",  # Invalid
                "is_async": False,
                "is_template": False,
                "template_variables": [],
                "requires_admin": False,
                "category": "auth",
                "parameter_mapping": {},
            }
        }

        with pytest.raises(ValueError, match="not callable"):
            validate_registry(registry)

    def test_template_flag_inconsistent_with_uri(self):
        """Test validation fails when template flag doesn't match URI."""
        def mock_service():
            return {}

        # URI has braces but is_template is False
        registry = {
            "test://{var}": {
                "uri": "test://{var}",
                "name": "Test",
                "description": "Test",
                "service_function": mock_service,
                "is_async": False,
                "is_template": False,  # Inconsistent!
                "template_variables": ["var"],
                "requires_admin": False,
                "category": "test",
                "parameter_mapping": {"var": "var"},
            }
        }

        with pytest.raises(ValueError, match="Template flag inconsistent"):
            validate_registry(registry)

    def test_template_missing_variables_list(self):
        """Test validation fails when template has empty variables list."""
        def mock_service():
            return {}

        registry = {
            "test://{var}": {
                "uri": "test://{var}",
                "name": "Test",
                "description": "Test",
                "service_function": mock_service,
                "is_async": False,
                "is_template": True,
                "template_variables": [],  # Empty but should have ["var"]
                "requires_admin": False,
                "category": "test",
                "parameter_mapping": {},
            }
        }

        with pytest.raises(ValueError, match="missing variable list"):
            validate_registry(registry)

    def test_template_missing_parameter_mapping(self):
        """Test validation fails when template variable not in mapping."""
        def mock_service():
            return {}

        registry = {
            "test://{var}": {
                "uri": "test://{var}",
                "name": "Test",
                "description": "Test",
                "service_function": mock_service,
                "is_async": False,
                "is_template": True,
                "template_variables": ["var"],
                "requires_admin": False,
                "category": "test",
                "parameter_mapping": {},  # Missing "var"
            }
        }

        with pytest.raises(ValueError, match="not in parameter mapping"):
            validate_registry(registry)

    def test_valid_template_resource(self):
        """Test validation passes for valid template resource."""
        def mock_service(name: str):
            return {"name": name}

        registry = {
            "test://{var}": {
                "uri": "test://{var}",
                "name": "Test",
                "description": "Test resource",
                "service_function": mock_service,
                "is_async": False,
                "is_template": True,
                "template_variables": ["var"],
                "requires_admin": False,
                "category": "test",
                "parameter_mapping": {"var": "name"},
            }
        }

        # Should not raise
        validate_registry(registry)
```

**Expected Result**: All tests fail (TypedDict and validation function don't exist)

### Green: Implement TypedDict and Validation

Create `src/quilt_mcp/tools/resource_access.py`:

```python
"""Resource access tool implementation."""

from typing import Any, Callable, TypedDict


class ResourceDefinition(TypedDict):
    """Definition of a single resource in the registry."""

    uri: str  # URI pattern (may contain {variables})
    name: str  # Human-readable name
    description: str  # Functional description
    service_function: Callable[..., Any]  # Function to invoke
    is_async: bool  # Whether service function is async
    is_template: bool  # Whether URI contains variables
    template_variables: list[str]  # Variable names (empty if not templated)
    requires_admin: bool  # Whether admin privileges required
    category: str  # Resource category
    parameter_mapping: dict[str, str]  # URI variable → function parameter


def validate_registry(registry: dict[str, ResourceDefinition]) -> None:
    """Validate registry structure and consistency.

    Args:
        registry: URI → ResourceDefinition mapping

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
                    raise ValueError(
                        f"Template variable not in parameter mapping: {var} in {uri}"
                    )
```

**Expected Result**: All tests pass

### Refactor: Type Hints and Documentation

- Add comprehensive docstrings
- Verify type hints are complete
- Ensure validation error messages are clear

### Commit

```bash
git add src/quilt_mcp/tools/resource_access.py tests/unit/tools/test_resource_registry.py
git commit -m "feat(tools): add resource registry type definitions

- Add ResourceDefinition TypedDict for registry entries
- Implement validate_registry() with comprehensive checks
- Validate URI consistency, template flags, and mappings
- Include unit tests for all validation scenarios

Phase 1, Episode 2
"
```

**Dependencies**: Episode 1 (uses response models in tests)
**Blocks**: Episodes 3-7 (ResourceManager depends on ResourceDefinition)

---

## Episode 3: Resource Registry Construction

**Objective**: Build registry with 5 representative Phase 1 resources

**Success Criteria**:
- ✅ Registry constructed with 5 resources (4 static, 1 template)
- ✅ All service functions importable
- ✅ Registry passes validation checks
- ✅ Categories correctly assigned
- ✅ Admin flags accurate
- ✅ Unit tests validate registry structure

**TDD Cycle**:

### Red: Write Failing Tests

Add to `tests/unit/tools/test_resource_registry.py`:

```python
from quilt_mcp.tools.resource_access import RESOURCE_REGISTRY


class TestResourceRegistry:
    """Test RESOURCE_REGISTRY structure and content."""

    def test_registry_exists(self):
        """Test RESOURCE_REGISTRY is defined."""
        assert RESOURCE_REGISTRY is not None
        assert isinstance(RESOURCE_REGISTRY, dict)

    def test_registry_has_phase1_resources(self):
        """Test registry contains Phase 1 resources."""
        expected_uris = [
            "auth://status",
            "auth://catalog/info",
            "admin://users",
            "permissions://discover",
            "metadata://templates/{template}",
        ]

        for uri in expected_uris:
            assert uri in RESOURCE_REGISTRY, f"Missing resource: {uri}"

    def test_registry_validates_successfully(self):
        """Test registry passes validation checks."""
        # Should not raise
        validate_registry(RESOURCE_REGISTRY)

    def test_static_resources_correctly_marked(self):
        """Test static resources have is_template=False."""
        static_uris = [
            "auth://status",
            "auth://catalog/info",
            "admin://users",
            "permissions://discover",
        ]

        for uri in static_uris:
            assert RESOURCE_REGISTRY[uri]["is_template"] is False
            assert len(RESOURCE_REGISTRY[uri]["template_variables"]) == 0

    def test_template_resource_correctly_marked(self):
        """Test template resource has is_template=True."""
        uri = "metadata://templates/{template}"

        assert RESOURCE_REGISTRY[uri]["is_template"] is True
        assert "template" in RESOURCE_REGISTRY[uri]["template_variables"]
        assert "template" in RESOURCE_REGISTRY[uri]["parameter_mapping"]

    def test_admin_resource_requires_admin(self):
        """Test admin resource has requires_admin=True."""
        assert RESOURCE_REGISTRY["admin://users"]["requires_admin"] is True

    def test_non_admin_resources_accessible(self):
        """Test non-admin resources have requires_admin=False."""
        non_admin_uris = [
            "auth://status",
            "auth://catalog/info",
            "permissions://discover",
            "metadata://templates/{template}",
        ]

        for uri in non_admin_uris:
            assert RESOURCE_REGISTRY[uri]["requires_admin"] is False

    def test_categories_assigned(self):
        """Test all resources have valid categories."""
        category_map = {
            "auth://status": "auth",
            "auth://catalog/info": "auth",
            "admin://users": "admin",
            "permissions://discover": "permissions",
            "metadata://templates/{template}": "metadata",
        }

        for uri, expected_category in category_map.items():
            assert RESOURCE_REGISTRY[uri]["category"] == expected_category

    def test_service_functions_callable(self):
        """Test all service functions are callable."""
        for uri, defn in RESOURCE_REGISTRY.items():
            assert callable(defn["service_function"]), \
                f"Service function not callable: {uri}"

    def test_async_flags_accurate(self):
        """Test async flags match actual service functions."""
        # admin_users_list is async, others are sync
        assert RESOURCE_REGISTRY["admin://users"]["is_async"] is True

        sync_uris = [
            "auth://status",
            "auth://catalog/info",
            "permissions://discover",
            "metadata://templates/{template}",
        ]

        for uri in sync_uris:
            assert RESOURCE_REGISTRY[uri]["is_async"] is False
```

**Expected Result**: All tests fail (registry not constructed yet)

### Green: Implement Registry

Add to `src/quilt_mcp/tools/resource_access.py`:

```python
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
        "is_async": True,
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

# Validate registry at module initialization
validate_registry(RESOURCE_REGISTRY)
```

**Expected Result**: All tests pass

### Refactor: Service Import Organization

- Organize imports by service module
- Add comments explaining resource selection
- Verify all imports resolve correctly

### Commit

```bash
git add src/quilt_mcp/tools/resource_access.py tests/unit/tools/test_resource_registry.py
git commit -m "feat(tools): build Phase 1 resource registry

- Add 5 representative resources (4 static, 1 template)
- Include auth, admin, permissions, metadata categories
- Import and validate all service functions
- Run validation on module initialization
- Comprehensive tests for registry structure

Resources:
- auth://status (static, auth)
- auth://catalog/info (static, auth)
- admin://users (static, admin, requires admin)
- permissions://discover (static, permissions)
- metadata://templates/{template} (template, metadata)

Phase 1, Episode 3
"
```

**Dependencies**: Episode 2 (uses ResourceDefinition and validate_registry)
**Blocks**: Episodes 4-7 (ResourceManager depends on registry)

---

## Episode 4: ResourceManager Core Implementation

**Objective**: Implement ResourceManager class with static URI dispatch

**Success Criteria**:
- ✅ ResourceManager class defined with constructor
- ✅ Static URI lookup implemented (O(1) dict lookup)
- ✅ Service function invocation handles async/sync correctly
- ✅ Pydantic model deserialization working
- ✅ Discovery mode returns structured metadata
- ✅ Unit tests cover all core functionality

**TDD Cycle**:

### Red: Write Failing Tests

Create `tests/unit/tools/test_resource_manager.py`:

```python
"""Tests for ResourceManager class."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from quilt_mcp.tools.resource_access import (
    ResourceManager,
    ResourceDefinition,
    RESOURCE_REGISTRY,
)


class TestResourceManagerInit:
    """Test ResourceManager initialization."""

    def test_init_with_registry(self):
        """Test ResourceManager initializes with registry."""
        manager = ResourceManager(RESOURCE_REGISTRY)

        assert manager is not None
        assert manager._registry == RESOURCE_REGISTRY

    def test_static_uris_filtered(self):
        """Test static URIs are pre-filtered for fast lookup."""
        manager = ResourceManager(RESOURCE_REGISTRY)

        # Should contain 4 static resources
        assert len(manager._static_uris) == 4
        assert "auth://status" in manager._static_uris
        assert "admin://users" in manager._static_uris

        # Should NOT contain template resource
        assert "metadata://templates/{template}" not in manager._static_uris


class TestResourceManagerStaticLookup:
    """Test static URI lookup."""

    @pytest.fixture
    def manager(self):
        """Create ResourceManager instance."""
        return ResourceManager(RESOURCE_REGISTRY)

    @pytest.mark.asyncio
    async def test_static_uri_lookup_success(self, manager):
        """Test successful static URI lookup."""
        result = await manager.get_resource("auth://status")

        assert "uri" in result
        assert result["uri"] == "auth://status"
        assert "resource_name" in result
        assert "data" in result
        assert "mime_type" in result

    @pytest.mark.asyncio
    async def test_invalid_uri_format_raises_value_error(self, manager):
        """Test invalid URI format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid URI format"):
            await manager.get_resource("invalid-no-scheme")

    @pytest.mark.asyncio
    async def test_unknown_uri_raises_key_error(self, manager):
        """Test unknown URI raises KeyError."""
        with pytest.raises(KeyError, match="not recognized"):
            await manager.get_resource("unknown://resource")

    @pytest.mark.asyncio
    async def test_template_uri_raises_key_error_phase1(self, manager):
        """Test template URI raises KeyError in Phase 1."""
        # Phase 1: Template URIs not supported yet
        with pytest.raises(KeyError):
            await manager.get_resource("metadata://templates/{template}")


class TestResourceManagerServiceInvocation:
    """Test service function invocation."""

    @pytest.mark.asyncio
    async def test_sync_service_function_invocation(self):
        """Test sync service function called via asyncio.to_thread."""
        def mock_sync_service():
            return {"test": "data"}

        registry = {
            "test://sync": {
                "uri": "test://sync",
                "name": "Test",
                "description": "Test",
                "service_function": mock_sync_service,
                "is_async": False,
                "is_template": False,
                "template_variables": [],
                "requires_admin": False,
                "category": "test",
                "parameter_mapping": {},
            }
        }

        manager = ResourceManager(registry)
        result = await manager.get_resource("test://sync")

        assert result["data"]["test"] == "data"

    @pytest.mark.asyncio
    async def test_async_service_function_invocation(self):
        """Test async service function called directly."""
        async def mock_async_service():
            return {"async": "data"}

        registry = {
            "test://async": {
                "uri": "test://async",
                "name": "Test",
                "description": "Test",
                "service_function": mock_async_service,
                "is_async": True,
                "is_template": False,
                "template_variables": [],
                "requires_admin": False,
                "category": "test",
                "parameter_mapping": {},
            }
        }

        manager = ResourceManager(registry)
        result = await manager.get_resource("test://async")

        assert result["data"]["async"] == "data"

    @pytest.mark.asyncio
    async def test_pydantic_model_deserialization(self):
        """Test Pydantic model result is deserialized to dict."""
        from pydantic import BaseModel

        class MockResponse(BaseModel):
            field1: str
            field2: int

        def mock_service():
            return MockResponse(field1="value", field2=42)

        registry = {
            "test://pydantic": {
                "uri": "test://pydantic",
                "name": "Test",
                "description": "Test",
                "service_function": mock_service,
                "is_async": False,
                "is_template": False,
                "template_variables": [],
                "requires_admin": False,
                "category": "test",
                "parameter_mapping": {},
            }
        }

        manager = ResourceManager(registry)
        result = await manager.get_resource("test://pydantic")

        # Should be deserialized to dict
        assert isinstance(result["data"], dict)
        assert result["data"]["field1"] == "value"
        assert result["data"]["field2"] == 42

    @pytest.mark.asyncio
    async def test_dict_result_pass_through(self):
        """Test dict result passes through unchanged."""
        def mock_service():
            return {"key": "value"}

        registry = {
            "test://dict": {
                "uri": "test://dict",
                "name": "Test",
                "description": "Test",
                "service_function": mock_service,
                "is_async": False,
                "is_template": False,
                "template_variables": [],
                "requires_admin": False,
                "category": "test",
                "parameter_mapping": {},
            }
        }

        manager = ResourceManager(registry)
        result = await manager.get_resource("test://dict")

        assert result["data"] == {"key": "value"}


class TestResourceManagerDiscoveryMode:
    """Test discovery mode functionality."""

    @pytest.fixture
    def manager(self):
        """Create ResourceManager instance."""
        return ResourceManager(RESOURCE_REGISTRY)

    @pytest.mark.asyncio
    async def test_discovery_mode_empty_string(self, manager):
        """Test empty string triggers discovery mode."""
        result = await manager.get_discovery_data()

        assert isinstance(result, dict)
        assert "auth" in result
        assert "admin" in result
        assert "permissions" in result
        assert "metadata" in result

    @pytest.mark.asyncio
    async def test_discovery_mode_none(self, manager):
        """Test None triggers discovery mode."""
        result = await manager.get_resource(None)

        # Should return discovery data structure
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_discovery_data_structure(self, manager):
        """Test discovery mode returns correct data structure."""
        result = await manager.get_discovery_data()

        # Check auth category
        auth_resources = result["auth"]
        assert len(auth_resources) == 2
        assert all(hasattr(r, "uri") for r in auth_resources)
        assert all(hasattr(r, "name") for r in auth_resources)
        assert all(r.category == "auth" for r in auth_resources)

    @pytest.mark.asyncio
    async def test_discovery_includes_template_resources(self, manager):
        """Test discovery mode includes template resources."""
        result = await manager.get_discovery_data()

        metadata_resources = result["metadata"]
        assert len(metadata_resources) == 1

        template_resource = metadata_resources[0]
        assert template_resource.is_template is True
        assert "template" in template_resource.template_variables

    @pytest.mark.asyncio
    async def test_discovery_resources_sorted_by_uri(self, manager):
        """Test resources within category are sorted by URI."""
        result = await manager.get_discovery_data()

        auth_uris = [r.uri for r in result["auth"]]
        assert auth_uris == sorted(auth_uris)
```

**Expected Result**: All tests fail (ResourceManager not implemented)

### Green: Implement ResourceManager

Add to `src/quilt_mcp/tools/resource_access.py`:

```python
import asyncio
from typing import Any, Optional
from quilt_mcp.models.responses import ResourceMetadata


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

    async def get_discovery_data(self) -> dict[str, list[ResourceMetadata]]:
        """Generate discovery mode response.

        Returns:
            Dict mapping category → list of ResourceMetadata
        """
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

**Expected Result**: All tests pass

### Refactor: Error Handling and Type Hints

- Improve error messages
- Verify type hints are complete
- Add detailed docstrings
- Extract helper methods if needed

### Commit

```bash
git add src/quilt_mcp/tools/resource_access.py tests/unit/tools/test_resource_manager.py
git commit -m "feat(tools): implement ResourceManager core functionality

- Add ResourceManager class with static URI dispatch
- Implement O(1) static URI lookup with pre-filtered dict
- Handle async/sync service function invocation
- Support Pydantic model deserialization
- Implement discovery mode with category grouping
- Comprehensive unit tests with >95% coverage

Phase 1, Episode 4
"
```

**Dependencies**: Episodes 1-3 (uses models, types, and registry)
**Blocks**: Episodes 5-7 (tool wrapper depends on ResourceManager)

---

## Episode 5: Tool Wrapper Function

**Objective**: Implement get_resource() tool function with error handling

**Success Criteria**:
- ✅ get_resource() function defined with FastMCP signature
- ✅ Success responses wrapped correctly
- ✅ All error cases handled with actionable guidance
- ✅ Discovery mode triggered by empty string
- ✅ Authorization errors detected and formatted
- ✅ Similar URI suggestions implemented
- ✅ Comprehensive docstring (100+ lines)
- ✅ Unit tests cover all error paths

**TDD Cycle**:

### Red: Write Failing Tests

Create `tests/unit/tools/test_get_resource_tool.py`:

```python
"""Tests for get_resource tool function."""

import pytest
from unittest.mock import AsyncMock, patch
from quilt_mcp.tools.resource_access import get_resource
from quilt_mcp.models.responses import (
    GetResourceSuccess,
    GetResourceError,
)


class TestGetResourceSuccess:
    """Test successful get_resource calls."""

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
        assert result.success is True
        assert result.uri == "auth://status"
        assert result.resource_name == "Auth Status"
        assert "data" in result.model_dump()
        assert result.mime_type == "application/json"

    @pytest.mark.asyncio
    async def test_all_phase1_static_resources_accessible(self):
        """Test all Phase 1 static resources are accessible."""
        static_uris = [
            "auth://status",
            "auth://catalog/info",
            "permissions://discover",
        ]

        for uri in static_uris:
            result = await get_resource(uri)
            assert isinstance(result, GetResourceSuccess)
            assert result.uri == uri


class TestGetResourceErrors:
    """Test error handling in get_resource."""

    @pytest.mark.asyncio
    async def test_invalid_uri_format(self):
        """Test invalid URI format returns error."""
        result = await get_resource("invalid-no-scheme")

        assert isinstance(result, GetResourceError)
        assert result.success is False
        assert result.error == "InvalidURI"
        assert "Invalid URI format" in result.cause
        assert len(result.suggested_actions) > 0
        assert result.valid_uris is not None

    @pytest.mark.asyncio
    async def test_unknown_uri(self):
        """Test unknown URI returns error with suggestions."""
        result = await get_resource("unknown://resource")

        assert isinstance(result, GetResourceError)
        assert result.success is False
        assert result.error == "InvalidURI"
        assert "not recognized" in result.cause
        assert len(result.suggested_actions) > 0
        assert result.valid_uris is not None

    @pytest.mark.asyncio
    async def test_similar_uri_suggestions(self):
        """Test similar URI suggestions for typos."""
        result = await get_resource("auth://wrong")

        assert isinstance(result, GetResourceError)
        assert result.error == "InvalidURI"
        # Should suggest URIs starting with "auth://"
        assert any("auth://" in action for action in result.suggested_actions)

    @pytest.mark.asyncio
    async def test_template_uri_not_supported_phase1(self):
        """Test template URI returns error in Phase 1."""
        result = await get_resource("metadata://templates/{template}")

        assert isinstance(result, GetResourceError)
        assert result.success is False


class TestGetResourceAuthorization:
    """Test authorization error handling."""

    @pytest.mark.asyncio
    async def test_admin_resource_unauthorized(self):
        """Test admin resource returns authorization error when not authorized."""
        # Mock service to raise authorization error
        with patch("quilt_mcp.services.governance_service.admin_users_list") as mock:
            mock.side_effect = RuntimeError("Unauthorized: 403")

            result = await get_resource("admin://users")

            assert isinstance(result, GetResourceError)
            assert result.error == "Unauthorized"
            assert "admin privileges" in result.cause
            assert any("admin" in action for action in result.suggested_actions)


class TestGetResourceDocumentation:
    """Test tool function documentation."""

    def test_function_has_docstring(self):
        """Test get_resource has comprehensive docstring."""
        assert get_resource.__doc__ is not None
        assert len(get_resource.__doc__) > 500  # At least 500 characters

    def test_docstring_includes_examples(self):
        """Test docstring includes usage examples."""
        doc = get_resource.__doc__
        assert "Examples:" in doc or "Example:" in doc

    def test_docstring_includes_discovery_mode(self):
        """Test docstring explains discovery mode."""
        doc = get_resource.__doc__
        assert "Discovery" in doc or "discovery" in doc

    def test_docstring_includes_error_handling(self):
        """Test docstring explains error handling."""
        doc = get_resource.__doc__
        assert "Error" in doc or "error" in doc


class TestSimilarUriHelper:
    """Test _get_similar_uris helper function."""

    def test_similar_uris_same_scheme(self):
        """Test similar URIs with same scheme are suggested."""
        from quilt_mcp.tools.resource_access import (
            _get_similar_uris,
            RESOURCE_REGISTRY,
        )

        similar = _get_similar_uris("auth://wrong", RESOURCE_REGISTRY)

        assert "auth://status" in similar or "auth://catalog/info" in similar

    def test_similar_uris_invalid_format(self):
        """Test similar URIs for invalid format."""
        from quilt_mcp.tools.resource_access import (
            _get_similar_uris,
            RESOURCE_REGISTRY,
        )

        similar = _get_similar_uris("invalid", RESOURCE_REGISTRY)

        assert "No suggestions" in similar or "not found" in similar
```

**Expected Result**: All tests fail (tool function not implemented)

### Green: Implement Tool Function

Add to `src/quilt_mcp/tools/resource_access.py`:

```python
from datetime import datetime
from quilt_mcp.models.responses import (
    GetResourceSuccess,
    GetResourceError,
)


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
    # Initialize resource manager
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
    """Find similar URIs for typo suggestions."""
    if "://" not in uri:
        return "No suggestions available"

    scheme = uri.split("://")[0]
    similar = [u for u in registry.keys() if u.startswith(f"{scheme}://")]

    if not similar:
        return "No similar URIs found"

    return ", ".join(similar[:3])
```

**Expected Result**: All tests pass

### Refactor: Documentation and Error Messages

- Expand docstring to 100+ lines
- Improve error messages for clarity
- Add more examples to docstring
- Verify all error paths have actionable guidance

### Commit

```bash
git add src/quilt_mcp/tools/resource_access.py tests/unit/tools/test_get_resource_tool.py
git commit -m "feat(tools): implement get_resource tool wrapper function

- Add get_resource() with FastMCP-compatible signature
- Implement comprehensive error handling (5 error types)
- Wrap success/error responses in Pydantic models
- Add similar URI suggestions for typos
- Detect and format authorization errors
- Include 100+ line comprehensive docstring
- Full unit test coverage for all code paths

Error types handled:
- InvalidURI (format and not found)
- Unauthorized (admin resources)
- ResourceExecutionError (service failures)
- UnexpectedError (catch-all)

Phase 1, Episode 5
"
```

**Dependencies**: Episodes 1-4 (uses models, manager, and registry)
**Blocks**: Episodes 6-7 (integration tests depend on complete tool)

---

## Episode 6: Integration Tests

**Objective**: Validate data parity and FastMCP integration

**Success Criteria**:
- ✅ Data parity tests for all 4 static Phase 1 resources
- ✅ FastMCP registration validated
- ✅ Service layer integration confirmed
- ✅ Admin resource authentication tested
- ✅ All integration tests pass

**TDD Cycle**:

### Red: Write Failing Tests

Create `tests/integration/test_resource_parity.py`:

```python
"""Integration tests validating data parity between tool and resources."""

import pytest
from quilt_mcp.tools.resource_access import get_resource
from quilt_mcp.services.auth_metadata import auth_status, catalog_info
from quilt_mcp.services.permissions_service import discover_permissions


class TestResourceDataParity:
    """Validate tool returns identical data to direct service calls."""

    @pytest.mark.asyncio
    async def test_auth_status_parity(self):
        """Test auth://status returns same data as direct service call."""
        # Get data via tool
        tool_result = await get_resource("auth://status")
        assert tool_result.success is True
        tool_data = tool_result.data

        # Get data via direct service call
        service_result = auth_status()
        if hasattr(service_result, "model_dump"):
            service_data = service_result.model_dump()
        else:
            service_data = service_result

        # Compare data structures
        assert tool_data == service_data, \
            f"Data mismatch:\nTool: {tool_data}\nService: {service_data}"

    @pytest.mark.asyncio
    async def test_catalog_info_parity(self):
        """Test auth://catalog/info returns same data as direct service call."""
        tool_result = await get_resource("auth://catalog/info")
        assert tool_result.success is True
        tool_data = tool_result.data

        service_result = catalog_info()
        if hasattr(service_result, "model_dump"):
            service_data = service_result.model_dump()
        else:
            service_data = service_result

        assert tool_data == service_data

    @pytest.mark.asyncio
    async def test_permissions_discover_parity(self):
        """Test permissions://discover returns same data as direct service call."""
        tool_result = await get_resource("permissions://discover")
        assert tool_result.success is True
        tool_data = tool_result.data

        service_result = discover_permissions()
        if hasattr(service_result, "model_dump"):
            service_data = service_result.model_dump()
        else:
            service_data = service_result

        assert tool_data == service_data

    @pytest.mark.asyncio
    async def test_all_static_resources_return_data(self):
        """Test all Phase 1 static resources return valid data."""
        static_uris = [
            "auth://status",
            "auth://catalog/info",
            "permissions://discover",
        ]

        for uri in static_uris:
            result = await get_resource(uri)
            assert result.success is True, f"Resource {uri} failed: {result}"
            assert "data" in result.model_dump(), f"No data in {uri} response"
            assert isinstance(result.data, dict), f"{uri} data not a dict"


class TestFastMCPIntegration:
    """Validate integration with FastMCP server."""

    def test_tool_registered_with_fastmcp(self):
        """Test get_resource tool is registered with FastMCP."""
        from quilt_mcp.main import mcp

        # Get tool list from MCP server
        tools = mcp.list_tools()
        tool_names = [t.name for t in tools]

        assert "get_resource" in tool_names, "get_resource tool not registered"

    def test_tool_schema_correct(self):
        """Test get_resource tool has correct schema."""
        from quilt_mcp.main import mcp

        tools = mcp.list_tools()
        tool = next((t for t in tools if t.name == "get_resource"), None)

        assert tool is not None
        assert "uri" in tool.inputSchema["properties"]
        assert tool.inputSchema["properties"]["uri"]["type"] == "string"

    @pytest.mark.asyncio
    async def test_tool_invocation_through_fastmcp(self):
        """Test tool can be invoked through FastMCP."""
        from quilt_mcp.main import mcp

        # Invoke tool through FastMCP
        result = await mcp.call_tool("get_resource", {"uri": "auth://status"})

        assert result is not None
        # Result format depends on FastMCP version


class TestServiceLayerIntegration:
    """Validate integration with service layer."""

    def test_service_functions_importable(self):
        """Test all Phase 1 service functions are importable."""
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

    def test_resources_module_unchanged(self):
        """Test resources module unchanged by tool implementation."""
        from quilt_mcp import resources

        # Verify key resources functions still defined
        assert hasattr(resources, "register_resources")

    @pytest.mark.asyncio
    async def test_admin_resource_requires_authentication(self):
        """Test admin resource enforces authentication."""
        # This test depends on authentication state
        # May pass or fail based on whether user is authenticated as admin
        result = await get_resource("admin://users")

        # Either succeeds (if admin) or returns Unauthorized error
        if not result.success:
            assert result.error in ["Unauthorized", "ResourceExecutionError"]
```

**Expected Result**: Most tests fail (integration not complete yet)

### Green: Validate Integration

Run tests and fix any integration issues:

1. Verify tool is registered in FastMCP
2. Validate service imports work
3. Check data serialization matches
4. Test authentication flow

**Expected Result**: All tests pass

### Refactor: Test Organization

- Group tests by integration area
- Add more descriptive test names
- Extract common test fixtures

### Commit

```bash
git add tests/integration/test_resource_parity.py
git commit -m "test(integration): add resource parity and integration tests

- Validate data parity for 4 Phase 1 static resources
- Test FastMCP registration and schema
- Verify service layer integration unchanged
- Test admin resource authentication enforcement
- Comprehensive integration test coverage

Phase 1, Episode 6
"
```

**Dependencies**: Episode 5 (requires complete tool implementation)
**Blocks**: Episode 7 (performance tests can run in parallel)

---

## Episode 7: Performance Benchmarks

**Objective**: Establish performance baseline and validate overhead budget

**Success Criteria**:
- ✅ Performance benchmarking framework implemented
- ✅ Static URI overhead measured (<10% target)
- ✅ Discovery mode performance validated (<500ms target)
- ✅ Service invocation benchmarks baseline established
- ✅ All performance tests pass

**TDD Cycle**:

### Red: Write Failing Tests

Create `tests/integration/test_resource_performance.py`:

```python
"""Performance benchmarks for resource access tool."""

import pytest
import time
from statistics import mean, stdev
from quilt_mcp.tools.resource_access import get_resource
from quilt_mcp.services.auth_metadata import auth_status


class TestStaticResourcePerformance:
    """Benchmark static resource access performance."""

    @pytest.mark.asyncio
    async def test_static_uri_overhead_within_budget(self):
        """Test tool overhead is <10% vs direct service call."""
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
    async def test_static_resource_response_time(self):
        """Test static resource access completes quickly."""
        iterations = 50
        times = []

        for _ in range(iterations):
            start = time.perf_counter()
            result = await get_resource("auth://status")
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        avg_time = mean(times)
        print(f"\nAverage response time: {avg_time*1000:.2f}ms (±{stdev(times)*1000:.2f}ms)")

        # Should complete in reasonable time (<100ms typical)
        assert avg_time < 0.5, f"Response time {avg_time*1000:.2f}ms too slow"


class TestDiscoveryModePerformance:
    """Benchmark discovery mode performance."""

    @pytest.mark.asyncio
    async def test_discovery_mode_within_budget(self):
        """Test discovery mode completes within 500ms."""
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

    @pytest.mark.asyncio
    async def test_discovery_mode_consistent_performance(self):
        """Test discovery mode has consistent performance."""
        iterations = 10
        times = []

        for _ in range(iterations):
            start = time.perf_counter()
            result = await get_resource("")
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        std_dev = stdev(times)
        avg_time = mean(times)
        variance_pct = (std_dev / avg_time) * 100

        print(f"\nDiscovery variance: {variance_pct:.1f}%")

        # Should be reasonably consistent (<50% variance)
        assert variance_pct < 50.0, f"Discovery mode variance {variance_pct:.1f}% too high"


class TestServiceInvocationPerformance:
    """Benchmark service function invocation."""

    @pytest.mark.asyncio
    async def test_multiple_resources_sequential(self):
        """Benchmark sequential access to multiple resources."""
        uris = [
            "auth://status",
            "auth://catalog/info",
            "permissions://discover",
        ]

        start = time.perf_counter()
        for uri in uris:
            result = await get_resource(uri)
            assert result.success is True
        elapsed = time.perf_counter() - start

        avg_per_resource = elapsed / len(uris)

        print(f"\nSequential access ({len(uris)} resources): {elapsed*1000:.2f}ms")
        print(f"Average per resource: {avg_per_resource*1000:.2f}ms")

        # Should be reasonably fast
        assert elapsed < 2.0, f"Sequential access took {elapsed:.2f}s, too slow"

    @pytest.mark.asyncio
    async def test_repeated_access_same_resource(self):
        """Benchmark repeated access to same resource."""
        iterations = 50
        times = []

        for _ in range(iterations):
            start = time.perf_counter()
            result = await get_resource("auth://status")
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        avg_time = mean(times)
        print(f"\nRepeated access: {avg_time*1000:.2f}ms (±{stdev(times)*1000:.2f}ms)")

        # Should be consistent
        assert stdev(times) < avg_time, "Performance too variable"


class TestPerformanceBaseline:
    """Establish performance baselines for future comparison."""

    @pytest.mark.asyncio
    async def test_baseline_static_resource(self):
        """Record baseline performance for static resources."""
        iterations = 100
        times = []

        for _ in range(iterations):
            start = time.perf_counter()
            result = await get_resource("auth://status")
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        baseline = {
            "mean": mean(times),
            "stdev": stdev(times),
            "min": min(times),
            "max": max(times),
            "p50": sorted(times)[len(times)//2],
            "p95": sorted(times)[int(len(times)*0.95)],
            "p99": sorted(times)[int(len(times)*0.99)],
        }

        print("\n=== Phase 1 Performance Baseline ===")
        print(f"Mean: {baseline['mean']*1000:.2f}ms")
        print(f"Stdev: {baseline['stdev']*1000:.2f}ms")
        print(f"Min: {baseline['min']*1000:.2f}ms")
        print(f"Max: {baseline['max']*1000:.2f}ms")
        print(f"P50: {baseline['p50']*1000:.2f}ms")
        print(f"P95: {baseline['p95']*1000:.2f}ms")
        print(f"P99: {baseline['p99']*1000:.2f}ms")

        # Store baseline for future comparison
        # (Could write to file for CI tracking)

    @pytest.mark.asyncio
    async def test_baseline_discovery_mode(self):
        """Record baseline performance for discovery mode."""
        iterations = 20
        times = []

        for _ in range(iterations):
            start = time.perf_counter()
            result = await get_resource("")
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        baseline = {
            "mean": mean(times),
            "stdev": stdev(times),
            "min": min(times),
            "max": max(times),
        }

        print("\n=== Discovery Mode Baseline ===")
        print(f"Mean: {baseline['mean']*1000:.2f}ms")
        print(f"Stdev: {baseline['stdev']*1000:.2f}ms")
        print(f"Min: {baseline['min']*1000:.2f}ms")
        print(f"Max: {baseline['max']*1000:.2f}ms")
```

**Expected Result**: All tests pass (establish baseline)

### Green: Optimize if Needed

If any performance tests fail:

1. Profile slow operations
2. Optimize bottlenecks
3. Re-run benchmarks
4. Verify targets met

**Expected Result**: All tests pass within budget

### Refactor: Test Organization

- Extract benchmark utilities
- Add more percentile measurements
- Consider baseline storage for CI

### Commit

```bash
git add tests/integration/test_resource_performance.py
git commit -m "test(performance): add performance benchmarks and baselines

- Benchmark static URI overhead (<10% target)
- Measure discovery mode performance (<500ms target)
- Test service invocation performance
- Establish performance baselines for future comparison
- Include percentile measurements (P50, P95, P99)

Performance targets met:
- Static URI overhead: <10%
- Discovery mode: <500ms
- Response time consistency validated

Phase 1, Episode 7
"
```

**Dependencies**: Episode 5 (requires complete tool implementation)
**Blocks**: None (final episode)

---

## Episode Completion Checklist

After each episode:

- [ ] All tests pass (`make test`)
- [ ] Lint checks pass (`make lint`)
- [ ] Type checks pass (`mypy src/quilt_mcp/tools/resource_access.py`)
- [ ] IDE diagnostics resolved
- [ ] Coverage >90% for episode code
- [ ] Episode committed and pushed
- [ ] CI passes for episode commit

---

## Phase 1 Completion Criteria

All episodes complete when:

- ✅ All 7 episodes committed and pushed
- ✅ All unit tests pass (>90% coverage)
- ✅ All integration tests pass
- ✅ All performance benchmarks pass
- ✅ No failing IDE diagnostics
- ✅ Phase 1 checklist completed
- ✅ Manual testing in Claude Desktop successful

---

## Post-Phase 1 Activities

After all episodes complete:

1. **Update documentation**
   - Add tool to README.md
   - Document Phase 1 limitations
   - Note Phase 2 roadmap

2. **Create Phase 1 summary**
   - Document lessons learned
   - Note optimization opportunities
   - Identify technical debt

3. **Prepare for Phase 2**
   - Design template URI expansion
   - Plan remaining resource additions
   - Design optimization strategies

4. **Merge to main**
   - Create PR with comprehensive description
   - Link to GitHub issue #233
   - Reference all episode commits

---

**Document Status**: ✅ Complete - Ready for Human Review

**Next Step**: Human approval → Create Phase 1 checklist (08-phase1-checklist.md)
