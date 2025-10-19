# Phase 2: Extended Discovery Resources - Implementation Spec

## Objective

Extend the resource framework with parameterized and nested resources that weren't in the legacy implementation but follow the same patterns. This phase adds authentication status, permissions discovery, and parameterized resource access.

## Prerequisites

- Phase 1 must be complete and tested
- Base resource framework is stable
- Resource registry supports parameterized URIs

## Scope

### Resources to Implement

1. **Authentication Resources** (`auth://`)
   - `auth://status` → `auth_status()`
   - `auth://catalog/info` → `catalog_info()`
   - `auth://catalog/name` → `catalog_name()`
   - `auth://filesystem/status` → `filesystem_status()`

2. **Permissions Resources** (`permissions://`)
   - `permissions://discover` → `aws_permissions_discover()`
   - `permissions://recommendations` → `bucket_recommendations_get()`
   - `permissions://buckets/{bucket}/access` → `bucket_access_check(bucket)` **[PARAMETERIZED]**

3. **Parameterized Admin Resources** (`admin://`)
   - `admin://users/{name}` → `admin_user_get(name)` **[PARAMETERIZED]**
   - `admin://config/sso` → `admin_sso_config_get()` **[NESTED]**
   - `admin://config/tabulator` → `admin_tabulator_open_query_get()` **[NESTED]**

4. **Parameterized Athena Resources** (`athena://`)
   - `athena://databases/{db}/tables/{table}/schema` → `athena_table_schema(db, table)` **[NESTED/PARAMETERIZED]**
   - `athena://queries/history` → `athena_query_history()` **[NESTED]**

5. **Parameterized Tabulator Resources** (`tabulator://`)
   - `tabulator://buckets/{bucket}/tables` → `tabulator_tables_list(bucket)` **[PARAMETERIZED]**

6. **Parameterized Metadata Resources** (`metadata://`)
   - `metadata://templates/{name}` → `get_metadata_template(name)` **[PARAMETERIZED]**

7. **Parameterized Workflow Resources** (`workflow://`)
   - `workflow://workflows/{id}` → `workflow_get_status(id)` **[PARAMETERIZED]**

## Architecture Enhancements

### Enhanced Base Framework (`base.py`)

#### URI Pattern Matching

```python
import re
from typing import Dict, Optional


class MCPResource(ABC):
    """Base class with enhanced pattern matching."""

    @property
    @abstractmethod
    def uri_template(self) -> str:
        """
        URI template with parameter placeholders.
        Examples:
        - 'admin://users' (no parameters)
        - 'admin://users/{name}' (one parameter)
        - 'athena://databases/{db}/tables/{table}/schema' (multiple parameters)
        """
        pass

    def matches(self, uri: str) -> bool:
        """Check if URI matches this resource's pattern."""
        pattern = self._template_to_regex(self.uri_template)
        return bool(re.match(pattern, uri))

    def extract_params(self, uri: str) -> Dict[str, str]:
        """Extract parameters from URI based on template."""
        pattern = self._template_to_regex(self.uri_template)
        match = re.match(pattern, uri)
        if not match:
            return {}
        return match.groupdict()

    @staticmethod
    def _template_to_regex(template: str) -> str:
        """Convert URI template to regex pattern."""
        # Escape special regex characters except {}
        escaped = re.escape(template)
        # Replace {param} with named capture groups
        pattern = re.sub(r'\\{(\w+)\\}', r'(?P<\1>[^/]+)', escaped)
        return f'^{pattern}$'

    @abstractmethod
    async def read(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        """
        Read resource with optional parameters extracted from URI.

        Args:
            uri: Full URI
            params: Parameters extracted from URI template

        Returns:
            ResourceResponse
        """
        pass
```

#### Enhanced ResourceRegistry

```python
class ResourceRegistry:
    """Enhanced registry with pattern matching."""

    def __init__(self):
        self._resources: List[MCPResource] = []

    def register(self, resource: MCPResource):
        """Register a resource (order matters for pattern matching)."""
        # Insert more specific patterns first
        self._resources.insert(0, resource)

    def get(self, uri: str) -> Optional[MCPResource]:
        """Get resource handler for URI."""
        for resource in self._resources:
            if resource.matches(uri):
                return resource
        return None

    async def read_resource(self, uri: str) -> ResourceResponse:
        """Read resource with parameter extraction."""
        resource = self.get(uri)
        if not resource:
            raise ValueError(f"No resource handler for URI: {uri}")

        params = resource.extract_params(uri)
        return await resource.read(uri, params)
```

### Resource Implementations

#### Authentication Resources (`auth.py`)

```python
from quilt_mcp.resources.base import MCPResource, ResourceResponse
from quilt_mcp.tools.auth import (
    auth_status,
    catalog_info,
    catalog_name,
    filesystem_status
)


class AuthStatusResource(MCPResource):
    """Authentication status and configuration."""

    @property
    def uri_scheme(self) -> str:
        return "auth"

    @property
    def uri_template(self) -> str:
        return "auth://status"

    @property
    def name(self) -> str:
        return "Authentication Status"

    @property
    def description(self) -> str:
        return "Current authentication status and catalog configuration"

    async def read(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        result = await auth_status()
        return ResourceResponse(uri=uri, content=result)


class CatalogInfoResource(MCPResource):
    """Catalog configuration details."""

    @property
    def uri_scheme(self) -> str:
        return "auth"

    @property
    def uri_template(self) -> str:
        return "auth://catalog/info"

    @property
    def name(self) -> str:
        return "Catalog Information"

    @property
    def description(self) -> str:
        return "Detailed catalog configuration and connectivity information"

    async def read(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        result = await catalog_info()
        return ResourceResponse(uri=uri, content=result)


class CatalogNameResource(MCPResource):
    """Catalog name identifier."""

    @property
    def uri_scheme(self) -> str:
        return "auth"

    @property
    def uri_template(self) -> str:
        return "auth://catalog/name"

    @property
    def name(self) -> str:
        return "Catalog Name"

    @property
    def description(self) -> str:
        return "Catalog name and detection method"

    async def read(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        result = await catalog_name()
        return ResourceResponse(uri=uri, content=result)


class FilesystemStatusResource(MCPResource):
    """Filesystem access status."""

    @property
    def uri_scheme(self) -> str:
        return "auth"

    @property
    def uri_template(self) -> str:
        return "auth://filesystem/status"

    @property
    def name(self) -> str:
        return "Filesystem Status"

    @property
    def description(self) -> str:
        return "Filesystem access permissions and writable directories"

    async def read(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        result = await filesystem_status()
        return ResourceResponse(uri=uri, content=result)
```

#### Permissions Resources (`permissions.py`)

```python
from quilt_mcp.resources.base import MCPResource, ResourceResponse
from quilt_mcp.tools.permissions import (
    aws_permissions_discover,
    bucket_recommendations_get,
    bucket_access_check
)


class PermissionsDiscoverResource(MCPResource):
    """AWS permissions discovery."""

    @property
    def uri_scheme(self) -> str:
        return "permissions"

    @property
    def uri_template(self) -> str:
        return "permissions://discover"

    @property
    def name(self) -> str:
        return "Permissions Discovery"

    @property
    def description(self) -> str:
        return "Discover AWS permissions for current user/role"

    async def read(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        result = await aws_permissions_discover()
        return ResourceResponse(uri=uri, content=result)


class BucketRecommendationsResource(MCPResource):
    """Bucket recommendations based on permissions."""

    @property
    def uri_scheme(self) -> str:
        return "permissions"

    @property
    def uri_template(self) -> str:
        return "permissions://recommendations"

    @property
    def name(self) -> str:
        return "Bucket Recommendations"

    @property
    def description(self) -> str:
        return "Smart bucket recommendations based on permissions and context"

    async def read(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        result = await bucket_recommendations_get()
        return ResourceResponse(uri=uri, content=result)


class BucketAccessResource(MCPResource):
    """Bucket-specific access check."""

    @property
    def uri_scheme(self) -> str:
        return "permissions"

    @property
    def uri_template(self) -> str:
        return "permissions://buckets/{bucket}/access"

    @property
    def name(self) -> str:
        return "Bucket Access Check"

    @property
    def description(self) -> str:
        return "Check access permissions for a specific bucket"

    async def read(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        if not params or "bucket" not in params:
            raise ValueError("Bucket name required in URI")

        bucket_name = params["bucket"]
        result = await bucket_access_check(bucket_name=bucket_name)

        return ResourceResponse(uri=uri, content=result)
```

#### Parameterized Admin Resources (add to `admin.py`)

```python
class AdminUserResource(MCPResource):
    """Get specific user details."""

    @property
    def uri_scheme(self) -> str:
        return "admin"

    @property
    def uri_template(self) -> str:
        return "admin://users/{name}"

    @property
    def name(self) -> str:
        return "Admin User Details"

    @property
    def description(self) -> str:
        return "Get detailed information about a specific user"

    async def read(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        if not params or "name" not in params:
            raise ValueError("User name required in URI")

        username = params["name"]
        result = await admin_user_get(name=username)

        if not result.get("success"):
            raise Exception(f"Failed to get user {username}: {result.get('error', 'Unknown error')}")

        return ResourceResponse(uri=uri, content=result)


class AdminSSOConfigResource(MCPResource):
    """SSO configuration."""

    @property
    def uri_scheme(self) -> str:
        return "admin"

    @property
    def uri_template(self) -> str:
        return "admin://config/sso"

    @property
    def name(self) -> str:
        return "SSO Configuration"

    @property
    def description(self) -> str:
        return "Current SSO configuration"

    async def read(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        result = await admin_sso_config_get()
        return ResourceResponse(uri=uri, content=result)


class AdminTabulatorConfigResource(MCPResource):
    """Tabulator open query configuration."""

    @property
    def uri_scheme(self) -> str:
        return "admin"

    @property
    def uri_template(self) -> str:
        return "admin://config/tabulator"

    @property
    def name(self) -> str:
        return "Tabulator Configuration"

    @property
    def description(self) -> str:
        return "Tabulator open query configuration"

    async def read(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        result = await admin_tabulator_open_query_get()
        return ResourceResponse(uri=uri, content=result)
```

#### Parameterized Athena Resources (add to `athena.py`)

```python
class AthenaTableSchemaResource(MCPResource):
    """Get table schema."""

    @property
    def uri_scheme(self) -> str:
        return "athena"

    @property
    def uri_template(self) -> str:
        return "athena://databases/{database}/tables/{table}/schema"

    @property
    def name(self) -> str:
        return "Athena Table Schema"

    @property
    def description(self) -> str:
        return "Get detailed schema for a specific table"

    async def read(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        if not params or "database" not in params or "table" not in params:
            raise ValueError("Database and table names required in URI")

        result = await athena_table_schema(
            database_name=params["database"],
            table_name=params["table"]
        )

        if not result.get("success"):
            raise Exception(f"Failed to get schema: {result.get('error', 'Unknown error')}")

        return ResourceResponse(uri=uri, content=result)


class AthenaQueryHistoryResource(MCPResource):
    """Athena query execution history."""

    @property
    def uri_scheme(self) -> str:
        return "athena"

    @property
    def uri_template(self) -> str:
        return "athena://queries/history"

    @property
    def name(self) -> str:
        return "Athena Query History"

    @property
    def description(self) -> str:
        return "Recent query execution history"

    async def read(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        result = await athena_query_history()

        if not result.get("success"):
            raise Exception(f"Failed to get query history: {result.get('error', 'Unknown error')}")

        return ResourceResponse(uri=uri, content=result)
```

#### Parameterized Tabulator Resources (add to `tabulator.py`)

```python
class TabulatorTablesResource(MCPResource):
    """List tables for a specific bucket."""

    @property
    def uri_scheme(self) -> str:
        return "tabulator"

    @property
    def uri_template(self) -> str:
        return "tabulator://buckets/{bucket}/tables"

    @property
    def name(self) -> str:
        return "Tabulator Tables"

    @property
    def description(self) -> str:
        return "List tabulator tables for a specific bucket"

    async def read(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        if not params or "bucket" not in params:
            raise ValueError("Bucket name required in URI")

        bucket_name = params["bucket"]
        result = await tabulator_tables_list(bucket_name=bucket_name)

        if not result.get("success"):
            raise Exception(f"Failed to list tables: {result.get('error', 'Unknown error')}")

        return ResourceResponse(
            uri=uri,
            content={
                "items": result.get("tables", []),
                "metadata": {
                    "bucket_name": bucket_name,
                    "total_count": result.get("count", 0),
                    "has_more": False
                }
            }
        )
```

#### Parameterized Metadata Resources (add to `metadata.py`)

```python
class MetadataTemplateResource(MCPResource):
    """Get a specific metadata template."""

    @property
    def uri_scheme(self) -> str:
        return "metadata"

    @property
    def uri_template(self) -> str:
        return "metadata://templates/{name}"

    @property
    def name(self) -> str:
        return "Metadata Template"

    @property
    def description(self) -> str:
        return "Get a specific metadata template by name"

    async def read(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        if not params or "name" not in params:
            raise ValueError("Template name required in URI")

        template_name = params["name"]
        result = await get_metadata_template(template_name=template_name)

        return ResourceResponse(uri=uri, content=result)
```

#### Parameterized Workflow Resources (add to `workflow.py`)

```python
class WorkflowStatusResource(MCPResource):
    """Get specific workflow status."""

    @property
    def uri_scheme(self) -> str:
        return "workflow"

    @property
    def uri_template(self) -> str:
        return "workflow://workflows/{id}"

    @property
    def name(self) -> str:
        return "Workflow Status"

    @property
    def description(self) -> str:
        return "Get current status of a specific workflow"

    async def read(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        if not params or "id" not in params:
            raise ValueError("Workflow ID required in URI")

        workflow_id = params["id"]
        result = await workflow_get_status(workflow_id=workflow_id)

        if not result.get("success"):
            raise Exception(f"Failed to get workflow status: {result.get('error', 'Unknown error')}")

        return ResourceResponse(uri=uri, content=result)
```

## Registry Updates

### Enhanced Registration (`__init__.py`)

```python
def register_all_resources():
    """Register all Phase 1 + Phase 2 resources."""
    registry = get_registry()

    # Phase 1 resources (unchanged)
    registry.register(AdminUsersResource())
    registry.register(AdminRolesResource())
    registry.register(AdminConfigResource())
    # ... etc

    # Phase 2: Auth resources
    registry.register(AuthStatusResource())
    registry.register(CatalogInfoResource())
    registry.register(CatalogNameResource())
    registry.register(FilesystemStatusResource())

    # Phase 2: Permissions resources
    registry.register(PermissionsDiscoverResource())
    registry.register(BucketRecommendationsResource())
    registry.register(BucketAccessResource())  # Parameterized

    # Phase 2: Parameterized admin resources
    registry.register(AdminUserResource())  # Must come after AdminUsersResource
    registry.register(AdminSSOConfigResource())
    registry.register(AdminTabulatorConfigResource())

    # Phase 2: Parameterized athena resources
    registry.register(AthenaTableSchemaResource())
    registry.register(AthenaQueryHistoryResource())

    # Phase 2: Parameterized tabulator resources
    registry.register(TabulatorTablesResource())

    # Phase 2: Parameterized metadata resources
    registry.register(MetadataTemplateResource())

    # Phase 2: Parameterized workflow resources
    registry.register(WorkflowStatusResource())
```

## Testing

### Enhanced Test Coverage

1. **URI Pattern Matching Tests** (`tests/unit/resources/test_base.py`)
   - Test parameter extraction
   - Test pattern matching edge cases
   - Test multiple parameter extraction

2. **Parameterized Resource Tests**
   - Test each parameterized resource
   - Test missing parameters
   - Test invalid parameter values

3. **Integration Tests**
   - Test resource chaining (e.g., list users, then get specific user)
   - Test error handling for missing resources

## Success Criteria

1. ✅ All 15 Phase 2 resources implemented and registered
2. ✅ URI pattern matching works correctly for all parameterized resources
3. ✅ Resource registry handles parameter extraction properly
4. ✅ All resources follow standardized response format
5. ✅ Unit tests cover parameterized resource logic
6. ✅ Integration tests verify end-to-end workflows
7. ✅ Error handling is robust for invalid URIs
8. ✅ Documentation updated with parameterized resource examples
9. ✅ Backward compatibility maintained with Phase 1 resources
10. ✅ Performance is acceptable (no significant overhead from pattern matching)

## Non-Goals for Phase 2

- **Query parameters** (e.g., `?limit=100`) - Consider for future enhancement
- **S3/bucket object resources** - Too complex, defer further
- **Package resources** - Too complex, defer further
- **Resource templates/resource substitution** - MCP 1.0 feature, future work
- **Resource caching** - Optimization for later

## Dependencies

- Phase 1 complete and tested
- Enhanced pattern matching in base framework
- No new external dependencies

## Timeline

- **Design & architecture**: ~1-2 days
- **Implementation**: ~3-4 days
- **Testing**: ~2-3 days
- **Review & refinement**: ~1-2 days
- **Total**: ~1-2 weeks

## Migration Notes

### Breaking Changes

None - Phase 2 is additive only. All Phase 1 resources remain unchanged.

### Ordering Considerations

**Important**: Register more specific patterns before general ones.

```python
# CORRECT ORDER
registry.register(AdminUserResource())      # admin://users/{name}
registry.register(AdminUsersResource())     # admin://users

# WRONG ORDER - would never match specific user
registry.register(AdminUsersResource())     # admin://users
registry.register(AdminUserResource())      # admin://users/{name} - unreachable!
```

## Next Steps After Phase 2

1. Evaluate Phase 2 UX and performance
2. Consider resource query parameters
3. Plan Phase 3 (configuration and testing)
4. Explore resource caching strategies
5. Document best practices for resource usage
