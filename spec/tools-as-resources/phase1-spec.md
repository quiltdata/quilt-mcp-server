# Phase 1: Core Discovery Resources - Implementation Spec

## Objective

Implement the most clear-cut resource candidates that align with the legacy resources from the `legacy_0_7_2` branch. These are purely informational, read-only resources with no side effects.

## Scope

### Resources to Implement

1. **Admin Resources** (`admin://`)
   - `admin://users` → `admin_users_list()`
   - `admin://roles` → `admin_roles_list()`
   - `admin://config` → Combined configuration (SSO status, tabulator settings)

2. **Athena Resources** (`athena://`)
   - `athena://databases` → `athena_databases_list()`
   - `athena://workgroups` → `athena_workgroups_list()`

3. **Metadata Resources** (`metadata://`)
   - `metadata://templates` → `list_metadata_templates()`
   - `metadata://examples` → `show_metadata_examples()`
   - `metadata://troubleshooting` → `fix_metadata_validation_issues()`

4. **Workflow Resources** (`workflow://`)
   - `workflow://workflows` → `workflow_list_all()`

5. **Tabulator Resources** (`tabulator://`)
   - `tabulator://buckets` → `tabulator_buckets_list()`

## Architecture

### Directory Structure

```
src/quilt_mcp/resources/
├── __init__.py              # Export ResourceRegistry, register all resources
├── base.py                  # MCPResource base class, ResourceResponse
├── admin.py                 # AdminUsersResource, AdminRolesResource, AdminConfigResource
├── athena.py                # AthenaDatabasesResource, AthenaWorkgroupsResource
├── metadata.py              # MetadataTemplatesResource, MetadataExamplesResource, MetadataTroubleshootingResource
├── workflow.py              # WorkflowsResource
└── tabulator.py             # TabulatorBucketsResource
```

### Base Framework (`base.py`)

#### MCPResource Base Class

```python
from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass


@dataclass
class ResourceResponse:
    """Standard response format for MCP resources."""
    uri: str
    mime_type: str = "application/json"
    content: Any = None

    def to_dict(self) -> dict:
        """Convert to MCP resource response format."""
        return {
            "uri": self.uri,
            "mimeType": self.mime_type,
            "text": self._serialize_content()
        }

    def _serialize_content(self) -> str:
        """Serialize content to string based on mime type."""
        if self.mime_type == "application/json":
            import json
            return json.dumps(self.content, indent=2)
        return str(self.content)


class MCPResource(ABC):
    """Base class for all MCP resources."""

    @property
    @abstractmethod
    def uri_scheme(self) -> str:
        """The URI scheme this resource handles (e.g., 'admin', 'athena')."""
        pass

    @property
    @abstractmethod
    def uri_pattern(self) -> str:
        """The URI pattern this resource matches (e.g., 'admin://users')."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for the resource."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what this resource provides."""
        pass

    @abstractmethod
    async def read(self, uri: str) -> ResourceResponse:
        """
        Read the resource at the given URI.

        Args:
            uri: Full URI to read (e.g., 'admin://users')

        Returns:
            ResourceResponse with the resource data

        Raises:
            ValueError: If URI is invalid or malformed
            PermissionError: If user lacks required permissions
            Exception: For other errors
        """
        pass

    def matches(self, uri: str) -> bool:
        """Check if this resource handles the given URI."""
        return uri.startswith(f"{self.uri_scheme}://")
```

#### ResourceRegistry

```python
from typing import Dict, List, Optional


class ResourceRegistry:
    """Registry for all MCP resources."""

    def __init__(self):
        self._resources: Dict[str, MCPResource] = {}

    def register(self, resource: MCPResource):
        """Register a resource."""
        self._resources[resource.uri_pattern] = resource

    def get(self, uri: str) -> Optional[MCPResource]:
        """Get resource handler for the given URI."""
        # Try exact match first
        if uri in self._resources:
            return self._resources[uri]

        # Try pattern matching
        for pattern, resource in self._resources.items():
            if resource.matches(uri):
                return resource

        return None

    def list_resources(self) -> List[dict]:
        """List all registered resources."""
        return [
            {
                "uri": resource.uri_pattern,
                "name": resource.name,
                "description": resource.description,
                "mimeType": "application/json"
            }
            for resource in self._resources.values()
        ]

    async def read_resource(self, uri: str) -> ResourceResponse:
        """Read a resource by URI."""
        resource = self.get(uri)
        if not resource:
            raise ValueError(f"No resource handler for URI: {uri}")

        return await resource.read(uri)


# Global registry instance
_registry = ResourceRegistry()


def get_registry() -> ResourceRegistry:
    """Get the global resource registry."""
    return _registry
```

### Resource Implementations

#### Admin Resources (`admin.py`)

```python
from quilt_mcp.resources.base import MCPResource, ResourceResponse
from quilt_mcp.tools.governance import (
    admin_users_list,
    admin_roles_list,
    admin_sso_config_get,
    admin_tabulator_open_query_get
)


class AdminUsersResource(MCPResource):
    """List all users in the registry."""

    @property
    def uri_scheme(self) -> str:
        return "admin"

    @property
    def uri_pattern(self) -> str:
        return "admin://users"

    @property
    def name(self) -> str:
        return "Admin Users List"

    @property
    def description(self) -> str:
        return "List all users in the Quilt registry with their roles and status"

    async def read(self, uri: str) -> ResourceResponse:
        if uri != self.uri_pattern:
            raise ValueError(f"Invalid URI: {uri}")

        result = await admin_users_list()

        if not result.get("success"):
            raise Exception(f"Failed to list users: {result.get('error', 'Unknown error')}")

        return ResourceResponse(
            uri=uri,
            content={
                "items": result.get("users", []),
                "metadata": {
                    "total_count": result.get("count", 0),
                    "has_more": False,
                    "continuation_token": None
                }
            }
        )


class AdminRolesResource(MCPResource):
    """List all available roles."""

    @property
    def uri_scheme(self) -> str:
        return "admin"

    @property
    def uri_pattern(self) -> str:
        return "admin://roles"

    @property
    def name(self) -> str:
        return "Admin Roles List"

    @property
    def description(self) -> str:
        return "List all available roles in the Quilt registry"

    async def read(self, uri: str) -> ResourceResponse:
        if uri != self.uri_pattern:
            raise ValueError(f"Invalid URI: {uri}")

        result = await admin_roles_list()

        if not result.get("success"):
            raise Exception(f"Failed to list roles: {result.get('error', 'Unknown error')}")

        return ResourceResponse(
            uri=uri,
            content={
                "items": result.get("roles", []),
                "metadata": {
                    "total_count": result.get("count", 0),
                    "has_more": False,
                    "continuation_token": None
                }
            }
        )


class AdminConfigResource(MCPResource):
    """Combined admin configuration resource."""

    @property
    def uri_scheme(self) -> str:
        return "admin"

    @property
    def uri_pattern(self) -> str:
        return "admin://config"

    @property
    def name(self) -> str:
        return "Admin Configuration"

    @property
    def description(self) -> str:
        return "Combined admin configuration (SSO, tabulator settings)"

    async def read(self, uri: str) -> ResourceResponse:
        if uri != self.uri_pattern:
            raise ValueError(f"Invalid URI: {uri}")

        # Gather all config settings
        sso_result = await admin_sso_config_get()
        tabulator_result = await admin_tabulator_open_query_get()

        config = {
            "sso": {
                "configured": sso_result.get("configured", False),
                "config": sso_result.get("config")
            },
            "tabulator": {
                "open_query_enabled": tabulator_result.get("open_query_enabled", False)
            }
        }

        return ResourceResponse(
            uri=uri,
            content=config
        )
```

#### Athena Resources (`athena.py`)

```python
from quilt_mcp.resources.base import MCPResource, ResourceResponse
from quilt_mcp.tools.athena_glue import (
    athena_databases_list,
    athena_workgroups_list
)


class AthenaDatabasesResource(MCPResource):
    """List available Athena databases."""

    @property
    def uri_scheme(self) -> str:
        return "athena"

    @property
    def uri_pattern(self) -> str:
        return "athena://databases"

    @property
    def name(self) -> str:
        return "Athena Databases"

    @property
    def description(self) -> str:
        return "List all available databases in AWS Glue Data Catalog"

    async def read(self, uri: str) -> ResourceResponse:
        if uri != self.uri_pattern:
            raise ValueError(f"Invalid URI: {uri}")

        result = await athena_databases_list()

        if not result.get("success"):
            raise Exception(f"Failed to list databases: {result.get('error', 'Unknown error')}")

        return ResourceResponse(
            uri=uri,
            content={
                "items": result.get("databases", []),
                "metadata": {
                    "total_count": len(result.get("databases", [])),
                    "has_more": False
                }
            }
        )


class AthenaWorkgroupsResource(MCPResource):
    """List available Athena workgroups."""

    @property
    def uri_scheme(self) -> str:
        return "athena"

    @property
    def uri_pattern(self) -> str:
        return "athena://workgroups"

    @property
    def name(self) -> str:
        return "Athena Workgroups"

    @property
    def description(self) -> str:
        return "List all accessible Athena workgroups"

    async def read(self, uri: str) -> ResourceResponse:
        if uri != self.uri_pattern:
            raise ValueError(f"Invalid URI: {uri}")

        result = await athena_workgroups_list()

        if not result.get("success"):
            raise Exception(f"Failed to list workgroups: {result.get('error', 'Unknown error')}")

        return ResourceResponse(
            uri=uri,
            content={
                "items": result.get("workgroups", []),
                "metadata": {
                    "total_count": len(result.get("workgroups", [])),
                    "has_more": False
                }
            }
        )
```

#### Metadata Resources (`metadata.py`)

```python
from quilt_mcp.resources.base import MCPResource, ResourceResponse
from quilt_mcp.tools.metadata_examples import (
    show_metadata_examples,
    fix_metadata_validation_issues
)
from quilt_mcp.tools.metadata_templates import list_metadata_templates


class MetadataTemplatesResource(MCPResource):
    """List available metadata templates."""

    @property
    def uri_scheme(self) -> str:
        return "metadata"

    @property
    def uri_pattern(self) -> str:
        return "metadata://templates"

    @property
    def name(self) -> str:
        return "Metadata Templates"

    @property
    def description(self) -> str:
        return "List available metadata templates with descriptions"

    async def read(self, uri: str) -> ResourceResponse:
        if uri != self.uri_pattern:
            raise ValueError(f"Invalid URI: {uri}")

        result = await list_metadata_templates()

        return ResourceResponse(
            uri=uri,
            content=result
        )


class MetadataExamplesResource(MCPResource):
    """Show metadata usage examples."""

    @property
    def uri_scheme(self) -> str:
        return "metadata"

    @property
    def uri_pattern(self) -> str:
        return "metadata://examples"

    @property
    def name(self) -> str:
        return "Metadata Examples"

    @property
    def description(self) -> str:
        return "Comprehensive metadata usage examples with working patterns"

    async def read(self, uri: str) -> ResourceResponse:
        if uri != self.uri_pattern:
            raise ValueError(f"Invalid URI: {uri}")

        result = await show_metadata_examples()

        return ResourceResponse(
            uri=uri,
            content=result
        )


class MetadataTroubleshootingResource(MCPResource):
    """Metadata validation troubleshooting guide."""

    @property
    def uri_scheme(self) -> str:
        return "metadata"

    @property
    def uri_pattern(self) -> str:
        return "metadata://troubleshooting"

    @property
    def name(self) -> str:
        return "Metadata Troubleshooting"

    @property
    def description(self) -> str:
        return "Guidance for fixing metadata validation issues"

    async def read(self, uri: str) -> ResourceResponse:
        if uri != self.uri_pattern:
            raise ValueError(f"Invalid URI: {uri}")

        result = await fix_metadata_validation_issues()

        return ResourceResponse(
            uri=uri,
            content=result
        )
```

#### Workflow Resources (`workflow.py`)

```python
from quilt_mcp.resources.base import MCPResource, ResourceResponse
from quilt_mcp.tools.workflow_orchestration import workflow_list_all


class WorkflowsResource(MCPResource):
    """List all workflows."""

    @property
    def uri_scheme(self) -> str:
        return "workflow"

    @property
    def uri_pattern(self) -> str:
        return "workflow://workflows"

    @property
    def name(self) -> str:
        return "Workflows"

    @property
    def description(self) -> str:
        return "List all workflows with their current status"

    async def read(self, uri: str) -> ResourceResponse:
        if uri != self.uri_pattern:
            raise ValueError(f"Invalid URI: {uri}")

        result = await workflow_list_all()

        if not result.get("success"):
            raise Exception(f"Failed to list workflows: {result.get('error', 'Unknown error')}")

        return ResourceResponse(
            uri=uri,
            content={
                "items": result.get("workflows", []),
                "metadata": {
                    "total_count": len(result.get("workflows", [])),
                    "has_more": False
                }
            }
        )
```

#### Tabulator Resources (`tabulator.py`)

```python
from quilt_mcp.resources.base import MCPResource, ResourceResponse
from quilt_mcp.tools.tabulator import tabulator_buckets_list


class TabulatorBucketsResource(MCPResource):
    """List all buckets in Tabulator catalog."""

    @property
    def uri_scheme(self) -> str:
        return "tabulator"

    @property
    def uri_pattern(self) -> str:
        return "tabulator://buckets"

    @property
    def name(self) -> str:
        return "Tabulator Buckets"

    @property
    def description(self) -> str:
        return "List all buckets available in the Tabulator catalog"

    async def read(self, uri: str) -> ResourceResponse:
        if uri != self.uri_pattern:
            raise ValueError(f"Invalid URI: {uri}")

        result = await tabulator_buckets_list()

        if not result.get("success"):
            raise Exception(f"Failed to list buckets: {result.get('error', 'Unknown error')}")

        return ResourceResponse(
            uri=uri,
            content={
                "items": result.get("buckets", []),
                "metadata": {
                    "total_count": result.get("count", 0),
                    "has_more": False
                }
            }
        )
```

### Registry Initialization (`__init__.py`)

```python
from quilt_mcp.resources.base import ResourceRegistry, get_registry
from quilt_mcp.resources.admin import (
    AdminUsersResource,
    AdminRolesResource,
    AdminConfigResource
)
from quilt_mcp.resources.athena import (
    AthenaDatabasesResource,
    AthenaWorkgroupsResource
)
from quilt_mcp.resources.metadata import (
    MetadataTemplatesResource,
    MetadataExamplesResource,
    MetadataTroubleshootingResource
)
from quilt_mcp.resources.workflow import WorkflowsResource
from quilt_mcp.resources.tabulator import TabulatorBucketsResource


def register_all_resources():
    """Register all Phase 1 resources."""
    registry = get_registry()

    # Admin resources
    registry.register(AdminUsersResource())
    registry.register(AdminRolesResource())
    registry.register(AdminConfigResource())

    # Athena resources
    registry.register(AthenaDatabasesResource())
    registry.register(AthenaWorkgroupsResource())

    # Metadata resources
    registry.register(MetadataTemplatesResource())
    registry.register(MetadataExamplesResource())
    registry.register(MetadataTroubleshootingResource())

    # Workflow resources
    registry.register(WorkflowsResource())

    # Tabulator resources
    registry.register(TabulatorBucketsResource())


__all__ = [
    "ResourceRegistry",
    "get_registry",
    "register_all_resources"
]
```

## Integration with MCP Server

### Server Updates (`src/quilt_mcp/server.py`)

```python
from quilt_mcp.resources import register_all_resources, get_registry

# In server initialization
async def initialize():
    """Initialize the MCP server."""
    # Register all resources
    register_all_resources()

    # ... rest of initialization


# Add resources/list handler
@server.list_resources()
async def handle_list_resources():
    """List all available resources."""
    registry = get_registry()
    return registry.list_resources()


# Add resources/read handler
@server.read_resource()
async def handle_read_resource(uri: str):
    """Read a resource by URI."""
    registry = get_registry()
    try:
        response = await registry.read_resource(uri)
        return response.to_dict()
    except ValueError as e:
        raise ValueError(f"Invalid resource URI: {uri}") from e
    except PermissionError as e:
        raise PermissionError(f"Access denied to resource: {uri}") from e
    except Exception as e:
        raise Exception(f"Error reading resource {uri}: {str(e)}") from e
```

## Testing

### Unit Tests (`tests/unit/resources/`)

Create unit tests for each resource class:

```
tests/unit/resources/
├── test_base.py              # Test base classes
├── test_admin.py             # Test admin resources
├── test_athena.py            # Test athena resources
├── test_metadata.py          # Test metadata resources
├── test_workflow.py          # Test workflow resources
└── test_tabulator.py         # Test tabulator resources
```

### Integration Tests (`tests/integration/resources/`)

Test resource integration with actual tools:

```
tests/integration/resources/
├── test_admin_resources.py
├── test_athena_resources.py
├── test_metadata_resources.py
├── test_workflow_resources.py
└── test_tabulator_resources.py
```

### E2E Tests (`tests/e2e/`)

Add resource tests to existing E2E suite to verify MCP protocol compliance.

## Success Criteria

1. ✅ All 11 Phase 1 resources are implemented and registered
2. ✅ Resources follow MCP protocol specification
3. ✅ All resources return standardized ResourceResponse format
4. ✅ Resources integrate with existing tool functions (no duplication)
5. ✅ Unit tests achieve >95% coverage for resource code
6. ✅ Integration tests verify resources work with real services
7. ✅ E2E tests confirm MCP protocol compliance
8. ✅ Resources are properly documented with docstrings
9. ✅ Existing tools remain functional (backward compatibility)
10. ✅ Resources handle errors gracefully with appropriate exceptions

## Non-Goals for Phase 1

- **Parameterized resources** (e.g., `admin://users/{name}`) - Defer to Phase 2
- **Nested resources** (e.g., `tabulator://buckets/{bucket}/tables`) - Defer to Phase 2
- **S3/bucket resources** - Defer to Phase 2 (complexity)
- **Package resources** - Defer to Phase 2 (complexity)
- **Deprecating tools** - Keep all existing tools functional
- **Caching** - Basic implementation first, optimize later

## Dependencies

- Existing tool functions in `src/quilt_mcp/tools/`
- MCP SDK for resource handlers
- No new external dependencies required

## Timeline

- **Implementation**: ~3-5 days
- **Testing**: ~2-3 days
- **Review & refinement**: ~1-2 days
- **Total**: ~1-1.5 weeks

## Next Steps After Phase 1

1. Review Phase 1 implementation
2. Gather feedback on resource UX
3. Design Phase 2 (parameterized and nested resources)
4. Plan resource caching strategy
5. Consider tool deprecation timeline
