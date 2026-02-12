# QuiltOps Package Deletion Implementation

## Tasks

1. **Add abstract method to QuiltOps**
   - Add `delete_package(bucket: str, name: str) -> bool` to `ops/quilt_ops.py`
   - Document expected behavior and return value

2. **Implement quilt3 backend**
   - In `ops/quilt_ops_concrete.py` (Quilt3Ops)
   - Single call: `quilt3.Package.browse(name, registry).delete()`
   - Handle exceptions → return False

3. **Implement platform backend**
   - In `ops/quilt_ops_concrete.py` (PlatformOps)
   - Read `.quilt/named_packages/{name}/*` timestamps
   - For each timestamp: call `packageRevisionDelete` GraphQL mutation
   - Handle partial failures (continue on error, return False if any fail)

4. **Refactor existing MCP tool**
   - In `tools/packages.py` line 1557: replace `quilt3.delete_package()` call
   - Get backend from context: `backend = get_backend()`
   - Call `backend.delete_package(name=package_name, bucket=normalized_registry)`
   - Keep existing auth checks and error handling

5. **Tests**
   - Unit: `tests/unit/ops/test_quilt_ops_concrete.py` - mock both backends
   - Func: `tests/func/test_package_operations.py` - mock GraphQL/API calls
   - E2E: `tests/e2e/backend/workflows/test_package_lifecycle.py` - real deletion

6. **Documentation**
   - Update README.md tools table
   - Add example to docs/examples/
   - CHANGELOG entry
