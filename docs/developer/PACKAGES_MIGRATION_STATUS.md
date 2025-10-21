# Packages.py Pydantic Migration Status

## Overview
This document tracks the migration of `src/quilt_mcp/tools/packages.py` from `dict[str, Any]` returns to Pydantic models.

## Migration Date
2025-01-XX (In Progress)

## ✅ Completed Tasks

### 1. Model Creation
All necessary Pydantic models have been created:

#### Input Models (`src/quilt_mcp/models/inputs.py`)
- ✅ `PackageBrowseParams` (already existed)
- ✅ `PackageCreateParams` (already existed)
- ✅ `PackageUpdateParams` (newly created)
- ✅ `PackageDeleteParams` (newly created)
- ✅ `PackagesListParams` (newly created)
- ✅ `PackageDiffParams` (newly created)
- ✅ `PackageCreateFromS3Params` (newly created)

#### Response Models (`src/quilt_mcp/models/responses.py`)
- ✅ `PackageBrowseSuccess` (updated structure)
- ✅ `PackageCreateSuccess` / `PackageCreateError` (already existed)
- ✅ `PackageUpdateSuccess` / `PackageUpdateError` (newly created)
- ✅ `PackageDeleteSuccess` / `PackageDeleteError` (newly created)
- ✅ `PackagesListSuccess` / `PackagesListError` (newly created)
- ✅ `PackageDiffSuccess` / `PackageDiffError` (newly created)
- ✅ `PackageCreateFromS3Success` / `PackageCreateFromS3Error` (newly created)
- ✅ `PackageSummary` (helper model for package_browse)

#### Type Aliases
- ✅ All response type aliases added to `responses.py`
- ✅ All models exported from `src/quilt_mcp/models/__init__.py`

### 2. Function Migrations

#### Fully Migrated Functions ✅
1. **`packages_list`** (lines 592-642)
   - Signature: `def packages_list(params: PackagesListParams) -> PackagesListSuccess | PackagesListError`
   - Returns Pydantic models
   - Handles all error cases
   - Updated docstrings

2. **`package_browse`** (lines 646-820)
   - Signature: `def package_browse(params: PackageBrowseParams) -> PackageBrowseSuccess | ErrorResponse`
   - Returns Pydantic models
   - All parameters accessed via `params.*`
   - Updated docstrings with Pydantic examples

3. **`package_diff`** (lines 864-938)
   - Signature: `def package_diff(params: PackageDiffParams) -> PackageDiffSuccess | PackageDiffError`
   - Returns Pydantic models
   - Error handling with typed responses
   - Updated docstrings

### 3. Supporting Changes
- ✅ Added all model imports to `packages.py` (lines 18-41)
- ✅ Updated `PackageBrowseSuccess` model to match actual return structure
- ✅ Created `PackageSummary` helper model for nested summary data

## 🔄 Remaining Work

### Functions Needing Migration

#### 1. `package_create` (lines 941-1111)
**Current Signature:**
```python
def package_create(
    package_name: str,
    s3_uris: list[str],
    registry: str = DEFAULT_REGISTRY,
    metadata: dict[str, Any] | None = None,
    message: str = "Created via package_create tool",
    flatten: bool = True,
    copy_mode: str = "all",
) -> dict[str, Any]:
```

**Target Signature:**
```python
def package_create(params: PackageCreateParams) -> PackageCreateSuccess | PackageCreateError:
```

**Migration Steps:**
1. Change function signature to accept `PackageCreateParams`
2. Replace all parameter references with `params.*` (e.g., `package_name` → `params.package_name`)
3. Replace dict returns with `PackageCreateSuccess(...)` or `PackageCreateError(...)`
4. Update docstring to reflect new signature
5. Handle the metadata parameter through `params.metadata`
6. Keep the existing business logic intact

**Key Changes Needed:**
- Line 993-1024: Metadata validation should be moved to Pydantic model or kept as-is
- Line 1001-1024: Error returns should use `PackageCreateError` model
- Line 1099-1111: Success return should use `PackageCreateSuccess` model
- All references to `package_name`, `s3_uris`, `registry`, `metadata`, `message`, `flatten`, `copy_mode` should use `params.*`

#### 2. `package_update` (lines 1114-1273)
**Current Signature:**
```python
def package_update(
    package_name: str,
    s3_uris: list[str],
    registry: str = DEFAULT_REGISTRY,
    metadata: dict[str, Any] | None = None,
    message: str = "Added objects via package_update tool",
    flatten: bool = True,
    copy_mode: str = "all",
) -> dict[str, Any]:
```

**Target Signature:**
```python
def package_update(params: PackageUpdateParams) -> PackageUpdateSuccess | PackageUpdateError:
```

**Migration Steps:**
1. Change function signature
2. Replace parameter references
3. Update return statements:
   - Line 1221: Error → `PackageUpdateError`
   - Line 1251-1267: Success → `PackageUpdateSuccess`
4. Update docstring

#### 3. `package_delete` (lines 1275-1337)
**Current Signature:**
```python
def package_delete(package_name: str, registry: str = DEFAULT_REGISTRY) -> dict[str, Any]:
```

**Target Signature:**
```python
def package_delete(params: PackageDeleteParams) -> PackageDeleteSuccess | PackageDeleteError:
```

**Migration Steps:**
1. Change function signature
2. Replace `package_name` with `params.package_name`
3. Replace `registry` with `params.registry`
4. Update return statements:
   - Line 1320-1328: Success → `PackageDeleteSuccess`
   - Line 1330-1336: Error → `PackageDeleteError`
5. Update docstring

#### 4. `package_create_from_s3` (lines 1340-1695)
**Current Signature:**
```python
def package_create_from_s3(
    source_bucket: str,
    package_name: str,
    source_prefix: str = "",
    target_registry: str | None = None,
    description: str = "",
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    auto_organize: bool = True,
    generate_readme: bool = True,
    confirm_structure: bool = True,
    metadata_template: str = "standard",
    dry_run: bool = False,
    metadata: dict[str, Any] | None = None,
    copy_mode: str = "all",
    force: bool = False,
) -> dict[str, Any]:
```

**Target Signature:**
```python
def package_create_from_s3(params: PackageCreateFromS3Params) -> PackageCreateFromS3Success | PackageCreateFromS3Error:
```

**Migration Steps:**
1. Change function signature
2. Replace ALL 15 parameter references with `params.*`
3. Update complex error returns (lines 1407-1450, 1482-1500, 1514-1536, 1541-1542)
4. Update success returns (lines 1614-1629, 1653-1688)
5. Update docstring extensively

## Migration Pattern Example

### Before:
```python
def my_function(
    param1: str,
    param2: int = 10,
) -> dict[str, Any]:
    if not param1:
        return {"error": "param1 required"}

    try:
        result = do_something(param1, param2)
        return {
            "status": "success",
            "data": result,
            "param2_used": param2,
        }
    except Exception as e:
        return {"error": str(e)}
```

### After:
```python
def my_function(params: MyFunctionParams) -> MyFunctionSuccess | MyFunctionError:
    if not params.param1:
        return MyFunctionError(error="param1 required")

    try:
        result = do_something(params.param1, params.param2)
        return MyFunctionSuccess(
            data=result,
            param2_used=params.param2,
        )
    except Exception as e:
        return MyFunctionError(error=str(e))
```

## Testing Strategy

After migration, test each function with:

### Unit Tests
```python
def test_function_success():
    params = FunctionParams(param1="value")
    result = my_function(params)
    assert isinstance(result, FunctionSuccess)
    assert result.success is True

def test_function_error():
    params = FunctionParams(param1="")
    result = my_function(params)
    assert isinstance(result, FunctionError)
    assert result.success is False
```

### Integration Tests
- Verify MCP tool registration still works
- Confirm dict serialization via `result.model_dump()` maintains structure
- Check backward compatibility with existing callers

## Notes

### Preserved Behavior
- All business logic remains unchanged
- Authorization checks (`_authorize_package`) work as before
- Metadata attachment (`_attach_auth_metadata`) continues to function
- Helper functions like `_collect_objects_into_package`, `_build_selector_fn` remain untouched

### Breaking Changes
None - the Pydantic models serialize to the same dict structure as before when using `.model_dump()`.

### Future Improvements
1. Consider moving metadata validation logic to Pydantic model validators
2. Add `@field_validator` decorators for custom validation rules
3. Create more granular models for complex nested structures (e.g., `confirmation_info` in package_create_from_s3)

## Completion Checklist

- [x] Create all input models
- [x] Create all response models
- [x] Export models from `__init__.py`
- [x] Add imports to `packages.py`
- [x] Migrate `packages_list`
- [x] Migrate `package_browse`
- [x] Migrate `package_diff`
- [ ] Migrate `package_create`
- [ ] Migrate `package_update`
- [ ] Migrate `package_delete`
- [ ] Migrate `package_create_from_s3`
- [ ] Run unit tests
- [ ] Run integration tests
- [ ] Update MCP server tool registrations
- [ ] Verify backward compatibility
- [ ] Update documentation

## Estimated Remaining Time
- `package_create`: ~30 minutes
- `package_update`: ~20 minutes
- `package_delete`: ~10 minutes
- `package_create_from_s3`: ~45 minutes
- Testing & validation: ~1 hour

**Total: ~2.5 hours**
