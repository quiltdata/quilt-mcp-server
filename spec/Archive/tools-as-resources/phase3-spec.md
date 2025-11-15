# Phase 3: Configuration, Testing & Documentation - Implementation Spec

## Objective

Ensure resources are properly configured, thoroughly tested, and well-documented. Update tool exclusions, add comprehensive test coverage, and provide migration documentation for users.

## Prerequisites

- Phase 1 complete and tested
- Phase 2 complete and tested
- All resources functional in development environment

## Scope

### 1. Configuration Updates

#### A. Tool Exclusion Configuration

Add tools that are now available as resources to the `excluded_tools` list in `utils.py`:

```python
# src/quilt_mcp/utils.py

# Tools that are now available as resources
RESOURCE_AVAILABLE_TOOLS = [
    # Phase 1 - Core Discovery Resources
    "admin_users_list",
    "admin_roles_list",
    "admin_sso_config_get",
    "admin_tabulator_open_query_get",
    "athena_databases_list",
    "athena_workgroups_list",
    "list_metadata_templates",
    "show_metadata_examples",
    "fix_metadata_validation_issues",
    "workflow_list_all",
    "tabulator_buckets_list",

    # Phase 2 - Extended Discovery Resources
    "auth_status",
    "catalog_info",
    "catalog_name",
    "filesystem_status",
    "aws_permissions_discover",
    "bucket_recommendations_get",
    "bucket_access_check",
    "admin_user_get",
    "athena_table_schema",
    "athena_query_history",
    "tabulator_tables_list",
    "get_metadata_template",
    "workflow_get_status",
]

# For backward compatibility, keep tools but mark them as deprecated
# Do NOT add to excluded_tools yet - maintain dual access during migration period
```

#### B. Server Configuration

Update server initialization to register resources:

```python
# src/quilt_mcp/server.py

from quilt_mcp.resources import register_all_resources, get_registry

async def main():
    """Main server entry point."""
    # Initialize resources BEFORE starting server
    register_all_resources()

    # Log resource registration
    registry = get_registry()
    resources = registry.list_resources()
    logger.info(f"Registered {len(resources)} MCP resources")

    # Start server
    await server.run()
```

#### C. Environment-Based Configuration

Add configuration for resource behavior:

```python
# src/quilt_mcp/config.py

import os
from typing import Optional


class ResourceConfig:
    """Configuration for MCP resources."""

    # Enable/disable resource framework
    RESOURCES_ENABLED: bool = os.getenv("QUILT_MCP_RESOURCES_ENABLED", "true").lower() == "true"

    # Resource cache TTL (seconds)
    RESOURCE_CACHE_TTL: int = int(os.getenv("QUILT_MCP_RESOURCE_CACHE_TTL", "300"))

    # Enable resource caching
    RESOURCE_CACHE_ENABLED: bool = os.getenv("QUILT_MCP_RESOURCE_CACHE_ENABLED", "false").lower() == "true"

    # Log resource access
    RESOURCE_ACCESS_LOGGING: bool = os.getenv("QUILT_MCP_RESOURCE_ACCESS_LOGGING", "true").lower() == "true"


# Global config instance
resource_config = ResourceConfig()
```

### 2. Testing Strategy

#### A. Unit Tests

**Location**: `tests/unit/resources/`

**Coverage Goals**: >95% for all resource code

```
tests/unit/resources/
├── test_base.py                      # Base classes, pattern matching, registry
├── test_admin_resources.py           # All admin resources
├── test_athena_resources.py          # All athena resources
├── test_auth_resources.py            # All auth resources
├── test_metadata_resources.py        # All metadata resources
├── test_permissions_resources.py     # All permissions resources
├── test_tabulator_resources.py       # All tabulator resources
└── test_workflow_resources.py        # All workflow resources
```

**Example Unit Test** (`test_admin_resources.py`):

```python
import pytest
from unittest.mock import AsyncMock, patch
from quilt_mcp.resources.admin import AdminUsersResource, AdminUserResource


@pytest.mark.asyncio
async def test_admin_users_resource_read():
    """Test AdminUsersResource.read()"""
    resource = AdminUsersResource()

    # Mock the tool function
    mock_result = {
        "success": True,
        "users": [
            {"name": "alice", "email": "alice@example.com", "role": "admin"},
            {"name": "bob", "email": "bob@example.com", "role": "user"}
        ],
        "count": 2
    }

    with patch("quilt_mcp.resources.admin.admin_users_list", new_callable=AsyncMock) as mock_tool:
        mock_tool.return_value = mock_result

        response = await resource.read("admin://users")

        assert response.uri == "admin://users"
        assert response.mime_type == "application/json"
        assert response.content["items"] == mock_result["users"]
        assert response.content["metadata"]["total_count"] == 2


@pytest.mark.asyncio
async def test_admin_user_resource_read_with_params():
    """Test AdminUserResource.read() with parameters"""
    resource = AdminUserResource()

    # Mock the tool function
    mock_result = {
        "success": True,
        "user": {"name": "alice", "email": "alice@example.com", "role": "admin"}
    }

    with patch("quilt_mcp.resources.admin.admin_user_get", new_callable=AsyncMock) as mock_tool:
        mock_tool.return_value = mock_result

        params = {"name": "alice"}
        response = await resource.read("admin://users/alice", params)

        assert response.uri == "admin://users/alice"
        assert response.content == mock_result
        mock_tool.assert_called_once_with(name="alice")


@pytest.mark.asyncio
async def test_admin_user_resource_missing_param():
    """Test AdminUserResource.read() fails without parameters"""
    resource = AdminUserResource()

    with pytest.raises(ValueError, match="User name required"):
        await resource.read("admin://users/alice", params=None)


@pytest.mark.asyncio
async def test_admin_users_resource_tool_failure():
    """Test AdminUsersResource.read() handles tool failures"""
    resource = AdminUsersResource()

    mock_result = {"success": False, "error": "Access denied"}

    with patch("quilt_mcp.resources.admin.admin_users_list", new_callable=AsyncMock) as mock_tool:
        mock_tool.return_value = mock_result

        with pytest.raises(Exception, match="Failed to list users"):
            await resource.read("admin://users")
```

#### B. Integration Tests

**Location**: `tests/integration/resources/`

**Goal**: Test resources with real services (mocked external APIs)

```python
# tests/integration/resources/test_admin_integration.py

import pytest
from quilt_mcp.resources import get_registry, register_all_resources


@pytest.fixture(scope="module")
def setup_registry():
    """Setup resource registry once per module."""
    register_all_resources()
    return get_registry()


@pytest.mark.asyncio
async def test_admin_users_flow(setup_registry):
    """Test complete admin users workflow."""
    registry = setup_registry

    # List all users
    response = await registry.read_resource("admin://users")
    assert response.content["items"]
    users = response.content["items"]

    # Get first user details
    if users:
        first_user = users[0]["name"]
        user_response = await registry.read_resource(f"admin://users/{first_user}")
        assert user_response.content["user"]["name"] == first_user


@pytest.mark.asyncio
async def test_resource_not_found(setup_registry):
    """Test resource not found error."""
    registry = setup_registry

    with pytest.raises(ValueError, match="No resource handler"):
        await registry.read_resource("invalid://resource")
```

#### C. E2E Tests

**Location**: `tests/e2e/`

**Goal**: Test MCP protocol compliance with real server

```python
# tests/e2e/test_resources_e2e.py

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_list_resources():
    """Test resources/list MCP endpoint."""
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "quilt-mcp"]
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List resources
            resources = await session.list_resources()

            # Verify Phase 1 resources present
            resource_uris = [r.uri for r in resources.resources]
            assert "admin://users" in resource_uris
            assert "admin://roles" in resource_uris
            assert "athena://databases" in resource_uris
            assert "metadata://templates" in resource_uris

            # Verify Phase 2 resources present
            assert "auth://status" in resource_uris
            assert "permissions://discover" in resource_uris


@pytest.mark.asyncio
async def test_read_resource():
    """Test resources/read MCP endpoint."""
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "quilt-mcp"]
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Read a resource
            result = await session.read_resource("metadata://templates")

            assert result.contents
            assert len(result.contents) == 1
            content = result.contents[0]
            assert content.uri == "metadata://templates"
            assert content.mimeType == "application/json"
            assert content.text  # Should contain JSON


@pytest.mark.asyncio
async def test_read_parameterized_resource():
    """Test reading parameterized resource."""
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "quilt-mcp"]
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Read parameterized resource
            result = await session.read_resource("metadata://templates/standard")

            content = result.contents[0]
            assert content.uri == "metadata://templates/standard"
            assert "standard" in content.text.lower()
```

#### D. Test Coverage Requirements

**Minimum Coverage**: 95% for all resource code

**Coverage Report**:

```bash
# Run tests with coverage
PYTHONPATH=src uv run pytest tests/unit/resources/ \
    --cov=quilt_mcp.resources \
    --cov-report=term-missing \
    --cov-report=html \
    --cov-fail-under=95

# View HTML report
open htmlcov/index.html
```

**Coverage Targets**:
- `base.py`: 100%
- `admin.py`: 95%
- `athena.py`: 95%
- `auth.py`: 95%
- `metadata.py`: 95%
- `permissions.py`: 95%
- `tabulator.py`: 95%
- `workflow.py`: 95%

### 3. Documentation

#### A. Resource Documentation (`docs/resources.md`)

Create comprehensive resource documentation:

```markdown
# MCP Resources Guide

## Overview

Quilt MCP Server provides resources for discovering and exploring Quilt catalogs, packages, and AWS services. Resources are read-only, informational endpoints that return data without side effects.

## Resource vs Tool

- **Resources**: Read-only, informational, cacheable (e.g., list users, get configuration)
- **Tools**: Actions with side effects (e.g., create package, delete user)

## Available Resources

### Admin Resources (`admin://`)

List and discover administrative information:

- `admin://users` - List all users
- `admin://users/{name}` - Get specific user details
- `admin://roles` - List all roles
- `admin://config` - Combined configuration
- `admin://config/sso` - SSO configuration
- `admin://config/tabulator` - Tabulator configuration

### Authentication Resources (`auth://`)

Check authentication and catalog status:

- `auth://status` - Authentication status
- `auth://catalog/info` - Catalog information
- `auth://catalog/name` - Catalog name
- `auth://filesystem/status` - Filesystem permissions

### Athena Resources (`athena://`)

Discover Athena databases and tables:

- `athena://databases` - List databases
- `athena://workgroups` - List workgroups
- `athena://databases/{db}/tables/{table}/schema` - Get table schema
- `athena://queries/history` - Query execution history

### Metadata Resources (`metadata://`)

Access metadata templates and examples:

- `metadata://templates` - List templates
- `metadata://templates/{name}` - Get specific template
- `metadata://examples` - Usage examples
- `metadata://troubleshooting` - Troubleshooting guide

### Permissions Resources (`permissions://`)

Discover AWS permissions and access:

- `permissions://discover` - Discover AWS permissions
- `permissions://recommendations` - Bucket recommendations
- `permissions://buckets/{bucket}/access` - Check bucket access

### Tabulator Resources (`tabulator://`)

Explore Tabulator catalog:

- `tabulator://buckets` - List buckets
- `tabulator://buckets/{bucket}/tables` - List tables in bucket

### Workflow Resources (`workflow://`)

Track workflows:

- `workflow://workflows` - List all workflows
- `workflow://workflows/{id}` - Get workflow status

## Usage Examples

### Python MCP Client

\`\`\`python
from mcp import ClientSession

async with ClientSession(read, write) as session:
    # List resources
    resources = await session.list_resources()

    # Read a resource
    result = await session.read_resource("admin://users")
    users = json.loads(result.contents[0].text)

    # Read parameterized resource
    result = await session.read_resource("admin://users/alice")
    user = json.loads(result.contents[0].text)
\`\`\`

### Claude Desktop

Resources appear in the resource browser and can be accessed directly:

1. Open Claude Desktop
2. View available resources in the sidebar
3. Click a resource to read its contents
4. Use resources in conversation context

## Migration Guide

### For Tool Users

If you're currently using tools, you can migrate to resources for read-only operations:

**Before** (using tools):
\`\`\`python
result = await client.call_tool("admin_users_list", {})
users = result.get("users", [])
\`\`\`

**After** (using resources):
\`\`\`python
response = await client.read_resource("admin://users")
data = json.loads(response.contents[0].text)
users = data.get("items", [])
\`\`\`

**Both work!** Tools remain available for backward compatibility.

## Resource Response Format

All resources return consistent JSON format:

\`\`\`json
{
  "items": [...],
  "metadata": {
    "total_count": 42,
    "has_more": false,
    "continuation_token": null
  }
}
\`\`\`

## Caching

Resources are designed to be cacheable. Clients can cache resource responses to reduce API calls:

- **Default TTL**: 5 minutes
- **Configure**: Set `QUILT_MCP_RESOURCE_CACHE_TTL` environment variable

## Error Handling

Resources return standard HTTP-like errors:

- **ValueError**: Invalid URI or missing parameters
- **PermissionError**: Insufficient permissions
- **Exception**: Other errors (with descriptive messages)

## Best Practices

1. **Use resources for discovery**: List, browse, explore
2. **Use tools for actions**: Create, update, delete
3. **Cache resource results**: Reduce repeated calls
4. **Handle errors gracefully**: Resources may fail due to permissions
```

#### B. API Reference

Update API reference to include resources.

#### C. Migration Guide

Provide detailed migration guide for users transitioning from tools to resources.

### 4. Backward Compatibility

#### Strategy

**Phase 3 approach**: Dual availability

- **Keep all tools functional** - No deprecation yet
- **Add resources alongside tools** - Parallel access
- **Document preferred approach** - Resources for reads, tools for writes
- **Monitor usage** - Track which approach users prefer

#### Timeline for Deprecation (Future)

Not part of Phase 3, but planned approach:

1. **Phase 3 (current)**: Dual availability, documentation
2. **3 months**: Collect feedback, monitor usage
3. **6 months**: Add deprecation warnings to tool functions
4. **9 months**: Final migration support
5. **12 months**: Remove obsolete tools (major version bump)

### 5. Performance Considerations

#### Resource Access Logging

```python
# src/quilt_mcp/resources/base.py

import time
import logging

logger = logging.getLogger(__name__)


class MCPResource(ABC):
    """Base class with performance logging."""

    async def read(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        """Read with performance logging."""
        start_time = time.time()

        try:
            response = await self._read_impl(uri, params)

            if resource_config.RESOURCE_ACCESS_LOGGING:
                elapsed = time.time() - start_time
                logger.info(f"Resource read: {uri} ({elapsed:.3f}s)")

            return response
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Resource read failed: {uri} ({elapsed:.3f}s) - {str(e)}")
            raise

    @abstractmethod
    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        """Implementation to be overridden by subclasses."""
        pass
```

## Success Criteria

### Phase 3 Complete When:

1. ✅ All tools marked (but not excluded) as resource-available
2. ✅ Server properly initializes and registers resources
3. ✅ Configuration options documented and working
4. ✅ Unit tests achieve >95% coverage
5. ✅ Integration tests verify end-to-end workflows
6. ✅ E2E tests confirm MCP protocol compliance
7. ✅ Documentation complete (resource guide, API reference, migration guide)
8. ✅ Performance logging implemented and tested
9. ✅ Backward compatibility verified (all existing tools still work)
10. ✅ Resources visible in Claude Desktop and other MCP clients

## Deliverables

### Code
- [ ] Updated `utils.py` with resource-available tool list
- [ ] Updated `server.py` with resource initialization
- [ ] New `config.py` with resource configuration
- [ ] Performance logging in base resource class

### Tests
- [ ] Unit tests for all resources (>95% coverage)
- [ ] Integration tests for resource workflows
- [ ] E2E tests for MCP protocol compliance
- [ ] Coverage report showing >95% for resource code

### Documentation
- [ ] Resource guide (`docs/resources.md`)
- [ ] API reference updates
- [ ] Migration guide
- [ ] README updates with resource examples

## Timeline

- **Configuration updates**: ~1 day
- **Unit test implementation**: ~3-4 days
- **Integration test implementation**: ~2 days
- **E2E test implementation**: ~1-2 days
- **Documentation writing**: ~2-3 days
- **Review & refinement**: ~2 days
- **Total**: ~2 weeks

## Dependencies

- Phase 1 complete
- Phase 2 complete
- pytest and pytest-cov installed
- MCP client library for E2E tests

## Post-Phase 3 Activities

1. Deploy to staging environment
2. Gather user feedback
3. Monitor performance metrics
4. Plan resource caching implementation
5. Consider additional resources (S3, packages)
6. Evaluate tool deprecation timeline

## Conclusion

Phase 3 completes the Tools-as-Resources implementation by ensuring everything is properly tested, documented, and configured. After Phase 3:

- ✅ All high-priority resources implemented (26 resources total)
- ✅ Comprehensive test coverage
- ✅ Complete documentation
- ✅ Backward compatibility maintained
- ✅ Ready for production deployment
- ✅ Clear migration path for users

The implementation provides a solid foundation for future enhancements while maintaining stability and user experience.
