# Implementation Tasks

## Phase 1: QuiltOps Abstraction with Quilt3_Backend Only

This task list follows Test-Driven Development (TDD) princiemples, implementing tests first for each component before writing the/

---

## Task 1: Create Core Domain Objects (TDD)

Create the backend-agnostic data structures that represent Quilt concepts using TDD approach.

### 1.1 TDD: Package_Info dataclass

- [x] Write tests for Package_Info validation in `tests/unit/domain/test_package_info.py`
- [x] Write tests for required field validation
- [x] Write tests for dataclasses.asdict() compatibility
- [x] Create `src/quilt_mcp/domain/package_info.py` to make tests pass
- [x] Implement Package_Info with fields: name, description, tags, modified_date, registry, bucket, top_hash
- [x] Add validation for required fields to satisfy tests

### 1.2 TDD: Content_Info dataclass

- [x] Write tests for Content_Info validation in `tests/unit/domain/test_content_info.py`
- [x] Write tests for required field validation
- [x] Write tests for dataclasses.asdict() compatibility
- [x] Create `src/quilt_mcp/domain/content_info.py` to make tests pass
- [x] Implement Content_Info with fields: path, size, type, modified_date, download_url
- [x] Add validation for required fields to satisfy tests

### 1.3 TDD: Bucket_Info dataclass

- [x] Write tests for Bucket_Info validation in `tests/unit/domain/test_bucket_info.py`
- [x] Write tests for required field validation
- [x] Write tests for dataclasses.asdict() compatibility
- [x] Create `src/quilt_mcp/domain/bucket_info.py` to make tests pass
- [x] Implement Bucket_Info with fields: name, region, access_level, created_date
- [x] Add validation for required fields to satisfy tests

### 1.4 Verification Checkpoint: Domain Objects

- [x] Run linting: `ruff check src/quilt_mcp/domain/`
- [x] Run tests: `uv run pytest tests/unit/domain/ -v`
- [x] Verify all tests pass
- [x] Commit changes: `git add . && git commit -m "feat: implement domain objects (Package_Info, Content_Info, Bucket_Info)"`

---

## Task 2: Create QuiltOps Abstract Interface (TDD)

Define the domain-driven abstraction interface using TDD approach.

### 2.1 TDD: Custom exceptions

- [x] Write tests for custom exceptions in `tests/unit/ops/test_exceptions.py`
- [x] Write tests for AuthenticationError, BackendError, ValidationError
- [x] Write tests for error context fields and messages
- [x] Create `src/quilt_mcp/ops/exceptions.py` to make tests pass
- [x] Implement exception classes with error context fields for debugging

### 2.2 TDD: QuiltOps abstract base class

- [x] Write tests for QuiltOps interface in `tests/unit/ops/test_quilt_ops.py`
- [x] Write tests that verify abstract methods raise NotImplementedError
- [x] Write tests for method signatures and type hints
- [x] Create `src/quilt_mcp/ops/quilt_ops.py` to make tests pass
- [x] Define abstract methods: search_packages, get_package_info, browse_content, list_buckets, get_content_url
- [x] Add proper type hints using domain objects
- [x] Add comprehensive docstrings for each method

### 2.3 Verification Checkpoint: QuiltOps Interface

- [x] Run linting: `ruff check src/quilt_mcp/ops/`
- [x] Run tests: `uv run pytest tests/unit/ops/ -v`
- [x] Verify all tests pass
- [x] Commit changes: `git add . && git commit -m "feat: implement QuiltOps abstract interface and exceptions"`

---

## Task 3: Implement Quilt3_Backend (TDD)

Create the backend implementation using TDD approach with mocked quilt3 library calls.

### 3.1 TDD: Quilt3_Backend class structure

- [x] Write tests for Quilt3_Backend initialization in `tests/unit/backends/test_quilt3_backend.py`
- [x] Write tests for session validation and error handling
- [x] Write tests for QuiltOps interface compliance
- [x] Create `src/quilt_mcp/backends/quilt3_backend.py` to make tests pass
- [x] Implement QuiltOps interface
- [x] Add session validation and initialization
- [x] Implement error handling for quilt3 operations

### 3.2 TDD: Package operations

- [x] Write tests for search_packages() with mocked quilt3.search() calls
- [x] Write tests for get_package_info() with mocked quilt3 package loading
- [x] Write tests for transformation from quilt3 objects to Package_Info
- [x] Write tests for error handling in package operations
- [x] Implement search_packages() with quilt3.search() and transform to Package_Info
- [x] Implement get_package_info() with quilt3 package loading and transform to Package_Info
- [x] Add transformation helper methods for quilt3 objects to domain objects

### 3.2a TDD: Package transformation unit tests

- [x] Write dedicated unit tests for _transform_package() method in isolation
- [x] Test transformation with mock quilt3.Package objects
- [X] Test handling of missing/null fields in quilt3 Package_Info objects
- [x] Test error handling in transformation logic

### 3.3 TDD: Content operations

- [x] Write tests for browse_content() with mocked quilt3 package browsing
- [x] Write tests for get_content_url() with mocked quilt3 URL generation
- [x] Write tests for directory vs file type detection
- [x] Write tests for transformation from quilt3 objects to Content_Info
- [x] Implement browse_content() with quilt3 package browsing and transform to Content_Info
- [x] Implement get_content_url() with quilt3 URL generation
- [x] Handle directory vs file type detection

### 3.3a TDD: Content transformation unit tests

- [x] Write dedicated unit tests for _transform_content() method in isolation
- [x] Test transformation with mock quilt3 content objects
- [X] Test handling of missing/null fields in quilt3 Content_Info objects
- [x] Test error handling in transformation logic

### 3.4 TDD: Bucket operations

- [x] Write tests for list_buckets() with mocked quilt3 calls
- [x] Write tests for transformation from quilt3 responses to Bucket_Info
- [x] Write tests for bucket metadata extraction
- [x] Implement list_buckets() with appropriate quilt3 calls and transform to Bucket_Info
- [x] Add bucket metadata extraction from quilt3 responses

### 3.4a TDD: Bucket transformation unit tests

- [x] Write dedicated unit tests for _transform_bucket() method in isolation
- [x] Test transformation with mock quilt3 bucket objects
- [X] Test handling of missing/null fields in quilt3 Bucket_Info objects
- [x] Test error handling in transformation logic

### 3.5 Verification Checkpoint: Quilt3_Backend

- [x] Run linting: `ruff check src/quilt_mcp/backends/`
- [x] Run tests: `uv run pytest tests/unit/backends/ -v`
- [X] Verify all tests pass
- [x] Commit changes: `git add . && git commit -m "feat: implement Quilt3_Backend with all QuiltOps operations"`

---

## Task 4: Create QuiltOps Factory (TDD - Phase 1 Version)

Create the factory using TDD approach, focusing only on quilt3 sessions for Phase 1.

### 4.1 TDD: QuiltOpsFactory class

- [x] Write tests for QuiltOpsFactory.create() in `tests/unit/ops/test_factory.py`
- [x] Write tests for quilt3 session detection and validation
- [X] Write tests for error handling when no quilt3 session is found
- [X] Write tests for clear error messages with remediation steps
- [x] Create `src/quilt_mcp/ops/factory.py` to make tests pass
- [x] Implement create() method that only checks for quilt3 sessions

### 4.2 Verification Checkpoint: QuiltOps Factory

- [x] Run linting: `ruff check src/quilt_mcp/ops/factory.py`
- [x] Run tests: `uv run pytest tests/unit/ops/test_factory.py -v`
- [x] Verify all tests pass
- [x] Commit changes: `git add . && git commit -m "feat: implement QuiltOpsFactory with quilt3 session detection"`

---

## Task 5: Migrate Existing MCP Tools to QuiltOps

Migrate existing MCP tools from QuiltService to QuiltOps. Use existing tests to verify behavior doesn't change.

### 5.1 Pre-migration audit (COMPLETED)

- [x] Audit all MCP tools: tool_migration_categories.md
- [x] Identify affected files: packages.py, search.py, stack_buckets.py, buckets.py, catalog.py
- [x] Document migration approach for each category

### 5.2 Phase 1: Core Package Operations (packages.py)

**Files to update:** `src/quilt_mcp/tools/packages.py`

- [ ] Migrate `packages_list()`: Replace `quilt_service.list_packages()` → `QuiltOps.search_packages()`
- [ ] Migrate `package_browse()`: Replace `quilt_service.browse_package()` → `QuiltOps.browse_content()`
- [ ] Migrate `package_diff()`: Use `QuiltOps.browse_content()` for both packages
- [ ] Update response formatting to use `dataclasses.asdict()` on domain objects
- [ ] **DECISION NEEDED:** Handle `create_package_revision()` - no QuiltOps equivalent yet
- [ ] Run existing tests: `uv run pytest tests/unit/tools/test_packages.py -v`
- [ ] Run integration tests: `uv run pytest tests/integration/ -k package -v`

### 5.3 Phase 2: Authentication & GraphQL (search.py, stack_buckets.py)

**Files to update:** `src/quilt_mcp/tools/search.py`, `src/quilt_mcp/tools/stack_buckets.py`

- [ ] Replace session checks with QuiltOpsFactory authentication
- [ ] Keep GraphQL functionality separate (not part of QuiltOps domain)
- [ ] Update error handling to use QuiltOps exceptions
- [ ] Run existing tests: `uv run pytest tests/unit/tools/test_search.py tests/unit/tools/test_stack_buckets.py -v`

### 5.4 Phase 3: Cleanup (buckets.py, catalog.py)

**Files to update:** `src/quilt_mcp/tools/buckets.py`, `src/quilt_mcp/tools/catalog.py`

- [ ] Remove unused QuiltService import from buckets.py
- [ ] Update documentation references in catalog.py
- [ ] Run full test suite to verify no regressions

### 5.5 Verification Checkpoint: Tool Migration

- [ ] Run linting: `ruff check src/quilt_mcp/tools/`
- [ ] Run all tool tests: `uv run pytest tests/unit/tools/ -v`
- [ ] Run all integration tests: `uv run pytest tests/integration/ -v`
- [ ] Verify all existing tests still pass
- [ ] Commit changes: `git add . && git commit -m "feat: migrate all MCP tools to use QuiltOps abstraction"`

---

## Task 6: Remove QuiltService and Finalize Integration (TDD)

Remove the old QuiltService class entirely and finalize the QuiltOps integration using TDD approach.

**Note:** Task 5 migrates the tools; this task removes the old service and cleans up.

### 6.1 Update service initialization

- [ ] Update main MCP server initialization to use QuiltOpsFactory
- [ ] Remove QuiltService instantiation and dependencies
- [ ] Add proper error handling for QuiltOps creation failures

### 6.2 Update dependency injection

- [ ] Update any dependency injection to provide QuiltOps instead of QuiltService
- [ ] Ensure all tools receive QuiltOps instances
- [ ] Remove QuiltService from service container

### 6.3 Clean up old code

- [ ] Remove the old QuiltService class
- [ ] Remove unused quilt3-specific imports from tools
- [ ] Clean up any remaining direct quilt3 usage in tools
- [ ] Remove obsolete tests that reference QuiltService
- [ ] Remove obsolete tests that test quilt3-specific behavior no longer relevant
- [ ] Update any remaining tests to use QuiltOps instead of QuiltService
- [ ] Use grep to verify no remaining QuiltService or direct quilt3 imports: `grep -r "QuiltService\|from quilt3\|import quilt3" src/quilt_mcp/tools/`

### 6.4 Verification Checkpoint: QuiltService Replacement

- [ ] Run linting: `ruff check src/quilt_mcp/`
- [ ] Run full test suite: `uv run pytest -v`
- [ ] Use grep to verify no QuiltService references remain: `grep -r "QuiltService" src/`
- [ ] Commit changes: `git add . && git commit -m "feat: replace QuiltService with QuiltOps throughout system"`

---

## Task 7: Migrate Existing Integration Tests

Update existing integration tests to work with the QuiltOps abstraction.

### 7.1 Audit existing integration tests

- [ ] Identify all integration tests in `tests/integration/`
- [ ] Document which tests use QuiltService directly
- [ ] Document which tests use quilt3 directly
- [ ] Create migration checklist for integration tests

### 7.2 Migrate integration tests

- [ ] Update integration tests to use QuiltOps instead of QuiltService
- [ ] Update test fixtures to create QuiltOps instances via factory
- [ ] Update assertions to work with domain objects (Package_Info, Content_Info, Bucket_Info)
- [ ] Remove direct quilt3 imports and usage from integration tests
- [ ] Ensure migrated tests still validate the same behaviors

### 7.3 Verification Checkpoint: Integration Tests

- [ ] Run linting: `ruff check tests/integration/`
- [ ] Run full integration test suite: `uv run pytest tests/integration/ -v`
- [ ] Use grep to verify no QuiltService usage remains in tests: `grep -r "QuiltService" tests/`
- [ ] Commit changes: `git add . && git commit -m "feat: migrate integration tests to use QuiltOps"`

---

## Task 8: Documentation and Migration Guide

Create documentation for the new abstraction layer and migration process.

### 8.1 Create API documentation

- [ ] Document QuiltOps interface and all methods
- [ ] Document domain objects and their fields
- [ ] Document error types and handling

### 8.2 Update system documentation

- [ ] Update architecture documentation to reflect new abstraction layer
- [ ] Update deployment documentation for any configuration changes
- [ ] Update troubleshooting guides for new error patterns

### 8.3 Final Verification Checkpoint: Complete Implementation

- [ ] Run full linting: `ruff check .`
- [ ] Run complete test suite: `uv run pytest -v --cov=src/quilt_mcp`
- [ ] Run integration tests with real quilt3 session: `uv run pytest tests/integration/ -v`
- [ ] Commit final changes: `git add . && git commit -m "feat: complete QuiltOps abstraction layer implementation"`
- [ ] Create summary commit: `git commit --allow-empty -m "feat: Phase 1 complete - QuiltOps abstraction with Quilt3_Backend"`

---

## Acceptance Criteria

### Phase 1 Complete When

- [ ] All existing MCP tools work correctly using QuiltOps with Quilt3_Backend
- [ ] No tools directly import or use quilt3 library (all go through QuiltOps)
- [ ] All tools work with domain objects (Package_Info, Content_Info, Bucket_Info)
- [ ] Authentication only requires valid quilt3 sessions
- [ ] Error messages are clear and include backend context
- [ ] Unit and integration tests pass
- [ ] Documentation is complete and accurate

### Ready for Phase 2 When

- [ ] QuiltOps interface is stable and well-tested
- [ ] Domain objects handle all necessary Quilt concepts
- [ ] Backend abstraction is proven to work with Quilt3_Backend
- [ ] Tool migration patterns are established and documented
- [ ] All existing integration tests work with QuiltOps
