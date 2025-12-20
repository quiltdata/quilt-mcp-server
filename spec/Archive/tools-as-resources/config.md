# Configuration Resource Design

## Problem Statement

The current implementation has several configuration getter tools that expose single settings:

- `admin_sso_config_get()` → Returns SSO configuration string/dict
- `admin_tabulator_open_query_get()` → Returns boolean flag
- `tabulator_open_query_status()` → **DUPLICATE** of above (different module)

## Issues with Current Approach

### 1. Tool Proliferation
- One tool per configuration field doesn't scale
- Creates confusion about where to find settings
- Leads to duplication (two modules with same functionality)

### 2. Poor Developer Experience
- Client must know which specific tool to call for each setting
- No way to get "all admin config" in one call
- Difficult to discover what configuration options exist

### 3. Semantic Mismatch
- Simple getters don't justify dedicated tools
- Tools should be for actions, not simple data retrieval
- Boolean flags are especially poor fits for tools

## Recommended Solution: Unified Configuration Resource

### Resource Structure

```
Resource: admin://config
Content-Type: application/json

{
  "sso": {
    "enabled": true,
    "provider": "okta",
    "config": {
      "client_id": "...",
      "issuer": "...",
      "authorization_endpoint": "...",
      "token_endpoint": "...",
      "userinfo_endpoint": "...",
      "jwks_uri": "..."
    }
  },
  "tabulator": {
    "open_query_enabled": true,
    "default_workgroup": "primary",
    "max_results": 1000,
    "cache_ttl": 3600
  },
  "catalog": {
    "url": "https://example.quiltdata.com",
    "authenticated": true,
    "region": "us-east-1"
  },
  "registry": {
    "default_bucket": "s3://quilt-example-staging",
    "allowed_buckets": ["s3://quilt-example-staging", "s3://quilt-example-prod"]
  }
}
```

### Benefits

1. **Single source of truth** - One resource for all admin configuration
2. **Discoverable** - Clients can explore all available settings
3. **Efficient** - One fetch gets all config data
4. **Extensible** - Easy to add new config sections
5. **Cacheable** - MCP clients can cache the entire config
6. **RESTful** - Follows standard configuration API patterns

## Tool/Resource Division

### Resources (Read-Only State)

| Resource | Purpose | Content |
|----------|---------|---------|
| `admin://config` | All admin configuration | SSO, tabulator, catalog, registry settings |
| `auth://status` | Current authentication state | User info, tokens, permissions |
| `auth://catalog/info` | Active catalog details | URL, region, connection status |

### Tools (Mutations)

| Tool | Purpose | Parameters |
|------|---------|------------|
| `admin_sso_config_set(config)` | Set SSO configuration | SSO config string |
| `admin_sso_config_remove()` | Remove SSO configuration | None |
| `admin_tabulator_open_query_set(enabled)` | Toggle open query | Boolean flag |
| `configure_catalog(catalog_url)` | Change active catalog | Catalog URL |
| `switch_catalog(catalog_name)` | Switch to named catalog | Catalog name |

### Pattern

- **Resource**: `admin://config` → Read all settings
- **Tool**: `admin_*_set()` → Mutate specific setting
- **Tool Response**: Returns updated config section

Example:
```python
# Read current config
config = await client.read_resource("admin://config")
print(config["tabulator"]["open_query_enabled"])  # False

# Mutate setting
result = await client.call_tool("admin_tabulator_open_query_set", {"enabled": True})
print(result["tabulator"]["open_query_enabled"])  # True

# Resource is now updated (or cache invalidated)
config = await client.read_resource("admin://config")
print(config["tabulator"]["open_query_enabled"])  # True
```

## Migration Strategy

### Phase 1: Add Unified Resource
1. Implement `admin://config` resource
2. Aggregate data from existing getters
3. Keep existing getter tools (deprecated but functional)
4. Update documentation to prefer resource

### Phase 2: Update Mutation Tools
1. Modify setter tools to return updated config section
2. Example: `admin_tabulator_open_query_set()` returns `{"tabulator": {...}}`
3. Allows clients to update local state without re-fetching

### Phase 3: Remove Duplicates
1. Remove `tabulator.tabulator_open_query_status()` (duplicate)
2. Keep `governance.admin_tabulator_open_query_get()` for backward compatibility
3. Mark as deprecated in documentation

### Phase 4: Deprecation (Future)
1. Add deprecation warnings to individual getter tools
2. Give users 2+ versions to migrate
3. Eventually remove individual getters
4. Keep only mutation tools + unified resource

## Duplication Issue

### Current State
Two modules expose the same tabulator open query functionality:

**Module: `governance`** (lines 29-30 in mcp-list.csv)
- `admin_tabulator_open_query_get()` - Get status
- `admin_tabulator_open_query_set(enabled)` - Set status

**Module: `tabulator`** (lines 73-74 in mcp-list.csv)
- `tabulator_open_query_status()` - Get status (**DUPLICATE**)
- `tabulator_open_query_toggle(enabled)` - Set status (**DUPLICATE**)

### Recommended Resolution

**Keep in `governance` module** (admin operations):
- ❌ Remove `admin_tabulator_open_query_get()` → Use `admin://config` resource
- ✅ Keep `admin_tabulator_open_query_set(enabled)` → Admin mutation

**Remove from `tabulator` module**:
- ❌ Remove `tabulator_open_query_status()` → Duplicate of getter
- ❌ Remove `tabulator_open_query_toggle()` → Duplicate of setter

**Rationale**:
- Tabulator open query is an **admin governance setting**
- Should be controlled through admin tools, not tabulator tools
- Tabulator module should focus on table operations (list, create, query)
- Reduces confusion about which tool to use

## Additional Configuration Candidates

### Other settings that could be in `admin://config`:

**User preferences:**
- Default output format (JSON, CSV, Parquet)
- Query timeout settings
- Maximum result limits

**Feature flags:**
- Beta feature enablement
- Experimental API access
- Debug mode

**Integration settings:**
- Webhook URLs
- External service endpoints
- API rate limits

**Security settings:**
- Session timeout
- MFA requirements
- IP allowlists

These should be added to `admin://config` as they're discovered/needed, rather than
creating individual getter tools for each one.

## Implementation Checklist

- [ ] Implement `admin://config` resource handler
- [ ] Aggregate SSO config from GraphQL/REST API
- [ ] Aggregate tabulator open query from GraphQL/REST API
- [ ] Add catalog info (URL, region, auth status)
- [ ] Add registry defaults
- [ ] Update mutation tools to return config sections
- [ ] Add cache invalidation on mutations
- [ ] Write integration tests for config resource
- [ ] Document migration path
- [ ] Mark duplicate tools as deprecated
- [ ] Update client examples to use resource

## References

- Main analysis: [analysis.md](./analysis.md)
- MCP tools list: [../../tests/fixtures/mcp-list.csv](../../tests/fixtures/mcp-list.csv)
- Governance module: `src/quilt_mcp/services/governance_service.py`
- Tabulator module: `src/quilt_mcp/services/tabulator_service.py`
