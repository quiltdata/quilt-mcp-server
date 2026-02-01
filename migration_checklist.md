# MCP Tools Migration Checklist

## Current QuiltService Usage Analysis

### Tools Using QuiltService:
1. **packages.py** - Heavy usage (primary package operations)
2. **search.py** - Session and GraphQL access
3. **stack_buckets.py** - Session and registry URL access
4. **buckets.py** - Import only (minimal usage)

### QuiltService Methods Used:
- `list_packages(registry)` → `QuiltOps.search_packages(query="", registry)`
- `browse_package(name, registry, top_hash)` → `QuiltOps.browse_content(name, registry, path="")`
- `create_package_revision(...)` → **No direct QuiltOps equivalent** (needs special handling)
- `has_session_support()` → **Authentication layer** (handled by factory)
- `get_session()` → **Authentication layer** (handled by factory)
- `get_registry_url()` → **Authentication layer** (handled by factory)
- `get_quilt3_module()` → **Remove** (backward compatibility only)

### Migration Strategy by Tool:

#### 1. packages.py (HIGH PRIORITY)
**Current Usage:**
- `quilt_service.list_packages()` → Package listing
- `quilt_service.browse_package()` → Package browsing
- `quilt_service.create_package_revision()` → Package creation

**Migration Plan:**
- Replace `list_packages()` with `QuiltOps.search_packages(query="", registry)`
- Replace `browse_package()` with `QuiltOps.browse_content(package_name, registry, path="")`
- **SPECIAL CASE**: `create_package_revision()` has no QuiltOps equivalent - needs to stay as direct quilt3 usage or be added to QuiltOps interface

#### 2. search.py (MEDIUM PRIORITY)
**Current Usage:**
- `quilt_service.has_session_support()` → Session validation
- `quilt_service.get_session()` → GraphQL access
- `quilt_service.get_registry_url()` → GraphQL endpoint construction

**Migration Plan:**
- Move session logic to QuiltOpsFactory authentication
- Keep GraphQL functionality as-is (not part of QuiltOps domain)

#### 3. stack_buckets.py (MEDIUM PRIORITY)
**Current Usage:**
- `quilt_service.has_session_support()` → Session validation
- `quilt_service.get_session()` → GraphQL access
- `quilt_service.get_registry_url()` → GraphQL endpoint construction

**Migration Plan:**
- Similar to search.py - move to factory authentication
- Keep GraphQL functionality as-is

#### 4. buckets.py (LOW PRIORITY)
**Current Usage:**
- Import only, no actual method calls

**Migration Plan:**
- Remove unused import

## Domain Object Mapping:

### Package Operations:
- `quilt3.Package` objects → `Package_Info` dataclass
- Package metadata → `Package_Info.description`, `Package_Info.tags`, etc.
- Package browsing results → `Content_Info` dataclass list

### Response Formatting:
- All tool responses using `dataclasses.asdict()` for MCP compatibility
- Maintain backward compatibility in response structure

## Testing Strategy:

### Integration Tests Needed:
1. **packages_list** tool with QuiltOps
2. **package_browse** tool with QuiltOps  
3. **package_diff** tool with QuiltOps
4. Response format compatibility tests
5. Error handling consistency tests

### Verification Checkpoints:
1. All existing integration tests still pass
2. Tool response formats unchanged
3. Error messages maintain clarity
4. Performance characteristics preserved