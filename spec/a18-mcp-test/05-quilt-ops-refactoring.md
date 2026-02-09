# QuiltOps Backend Method Refactoring

## Summary

Refactored QuiltOps to move non-backend-specific methods from abstract to concrete implementations in the base class, following the Template Method pattern more consistently.

## Changes Made

### 1. `_backend_diff_packages` - Moved to Base Class

**Before:** Abstract method requiring each backend to implement package diffing.

**After:** Concrete implementation in QuiltOps base class using `_backend_get_package_entries()`.

**Implementation:**
```python
def _backend_diff_packages(self, pkg1: Any, pkg2: Any) -> Dict[str, List[str]]:
    """Compute differences using _backend_get_package_entries()."""
    entries1 = self._backend_get_package_entries(pkg1)
    entries2 = self._backend_get_package_entries(pkg2)

    keys1 = set(entries1.keys())
    keys2 = set(keys2.keys())

    return {
        "added": sorted(keys2 - keys1),
        "deleted": sorted(keys1 - keys2),
        "modified": [k for k in sorted(keys1 & keys2)
                     if entries1[k]["hash"] != entries2[k]["hash"]]
    }
```

**Rationale:** The diff logic is not backend-specific. It's just comparing two sets of entries, which can be obtained via `_backend_get_package_entries()`. Backends can still override for optimization (quilt3 uses native `pkg.diff()`).

### 2. `_backend_get_catalog_config` - Moved to Base Class

**Before:** Abstract method requiring each backend to implement HTTP GET to config.json.

**After:** Concrete implementation in QuiltOps base class using standard requests library.

**Implementation:**
```python
def _backend_get_catalog_config(self, catalog_url: str) -> Dict[str, Any]:
    """Standard HTTP GET implementation."""
    from quilt_mcp.utils.common import normalize_url
    import requests

    normalized_url = normalize_url(catalog_url)
    config_url = f"{normalized_url}/config.json"

    response = requests.get(config_url, timeout=10)
    response.raise_for_status()
    return response.json()
```

**Rationale:** Fetching catalog config is a standard HTTP operation. Both backends had identical implementations. No backend-specific logic required.

### 3. Methods Kept Backend-Specific

#### `_backend_get_file_url` - CORRECTLY Backend-Specific
- quilt3: Uses Package API for presigned URLs
- Platform: Uses GraphQL API or different URL generation
- Different auth mechanisms per backend

#### `_backend_browse_package_content` - CORRECTLY Backend-Specific
- Requires path navigation within package structure
- quilt3: Uses package navigation and walk
- Platform: Uses GraphQL queries
- Different from `_backend_get_package_entries()` which returns flat list

## Backend-Specific Changes

### quilt3_backend.py
- **Removed:** `_backend_get_catalog_config` (uses base class)
- **Kept:** `_backend_diff_packages` as override (uses optimized native `pkg.diff()`)

### platform_backend.py
- **Removed:** `_backend_get_catalog_config` (uses base class)
- **Removed:** `_backend_diff_packages` (uses base class)
- **Removed:** `_entries_equal()` helper (no longer used)

## Test Results

All tests pass:
- ✅ 134 ops unit tests
- ✅ 135 backend unit tests
- ✅ Linting and type checking pass

## Architecture Benefits

1. **Less Code Duplication:** Eliminated duplicate implementations in backends
2. **Consistent Behavior:** Same diff logic across all backends
3. **Easier Maintenance:** Logic lives in one place
4. **Template Method Pattern:** Better adherence to design pattern
5. **Backend Flexibility:** Backends can still override for optimization

## Design Principle Applied

**Template Method Pattern:**
- Base class provides orchestration and common implementations
- Backends only implement truly backend-specific operations
- Clear separation between what's generic (base) vs specific (backend)
