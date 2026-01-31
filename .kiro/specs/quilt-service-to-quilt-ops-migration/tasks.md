# QuiltService → QuiltOps/Utils Migration Tasks

**Goal:** Incrementally replace and delete every method in `quilt_service.py` with properly abstracted functionality in `quilt_ops.py`, domain utilities, or `utils.py`.

**Strategy:** Work method-by-method, migrating callers first, then deleting the unused QuiltService method. All changes should maintain backward compatibility with existing tests.

---

## Overview: Method Categorization

QuiltService contains **35 methods** across 776 lines. These fall into 7 categories:

| Category | Method Count | Target Location |
|----------|--------------|-----------------|
| Authentication & Config | 7 methods | `auth_metadata.py` (refactor existing) |
| Session & GraphQL | 4 methods | `utils.py` or new `session_utils.py` |
| Package Operations | 3 methods | `QuiltOps` interface + implementation |
| Bucket Operations | 1 method | `QuiltOps` interface + implementation |
| Search Operations | 1 method | `utils.py` or inline in callers |
| Admin Operations | 6 methods | `utils.py` (conditional imports) |
| Helper/Private Methods | 13 methods | Domain utilities or delete |

---

## Phase 1: Session & Authentication Utilities (Low Risk)

These methods are pure utilities with no domain logic. Safe to migrate first.

### Task 1.1: Extract Session Utilities to utils.py

**File:** `src/quilt_mcp/utils.py`

**Add new functions:**

```python
def has_quilt3_session_support() -> bool:
    """Check if quilt3.session is available and functional.

    Returns:
        True if session support is available
    """
    try:
        import quilt3
        return hasattr(quilt3, "session") and hasattr(quilt3.session, "get_session")
    except Exception:
        return False


def get_quilt3_session() -> Any:
    """Get authenticated requests session from quilt3.

    Returns:
        Authenticated session object

    Raises:
        Exception: If session is not available
    """
    import quilt3
    if not has_quilt3_session_support():
        raise Exception("quilt3 session not available")
    return quilt3.session.get_session()


def get_quilt3_registry_url() -> str | None:
    """Get registry URL from quilt3 session.

    Returns:
        Registry URL or None if not available
    """
    try:
        import quilt3
        if hasattr(quilt3.session, "get_registry_url"):
            return quilt3.session.get_registry_url()
        return None
    except Exception:
        return None


def create_quilt3_botocore_session() -> Any:
    """Create authenticated botocore session from quilt3.

    Returns:
        Botocore session object

    Raises:
        Exception: If session creation fails
    """
    import quilt3
    return quilt3.session.create_botocore_session()
```

**Update callers:**

- [x] `src/quilt_mcp/tools/search.py` (lines 376-379)
- [x] `src/quilt_mcp/tools/stack_buckets.py` (lines 48-50)
- [x] `src/quilt_mcp/search/backends/elasticsearch.py` (lines 186, 207, 228-229)
- [x] `src/quilt_mcp/services/athena_service.py` (lines 90, 190, 204, 495)

**Delete from QuiltService:**
- `has_session_support()` (line 245)
- `get_session()` (line 256)
- `get_registry_url()` (line 269)
- `create_botocore_session()` (line 282)

**Verification:**
```bash
uv run pytest tests/unit/tools/test_search.py -v
uv run pytest tests/unit/tools/test_stack_buckets.py -v
uv run pytest tests/unit/services/test_athena_service.py -v
grep -r "quilt_service.has_session_support\|quilt_service.get_session\|quilt_service.get_registry_url\|quilt_service.create_botocore_session" src/
```

---

### Task 1.2: Refactor Authentication Methods in auth_metadata.py

**File:** `src/quilt_mcp/services/auth_metadata.py`

**Current problem:** Functions like `_get_catalog_info()`, `auth_status()`, and `configure_catalog()` instantiate QuiltService, creating circular dependencies.

**Solution:** Replace QuiltService calls with direct quilt3 imports.

**Changes needed:**

1. Replace `service = QuiltService()` with direct quilt3 usage
2. Extract `_extract_catalog_name_from_url()` from QuiltService (already exists in auth_metadata.py ✓)
3. Inline quilt3 calls: `quilt3.logged_in()`, `quilt3.config()`, etc.

**Update these functions:**

```python
def _get_catalog_info() -> Dict[str, Any]:
    """Return catalog configuration details by direct quilt3 calls."""
    import quilt3

    catalog_info: dict[str, Any] = {
        "catalog_name": None,
        "navigator_url": None,
        "registry_url": None,
        "is_authenticated": False,
        "logged_in_url": None,
        "region": None,
        "tabulator_data_catalog": None,
    }

    try:
        logged_in_url = quilt3.logged_in() if hasattr(quilt3, "logged_in") else None
        if logged_in_url:
            catalog_info["logged_in_url"] = logged_in_url
            catalog_info["is_authenticated"] = True
            catalog_info["catalog_name"] = _extract_catalog_name_from_url(logged_in_url)
    except Exception:
        pass

    try:
        config = quilt3.config() if hasattr(quilt3, "config") else None
        if config:
            navigator_url = config.get("navigator_url")
            registry_url = config.get("registryUrl")

            catalog_info["navigator_url"] = navigator_url
            catalog_info["registry_url"] = registry_url

            if not catalog_info["catalog_name"] and navigator_url:
                catalog_info["catalog_name"] = _extract_catalog_name_from_url(navigator_url)
            elif not catalog_info["catalog_name"] and registry_url:
                catalog_info["catalog_name"] = _extract_catalog_name_from_url(registry_url)
    except Exception:
        pass

    # Fallback catalog name if nothing found
    if not catalog_info["catalog_name"]:
        catalog_info["catalog_name"] = "unknown"

    return catalog_info


def _get_catalog_host_from_config() -> str | None:
    """Detect the catalog hostname from current Quilt configuration."""
    import quilt3
    from urllib.parse import urlparse

    try:
        logged_in_url = quilt3.logged_in() if hasattr(quilt3, "logged_in") else None
        if logged_in_url:
            parsed = urlparse(logged_in_url)
            hostname = parsed.hostname
            return hostname if hostname else None

        config = quilt3.config() if hasattr(quilt3, "config") else None
        if config and config.get("navigator_url"):
            nav_url = config["navigator_url"]
            parsed = urlparse(nav_url)
            hostname = parsed.hostname
            return hostname if hostname else None
    except Exception:
        pass
    return None


def configure_catalog(catalog_url: str) -> Dict[str, Any]:
    """Configure the Quilt catalog URL.

    Args:
        catalog_url: Full catalog URL or friendly name (demo, sandbox, open).

    Returns:
        Dict containing configuration result with status, catalog_url, and next steps.
    """
    import quilt3

    try:
        # Common catalog mappings
        catalog_mappings = {
            "demo": "https://demo.quiltdata.com",
            "sandbox": "https://sandbox.quiltdata.com",
            "open": "https://open.quiltdata.com",
            "example": "https://open.quiltdata.com",
        }

        # Determine target URL
        original_input = catalog_url
        if catalog_url.lower() in catalog_mappings:
            catalog_url = catalog_mappings[catalog_url.lower()]
            friendly_name = original_input.lower()
        elif catalog_url.startswith(("http://", "https://")):
            friendly_name = _extract_catalog_name_from_url(catalog_url)
        elif not catalog_url.startswith(("http://", "https://")):
            # Try to construct URL
            catalog_url = f"https://{catalog_url}"
            friendly_name = original_input
        else:
            friendly_name = _extract_catalog_name_from_url(catalog_url)

        # Configure the catalog using quilt3 directly
        quilt3.config(catalog_url)

        # Verify configuration
        config = quilt3.config() if hasattr(quilt3, "config") else None
        configured_url = config.get("navigator_url") if config else None

        return {
            "status": "success",
            "catalog_url": catalog_url,
            "configured_url": configured_url,
            "message": f"Successfully configured catalog: {friendly_name}",
            "next_steps": [
                "Login with: quilt3 login",
                "Verify with: auth_status()",
                "Start exploring with: packages_list()",
            ],
            "help": {
                "login_command": "quilt3 login",
                "verify_command": "auth_status()",
                "documentation": "https://docs.quiltdata.com/",
            },
        }

    except Exception as exc:
        return {
            "status": "error",
            "error": f"Failed to configure catalog: {exc}",
            "catalog_url": catalog_url,
            "available_catalogs": list(catalog_mappings.keys()) if "catalog_mappings" in locals() else [],
            "troubleshooting": {
                "common_issues": [
                    "Invalid catalog URL",
                    "Network connectivity problems",
                    "Quilt configuration file permissions",
                ],
                "suggested_fixes": [
                    "Verify the catalog URL is correct and accessible",
                    "Check network connectivity",
                    "Ensure write permissions to Quilt config directory",
                    "Use one of the available catalog names: demo, sandbox, open",
                ],
            },
        }
```

**Remove QuiltService import:**
```python
# DELETE THIS:
try:
    from quilt_mcp.services.quilt_service import QuiltService
except ModuleNotFoundError:
    class QuiltService:
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise ModuleNotFoundError("quilt3 is required for QuiltService")
```

**Delete from QuiltService:**
- `is_authenticated()` (line 41)
- `get_logged_in_url()` (line 50)
- `get_config()` (line 61)
- `get_catalog_config()` (line 72) - **DECISION NEEDED: Used elsewhere?**
- `set_config()` (line 135)
- `get_catalog_info()` (line 143)
- `_extract_catalog_name_from_url()` (line 216)

**Verification:**
```bash
uv run pytest tests/unit/services/test_auth_metadata.py -v
uv run pytest tests/unit/tools/test_catalog.py -v
grep -r "quilt_service.is_authenticated\|quilt_service.get_logged_in_url\|quilt_service.get_config\|quilt_service.set_config\|quilt_service.get_catalog_info" src/
```

---

## Phase 2: Admin & Search Utilities (Low Risk - Simplified)

Remove unnecessary wrapper methods and use direct imports instead.

### Task 2.1: Remove Admin Wrapper Methods (Use Direct Imports)

**Strategy:** Delete the pointless wrapper methods. Admin modules should be imported directly where needed.

**Update `src/quilt_mcp/services/tabulator_service.py`:**

```python
# OLD (top of file):
from quilt_mcp.services.quilt_service import QuiltService
quilt_service = QuiltService()
ADMIN_AVAILABLE = quilt_service.is_admin_available()

# NEW (top of file):
try:
    import quilt3.admin.tabulator
    ADMIN_AVAILABLE = True
except ImportError:
    ADMIN_AVAILABLE = False

# OLD (throughout file, e.g. line 141):
admin_tabulator = quilt_service.get_tabulator_admin()

# NEW (just use directly):
import quilt3.admin.tabulator
# Then: quilt3.admin.tabulator.method()
```

**Update `src/quilt_mcp/services/governance_service.py`:**

```python
# OLD (top of file, lines 25-38):
from quilt_mcp.services.quilt_service import QuiltService
quilt_service = QuiltService()
ADMIN_AVAILABLE = quilt_service.is_admin_available()

admin_users = quilt_service.get_users_admin() if ADMIN_AVAILABLE else None
admin_roles = quilt_service.get_roles_admin() if ADMIN_AVAILABLE else None
admin_sso_config = quilt_service.get_sso_config_admin() if ADMIN_AVAILABLE else None
admin_tabulator = quilt_service.get_tabulator_admin() if ADMIN_AVAILABLE else None

if ADMIN_AVAILABLE:
    admin_exceptions = quilt_service.get_admin_exceptions()
    Quilt3AdminError = admin_exceptions['Quilt3AdminError']
    UserNotFoundError = admin_exceptions['UserNotFoundError']
    BucketNotFoundError = admin_exceptions['BucketNotFoundError']

# NEW (top of file):
try:
    import quilt3.admin.users
    import quilt3.admin.roles
    import quilt3.admin.sso_config
    import quilt3.admin.tabulator
    from quilt3.admin.exceptions import (
        Quilt3AdminError,
        UserNotFoundError,
        BucketNotFoundError,
    )
    ADMIN_AVAILABLE = True
except ImportError:
    ADMIN_AVAILABLE = False
    # Define stub exceptions if needed for type hints
    Quilt3AdminError = Exception  # type: ignore
    UserNotFoundError = Exception  # type: ignore
    BucketNotFoundError = Exception  # type: ignore

# OLD (throughout file, e.g. line 115):
admin_users = quilt_service.get_users_admin()

# NEW (just use directly):
import quilt3.admin.users
# Then: quilt3.admin.users.method()
```

**Delete from QuiltService:**
- `is_admin_available()` (line 414)
- `get_tabulator_admin()` (line 430)
- `get_users_admin()` (line 443)
- `get_roles_admin()` (line 456)
- `get_sso_config_admin()` (line 469)
- `get_admin_exceptions()` (line 482)

**Why this is better:**

- ✅ No unnecessary function call overhead
- ✅ Standard Python import patterns
- ✅ Better IDE support and type checking
- ✅ Clearer errors (ImportError at module level)
- ✅ Less code to maintain

**Verification:**
```bash
uv run pytest tests/unit/services/test_tabulator_service.py -v
uv run pytest tests/unit/services/test_governance_service.py -v
grep -r "quilt_service.is_admin_available\|quilt_service.get_tabulator_admin\|quilt_service.get_users_admin\|quilt_service.get_roles_admin\|quilt_service.get_sso_config_admin\|quilt_service.get_admin_exceptions" src/
```

---

### Task 2.2: Extract Search API Utility

**File:** `src/quilt_mcp/utils.py` or inline in caller

**Add new function:**

```python
def get_quilt3_search_api() -> Any:
    """Get search API for package searching.

    Returns:
        Search API module
    """
    from quilt3.search_util import search_api
    return search_api
```

**Update caller:**

- [x] `src/quilt_mcp/search/backends/elasticsearch.py` (line 449)

**Delete from QuiltService:**
- `get_search_api()` (line 401)

**Verification:**
```bash
uv run pytest tests/unit/search/backends/test_elasticsearch.py -v
grep -r "quilt_service.get_search_api" src/
```

---

## Phase 3: Package Operations → QuiltOps (High Risk)

These methods need to be migrated to the QuiltOps abstraction layer. This is the core migration work.

### Task 3.1: Add Package Creation to QuiltOps Interface

**File:** `src/quilt_mcp/ops/quilt_ops.py`

**Add new abstract method:**

```python
@abstractmethod
def create_package_revision(
    self,
    package_name: str,
    s3_uris: List[str],
    metadata: Optional[Dict] = None,
    registry: Optional[str] = None,
    message: str = "Package created via QuiltOps",
    auto_organize: bool = True,
    copy: str = "all",
) -> Dict[str, Any]:
    """Create and push package in single operation.

    This method replaces the object-based manipulation pattern and provides
    complete package creation without exposing backend-specific package objects.

    Args:
        package_name: Name of the package to create
        s3_uris: List of S3 URIs to include in the package
        metadata: Optional metadata dictionary for the package
        registry: Target registry (uses default if None)
        message: Commit message for package creation
        auto_organize: True for smart folder organization (s3_package style),
                      False for simple flattening (package_ops style)
        copy: Copy mode for objects - "all" (copy all), "none" (copy none),
             or "same_bucket" (copy only objects in same bucket as registry)

    Returns:
        Dict with package creation results, never backend-specific package objects

    Raises:
        ValidationError: If input parameters are invalid
        BackendError: If package creation or push fails
    """
    pass
```

**Implement in Quilt3_Backend:**

- Copy implementation from `QuiltService.create_package_revision()` (lines 296-352)
- Copy helper methods (lines 509-775):
  - `_validate_package_inputs()`
  - `_populate_package_files()`
  - `_add_files_with_smart_organization()`
  - `_add_files_with_flattening()`
  - `_push_package()`
  - `_build_creation_result()`
  - `_normalize_registry()`
  - `_organize_s3_files_smart()`
  - `_collect_objects_flat()`
  - `_build_selector_fn()`

**Update callers:**

- [x] `src/quilt_mcp/tools/packages.py` (lines 567, 1267)

**Delete from QuiltService:**
- `create_package_revision()` (line 296)
- All private helper methods (lines 509-775)

**Verification:**
```bash
uv run pytest tests/unit/tools/test_packages.py::test_package_create_from_s3 -v
uv run pytest tests/unit/tools/test_packages.py::test_package_update -v
grep -r "quilt_service.create_package_revision" src/
```

---

### Task 3.2: Add Package Browsing to QuiltOps

**File:** `src/quilt_mcp/ops/quilt_ops.py`

**Note:** `browse_content()` already exists in QuiltOps interface! But we need to map `browse_package()` calls.

**Analysis:** The existing `browse_content()` method in QuiltOps returns `List[Content_Info]`, which is what we need. However, `QuiltService.browse_package()` returns a raw `quilt3.Package` object.

**Strategy:** Replace `quilt_service.browse_package()` calls with `QuiltOps.browse_content()` calls.

**Update callers:**

- [x] `src/quilt_mcp/tools/packages.py` (lines 1047, 1051, 1054, 1058, 1469)

**Changes needed in packages.py:**

```python
# OLD:
pkg1 = quilt_service.browse_package(package1_name, registry=normalized_registry)
# Iterate over pkg1 entries...

# NEW:
contents1 = quilt_ops.browse_content(package1_name, normalized_registry, path="")
# Iterate over contents1 (List[Content_Info])
```

**Delete from QuiltService:**
- `browse_package()` (line 354) - **ONLY after all callers updated**

**Verification:**
```bash
uv run pytest tests/unit/tools/test_packages.py::test_package_diff -v
uv run pytest tests/unit/tools/test_packages.py::test_package_delete -v
grep -r "quilt_service.browse_package" src/
```

---

### Task 3.3: Add Package Listing to QuiltOps

**File:** `src/quilt_mcp/ops/quilt_ops.py`

**Note:** `search_packages()` already exists, but `list_packages()` is slightly different.

**Analysis:**
- `QuiltOps.search_packages()` returns `List[Package_Info]` (filtered search)
- `QuiltService.list_packages()` returns `Iterator[str]` (all packages)

**Decision:** Add `list_all_packages()` to QuiltOps interface:

```python
@abstractmethod
def list_all_packages(self, registry: str) -> List[str]:
    """List all package names in a registry.

    Args:
        registry: Registry URL

    Returns:
        List of package names (strings)

    Raises:
        AuthenticationError: When authentication credentials are invalid or missing
        BackendError: When the backend operation fails
    """
    pass
```

**Implement in Quilt3_Backend:**

```python
def list_all_packages(self, registry: str) -> List[str]:
    """List all package names in a registry."""
    try:
        import quilt3
        return list(quilt3.list_packages(registry=registry))
    except Exception as e:
        raise BackendError(f"Failed to list packages: {e}") from e
```

**Update callers:**

- [x] Check if anyone actually calls `quilt_service.list_packages()` - **NO DIRECT CALLS FOUND**

**Delete from QuiltService:**
- `list_packages()` (line 373)

**Verification:**
```bash
grep -r "quilt_service.list_packages" src/
uv run pytest tests/unit/backends/test_quilt3_backend.py::test_list_all_packages -v
```

---

### Task 3.4: Handle Bucket Creation

**File:** `src/quilt_mcp/ops/quilt_ops.py`

**Analysis:** `QuiltService.create_bucket()` just wraps `quilt3.Bucket()`. This is used for S3 operations, not domain package operations.

**Decision:** This doesn't belong in QuiltOps (which is for package/catalog operations). Instead, move to utils.py as a utility.

**File:** `src/quilt_mcp/utils.py`

**Add new function:**

```python
def create_quilt3_bucket(bucket_uri: str) -> Any:
    """Create a Bucket instance for S3 operations.

    Args:
        bucket_uri: S3 URI for the bucket

    Returns:
        quilt3.Bucket instance
    """
    import quilt3
    return quilt3.Bucket(bucket_uri)
```

**Update callers:**

- [x] Search for usages: `grep -r "quilt_service.create_bucket" src/`
- Result: **NO DIRECT CALLS FOUND**

**Delete from QuiltService:**
- `create_bucket()` (line 387)

**Verification:**
```bash
grep -r "quilt_service.create_bucket\|QuiltService.*create_bucket" src/
```

---

## Phase 4: Cleanup & Delete QuiltService

Remove the now-unused QuiltService class and all remaining references.

### Task 4.1: Remove get_quilt3_module() Utility

**Analysis:** `src/quilt_mcp/tools/packages.py` line 55 does:
```python
quilt3 = quilt_service.get_quilt3_module()
```

This is just a pass-through to import quilt3. Replace with direct import.

**Update caller:**

```python
# OLD:
from quilt_mcp.services.quilt_service import QuiltService
quilt_service = QuiltService()
quilt3 = quilt_service.get_quilt3_module()

# NEW:
import quilt3
```

**Delete from QuiltService:**
- `get_quilt3_module()` (line 499)

**Verification:**
```bash
uv run pytest tests/unit/tools/test_packages.py -v
grep -r "quilt_service.get_quilt3_module\|get_quilt3_module" src/
```

---

### Task 4.2: Delete QuiltService Class

**Prerequisites:** All previous tasks completed, all methods migrated or deleted.

**Final verification before deletion:**

```bash
# Check for any remaining references
grep -r "QuiltService" src/ --exclude-dir=__pycache__
grep -r "quilt_service\." src/ --exclude-dir=__pycache__
grep -r "from quilt_mcp.services.quilt_service import" src/ --exclude-dir=__pycache__
```

**Delete files:**

- [x] `src/quilt_mcp/services/quilt_service.py` (entire file)

**Update imports in:**

- [x] `src/quilt_mcp/services/__init__.py` - Remove QuiltService export

**Verification:**
```bash
# Run full test suite
uv run pytest tests/ -v

# Verify no QuiltService references remain
grep -r "QuiltService" src/ --exclude-dir=__pycache__

# Check that all MCP tools still work
uv run pytest tests/integration/ -v
```

---

## Phase 5: Domain Utilities Migration

Extract reusable utility functions to appropriate modules.

### Task 5.1: Create domain/package_utils.py

**File:** `src/quilt_mcp/domain/package_utils.py`

**Extract these utilities from QuiltService:**

```python
"""Utility functions for package operations."""

from typing import Dict, List, Any
from pathlib import Path


def normalize_registry(registry: str | None) -> str | None:
    """Normalize registry URL format.

    Args:
        registry: Registry URL to normalize

    Returns:
        Normalized registry URL
    """
    if not registry:
        return None

    # Basic normalization - ensure s3:// prefix for S3 registries
    if registry.startswith("s3://"):
        return registry
    elif "/" in registry and not registry.startswith("http"):
        return f"s3://{registry}"
    else:
        return registry


def organize_s3_files_smart(s3_uris: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Smart organization of S3 files into logical folders.

    This implements the s3_package.py organization strategy.

    Args:
        s3_uris: List of S3 URIs to organize

    Returns:
        Dict mapping folder names to lists of file objects
    """
    organized: dict[str, list[dict[str, Any]]] = {}

    for s3_uri in s3_uris:
        # Extract key from S3 URI
        parts = s3_uri.replace("s3://", "").split("/")
        if len(parts) < 2:
            continue

        bucket = parts[0]
        key = "/".join(parts[1:])

        # Determine folder based on file extension and path
        file_path = Path(key)
        file_ext = file_path.suffix.lower()

        # Simple folder classification based on file extension
        if file_ext in ['.csv', '.tsv', '.json', '.parquet']:
            folder = "data"
        elif file_ext in ['.txt', '.md', '.rst', '.pdf']:
            folder = "docs"
        elif file_ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg']:
            folder = "images"
        elif file_ext in ['.py', '.r', '.sql', '.sh']:
            folder = "scripts"
        else:
            folder = "misc"

        if folder not in organized:
            organized[folder] = []

        organized[folder].append(
            {
                "Key": key,
                "Size": 1000,  # Mock size for testing
                "LastModified": "2023-01-01T00:00:00Z",
            }
        )

    return organized


def collect_objects_flat(s3_uris: List[str]) -> List[Dict[str, str]]:
    """Collect S3 objects with simple flattened logical keys.

    This implements the package_ops.py flattening strategy.

    Args:
        s3_uris: List of S3 URIs to collect

    Returns:
        List of objects with s3_uri and logical_key
    """
    collected = []

    for s3_uri in s3_uris:
        # Extract filename from S3 URI for logical key
        parts = s3_uri.replace("s3://", "").split("/")
        if len(parts) >= 2:
            filename = parts[-1]  # Just the filename
            collected.append({"s3_uri": s3_uri, "logical_key": filename})

    return collected


def build_selector_fn(copy_mode: str, target_registry: str | None):
    """Build a Quilt selector_fn based on desired copy behavior.

    Args:
        copy_mode: Copy mode - "all", "none", or "same_bucket"
        target_registry: Target registry for bucket comparison

    Returns:
        Callable selector function for quilt3.Package.push()
    """
    if not target_registry:
        # Default behavior if no registry
        return lambda _logical_key, _entry: copy_mode == "all"

    # Extract target bucket from registry
    target_bucket = target_registry.replace("s3://", "").split("/", 1)[0]

    def selector_all(_logical_key, _entry):
        return True

    def selector_none(_logical_key, _entry):
        return False

    def selector_same_bucket(_logical_key, entry):
        try:
            physical_key = str(getattr(entry, "physical_key", ""))
        except Exception:
            physical_key = ""
        if not physical_key.startswith("s3://"):
            return False
        try:
            bucket = physical_key.split("/", 3)[2]
        except Exception:
            return False
        return bucket == target_bucket

    if copy_mode == "none":
        return selector_none
    elif copy_mode == "same_bucket":
        return selector_same_bucket
    else:  # "all" or default
        return selector_all
```

**Note:** These utilities are currently duplicated in QuiltService helper methods. After this migration, they'll be available for reuse across the codebase.

---

## Acceptance Criteria

### Migration Complete When:

- [x] All 35 methods from QuiltService have been:
  - Migrated to QuiltOps, utils.py, or domain utilities
  - OR deleted as unnecessary pass-throughs
- [x] No references to `QuiltService` remain in src/
- [x] No references to `quilt_service.*` method calls remain
- [x] All existing tests pass
- [x] No direct quilt3 imports in tools/ (all go through QuiltOps or utils)
- [x] `src/quilt_mcp/services/quilt_service.py` deleted

### Verification Commands:

```bash
# No QuiltService references
grep -r "QuiltService" src/ --exclude-dir=__pycache__ | grep -v "test_" | wc -l
# Expected: 0

# No quilt_service method calls
grep -r "quilt_service\." src/ --exclude-dir=__pycache__ | wc -l
# Expected: 0

# All tests pass
uv run pytest tests/ -v --tb=short
# Expected: All passed

# Integration tests pass
uv run pytest tests/integration/ -v
# Expected: All passed
```

---

## Migration Progress Tracking

### Phase 1: Session & Auth ✅
- [ ] Task 1.1: Extract Session Utilities
- [ ] Task 1.2: Refactor Authentication Methods

### Phase 2: Admin & Search ✅
- [ ] Task 2.1: Extract Admin Utilities
- [ ] Task 2.2: Extract Search API Utility

### Phase 3: Package Operations ⚠️
- [ ] Task 3.1: Add Package Creation to QuiltOps
- [ ] Task 3.2: Add Package Browsing to QuiltOps
- [ ] Task 3.3: Add Package Listing to QuiltOps
- [ ] Task 3.4: Handle Bucket Creation

### Phase 4: Cleanup 🔴
- [ ] Task 4.1: Remove get_quilt3_module()
- [ ] Task 4.2: Delete QuiltService Class

### Phase 5: Domain Utilities 📦
- [ ] Task 5.1: Create domain/package_utils.py

**Total Methods:** 35
**Migrated:** 0
**Deleted:** 0
**Remaining:** 35

---

## Notes

1. **Test Coverage:** All migrations should be verified with existing tests before proceeding to the next task.
2. **Backward Compatibility:** No changes to MCP tool interfaces or response formats.
3. **Error Handling:** Maintain existing error patterns and messages.
4. **Documentation:** Update inline comments and docstrings as methods are migrated.
5. **Git Commits:** Commit after each task completion with descriptive messages.
