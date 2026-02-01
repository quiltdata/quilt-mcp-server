# Tasks: Migration All MCP Tools → QuiltOps

## Feature 1: Package Diffing (Complete End-to-End)

- [x] 1.1 Add diff_packages() abstract method to QuiltOps base class
  - Copy method signature from design.md
  - Include comprehensive docstring with parameters and return format
  - Ensure method returns Dict[str, List[str]] with keys: added, deleted, modified

- [x] 1.2 Extract package diffing logic from package_diff() tool to Quilt3_Backend.diff_packages()
  - **EXTRACT** the package browsing logic from `package_diff()` tool (lines 1029-1040)
  - **MOVE** the conditional hash handling: `if package1_hash:` logic to backend
  - **MOVE** the quilt3.Package.browse() calls with registry and top_hash parameters to backend
  - **MOVE** the pkg1.diff(pkg2) call and result processing (lines 1047-1058) to backend
  - **MOVE** the tuple-to-dict transformation logic for diff results to backend
  - Return domain dict format instead of raw quilt3 objects

- [x] 1.3 Add proper mocked unit tests for backend diff_packages() method
  - Add tests in `tests/unit/backends/test_quilt3_backend_packages.py`
  - Mock quilt3.Package.browse() calls with proper parameters
  - Mock pkg1.diff(pkg2) calls and return values
  - Test conditional hash handling logic
  - Test tuple-to-dict transformation logic
  - Test error handling for missing packages or invalid hashes
  - Verify domain dict format is returned correctly

- [x] 1.4 Remove trivial unit tests for package_diff() tool
  - Identify and remove unit tests that just test tool parameter validation
  - Keep only tests that verify tool-specific error handling and response formatting
  - Tools are now thin wrappers, so extensive unit testing is not needed

- [x] 1.5 Rewrite package_diff() tool as thin wrapper
  - **REPLACE** lines 1029-1058 (all business logic) with single `quilt_ops.diff_packages()` call
  - **REMOVE** all quilt3 manipulation logic (now in backend)
  - Keep parameter validation and error handling
  - Transform QuiltOps domain result to PackageDiffSuccess/PackageDiffError response format

- [x] 1.6 Ensure integration tests exist and pass for package diffing
  - Verify integration tests exist for package_diff() tool in `tests/integration/`
  - Run integration tests: `make test-integration`
  - Fix any integration test failures
  - Ensure end-to-end package diffing workflow works correctly

## Feature 2: Package Updates (Complete End-to-End)

- [x] 2.1 Complete package_update() migration to QuiltOps (CONSOLIDATED)
  - Add update_package_revision() abstract method to QuiltOps base class
  - Extract package update logic from package_update() tool to Quilt3_Backend.update_package_revision()
  - Add proper mocked unit tests for backend update_package_revision() method
  - Remove trivial unit tests for package_update() tool
  - Rewrite package_update() tool as thin wrapper
  - Ensure integration tests exist and pass for package updates

## Feature 3: Package Creation (Complete End-to-End)

- [x] 3.1 Complete package_create() and package_create_from_s3() migration to QuiltOps (CONSOLIDATED)
  - Migrate package_create() tool by simple replacement
  - Remove trivial unit tests for package creation tools
  - Migrate package_create_from_s3() tool by simple replacement
  - Ensure integration tests exist and pass for package creation

## Feature 4: GraphQL Search (Complete End-to-End)

- [x] 4.1 Complete search GraphQL migration to QuiltOps (CONSOLIDATED)
  - Migrate search._get_graphql_endpoint() helper by translation
  - Test complete search workflow

## Feature 5: Stack Buckets GraphQL (Complete End-to-End)

- [x] 5.1 Complete stack_buckets GraphQL migration to QuiltOps (CONSOLIDATED)
  - Migrate stack_buckets._get_stack_buckets_via_graphql() helper (line 42)
  - Test complete stack buckets workflow

## Feature 6: Cleanup and Final Verification

- [x] 6.1 Complete cleanup and final verification (CONSOLIDATED)
  - Verify no remaining QuiltService imports
  - Verify no remaining QuiltService usage
  - Remove ENDPOINTs you replace from the QuiltService file
  - Run comprehensive tests and fix ALL errors
  - Final validation and cleanup

## Success Criteria

- [ ] QuiltOps has diff_packages() and update_package_revision() methods
- [ ] All 6 tools/helpers use QuiltOpsFactory exclusively
- [ ] No QuiltService imports remain in src/
- [ ] QuiltService.py and related files deleted
- [ ] All tests pass: `make test-all`
- [ ] Linting passes: `make lint`
- [ ] No regressions in existing functionality