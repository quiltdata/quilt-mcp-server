# QuiltService Method Usage Patterns Documentation

## Overview
This document captures the current usage patterns of QuiltService methods across MCP tools to ensure accurate migration to QuiltOps.

## Method Usage Analysis

### 1. Package Operations

#### `list_packages(registry: str) -> Iterator[str]`
**Usage Location:** `src/quilt_mcp/tools/packages.py:659`
```python
quilt_service = QuiltService()
with suppress_stdout():
    pkgs = list(quilt_service.list_packages(registry=normalized_registry))
```

**Current Behavior:**
- Returns iterator of package name strings
- Used with `list()` to convert to list
- Wrapped in `suppress_stdout()` to avoid JSON-RPC interference
- Registry parameter is normalized before use

**Migration Target:** `QuiltOps.search_packages(query="", registry=registry)`
- Need to transform Package_Info objects to string names for compatibility
- Maintain stdout suppression pattern

#### `browse_package(name: str, registry: str, top_hash: str = None) -> Package`
**Usage Locations:** 
- `src/quilt_mcp/tools/packages.py:799` (package_browse)
- `src/quilt_mcp/tools/packages.py:1064-1075` (package_diff)
- `src/quilt_mcp/tools/packages.py:1486` (package_update)

```python
quilt_service = QuiltService()
with suppress_stdout():
    pkg = quilt_service.browse_package(package_name, registry=normalized_registry)
    # Optional: with top_hash parameter
    pkg1 = quilt_service.browse_package(
        package1_name, registry=normalized_registry, top_hash=package1_hash
    )
```

**Current Behavior:**
- Returns quilt3.Package object
- Used for both browsing and diffing operations
- Supports optional top_hash parameter for specific versions
- Wrapped in `suppress_stdout()` to avoid JSON-RPC interference

**Migration Target:** `QuiltOps.browse_content(package_name, registry, path="")`
- Need to transform Content_Info objects to match current response format
- Handle top_hash parameter (may need QuiltOps interface extension)

#### `create_package_revision(...)` - SPECIAL CASE
**Usage Locations:**
- `src/quilt_mcp/tools/packages.py:558` (package_create)
- `src/quilt_mcp/tools/packages.py:1284` (package_update)

```python
quilt_service = QuiltService()
result = quilt_service.create_package_revision(
    package_name=package_name,
    s3_uris=s3_uris,
    metadata=metadata,
    registry=registry,
    message=message,
    auto_organize=True,  # or False
    copy=copy_mode
)
```

**Current Behavior:**
- Complex package creation with multiple parameters
- Handles metadata, organization, and copy modes
- Returns dictionary result (never exposes quilt3.Package objects)

**Migration Challenge:** 
- No equivalent in QuiltOps interface
- Options: Add to QuiltOps OR keep as direct quilt3 usage
- Decision needed before migration

### 2. Session & Authentication Operations

#### `has_session_support() -> bool`
**Usage Locations:**
- `src/quilt_mcp/tools/search.py:376`
- `src/quilt_mcp/tools/stack_buckets.py:48`

```python
quilt_service = QuiltService()
if not quilt_service.has_session_support():
    return None, None  # or appropriate error handling
```

**Current Behavior:**
- Checks if quilt3.session is available
- Used as guard clause before session operations
- Returns boolean

**Migration Target:** QuiltOpsFactory authentication validation
- Move to factory-level authentication checking
- Maintain same boolean return pattern

#### `get_session() -> requests.Session`
**Usage Locations:**
- `src/quilt_mcp/tools/search.py:378`
- `src/quilt_mcp/tools/stack_buckets.py:49`

```python
if quilt_service.has_session_support():
    session = quilt_service.get_session()
    # Use session for GraphQL requests
```

**Current Behavior:**
- Returns authenticated requests.Session object
- Used for GraphQL API calls
- Always preceded by has_session_support() check

**Migration Strategy:**
- Keep for GraphQL functionality (not part of QuiltOps domain)
- Use QuiltOpsFactory for authentication validation
- Maintain session access for non-domain operations

#### `get_registry_url() -> str | None`
**Usage Locations:**
- `src/quilt_mcp/tools/search.py:379`
- `src/quilt_mcp/tools/stack_buckets.py:50`

```python
registry_url = quilt_service.get_registry_url()
if not registry_url:
    return None, None
```

**Current Behavior:**
- Returns registry URL from session
- Used to construct GraphQL endpoints
- Can return None if not available

**Migration Strategy:**
- Keep for GraphQL functionality
- Use QuiltOpsFactory for authentication validation

### 3. Backward Compatibility Operations

#### `get_quilt3_module() -> module`
**Usage Location:** `src/quilt_mcp/tools/packages.py:46`
```python
quilt3 = quilt_service.get_quilt3_module()
```

**Current Behavior:**
- Provides backward compatibility access to quilt3 module
- Used for test compatibility
- Should be removed during migration

**Migration Strategy:** Remove entirely

## Error Handling Patterns

### Common Error Handling:
```python
try:
    quilt_service = QuiltService()
    with suppress_stdout():
        result = quilt_service.some_method(...)
except Exception as e:
    return ErrorResponse(error=str(e))
```

**Key Patterns:**
1. **stdout suppression** - Critical for JSON-RPC compatibility
2. **Exception wrapping** - Convert to error response objects
3. **Registry normalization** - Always normalize registry URLs
4. **Service instantiation** - Create new instance per operation

## Response Format Patterns

### Current Response Structures:
1. **Success responses** - Custom dataclass objects
2. **Error responses** - Objects with `error` attribute
3. **List responses** - Objects with list attributes (e.g., `packages`)
4. **Complex responses** - Multiple attributes with metadata

### Migration Requirements:
- Maintain exact response structure
- Use `dataclasses.asdict()` for MCP compatibility
- Preserve error message formats
- Keep performance characteristics

## Performance Considerations

### Current Optimizations:
1. **stdout suppression** - Prevents JSON-RPC interference
2. **Iterator usage** - Memory efficient for large package lists
3. **Session reuse** - Authenticated session caching
4. **Registry normalization** - Consistent URL handling

### Migration Preservation:
- Maintain stdout suppression patterns
- Preserve memory efficiency
- Keep authentication session benefits
- Maintain URL normalization logic