# Tasks: Migration All MCP Tools → QuiltOps

## Feature 1: Package Diffing (Complete End-to-End)

- [ ] 1.1 Add diff_packages() abstract method to QuiltOps base class
  - Copy method signature from design.md
  - Include comprehensive docstring with parameters and return format
  - Ensure method returns Dict[str, List[str]] with keys: added, deleted, modified

- [ ] 1.2 Extract package diffing logic from package_diff() tool to Quilt3_Backend.diff_packages()
  - **EXTRACT** the package browsing logic from `package_diff()` tool (lines 1029-1040)
  - **MOVE** the conditional hash handling: `if package1_hash:` logic to backend
  - **MOVE** the quilt3.Package.browse() calls with registry and top_hash parameters to backend
  - **MOVE** the pkg1.diff(pkg2) call and result processing (lines 1047-1058) to backend
  - **MOVE** the tuple-to-dict transformation logic for diff results to backend
  - Return domain dict format instead of raw quilt3 objects

- [ ] 1.3 Add proper mocked unit tests for backend diff_packages() method
  - Add tests in `tests/unit/backends/test_quilt3_backend_packages.py`
  - Mock quilt3.Package.browse() calls with proper parameters
  - Mock pkg1.diff(pkg2) calls and return values
  - Test conditional hash handling logic
  - Test tuple-to-dict transformation logic
  - Test error handling for missing packages or invalid hashes
  - Verify domain dict format is returned correctly

- [ ] 1.4 Remove trivial unit tests for package_diff() tool
  - Identify and remove unit tests that just test tool parameter validation
  - Keep only tests that verify tool-specific error handling and response formatting
  - Tools are now thin wrappers, so extensive unit testing is not needed

- [ ] 1.5 Rewrite package_diff() tool as thin wrapper
  - **REPLACE** lines 1029-1058 (all business logic) with single `quilt_ops.diff_packages()` call
  - **REMOVE** all quilt3 manipulation logic (now in backend)
  - Keep parameter validation and error handling
  - Transform QuiltOps domain result to PackageDiffSuccess/PackageDiffError response format

- [ ] 1.6 Ensure integration tests exist and pass for package diffing
  - Verify integration tests exist for package_diff() tool in `tests/integration/`
  - Run integration tests: `make test-integration`
  - Fix any integration test failures
  - Ensure end-to-end package diffing workflow works correctly

## Feature 2: Package Updates (Complete End-to-End)

- [ ] 2.1 Add update_package_revision() abstract method to QuiltOps base class
  - Copy method signature from design.md
  - Include comprehensive docstring explaining package update workflow
  - Ensure method returns Package_Creation_Result domain object

- [ ] 2.2 Extract package update logic from package_update() tool to Quilt3_Backend.update_package_revision()
  - **EXTRACT** the package browsing logic from `package_update()` tool (line 1439)
  - **MOVE** the `quilt_service.browse_package(package_name, registry=normalized_registry)` call to backend
  - **MOVE** the `_collect_objects_into_package()` logic that adds S3 URIs to the package to backend
  - **MOVE** the metadata merging logic (lines 1460-1470): `combined.update(existing_pkg.meta)` to backend
  - **MOVE** the package push logic with selector_fn from the tool to backend
  - Return Package_Creation_Result domain object instead of raw quilt3 objects

- [ ] 2.3 Add proper mocked unit tests for backend update_package_revision() method
  - Add tests in `tests/unit/backends/test_quilt3_backend_packages.py`
  - Mock quilt3.Package.browse() call for existing package
  - Mock S3 URI collection and package modification logic
  - Mock metadata merging behavior
  - Mock package push logic and return values
  - Test different parameter combinations (auto_organize, copy modes, metadata)
  - Verify Package_Creation_Result domain object is returned correctly

- [ ] 2.4 Remove trivial unit tests for package_update() tool
  - Identify and remove unit tests that just test tool parameter validation
  - Keep only tests that verify tool-specific error handling and response formatting
  - Tools are now thin wrappers, so extensive unit testing is not needed

- [ ] 2.5 Rewrite package_update() tool as thin wrapper
  - **REPLACE** lines 1439-1480+ (all business logic) with single `quilt_ops.update_package_revision()` call
  - **REMOVE** `_collect_objects_into_package()` call (now in backend)
  - **REMOVE** metadata merging logic (now in backend)
  - **REMOVE** package push logic (now in backend)
  - Keep parameter validation and error handling
  - Transform QuiltOps domain result to PackageUpdateSuccess/PackageUpdateError response format

- [ ] 2.6 Ensure integration tests exist and pass for package updates
  - Verify integration tests exist for package_update() tool in `tests/integration/`
  - Run integration tests: `make test-integration`
  - Fix any integration test failures
  - Ensure end-to-end package update workflow works correctly

## Feature 3: Package Creation (Complete End-to-End)

- [ ] 3.1 Migrate package_create() tool by simple replacement
  - **REPLACE** `quilt_service.create_package_revision()` call with `quilt_ops.create_package_revision()`
  - **VERIFY** QuiltOps.create_package_revision() already exists and works
  - Update result handling to match QuiltOps return format
  - Keep all existing parameter validation and error handling
  - Keep existing functionality and response formatting

- [ ] 3.2 Remove trivial unit tests for package creation tools
  - Identify and remove unit tests that just test tool parameter validation
  - Keep only tests that verify tool-specific error handling and response formatting
  - Tools are now thin wrappers, so extensive unit testing is not needed

- [ ] 3.3 Migrate package_create_from_s3() tool by simple replacement
  - **REPLACE** `quilt_service.create_package_revision()` call with `quilt_ops.create_package_revision()`
  - Apply same changes as package_create() tool
  - Ensure S3 URI handling remains consistent with existing behavior

- [ ] 3.4 Ensure integration tests exist and pass for package creation
  - Verify integration tests exist for package_create() and package_create_from_s3() tools
  - Run integration tests: `make test-integration`
  - Fix any integration test failures
  - Ensure end-to-end package creation workflows work correctly

## Feature 4: GraphQL Search (Complete End-to-End)

- [ ] 4.1 Migrate search._get_graphql_endpoint() helper by translation
  - **TRANSLATE** QuiltService session logic to QuiltOpsFactory pattern
  - **REPLACE** entire function with QuiltOpsFactory.create() call
  - **COPY** existing error handling patterns (return None on failure)
  - Update search_graphql() to use quilt_ops.execute_graphql_query()
  - **REPLACE** session.post() usage with QuiltOps method
  - Keep existing response format and error handling

- [ ] 4.2 Test complete search workflow
  - Execute: `make test`
  - Test search_graphql() functionality end-to-end
  - Verify same behavior as before migration
  - Fix any issues before proceeding to next feature

## Feature 5: Stack Buckets GraphQL (Complete End-to-End)

- [ ] 5.1 Migrate stack_buckets._get_stack_buckets_via_graphql() helper (line 42)
  - Replace QuiltService session usage
  - Use QuiltOpsFactory.create() and execute_graphql_query()
  - Update BUCKET_CONFIGS_QUERY execution
  - Maintain existing result processing

- [ ] 5.2 Test complete stack buckets workflow
  - Execute: `make test`
  - Test stack_buckets functionality end-to-end
  - Verify bucket configuration queries work correctly
  - Fix any issues before proceeding to cleanup

## Feature 6: Cleanup and Final Verification

- [ ] 6.1 Verify no remaining QuiltService imports
  - Execute: `grep -r "from.*quilt_service import" src/`
  - Fix any remaining import statements
  - Update any missed QuiltService usage

- [ ] 6.2 Verify no remaining QuiltService usage
  - Execute: `grep -r "quilt_service\." src/`
  - Replace any remaining direct usage
  - Ensure complete migration to QuiltOps

- [ ] 6.3 Delete QuiltService files
  - Delete src/quilt_mcp/services/quilt_service.py
  - Delete tests/unit/test_quilt_service.py
  - Remove any QuiltService-related imports from __init__.py files

- [ ] 6.4 Run comprehensive tests and fix ALL errors
  - Execute: `make test-all`
  - Fix every single test failure, regardless of apparent cause
  - Fix any linting issues: `make lint`
  - Ensure 100% test pass rate

- [ ] 6.5 Final validation and cleanup
  - Execute: `make test-all` one more time
  - Verify all success criteria are met
  - Fix any remaining issues until everything passes
  - Document any breaking changes or migration notes

## Success Criteria

- [ ] QuiltOps has diff_packages() and update_package_revision() methods
- [ ] All 6 tools/helpers use QuiltOpsFactory exclusively
- [ ] No QuiltService imports remain in src/
- [ ] QuiltService.py and related files deleted
- [ ] All tests pass: `make test-all`
- [ ] Linting passes: `make lint`
- [ ] No regressions in existing functionality