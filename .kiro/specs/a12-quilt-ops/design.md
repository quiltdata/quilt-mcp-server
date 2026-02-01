# Design: Migration All MCP Tools → QuiltOps

## Overview

This design documents the migration of all remaining MCP tools from QuiltService to QuiltOps. The key insight is that **we need to translate existing working code, not rewrite from scratch**. The QuiltService already contains all the necessary implementations - we just need to move them to the appropriate QuiltOps backend.

## Current State Analysis

### Already Migrated Tools
- `packages_list()` tool → Uses `quilt_ops.search_packages()`
- `package_browse()` tool → Uses `quilt_ops.browse_content()`

### Tools Needing Migration
Based on analysis of existing QuiltService usage:

1. **Package Creation Tools**
   - `package_create()` tool (line 1103) → Uses `quilt_service.create_package_revision()`
   - `package_create_from_s3()` tool (line 1661) → Uses `quilt_service.create_package_revision()`

2. **Package Diffing Tool**
   - `package_diff()` tool (line 963) → Uses `quilt_service.browse_package()`

3. **Package Update Tool**
   - `package_update()` tool (line 1338) → Uses `quilt_service.browse_package()`

4. **GraphQL Helpers**
   - `search._get_graphql_endpoint()` helper (line 363) → Uses `quilt_service` session methods
   - `stack_buckets._get_stack_buckets_via_graphql()` helper (line 42) → Uses `quilt_service` session methods

## Translation Strategy

### Missing QuiltOps Methods

The QuiltService contains implementations that need to be translated to QuiltOps:

#### 1. Package Diffing (`diff_packages`)

**Current QuiltService Implementation:**
```python
def browse_package(self, package_name: str, registry: str, top_hash: str | None = None, **kwargs: Any) -> Any:
    """Browse an existing package."""
    browse_args = {"registry": registry}
    if top_hash:
        browse_args["top_hash"] = top_hash
    browse_args.update(kwargs)
    return quilt3.Package.browse(package_name, **browse_args)
```

**Translation to QuiltOps:**
```python
def diff_packages(
    self,
    package1_name: str,
    package2_name: str,
    registry: str,
    package1_hash: Optional[str] = None,
    package2_hash: Optional[str] = None,
) -> Dict[str, List[str]]:
    """Compare two package versions and return differences."""
    # Use existing browse logic from QuiltService
    pkg1 = quilt3.Package.browse(
        package1_name, 
        registry=registry, 
        top_hash=package1_hash
    )
    pkg2 = quilt3.Package.browse(
        package2_name, 
        registry=registry, 
        top_hash=package2_hash
    )
    
    # Use quilt3's built-in diff functionality
    diff_result = pkg1.diff(pkg2)
    
    # Transform to domain format
    return {
        "added": [str(path) for path in diff_result.get("added", [])],
        "deleted": [str(path) for path in diff_result.get("deleted", [])],
        "modified": [str(path) for path in diff_result.get("modified", [])]
    }
```

#### 2. Package Updates (`update_package_revision`)

**Current Pattern in Tools:**
The `package_update()` tool currently:
1. Browses existing package using `quilt_service.browse_package()`
2. Adds new files using `pkg.set()` or `pkg.set_dir()`
3. Pushes with `pkg.push()`

**Translation to QuiltOps:**
```python
def update_package_revision(
    self,
    package_name: str,
    s3_uris: List[str],
    registry: str,
    metadata: Optional[Dict] = None,
    message: str = "Package updated via QuiltOps",
    auto_organize: bool = False,
    copy: str = "none",
) -> Package_Creation_Result:
    """Update an existing package with new files."""
    # Browse existing package (translate from QuiltService.browse_package)
    pkg = quilt3.Package.browse(package_name, registry=registry)
    
    # Add S3 URIs (existing logic from tools)
    for s3_uri in s3_uris:
        if auto_organize:
            # Use set_dir for auto-organization
            pkg.set_dir("", s3_uri)
        else:
            # Use set for individual files
            pkg.set(Path(s3_uri).name, s3_uri)
    
    # Handle copy parameter with selector_fn
    selector_fn = None
    if copy != "none":
        # Implement copy logic based on existing patterns
        pass
    
    # Push package (existing logic)
    result = pkg.push(
        registry=registry,
        message=message,
        metadata=metadata,
        selector_fn=selector_fn
    )
    
    # Return domain object
    return Package_Creation_Result(
        package_name=package_name,
        registry=registry,
        top_hash=result.top_hash,
        catalog_url=f"{registry}/b/{package_name}/tree/{result.top_hash}/"
    )
```

### GraphQL Session Translation

**Current QuiltService Implementation:**
```python
def get_session(self) -> Any:
    """Get authenticated requests session."""
    if not self.has_session_support():
        raise Exception("quilt3 session not available")
    return quilt3.session.get_session()
```

**Translation to QuiltOps:**
The `execute_graphql_query()` method already exists in QuiltOps and handles session management internally.

## Implementation Plan

### Phase 1: Translate Package Diffing (Complete End-to-End)

1. **Add `diff_packages()` to QuiltOps interface**
   - Copy method signature from analysis above
   - Add comprehensive docstring

2. **Implement in Quilt3_Backend**
   - **Translate** the `browse_package()` logic from QuiltService
   - Use existing quilt3.Package.browse() calls
   - Add quilt3 diff() functionality
   - Transform result to domain format

3. **Add tests**
   - Mock the same quilt3 calls that QuiltService uses
   - Test the transformation logic

4. **Migrate `package_diff()` tool**
   - Replace `quilt_service.browse_package()` calls
   - Use new `quilt_ops.diff_packages()` method
   - Keep existing result formatting

5. **Test complete workflow**
   - Verify tool works end-to-end
   - Fix any issues before proceeding

### Phase 2: Translate Package Updates (Complete End-to-End)

1. **Add `update_package_revision()` to QuiltOps interface**
   - Copy method signature from analysis above

2. **Implement in Quilt3_Backend**
   - **Translate** existing package update logic from tools
   - Use same quilt3.Package.browse() pattern
   - Copy file addition logic (pkg.set/pkg.set_dir)
   - Copy push logic with selector_fn

3. **Add tests**
   - Mock same operations as existing tool code

4. **Migrate `package_update()` tool**
   - Replace direct quilt3 calls with QuiltOps method
   - Keep existing parameter handling

5. **Test complete workflow**

### Phase 3: Translate Package Creation (Complete End-to-End)

1. **Migrate `package_create()` and `package_create_from_s3()` tools**
   - Replace `quilt_service.create_package_revision()` calls
   - Use existing `quilt_ops.create_package_revision()` method
   - Update result handling for QuiltOps format

2. **Test complete workflow**

### Phase 4: Translate GraphQL Operations (Complete End-to-End)

1. **Migrate `search._get_graphql_endpoint()` helper**
   - Replace QuiltService session usage
   - Use existing `quilt_ops.execute_graphql_query()` method

2. **Migrate `stack_buckets._get_stack_buckets_via_graphql()` helper**
   - Same translation pattern

3. **Test complete workflows**

### Phase 5: Cleanup

1. **Verify no remaining QuiltService usage**
2. **Delete QuiltService files**
3. **Final testing**

## Key Translation Principles

1. **Don't Rewrite - Translate**: Copy existing working code from QuiltService and tools
2. **Preserve Behavior**: Keep exact same error handling and return formats
3. **Minimal Changes**: Only change the interface, not the implementation logic
4. **Test Same Patterns**: Mock the same quilt3 calls that worked before

## Testing Strategy

### Unit Tests (Backend Focus)
- **Add proper mocked unit tests** for new QuiltOps backend methods
- Mock quilt3 calls (Package.browse, diff, push, etc.) in backend tests
- Test business logic extraction and domain object transformation
- Located in `tests/unit/backends/test_quilt3_backend_packages.py`

### Tool Tests (Minimal)
- **Remove trivial unit tests** for tools that just test parameter validation
- Keep only tests that verify tool-specific error handling and response formatting
- Tools become thin wrappers, so extensive unit testing is not needed

### Integration Tests (End-to-End)
- **Ensure integration tests exist and pass** for all migrated functionality
- Use `QUILT_TEST_BUCKET` environment variable for real AWS operations
- Run with `make test-integration`
- Test complete workflows from tool call to actual package operations

### Test Configuration
Integration tests require proper AWS setup:

```bash
# Required environment variables (set in .env file)
QUILT_TEST_BUCKET=s3://your-test-bucket
QUILT_CATALOG_URL=https://your-catalog.com
AWS_PROFILE=your-aws-profile  # or AWS credentials

# Test fixtures available in tests/conftest.py
test_bucket()      # Returns bucket name without s3:// prefix
test_registry()    # Returns full S3 URI (s3://bucket-name)
test_bucket_name() # Alias for test_bucket()
```

**Important**: Integration tests will be skipped if `QUILT_TEST_BUCKET` is not set. In CI/CD, tests fail if the environment variable is missing.

## Files Requiring Changes

### New Methods to Add
- `src/quilt_mcp/ops/quilt_ops.py` - Add abstract method signatures
- `src/quilt_mcp/backends/quilt3_backend_packages.py` - Translate implementations

### Tools to Migrate
- `src/quilt_mcp/tools/packages.py` - 4 tools to migrate
- `src/quilt_mcp/tools/search.py` - 1 helper to migrate  
- `src/quilt_mcp/tools/stack_buckets.py` - 1 helper to migrate

### Tests to Add
- `tests/unit/backends/test_quilt3_backend_packages.py` - Test translated methods

### Files to Delete (After Migration)
- `src/quilt_mcp/services/quilt_service.py`
- `tests/unit/test_quilt_service.py`

## Success Criteria

- All 6 tools/helpers use QuiltOpsFactory exclusively
- No QuiltService imports remain in src/
- QuiltService files deleted
- All tests pass: `make test-all`
- No regressions in existing functionality
- Same behavior as before, just through QuiltOps interface