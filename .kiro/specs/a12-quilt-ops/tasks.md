# Tasks: Migration All MCP Tools → QuiltOps

## Phase 1: Extend QuiltOps Interface

- [ ] 1.1 Add diff_packages() abstract method to QuiltOps base class
  - Add method signature with proper type hints
  - Include comprehensive docstring with parameters and return format
  - Ensure method returns Dict[str, List[str]] with keys: added, deleted, modified

- [ ] 1.2 Add update_package_revision() abstract method to QuiltOps base class
  - Add method signature with all required parameters
  - Include comprehensive docstring explaining package update workflow
  - Ensure method returns Package_Creation_Result domain object

- [ ] 1.3 Run tests and fix any interface-related errors
  - Execute: `make test`
  - Fix any abstract method or type hint errors
  - Ensure all existing QuiltOps implementations still work

## Phase 2: Implement Methods in Quilt3 Backend

- [ ] 2.1 Implement diff_packages() in Quilt3_Backend
  - Browse both packages using quilt3.Package.browse()
  - Call pkg1.diff(pkg2) to get differences
  - Transform quilt3 diff result to domain dict format
  - Handle optional package hashes for specific versions
  - Add proper error handling for missing packages

- [ ] 2.2 Implement update_package_revision() in Quilt3_Backend
  - Browse existing package to get current state
  - Add S3 URIs using pkg.set() or pkg.set_dir() methods
  - Handle auto_organize parameter for folder structure
  - Implement copy parameter logic with selector_fn
  - Call pkg.push() with proper metadata and message
  - Return Package_Creation_Result with all required fields

- [ ] 2.3 Run tests and fix any implementation errors
  - Execute: `make test`
  - Fix any quilt3 integration issues
  - Ensure new methods work with existing backend infrastructure

## Phase 3: Add Comprehensive Test Coverage

- [ ] 3.1 Add test_diff_packages_basic test
  - Test basic package diffing functionality
  - Mock quilt3.Package.browse() and diff() calls
  - Verify correct transformation of diff results
  - Test with different package states (added/deleted/modified files)

- [ ] 3.2 Add test_diff_packages_with_hashes test
  - Test package diffing with specific version hashes
  - Verify hash parameters are passed correctly to browse()
  - Test error handling for invalid hashes

- [ ] 3.3 Add test_update_package_revision_basic test
  - Test basic package update functionality
  - Mock package browsing, file addition, and push operations
  - Verify S3 URIs are added correctly
  - Test return value structure

- [ ] 3.4 Add test_update_package_revision_with_metadata test
  - Test package updates with custom metadata
  - Verify metadata is passed correctly to push()
  - Test custom commit messages

- [ ] 3.5 Add test_update_package_revision_auto_organize test
  - Test auto_organize parameter functionality
  - Verify folder structure organization logic
  - Test different copy mode behaviors

- [ ] 3.6 Run tests and fix any test-related errors
  - Execute: `make test`
  - Fix any mock setup or assertion issues
  - Ensure all new tests pass consistently

## Phase 4: Migrate Package Tools

- [ ] 4.1 Migrate package_create() tool (line 1103)
  - Replace quilt_service.create_package_revision() call
  - Use QuiltOpsFactory.create() to get QuiltOps instance
  - Update result handling for QuiltOps return format
  - Maintain all existing functionality and error handling

- [ ] 4.2 Migrate package_create_from_s3() tool (line 1661)
  - Apply same changes as package_create()
  - Replace QuiltService usage with QuiltOpsFactory
  - Ensure S3 URI handling remains consistent

- [ ] 4.3 Migrate package_update() tool (line 1338)
  - Replace quilt_service.browse_package() call
  - Use quilt_ops.update_package_revision() directly
  - Update parameter mapping and result handling
  - Maintain existing validation and error handling

- [ ] 4.4 Migrate package_diff() tool (line 963)
  - Replace two quilt_service.browse_package() calls
  - Use quilt_ops.diff_packages() directly
  - Update result formatting for tool response
  - Maintain existing diff display logic

- [ ] 4.5 Run tests and fix any tool migration errors
  - Execute: `make test`
  - Fix any parameter mapping or result handling issues
  - Ensure all package tools work with QuiltOps

## Phase 5: Migrate GraphQL Helpers

- [ ] 5.1 Migrate search._get_graphql_endpoint() helper (line 363)
  - Replace entire function with QuiltOpsFactory.create()
  - Update search_graphql() to use quilt_ops.execute_graphql_query()
  - Remove session.post() usage
  - Maintain existing error handling and response format

- [ ] 5.2 Migrate stack_buckets._get_stack_buckets_via_graphql() helper (line 42)
  - Replace QuiltService session usage
  - Use QuiltOpsFactory.create() and execute_graphql_query()
  - Update BUCKET_CONFIGS_QUERY execution
  - Maintain existing result processing

- [ ] 5.3 Run tests and fix any GraphQL migration errors
  - Execute: `make test`
  - Fix any GraphQL query or response handling issues
  - Ensure search and stack_buckets tools work correctly

## Phase 6: Cleanup and Verification

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