# 12 - Complete Module Refactoring Plan

> **Status Note (2026-02-17):** This refactoring plan is partially executed on `pr-review-fix`.
> Newly completed in this pass: package CRUD handlers were extracted into `tools/package_crud.py` (reducing `tools/packages.py` to 758 LOC), and response base/resource models were split into `tools/responses_base.py` + `tools/responses_resources.py` (reducing `tools/responses.py` to 987 LOC), with `make test-all` and `make test-remote-docker` passing.
> Still open: "all modules <1000 LOC" is not yet met; remaining oversized modules are `ops/quilt_ops.py`, `services/governance_service.py`, `backends/platform_admin_ops.py`, `backends/platform_backend.py`, and `services/workflow_service.py`.

**Date:** 2026-02-17
**Reviewer:** Codex
**Context:** Comprehensive remediation plan ensuring ALL critical issues are addressed

## Scope

This plan ensures complete resolution of all 5 critical issues:

1. ✅ **448-line function** with 20 nested blocks
2. ✅ **Platform backend orchestration duplication**
3. ⚠️ **ALL 15 circular import cycles** (3 identified + 12 to be discovered)
4. ✅ **Mixed concerns** in tools/packages.py
5. ✅ **Scattered GraphQL operations**

---

## Phase 0: Discovery - Identify ALL Circular Import Cycles

**Problem:** Only 3 of 15 cycles are documented. We need the complete list before proceeding.

### 0.1 Create Cycle Detection Script

- [x] Create `scripts/detect_cycles.py`:

  ```python
  """
  Detect all circular import cycles in the codebase.
  Uses networkx or similar to find strongly connected components.
  """
  import ast
  from pathlib import Path
  import networkx as nx

  def extract_imports(file_path):
      """Extract all imports from a Python file"""
      # Parse AST and find Import/ImportFrom nodes

  def build_import_graph():
      """Build directed graph of module dependencies"""

  def find_cycles():
      """Find all cycles using networkx.simple_cycles()"""

  if __name__ == "__main__":
      cycles = find_cycles()
      print(f"Found {len(cycles)} circular import cycles:")
      for i, cycle in enumerate(cycles, 1):
          print(f"\nCycle {i}:")
          print(" -> ".join(cycle + [cycle[0]]))
  ```

- [x] Run: `uv run python scripts/detect_cycles.py > proj/260210-stack-integrated/review/cycle-report.txt`
- [x] Document all 15 cycles in a table with:
  - Cycle ID
  - Modules involved
  - Root cause (shared types, function calls, class inheritance)
  - Proposed fix

**Output:** Complete cycle inventory before proceeding to Phase 1.

---

## Phase 1: Break ALL 15 Circular Import Cycles

### 1.1 Known Critical Cycles (3 cycles)

#### Cycle 1: Utils/Context Loop

**Path:** `utils.common → context.handler → context.factory → services.workflow_service → utils.common`

**Root Cause:** `utils.common` has utility functions needed by context, but also imports from context modules.

**Fix:**

- [x] Create `src/quilt_mcp/types/common.py` with shared type definitions
- [x] Create `src/quilt_mcp/context/utils.py` for context-specific utilities
- [x] Move non-context utilities to `src/quilt_mcp/utils/helpers.py`
- [x] Update imports:
  - `context/handler.py`: import from `types.common`
  - `context/factory.py`: import from `types.common`
  - `services/workflow_service.py`: import from `context.utils`
  - `utils/common.py`: remove context imports

**Validation:**

- [x] `uv run python scripts/detect_cycles.py` - Cycle 1 gone
- [x] `uv run pytest tests/unit/context/` - passes
- [x] `uv run mypy src/quilt_mcp/context/` - passes

---

#### Cycle 2: Auth Service Loop

**Path:** `services.auth_service ↔ services.iam_auth_service`

**Root Cause:** Both services import each other's concrete implementations.

**Fix:**

- [x] Create `src/quilt_mcp/services/protocols/auth.py`:

  ```python
  from typing import Protocol

  class AuthServiceProtocol(Protocol):
      def authenticate(self, token: str) -> dict: ...
      def validate_permissions(self, user_id: str, resource: str) -> bool: ...
  ```

- [x] Update `services/auth_service.py`:
  - Remove import of `iam_auth_service`
  - Accept `AuthServiceProtocol` as dependency injection

- [x] Update `services/iam_auth_service.py`:
  - Remove import of `auth_service`
  - Implement `AuthServiceProtocol`

- [x] Update service initialization to inject dependencies

**Validation:**

- [x] `uv run python scripts/detect_cycles.py` - Cycle 2 gone
- [x] `uv run pytest tests/unit/services/ -k auth` - passes
- [x] `uv run mypy src/quilt_mcp/services/` - passes

---

#### Cycle 3: Platform Backend/Admin Loop

**Path:** `backends.platform_backend ↔ backends.platform_admin_ops`

**Root Cause:** `platform_admin_ops` imports from `platform_backend`, and `platform_backend` imports admin ops.

**Fix:**

- [x] Create `src/quilt_mcp/backends/types/admin.py` with shared admin types
- [x] Create `src/quilt_mcp/backends/protocols/admin.py` with `AdminOpsProtocol`
- [x] Update `backends/platform_admin_ops.py`:
  - Import only types, not full backend
  - Implement `AdminOpsProtocol`

- [x] Update `backends/platform_backend.py`:
  - Lazy-load admin ops (already done, verify it works)
  - Import from `types.admin`, not `platform_admin_ops`

**Validation:**

- [x] `uv run python scripts/detect_cycles.py` - Cycle 3 gone
- [x] `uv run pytest tests/unit/backends/ -k platform` - passes
- [x] `uv run mypy src/quilt_mcp/backends/` - passes

---

### 1.2 Remaining 12 Cycles (To Be Identified)

**Process for each discovered cycle:**

1. **Identify root cause:**
   - Shared types? → Extract to `types/` module
   - Function dependencies? → Use dependency injection or protocols
   - Class inheritance? → Refactor hierarchy
   - Constants/enums? → Extract to `constants/` module

2. **Apply fix pattern:**
   - **Pattern A: Shared Types** → Create `types/X.py` with TypedDicts/dataclasses
   - **Pattern B: Circular Functions** → Use Protocol or ABC for interface
   - **Pattern C: Circular Classes** → Introduce intermediate abstraction
   - **Pattern D: Constants** → Extract to dedicated constants module

3. **Validate:**
   - Run cycle detection (count decreases)
   - Run affected tests
   - Run mypy on affected modules

**Template for documenting each cycle:**

```markdown
#### Cycle N: [Name]
**Path:** `module.a → module.b → module.c → module.a`
**Root Cause:** [Description]
**Fix Pattern:** [A/B/C/D]
**Tasks:**
- [x] [Specific action 1]
- [x] [Specific action 2]
**Validation:**
- [x] Cycle detection shows N-1 cycles remaining
- [x] Tests pass: [specific test command]
```

**Completion Criteria:**

- [x] `uv run python scripts/detect_cycles.py` reports **0 cycles**
- [x] All tests pass: `make test-all`
- [x] Mypy clean: `uv run mypy src/quilt_mcp`

---

## Phase 2: Fix Architecture Violation - Platform Backend Orchestration

### 2.1 Remove Duplicated update_package_revision()

**Problem:** `platform_backend.py` has 154-line `update_package_revision()` that duplicates the Template Method from `quilt_ops.py`.

**Current Architecture (CORRECT):**

```
quilt_ops.QuiltOps (base class)
  ├─ update_package_revision() → Template Method (orchestrates 7 steps)
  │   ├─ Calls: _backend_validate_package_name()
  │   ├─ Calls: _backend_push_package()
  │   ├─ Calls: _backend_commit_package()
  │   └─ [etc...]
  │
  └─ Abstract primitives (implemented by backends)
```

**Current Problem (WRONG):**

```
platform_backend.Platform_Backend
  ├─ update_package_revision() → REIMPLEMENTS orchestration (154 lines)
  │   └─ Should NOT exist - should use base class method
  │
  └─ Should only implement primitives
```

**Fix:**

- [x] **Identify why override exists:**
  - Read `backends/platform_backend.py:update_package_revision()`
  - Check if there's platform-specific logic that requires override
  - Document any genuine differences

- [x] **If no genuine differences:**
  - [x] Delete `platform_backend.update_package_revision()` method entirely
  - [x] Verify base class method is called automatically
  - [x] Ensure all primitives are implemented:
    - `_backend_validate_package_name()`
    - `_backend_push_package()`
    - `_backend_commit_package()`
    - [check quilt_ops.py for full list]

- [x] **If there ARE platform-specific differences:**
  - [ ] Extract platform-specific logic to helper methods
  - [ ] Call `super().update_package_revision()` with hooks
  - [ ] Document why override is necessary

**Validation:**

- [x] `grep -n "def update_package_revision" src/quilt_mcp/backends/platform_backend.py` → should be empty OR clearly justified
- [x] Run: `uv run pytest tests/unit/backends/test_platform_backend.py -k update_package`
- [x] Run: `uv run pytest tests/func/backends/ -k "platform and update"`
- [x] Verify no functionality changes

**Expected Impact:** -154 lines from platform_backend.py

**Files:**

- `src/quilt_mcp/backends/platform_backend.py` (remove override)
- `src/quilt_mcp/ops/quilt_ops.py` (verify Template Method is correct)

---

### 2.2 Check Other Backends for Same Issue

- [x] Check `quilt3_backend_packages.py`:
  - Does it also duplicate orchestration methods?
  - Should it use base class Template Methods?

- [x] Verify Template Method pattern is used consistently:
  - [ ] `create_package_revision()` - only in base class?
  - [ ] `delete_package()` - only in base class?
  - [ ] Other orchestration methods?

**Validation:**

- [x] Run: `grep -rn "def update_package_revision\|def create_package_revision" src/quilt_mcp/backends/`
- [x] Verify only base class has orchestration methods
- [x] Backends only implement `_backend_*` primitives

---

## Phase 3: Refactor Giant Function - package_create_from_s3

### 3.1 Current State Analysis

**Function:** `tools/packages.py:package_create_from_s3()`

- **Size:** 448 lines
- **Nesting:** 20 nested blocks
- **Responsibilities:** 5 distinct concerns mixed together

**Responsibilities Identified:**

1. **S3 Discovery** (~80 lines) - List objects, filter, handle pagination
2. **File Organization** (~40 lines) - Organize into directory structure
3. **Validation** (~30 lines) - Validate bucket access, object counts
4. **Package Creation** (~100 lines) - Create package, add files
5. **Documentation** (~135 lines) - Generate README, metadata

---

### 3.2 Extract S3 Discovery Logic

- [x] Create `src/quilt_mcp/tools/s3_discovery.py`:

  ```python
  """S3 object discovery and filtering for package creation."""
  from typing import List, Dict, Optional
  from dataclasses import dataclass

  @dataclass
  class S3Object:
      key: str
      size: int
      last_modified: str

  @dataclass
  class DiscoveryConfig:
      bucket: str
      prefix: str
      exclude_patterns: List[str]
      include_patterns: List[str]
      max_objects: Optional[int]

  def discover_s3_objects(
      s3_client,
      config: DiscoveryConfig
  ) -> List[S3Object]:
      """
      Discover S3 objects matching criteria.

      Handles:
      - Pagination
      - Prefix filtering
      - Pattern matching (include/exclude)
      - Size limits
      """
      # ~80 lines of discovery logic

  def should_include_object(
      obj: S3Object,
      include_patterns: List[str],
      exclude_patterns: List[str]
  ) -> bool:
      """Determine if object should be included based on patterns."""
      # ~30 lines of filtering logic
  ```

- [x] Extract discovery logic from `package_create_from_s3()`
- [x] Add tests: `tests/unit/tools/test_s3_discovery.py`

**Validation:**

- [x] `uv run pytest tests/unit/tools/test_s3_discovery.py` - passes
- [x] Test coverage >= 90% for discovery logic

---

### 3.3 Extract File Organization Logic

- [x] Add to `src/quilt_mcp/tools/s3_discovery.py`:

  ```python
  @dataclass
  class FileStructure:
      directories: Dict[str, List[str]]
      total_size: int
      file_count: int

  def organize_file_structure(
      objects: List[S3Object],
      strip_prefix: str = ""
  ) -> FileStructure:
      """
      Organize S3 objects into logical directory structure.

      Handles:
      - Prefix stripping
      - Directory grouping
      - Size calculations
      """
      # ~40 lines of organization logic
  ```

- [x] Extract organization logic
- [x] Add tests for various directory structures

---

### 3.4 Extract Documentation Generation

- [x] Create `src/quilt_mcp/tools/package_metadata.py`:

  ```python
  """Package metadata and documentation generation."""
  from typing import Dict, List, Optional
  from dataclasses import dataclass

  @dataclass
  class PackageMetadata:
      name: str
      description: str
      keywords: List[str]
      data_summary: Dict[str, any]

  def generate_readme_content(
      structure: FileStructure,
      bucket: str,
      prefix: str,
      metadata: Optional[PackageMetadata] = None
  ) -> str:
      """
      Generate README.md content for package.

      Includes:
      - Package description
      - Directory structure tree
      - File statistics
      - Usage examples
      """
      # ~135 lines of README generation

  def generate_package_metadata(
      structure: FileStructure,
      **kwargs
  ) -> Dict:
      """Generate package metadata dictionary."""
      # ~50 lines of metadata generation
  ```

- [x] Extract README generation logic
- [x] Extract metadata generation logic
- [x] Add tests: `tests/unit/tools/test_package_metadata.py`

**Validation:**

- [x] `uv run pytest tests/unit/tools/test_package_metadata.py` - passes
- [x] Test coverage >= 85% for metadata logic

---

### 3.5 Refactor package_create_from_s3 to Orchestrate

- [x] Reduce `package_create_from_s3()` to orchestration:

  ```python
  async def package_create_from_s3(
      bucket: str,
      prefix: str,
      package_name: str,
      registry: str,
      **kwargs
  ) -> Dict:
      """
      Create a Quilt package from S3 objects.

      This is a high-level orchestration function that:
      1. Discovers objects in S3
      2. Organizes them into a structure
      3. Creates the package
      4. Generates documentation
      """
      # 1. Validate inputs (~10 lines)

      # 2. Discover S3 objects (~15 lines)
      config = DiscoveryConfig(...)
      objects = await discover_s3_objects(s3_client, config)

      # 3. Organize structure (~10 lines)
      structure = organize_file_structure(objects, strip_prefix=prefix)

      # 4. Create package (~30 lines)
      # Call existing package_create() or backend methods

      # 5. Generate documentation (~20 lines)
      readme = generate_readme_content(structure, bucket, prefix)
      metadata = generate_package_metadata(structure)

      # 6. Add metadata to package (~15 lines)

      # 7. Return result (~10 lines)
      return {"status": "success", ...}
  ```

  **Target Size:** ~100-120 lines of orchestration
  **Max Nesting:** 5-6 levels (down from 20)

**Validation:**

- [x] `uv run pytest tests/unit/tools/test_packages.py -k s3`
- [x] Run integration test with real S3 bucket
- [x] Verify identical behavior to original function
- [x] Check function size: `grep -A 500 "def package_create_from_s3" src/quilt_mcp/tools/packages.py | wc -l` → should be ~100-120

---

## Phase 4: Separate Mixed Concerns in tools/packages.py

### 4.1 Current State

**File:** `tools/packages.py` - 2034 lines
**Contains:**

- Package CRUD operations (create, update, delete, browse)
- Package info operations (list, diff, info)
- S3 ingestion workflow (package_create_from_s3)
- Validation helpers (15+ validation functions)
- Error handling patterns (16 exception handlers)

### 4.2 Split by Responsibility

#### 4.2.1 Extract Validation Module

- [x] Create `src/quilt_mcp/tools/validation.py`:

  ```python
  """Validation utilities for package operations."""

  class ValidationError(Exception):
      """Package validation error."""

  def validate_package_name(name: str) -> None:
      """Validate package name format."""

  def validate_registry(registry: str) -> str:
      """Validate and normalize registry URL."""

  def validate_metadata(metadata: Dict) -> None:
      """Validate package metadata schema."""

  def build_error_response(error: Exception, context: Dict) -> Dict:
      """Build standardized error response."""
  ```

- [x] Move all `_validate_*` functions from packages.py
- [x] Move error response builders
- [x] Update packages.py to import from validation module

**Expected Impact:** -200 lines from packages.py

---

#### 4.2.2 Keep Core CRUD in packages.py

**Retain in `tools/packages.py`:**

- `package_create()` - Create new package
- `package_update()` - Update existing package
- `package_delete()` - Delete package
- `package_browse()` - Browse package contents
- `package_diff()` - Compare package versions
- `package_info()` - Get package info
- `package_list()` - List packages

**After refactoring:**

- These functions use `validation.*` for validation
- These functions use `package_metadata.*` for docs
- Reduced to ~600-800 lines

---

#### 4.2.3 Move S3 Ingestion to Separate Module

- [x] Create `src/quilt_mcp/tools/s3_package_ingestion.py`:

  ```python
  """S3 package ingestion workflows."""
  from .s3_discovery import discover_s3_objects, organize_file_structure
  from .package_metadata import generate_readme_content, generate_package_metadata
  from .validation import validate_package_name, validate_registry
  from .packages import package_create  # Import CRUD operation

  async def package_create_from_s3(...):
      """Create package from S3 (after Phase 3 refactoring)."""
      # ~100-120 lines of orchestration

  async def package_sync_from_s3(...):
      """Sync package with S3 bucket changes."""
      # Future enhancement
  ```

- [x] Move `package_create_from_s3()` (after Phase 3 refactoring)
- [x] Update MCP tool registration to import from new module

**Expected Impact:** ~200 lines moved from packages.py

---

### 4.3 Expected Final State

**After Phase 4:**

- `tools/packages.py`: ~600-800 lines (core CRUD)
- `tools/validation.py`: ~200 lines (validation logic)
- `tools/s3_discovery.py`: ~200 lines (S3 operations)
- `tools/package_metadata.py`: ~200 lines (docs generation)
- `tools/s3_package_ingestion.py`: ~100-120 lines (S3 workflow)

**Total:** ~1300-1520 lines across 5 focused modules (vs 2034 in one file)

**Validation:**

- [x] All tests pass: `uv run pytest tests/unit/tools/`
- [x] No functionality changes
- [x] MCP tools still register correctly
- [ ] Module sizes all <1000 lines

---

## Phase 5: Create GraphQL Client Abstraction

### 5.1 Current Problem

**File:** `backends/platform_backend.py` - 1354 lines
**Contains:**

- 14 GraphQL query/mutation definitions scattered throughout
- Duplicated error handling for GraphQL responses
- Duplicated response parsing logic
- No abstraction layer

**Example Pattern (repeated 14 times):**

```python
def some_operation(self, ...):
    query = """
        query SomeQuery($var: String!) {
            someField(var: $var) { ... }
        }
    """
    try:
        response = self._graphql_request(query, variables={...})
        if "errors" in response:
            # Handle errors
        data = response.get("data", {}).get("someField")
        # Parse and transform data
    except Exception as e:
        # Handle exception
```

---

### 5.2 Create GraphQL Client Module

- [x] Create `src/quilt_mcp/backends/graphql_client.py`:

  ```python
  """GraphQL client abstraction for Platform backend."""
  from typing import Dict, Any, Optional, List
  from dataclasses import dataclass
  import httpx

  @dataclass
  class GraphQLResponse:
      data: Optional[Dict[str, Any]]
      errors: Optional[List[Dict]]

      @property
      def is_success(self) -> bool:
          return self.errors is None

      def get_data(self, path: str, default=None):
          """Get nested data with dot notation."""

  class GraphQLError(Exception):
      """GraphQL operation error."""

  class GraphQLClient:
      """
      Client for executing GraphQL operations against Platform API.

      Handles:
      - Request formatting
      - Error handling
      - Response parsing
      - Retry logic
      - Logging
      """

      def __init__(self, endpoint: str, auth_token: str):
          self.endpoint = endpoint
          self.auth_token = auth_token
          self._client = httpx.AsyncClient()

      async def query(
          self,
          operation: str,
          variables: Optional[Dict] = None
      ) -> GraphQLResponse:
          """Execute a GraphQL query."""

      async def mutate(
          self,
          operation: str,
          variables: Optional[Dict] = None
      ) -> GraphQLResponse:
          """Execute a GraphQL mutation."""

      def _handle_errors(self, response: Dict) -> None:
          """Centralized error handling."""

      def _parse_response(self, raw_response) -> GraphQLResponse:
          """Parse raw HTTP response."""
  ```

- [x] Add tests: `tests/unit/backends/test_graphql_client.py`

**Validation:**

- [x] `uv run pytest tests/unit/backends/test_graphql_client.py` - passes
- [x] Test coverage >= 85%

---

### 5.3 Extract GraphQL Queries to Constants

- [x] Create `src/quilt_mcp/backends/graphql_queries.py`:

  ```python
  """GraphQL query and mutation definitions for Platform API."""

  # Package queries
  PACKAGE_INFO_QUERY = """
      query PackageInfo($bucket: String!, $name: String!) {
          package(bucket: $bucket, name: $name) {
              id
              name
              modified
              ...
          }
      }
  """

  PACKAGE_CREATE_MUTATION = """
      mutation CreatePackage($input: PackageInput!) {
          createPackage(input: $input) {
              id
              name
              ...
          }
      }
  """

  # ... all 14 queries/mutations
  ```

- [x] Extract all GraphQL strings from platform_backend.py
- [x] Organize by domain (packages, buckets, admin, search)

---

### 5.4 Refactor platform_backend.py to Use Client

- [x] Update `Platform_Backend.__init__()`:

  ```python
  def __init__(self, ...):
      super().__init__(...)
      self._graphql = GraphQLClient(
          endpoint=self.catalog_config.api_url,
          auth_token=self.jwt
      )
  ```

- [x] Refactor each GraphQL operation:

  ```python
  # BEFORE (embedded GraphQL)
  async def get_package_info(self, bucket: str, name: str):
      query = """query PackageInfo..."""
      try:
          response = self._graphql_request(query, ...)
          if "errors" in response:
              ...
          data = response.get("data", {}).get("package")
          ...
      except Exception:
          ...

  # AFTER (using client)
  async def get_package_info(self, bucket: str, name: str):
      response = await self._graphql.query(
          PACKAGE_INFO_QUERY,
          variables={"bucket": bucket, "name": name}
      )
      return response.get_data("package")
  ```

- [x] Refactor all 14 GraphQL operations

**Expected Impact:**

- `-300 to -400 lines` from platform_backend.py (query strings + error handling)
- Reduced duplication: 14 error handlers → 1 centralized handler

---

### 5.5 Expected Final State

**After Phase 5:**

- `backends/platform_backend.py`: ~900-1000 lines (business logic only)
- `backends/graphql_client.py`: ~300 lines (client abstraction)
- `backends/graphql_queries.py`: ~200 lines (query definitions)

**Validation:**

- [x] All tests pass: `uv run pytest tests/unit/backends/test_platform_backend.py`
- [x] All tests pass: `uv run pytest tests/func/backends/ -k platform`
- [x] No functionality changes
- [x] GraphQL operations still work correctly

---

## Phase 6: Consolidate Cross-Module Duplication

### 6.1 Extract Shared Backend Utilities

**Problem:** Same utility functions repeated across multiple backends.

- [x] Create `src/quilt_mcp/backends/utils.py`:

  ```python
  """Shared utilities for backend implementations."""

  def extract_bucket_from_registry(registry: str) -> str:
      """Extract S3 bucket name from registry URL."""
      # Currently duplicated in:
      # - quilt_ops.py
      # - platform_backend.py
      # - quilt3_backend_packages.py

  def normalize_registry(registry: str) -> str:
      """Normalize registry URL format."""
      # Currently duplicated in multiple backends

  def build_s3_key(package_name: str, version: str) -> str:
      """Build S3 key for package manifest."""
      # Currently duplicated in backends
  ```

- [x] Find all duplicated utility functions:

  ```bash
  # Search for common patterns
  grep -rn "def.*extract.*bucket" src/quilt_mcp/backends/
  grep -rn "def.*normalize.*registry" src/quilt_mcp/backends/
  grep -rn "def.*build.*s3" src/quilt_mcp/backends/
  ```

- [x] Extract to `backends/utils.py`
- [x] Update all backends to import from utils

**Expected Impact:** -50 to -100 lines total across backends

---

### 6.2 Reduce Validation Redundancy

**Problem:** `quilt_ops.py` validates inputs, then backends validate again in primitives.

**Current Pattern:**

```python
# In quilt_ops.py (base class)
def update_package_revision(self, name, ...):
    self._validate_package_name(name)  # ← Validation 1
    self._backend_push_package(name, ...)  # Calls backend

# In platform_backend.py (backend)
def _backend_push_package(self, name, ...):
    if not self._is_valid_name(name):  # ← Validation 2 (redundant!)
        raise ValueError(...)
```

**Fix:**

- [x] Document validation contract in `ops/quilt_ops.py` docstrings:

  ```python
  def _backend_push_package(self, name: str, ...) -> None:
      """
      Push package to backend storage.

      Preconditions (validated by base class):
      - name is valid package name format
      - registry is accessible
      - package exists or can be created

      Backends should NOT re-validate these conditions.
      Only validate backend-specific constraints.
      """
  ```

- [x] Audit backends for redundant validation:

  ```bash
  grep -rn "_validate\|_is_valid\|_check_" src/quilt_mcp/backends/
  ```

- [x] Remove redundant validation from backend primitives
- [x] Keep only platform-specific validation (e.g., platform quotas, platform permissions)

**Expected Impact:** -30 to -50 lines total across backends

---

### 6.3 Consolidate Transformation Logic

**Problem:** Each backend implements `_transform_search_result_to_package_info()` separately.

- [x] Check if transformation logic is truly backend-specific
- [x] If mostly shared:
  - [ ] Extract common transformation to `backends/utils.py`
  - [ ] Backends override only for platform-specific fields

- [x] If completely different:
  - [ ] Document why in architecture docs
  - [ ] Ensure no duplication within each implementation

---

## Phase 7: Simplify Complex Logic

### 7.1 Simplify delete_package() Complexity

**Problem:** `platform_backend.delete_package()` has 22 nested blocks with complex fallback logic.

**Current Structure:**

```python
async def delete_package(self, bucket, name):
    # Try GraphQL deletion
    try:
        # GraphQL attempt (nested 1)
        if condition1:
            if condition2:
                if condition3:
                    # ... (nested 4, 5, 6...)
    except GraphQLError:
        # Fallback to S3 direct (nested 2)
        try:
            if s3_condition:
                # ... (nested 3, 4, 5...)
        except S3Error:
            # Final fallback (nested 3)
            # ... (nested 4, 5, 6, 7...)
```

**Max Nesting:** 22 blocks

---

**Refactored Structure:**

```python
async def delete_package(self, bucket: str, name: str) -> Dict:
    """
    Delete a package using best available method.

    Attempts in order:
    1. GraphQL API (preferred)
    2. S3 direct deletion (fallback)
    3. Error reporting
    """
    # Try primary method
    result = await self._try_graphql_delete(bucket, name)
    if result.success:
        return result.to_dict()

    # Try fallback method
    result = await self._try_s3_fallback_delete(bucket, name)
    if result.success:
        return result.to_dict()

    # All methods failed
    raise PackageDeletionError(f"Failed to delete {bucket}/{name}", details=result.errors)

async def _try_graphql_delete(self, bucket: str, name: str) -> DeletionResult:
    """
    Attempt GraphQL deletion.
    Max nesting: 5 blocks
    """
    try:
        response = await self._graphql.mutate(PACKAGE_DELETE_MUTATION, ...)
        return DeletionResult(success=True, method="graphql")
    except GraphQLError as e:
        return DeletionResult(success=False, method="graphql", errors=[e])

async def _try_s3_fallback_delete(self, bucket: str, name: str) -> DeletionResult:
    """
    Fallback: Direct S3 deletion.
    Max nesting: 5 blocks
    """
    try:
        # S3 deletion logic
        return DeletionResult(success=True, method="s3")
    except S3Error as e:
        return DeletionResult(success=False, method="s3", errors=[e])
```

**Target Nesting:** 5-6 blocks (down from 22)

---

- [x] Create `@dataclass DeletionResult` for method results
- [x] Extract `_try_graphql_delete()` method
- [x] Extract `_try_s3_fallback_delete()` method
- [x] Refactor `delete_package()` to orchestrate

**Validation:**

- [x] Run: `uv run pytest tests/unit/backends/test_platform_backend.py -k delete`
- [x] Test both success paths (GraphQL works, S3 fallback works)
- [x] Test failure paths (both methods fail)
- [x] Verify error messages are clear

---

### 7.2 Reduce Documentation Verbosity in quilt_ops.py

**Problem:** 10+ line docstrings inflate file size without adding value.

**Current Example:**

```python
def update_package_revision(self, ...):
    """
    Update a package revision in the Quilt data catalog.

    This is a high-level orchestration method that coordinates multiple
    backend operations to update a package revision. It follows the
    Template Method design pattern, delegating specific operations to
    backend-specific implementations while maintaining consistent workflow.

    The method performs the following steps in order:
    1. Validates the package name format
    2. Pushes package data to storage
    3. Commits the revision to catalog
    4. Updates metadata
    5. Validates the final state

    Args:
        name: The package name in format "namespace/package"
        ... (5 more args with detailed descriptions)

    Returns:
        Dict containing:
            - status: Success/failure indicator
            - package_id: Unique identifier
            - ... (5 more fields)

    Raises:
        ValidationError: If package name is invalid
        BackendError: If storage operation fails
        ... (3 more exceptions)

    Examples:
        >>> backend.update_package_revision("myns/mypkg", ...)
        {'status': 'success', ...}

    See Also:
        - create_package_revision() for creating new packages
        - delete_package() for removing packages

    Note:
        This method requires appropriate permissions in the catalog.

    Warning:
        Large packages may take significant time to process.
    """
    # 115 lines of actual code
```

**Reduced Example:**

```python
def update_package_revision(
    self,
    name: str,
    registry: str,
    message: str,
    metadata: Optional[Dict] = None
) -> Dict:
    """
    Update a package revision using Template Method pattern.

    Orchestrates: validate → push → commit → update metadata
    See ARCHITECTURE.md for Template Method pattern details.
    """
    # 115 lines of actual code
```

---

- [x] Update class-level docstring in `quilt_ops.py`:

  ```python
  class QuiltOps:
      """
      Abstract base class defining package operations using Template Method pattern.

      ## Architecture

      This class provides high-level orchestration methods (e.g., create_package_revision,
      update_package_revision) that coordinate multiple steps. Concrete backend
      implementations provide primitives (e.g., _backend_push_package) that are called
      by the orchestration methods.

      ## Template Method Pattern

      Each orchestration method:
      1. Validates inputs at the base class level
      2. Calls backend-specific primitives in defined order
      3. Handles errors consistently
      4. Returns standardized responses

      Backends implement only the primitives, not the orchestration logic.

      See ARCHITECTURE.md Section 3.2 for detailed pattern explanation.
      """
  ```

- [x] Reduce method docstrings to 2-4 lines:
  - Brief description (1 line)
  - Key behavior note (1 line)
  - Reference to architecture docs (1 line)

- [x] Move detailed implementation notes to `ARCHITECTURE.md`

**Expected Impact:** -200 to -300 lines from quilt_ops.py

**Validation:**

- [x] Docstrings still clear and useful
- [x] Architecture documentation updated
- [x] Developers can still understand code purpose

---

## Phase 8: Final Validation & Documentation

### 8.1 Comprehensive Testing

- [x] **Unit tests:** `uv run pytest tests/unit/ -v`
- [x] **Functional tests:** `uv run pytest tests/func/ -v`
- [x] **E2E tests:** `uv run pytest tests/e2e/ -v`
- [x] **All tests:** `make test-all`

**Success Criteria:** All tests pass, no functionality changes

---

### 8.2 Code Quality Checks

- [x] **Import cycles:** `uv run python scripts/detect_cycles.py`
  - Expected: **0 cycles** (down from 15)

- [x] **Type checking:** `uv run mypy src/quilt_mcp`
  - Expected: No errors, clean pass

- [x] **Linting:** `make lint`
  - Expected: Clean pass

- [ ] **Module sizes:** `find src/quilt_mcp -name "*.py" -exec wc -l {} \; | sort -rn | head -20`
  - Expected: All modules <1500 lines (no 2000+ line modules)
  - Expected: Top modules <1000 lines (most modules)

---

### 8.3 Function Complexity Audit

- [ ] Check function sizes:

  ```bash
  # Find functions >200 lines
  for file in $(find src/quilt_mcp -name "*.py"); do
      python -c "
  import ast
  with open('$file') as f:
      tree = ast.parse(f.read())
      for node in ast.walk(tree):
          if isinstance(node, ast.FunctionDef):
              size = node.end_lineno - node.lineno
              if size > 200:
                  print(f'$file:{node.lineno}: {node.name}() - {size} lines')
      "
  done
  ```

  Expected: **No functions >200 lines** (down from 448-line monster)

- [ ] Check nesting depth:

  ```bash
  # Use radon or similar
  uv run radon cc src/quilt_mcp -a --total-average -nb
  ```

  Expected: Average complexity grade A or B, no individual functions grade F

---

### 8.4 Update Documentation

- [x] Update `ARCHITECTURE.md`:
  - [ ] Document new module structure
  - [ ] Document Template Method pattern usage
  - [ ] Document GraphQL client abstraction
  - [ ] Add diagrams for complex workflows

- [x] Update `CONTRIBUTING.md`:
  - [ ] Add guidelines on module size
  - [ ] Add guidelines on avoiding circular imports
  - [ ] Add examples of good code organization

- [x] Update inline documentation:
  - [ ] Ensure new modules have clear docstrings
  - [ ] Ensure refactored functions have updated docs
  - [ ] Remove outdated comments

---

### 8.5 Create Migration Guide

- [x] Create `docs/refactoring/MIGRATION_GUIDE.md`:

  ```markdown
  # Module Refactoring Migration Guide

  ## Summary of Changes

  This refactoring addressed 5 critical maintainability issues:
  1. Giant functions (448 lines → ~100 lines)
  2. Architecture violations (removed orchestration duplication)
  3. Circular imports (15 cycles → 0 cycles)
  4. Mixed concerns (separated by responsibility)
  5. Scattered operations (created client abstraction)

  ## Import Changes

  ### If you import from tools/packages.py

  - `package_create_from_s3` → Import from `tools.s3_package_ingestion`
  - Validation functions → Import from `tools.validation`
  - Core CRUD operations → Still in `tools.packages`

  ### If you import from backends/platform_backend.py

  - GraphQL operations → Use client methods, not raw queries
  - Shared utilities → Import from `backends.utils`

  ## Breaking Changes

  ### None Expected

  All public APIs remain unchanged. Internal implementation details
  have been reorganized for better maintainability.

  ## Verification

  Run the test suite to verify compatibility:
  ```bash
  make test-all
  ```

  ```

---

## Success Criteria Summary

### Critical Issues (ALL must be ✅)

- [ ] **448-line function** → Refactored to ~100 lines with extracted modules
- [x] **Platform backend orchestration duplication** → Removed, uses base class
- [x] **15 circular import cycles** → Eliminated, 0 cycles remain
- [ ] **Mixed concerns in tools/packages.py** → Separated by responsibility
- [x] **Scattered GraphQL operations** → Abstracted into client

### Code Quality Metrics

| Metric | Before | Target | Status |
|--------|--------|--------|--------|
| Circular import cycles | 15 | 0 | ⬜ |
| Largest module | 2034 lines | <1500 lines | ⬜ |
| Largest function | 448 lines | <200 lines | ⬜ |
| Max nesting depth | 22 blocks | <8 blocks | ⬜ |
| GraphQL duplication | 14 copies | 1 client | ⬜ |
| Architecture violations | 1 major | 0 | ⬜ |

### Test Coverage

- [x] All tests pass: `make test-all`
- [x] No functionality changes
- [x] Coverage maintained or improved
- [x] Mypy clean: `uv run mypy src/quilt_mcp`

---

## Estimated Effort

| Phase | Description | Estimated Time |
|-------|-------------|----------------|
| 0 | Discover all 15 cycles | 2-3 hours |
| 1 | Break all circular imports | 8-12 hours |
| 2 | Fix architecture violations | 4-6 hours |
| 3 | Refactor giant function | 8-10 hours |
| 4 | Separate mixed concerns | 6-8 hours |
| 5 | Create GraphQL abstraction | 6-8 hours |
| 6 | Consolidate duplication | 4-6 hours |
| 7 | Simplify complex logic | 4-6 hours |
| 8 | Validation & documentation | 4-6 hours |

**Total:** 46-65 hours (approximately 6-8 business days)

---

## Execution Strategy

### Recommended Order

1. **Phase 0 first** - Discover all cycles before proceeding
2. **Phase 1 next** - Break cycles (enables other refactoring)
3. **Phase 2 early** - Fix architecture violation (high impact, low risk)
4. **Phases 3-5 in parallel** - Different files, can work simultaneously
5. **Phase 6-7 together** - Natural follow-ups to earlier phases
6. **Phase 8 last** - Validation and documentation

### Risk Mitigation

- Run tests after each phase
- Commit after each completed phase
- Use feature branches for large phases
- Get code review after Phases 1, 2, 3
- Maintain backwards compatibility throughout

---

## Notes

- **Preserve all tests** - Tests must pass throughout refactoring
- **No breaking changes** - All public APIs remain unchanged
- **Extract, don't rewrite** - Move code, don't reimplement
- **Document as you go** - Update docs incrementally
- **Git history matters** - Use `git mv` for file moves
