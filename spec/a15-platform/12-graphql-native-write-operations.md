# Platform Backend: GraphQL-Native Write Operations

**Document:** 12-graphql-native-write-operations.md
**Status:** Specification
**Created:** 2026-02-02
**Branch:** `a16-graphql-backend`
**Related:** [07-implementation-plan.md](./07-implementation-plan.md), [11-test-coverage-plan.md](./11-test-coverage-plan.md)

## Executive Summary

### Problem

The current Platform_Backend implementation (commit cb369d9, 2026-02-02) uses **GraphQL for read operations** but **delegates to `quilt3.Package` for write operations**. This creates architectural inconsistency:

- ✅ Read operations: Pure GraphQL queries
- ❌ Write operations: Imports `quilt3.Package`, uses Python SDK
- Result: Mixed architecture defeating the purpose of a GraphQL-native backend

### Solution

Replace `quilt3.Package` delegation with native GraphQL `packageConstruct` and `packagePromote` mutations for all write operations (`create_package_revision()` and `update_package_revision()`).

### Impact

**Benefits:**

- Architectural consistency (pure GraphQL for all operations)
- Removes `quilt3` dependency from Platform_Backend
- Aligns with Platform's Lambda-based backend architecture
- Simpler testing (mock GraphQL responses vs complex quilt3 mocking)

**Limitations:**

- `copy=True` parameter deferred (will raise `NotImplementedError`)
- Must implement metadata merging in Python (no longer handled by quilt3)

### Scope

**In Scope:**

- Replace `create_package_revision()` implementation with `packageConstruct` mutation
- Replace `update_package_revision()` implementation with `packageConstruct` mutation
- Update unit tests to mock GraphQL mutations instead of quilt3
- Document `copy=True` limitation

**Out of Scope:**

- `copy=True` support (deferred to future work)
- Admin operations (not implemented in Platform_Backend)
- Integration tests (covered by existing test suite)

---

## Architecture

### Current Architecture (Problematic)

```text
Platform_Backend
├── Read Operations  → GraphQL Queries ✓
│   ├── search_packages()
│   ├── get_package_info()
│   ├── browse_content()
│   └── list_all_packages()
│
└── Write Operations → quilt3.Package ✗
    ├── create_package_revision()  [imports quilt3]
    └── update_package_revision()  [imports quilt3]
```

**Issues:**

1. Imports `quilt3` Python SDK despite being GraphQL backend
2. Uses AWS credentials for both GraphQL auth AND quilt3 operations
3. Inconsistent with Platform's Lambda-based package creation
4. Defeats purpose of GraphQL-native backend

### Target Architecture (GraphQL-Native)

```text
Platform_Backend
├── Read Operations  → GraphQL Queries ✓
│   ├── search_packages()
│   ├── get_package_info()
│   ├── browse_content()
│   └── list_all_packages()
│
└── Write Operations → GraphQL Mutations ✓
    ├── create_package_revision()  [packageConstruct mutation]
    └── update_package_revision()  [packageConstruct mutation]
```

**Benefits:**

1. No `quilt3` imports in Platform_Backend
2. Single authentication mechanism (JWT for GraphQL)
3. Consistent with Platform's Lambda-based architecture
4. Pure GraphQL implementation

---

## GraphQL Schema

### Mutations

**Location:** `/Users/ernest/GitHub/enterprise/registry/quilt_server/graphql/schema.graphql`

#### packageConstruct

Creates a new package revision from a list of entries.

```graphql
type Mutation {
  packageConstruct(
    params: PackagePushParams!
    src: PackageConstructSource!
  ): PackageConstructResult!
}

input PackagePushParams {
  message: String
  userMeta: JsonRecord
  workflow: String
  bucket: String!
  name: String!
}

input PackageConstructSource {
  entries: [PackageConstructEntry!]!
}

input PackageConstructEntry {
  logicalKey: String!      # Package-relative path (e.g., "data/file.csv")
  physicalKey: String!     # S3 URI (e.g., "s3://bucket/path/file.csv")
  hash: PackageEntryHash   # Optional SHA256 hash
  size: Float              # Optional file size in bytes
  meta: JsonRecord         # Optional entry metadata
}

type PackageConstructResult {
  __typename: String!
  ... on PackagePushSuccess {
    package: Package!
    revision: PackageRevision!
  }
  ... on PackagePushInvalidInputFailure {
    errors: [InvalidInputError!]!
  }
  ... on PackagePushComputeFailure {
    message: String!
  }
}
```

#### packagePromote

Promotes (copies) an existing package revision to a new location.

```graphql
type Mutation {
  packagePromote(
    params: PackagePushParams!
    src: PackagePromoteSource!
    destPrefix: String
  ): PackagePromoteResult!
}

input PackagePromoteSource {
  bucket: String!
  name: String!
  hash: String!
}
```

**Note:** `packagePromote` is **out of scope** for initial implementation (used for `copy=True` support, which is deferred).

---

## Implementation Specification

### Phase 1: create_package_revision()

**File:** `src/quilt_mcp/backends/platform_backend.py` (lines 521-582)

**Current Behavior:**

1. Validates inputs
2. Imports `quilt3.Package`
3. Creates package instance
4. Adds files via `package.set()`
5. Pushes via `package.push()` with `selector_fn` for copy control

**Target Behavior:**

1. Validates inputs
2. **Raises `NotImplementedError` if `copy=True`** (deferred feature)
3. Builds GraphQL `packageConstruct` mutation
4. Constructs `entries` array:
   - Extract `logicalKey` from S3 URI using existing `_extract_logical_key()` helper
   - Set `physicalKey` to raw S3 URI
   - Set `hash` to `None` (optional)
   - Set `size` to `None` (optional, can optimize later)
   - Set `meta` to `None` (optional)
5. Executes mutation via `self.execute_graphql_query()`
6. Parses response:
   - Success: Extract `top_hash` from `revision.hash`
   - Invalid input: Raise `ValidationError`
   - Compute failure: Raise `BackendError`
7. Returns `Package_Creation_Result`

**GraphQL Mutation Structure:**

```graphql
mutation PackageConstruct($params: PackagePushParams!, $src: PackageConstructSource!) {
  packageConstruct(params: $params, src: $src) {
    __typename
    ... on PackagePushSuccess {
      package { name }
      revision { hash }
    }
    ... on PackagePushInvalidInputFailure {
      errors { path message }
    }
    ... on PackagePushComputeFailure {
      message
    }
  }
}
```

**Variables:**

```python
variables = {
    "params": {
        "bucket": self._extract_bucket_from_registry(registry),
        "name": package_name,
        "message": message,
        "userMeta": metadata or {},
        "workflow": None,
    },
    "src": {
        "entries": [
            {
                "logicalKey": self._extract_logical_key(s3_uri, auto_organize),
                "physicalKey": s3_uri,
                "hash": None,
                "size": None,
                "meta": None,
            }
            for s3_uri in s3_uris
        ]
    }
}
```

**Error Mapping:**

| GraphQL Response | Exception Type | Context |
|------------------|----------------|---------|
| `PackagePushInvalidInputFailure` | `ValidationError` | Include error path and message |
| `PackagePushComputeFailure` | `BackendError` | Include failure message |
| GraphQL network error | `BackendError` | Include exception details |
| `copy=True` parameter | `NotImplementedError` | "copy=True not yet supported in Platform_Backend" |

**Validation Checklist:**

- [ ] Remove `import quilt3` statement
- [ ] Remove `quilt3.Package()` instantiation
- [ ] Remove `package.set()` and `package.push()` calls
- [ ] Add `copy=True` validation (raise NotImplementedError)
- [ ] Build `packageConstruct` mutation query
- [ ] Construct `entries` array from `s3_uris`
- [ ] Execute mutation via `execute_graphql_query()`
- [ ] Handle all three response types (Success, InvalidInput, ComputeFailure)
- [ ] Extract `top_hash` from `revision.hash`
- [ ] Return `Package_Creation_Result` with correct fields
- [ ] Preserve existing `_validate_package_creation_inputs()` call

### Phase 2: update_package_revision()

**File:** `src/quilt_mcp/backends/platform_backend.py` (lines 584-676)

**Current Behavior:**

1. Validates inputs
2. Imports `quilt3.Package`
3. Browses existing package via `quilt3.Package.browse()`
4. Adds new files via `updated_pkg.set()`
5. Merges metadata (existing + new)
6. Pushes with `selector_fn` based on `copy` parameter

**Target Behavior:**

1. Validates inputs
2. **Raises `NotImplementedError` if `copy != "none"`** (deferred feature)
3. Queries existing package contents:
   - Use GraphQL `package { revision { contentsFlatMap } }` query
   - Extract existing entries (logicalKey → physicalKey mapping)
4. Queries existing metadata:
   - Use GraphQL `package { revision { userMeta } }` query
   - Parse JSON metadata
5. Builds merged entries array:
   - Start with existing entries
   - Add new entries (overwrites if same logicalKey)
6. Merges metadata:
   - Combine existing userMeta + new metadata
   - New keys override existing
7. Executes `packageConstruct` mutation with merged data
8. Returns `Package_Creation_Result`

**GraphQL Query for Existing Package:**

```graphql
query GetPackageForUpdate($bucket: String!, $name: String!) {
  package(bucket: $bucket, name: $name) {
    revision(hashOrTag: "latest") {
      hash
      userMeta
      contentsFlatMap(max: 10000)
    }
  }
}
```

**Merge Logic:**

```python
# 1. Get existing entries
existing_entries = query_result["data"]["package"]["revision"]["contentsFlatMap"]
# Format: { "logical/key": { "physicalKey": "s3://...", "size": 123, ... } }

# 2. Get existing metadata
existing_meta = query_result["data"]["package"]["revision"]["userMeta"] or {}

# 3. Build entries array
entries = []
for logical_key, entry_data in existing_entries.items():
    entries.append({
        "logicalKey": logical_key,
        "physicalKey": entry_data["physicalKey"],
        "size": entry_data.get("size"),
        "hash": entry_data.get("hash"),
        "meta": None,
    })

# 4. Add new files (overwrites if same logicalKey)
for s3_uri in s3_uris:
    logical_key = self._extract_logical_key(s3_uri, auto_organize)
    # Remove existing entry with same logical_key
    entries = [e for e in entries if e["logicalKey"] != logical_key]
    # Add new entry
    entries.append({
        "logicalKey": logical_key,
        "physicalKey": s3_uri,
        "hash": None,
        "size": None,
        "meta": None,
    })

# 5. Merge metadata
merged_meta = {**existing_meta, **(metadata or {})}
```

**Validation Checklist:**

- [ ] Remove `import quilt3` statement
- [ ] Remove `quilt3.Package.browse()` call
- [ ] Add `copy != "none"` validation (raise NotImplementedError)
- [ ] Query existing package via GraphQL
- [ ] Extract existing entries from `contentsFlatMap`
- [ ] Extract existing metadata from `userMeta`
- [ ] Build merged entries array (existing + new)
- [ ] Merge metadata dictionaries (new overrides existing)
- [ ] Execute `packageConstruct` mutation
- [ ] Handle empty package case (if package not found)
- [ ] Return `Package_Creation_Result` with correct file_count

### Phase 3: Update Tests

**Files:**

1. `tests/unit/backends/test_platform_backend_core.py` - Update existing write operation tests
2. `tests/unit/backends/test_platform_backend_packages.py` - **NEW FILE** (per test coverage plan)

**Test Changes:**

#### Remove quilt3 Mocks

**Current pattern:**

```python
class FakePackage:
    def __init__(self):
        self.meta = {}
    def push(self, *args, **kwargs):
        return "top-hash"

fake_quilt3 = SimpleNamespace(Package=FakePackage)
monkeypatch.setitem(sys.modules, "quilt3", fake_quilt3)
```

**Target pattern:** Remove entirely (no longer imports quilt3)

#### Add GraphQL Mutation Mocks

**Success scenario:**

```python
def test_create_package_with_graphql(monkeypatch):
    backend = _make_backend(monkeypatch)

    # Mock successful packageConstruct response
    def mock_graphql(query, variables=None):
        return {
            "data": {
                "packageConstruct": {
                    "__typename": "PackagePushSuccess",
                    "package": {"name": "test-package"},
                    "revision": {"hash": "abc123def456"}
                }
            }
        }

    backend.execute_graphql_query = mock_graphql

    result = backend.create_package_revision(
        package_name="test-package",
        s3_uris=["s3://bucket/file.txt"],
        registry="s3://bucket",
        message="Test package"
    )

    assert result.success
    assert result.top_hash == "abc123def456"
```

**Error scenario:**

```python
def test_create_package_invalid_input(monkeypatch):
    backend = _make_backend(monkeypatch)

    def mock_graphql_error(query, variables=None):
        return {
            "data": {
                "packageConstruct": {
                    "__typename": "PackagePushInvalidInputFailure",
                    "errors": [
                        {"path": "entries.0.physicalKey", "message": "Invalid S3 URI"}
                    ]
                }
            }
        }

    backend.execute_graphql_query = mock_graphql_error

    with pytest.raises(ValidationError):
        backend.create_package_revision(
            package_name="test-package",
            s3_uris=["invalid-uri"],
            registry="s3://bucket"
        )
```

**Copy mode validation:**

```python
def test_create_package_copy_true_not_supported(monkeypatch):
    backend = _make_backend(monkeypatch)

    with pytest.raises(NotImplementedError, match="copy=True not yet supported"):
        backend.create_package_revision(
            package_name="test-package",
            s3_uris=["s3://bucket/file.txt"],
            registry="s3://bucket",
            copy=True  # Should raise NotImplementedError
        )
```

**Test Coverage Requirements:**

- [ ] `test_create_package_graphql_success` - Basic package creation
- [ ] `test_create_package_with_metadata` - Include userMeta
- [ ] `test_create_package_invalid_input_failure` - Handle GraphQL validation errors
- [ ] `test_create_package_compute_failure` - Handle Lambda failures
- [ ] `test_create_package_copy_true_raises` - Validate copy=True raises NotImplementedError
- [ ] `test_update_package_graphql_success` - Update with new files
- [ ] `test_update_package_merges_metadata` - Verify metadata merging
- [ ] `test_update_package_preserves_existing_files` - Check existing entries preserved
- [ ] `test_update_package_copy_all_raises` - Validate copy != "none" raises NotImplementedError

---

## Backend Comparison

### Platform GraphQL Backend Flow

```text
Client Request
    ↓
MCP Tool (package_create)
    ↓
Platform_Backend.create_package_revision()
    ↓
GraphQL packageConstruct mutation
    ↓
Platform Registry (Django + GraphQL)
    ↓
pkgpush.package_construct()
    ↓
Upload request to S3
    ↓
Invoke Lambda (QUILT_PKG_CREATE_LAMBDA_ARN)
    ↓
Lambda processes package creation
    ↓
Return PackagePushResult
    ↓
Return to client
```

### Quilt3 Backend Flow (for comparison)

```text
Client Request
    ↓
MCP Tool (package_create)
    ↓
Quilt3_Backend.create_package_revision()
    ↓
quilt3.Package()
    ↓
package.push()
    ↓
Direct S3 + ElasticSearch operations
    ↓
Return to client
```

**Key Difference:** Platform uses Lambda-based serverless package creation, while Quilt3 uses direct client-side operations. Platform_Backend should align with Platform architecture.

---

## Open Questions & Decisions

### 1. File Size Metadata

**Question:** Should we populate the `size` field in `PackageConstructEntry`?

**Options:**

- **A:** Pass `None` (simplest, field is optional)
- **B:** Add helper to get size from S3 (requires S3 API call per file)

**Decision:** Pass `None` initially (Option A). Can add size optimization later if needed.

**Rationale:**

- `size` is optional in GraphQL schema
- Lambda can compute size during package creation
- Avoids extra S3 API calls
- Simplifies implementation

### 2. File Hash Metadata

**Question:** Should we compute SHA256 hashes for entries?

**Options:**

- **A:** Pass `None` (simplest, field is optional)
- **B:** Compute hash per file (expensive, requires downloading files)

**Decision:** Pass `None` initially (Option A).

**Rationale:**

- `hash` is optional in GraphQL schema
- Lambda computes hashes server-side during package creation
- Avoids expensive client-side hash computation
- Matches Platform's serverless architecture

### 3. Copy Mode Support

**Question:** How to handle `copy=True` parameter?

**Options:**

- **A:** Raise `NotImplementedError` (deferred)
- **B:** Use `packagePromote` mutation (complex, requires temp package)
- **C:** Copy S3 objects manually (requires boto3, defeats GraphQL purpose)

**Decision:** Option A - Raise `NotImplementedError` with clear message.

**Rationale:**

- Most use cases don't require data copying
- `packageConstruct` creates symlink-like references (sufficient for most scenarios)
- Can add `packagePromote` support incrementally later
- Simplifies initial implementation
- Clear error message guides users

**Error Message:**

```python
if copy:
    raise NotImplementedError(
        "copy=True not yet supported in Platform_Backend. "
        "Use copy=False to create symlink-like package references."
    )
```

### 4. Metadata Merging in Updates

**Question:** How to merge metadata when updating packages?

**Decision:** Query existing `userMeta` via GraphQL, merge in Python.

**Approach:**

```python
# Query existing metadata
existing_meta = graphql_query("package { revision { userMeta } }")

# Merge (new overrides existing)
merged_meta = {**existing_meta, **(new_metadata or {})}

# Pass to packageConstruct
variables = {"params": {"userMeta": merged_meta, ...}, ...}
```

**Rationale:**

- Simple dictionary merge in Python
- Explicit control over merge behavior
- Consistent with quilt3 behavior (new keys override)

### 5. Backwards Compatibility

**Question:** Must behavior match quilt3.Package exactly?

**Decision:** Close parity acceptable, but differences must be documented.

**Acceptable Differences:**

- GraphQL error formats (different from quilt3 exceptions)
- `copy=True` not supported (raises NotImplementedError)
- Error messages may differ slightly

**Non-Negotiable:**

- Must return same `Package_Creation_Result` structure
- Must support same core parameters (package_name, s3_uris, metadata, registry)
- Must validate inputs consistently
- Must handle metadata merging in updates

---

## Migration & Rollout

### Update Documentation

**Files to Update:**

1. [spec/a15-platform/07-implementation-plan.md](./07-implementation-plan.md)
   - Update Phase 3 (Write Operations) section
   - Change "Delegates to quilt3.Package" to "Uses GraphQL packageConstruct mutation"
   - Update rationale to explain GraphQL-native approach

2. [spec/a15-platform/11-test-coverage-plan.md](./11-test-coverage-plan.md)
   - Update test patterns for write operations
   - Change `FakePackage` mocks to GraphQL mutation mocks
   - Update test descriptions

3. README or API documentation
   - Document `copy=True` limitation
   - Add note about GraphQL-native architecture

### Deprecation Strategy

**No deprecation needed** - This is an internal refactor. External API (MCP tools) remains unchanged.

**User-Facing Impact:**

- `copy=True` parameter now raises `NotImplementedError` (breaking change for users relying on this)
- Error messages may differ slightly
- Otherwise transparent to users

### Rollback Plan

**If issues arise:**

1. Revert commit implementing GraphQL mutations
2. Restore quilt3.Package delegation
3. Document as "temporary revert"
4. Investigate root cause
5. Re-attempt with fixes

**Risk Assessment:** Low - extensive unit tests will catch issues before production

---

## Success Criteria

### Functional Requirements

- [ ] `create_package_revision()` uses GraphQL `packageConstruct` mutation
- [ ] `update_package_revision()` uses GraphQL for query + mutation
- [ ] No `import quilt3` statements in Platform_Backend write operations
- [ ] `copy=True` raises `NotImplementedError` with clear message
- [ ] Metadata merging works correctly in updates
- [ ] All GraphQL error types handled (InvalidInput, ComputeFailure)
- [ ] Returns `Package_Creation_Result` with correct fields

### Non-Functional Requirements

- [ ] All existing unit tests pass
- [ ] New tests cover GraphQL mutation scenarios
- [ ] Code coverage maintained or improved
- [ ] No performance regression
- [ ] Documentation updated
- [ ] Error messages clear and actionable

### Testing Checklist

- [ ] Unit tests mock GraphQL responses correctly
- [ ] Test all three response types (Success, InvalidInput, ComputeFailure)
- [ ] Test metadata merging in updates
- [ ] Test copy=True validation raises NotImplementedError
- [ ] Test with empty packages (no existing entries)
- [ ] Test with large numbers of entries (pagination if needed)
- [ ] Integration tests pass (if applicable)

---

## Timeline

**Estimated Effort:** 8-11 hours

| Phase | Description | Effort |
|-------|-------------|--------|
| Phase 1 | Implement `create_package_revision()` | 2-3 hours |
| Phase 2 | Implement `update_package_revision()` | 2-3 hours |
| Phase 3 | Update tests | 2-3 hours |
| Phase 4 | Documentation updates | 1 hour |
| Phase 5 | Remove quilt3 dependency (optional) | 1 hour |

**Total:** 8-11 hours of development time

---

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| GraphQL mutation behavior differs from quilt3 | High | Medium | Extensive testing, document differences |
| Breaking change for copy=True users | Medium | Low | Clear error message, document limitation |
| Metadata merging logic incorrect | High | Low | Unit tests for merge scenarios |
| Performance regression | Low | Low | GraphQL should be comparable or faster |
| Lambda errors not properly handled | Medium | Low | Test all error scenarios |

---

## Future Work

### Copy Mode Support

**When:** After initial GraphQL-native implementation is stable

**Approach:** Use `packagePromote` mutation

**Steps:**

1. Create temporary package with `packageConstruct`
2. Promote to final destination with `packagePromote`
3. Clean up temporary package
4. Handle errors at each step

**Complexity:** Medium - requires multi-step transaction logic

### File Size Optimization

**When:** If performance profiling shows bottleneck

**Approach:** Add `_get_file_size()` helper

**Implementation:**

```python
def _get_file_size(self, s3_uri: str) -> Optional[float]:
    """Get S3 object size without downloading."""
    try:
        bucket, key, version = parse_s3_uri(s3_uri)
        client = self.get_boto3_client("s3")
        response = client.head_object(Bucket=bucket, Key=key)
        return float(response["ContentLength"])
    except Exception:
        return None
```

### Hash Computation

**When:** If data integrity validation is required

**Approach:** Compute SHA256 client-side before upload

**Tradeoffs:** Expensive (requires downloading files), may not be worth the cost

---

## References

### GraphQL Schema

- **Location:** `/Users/ernest/GitHub/enterprise/registry/quilt_server/graphql/schema.graphql`
- **Lines 859-891:** Package mutation input types
- **Lines 976-989:** Package mutations

### Implementation

- **Backend:** [src/quilt_mcp/backends/platform_backend.py](../../src/quilt_mcp/backends/platform_backend.py)
- **Tests:** [tests/unit/backends/test_platform_backend_core.py](../../tests/unit/backends/test_platform_backend_core.py)

### Related Specs

- [07-implementation-plan.md](./07-implementation-plan.md) - Original implementation plan (now outdated for write operations)
- [11-test-coverage-plan.md](./11-test-coverage-plan.md) - Test coverage plan (needs updates)
- [04-tabulator-mixin.md](./04-tabulator-mixin.md) - GraphQL execution pattern

### Commits

- **cb369d9** - Initial Platform_Backend implementation (2026-02-02)
  - Used quilt3.Package for write operations
  - This spec supersedes that approach

---

## Appendix: GraphQL Mutation Examples

### Create Package Example

**Request:**

```graphql
mutation {
  packageConstruct(
    params: {
      bucket: "my-bucket"
      name: "my-package"
      message: "Initial version"
      userMeta: {
        "author": "Jane Doe",
        "project": "Data Analysis"
      }
    }
    src: {
      entries: [
        {
          logicalKey: "data/file1.csv"
          physicalKey: "s3://source-bucket/path/file1.csv"
        }
        {
          logicalKey: "data/file2.csv"
          physicalKey: "s3://source-bucket/path/file2.csv"
        }
      ]
    }
  ) {
    __typename
    ... on PackagePushSuccess {
      package { name }
      revision { hash }
    }
    ... on PackagePushInvalidInputFailure {
      errors { path message }
    }
    ... on PackagePushComputeFailure {
      message
    }
  }
}
```

**Success Response:**

```json
{
  "data": {
    "packageConstruct": {
      "__typename": "PackagePushSuccess",
      "package": {
        "name": "my-package"
      },
      "revision": {
        "hash": "a1b2c3d4e5f6"
      }
    }
  }
}
```

**Error Response (Invalid Input):**

```json
{
  "data": {
    "packageConstruct": {
      "__typename": "PackagePushInvalidInputFailure",
      "errors": [
        {
          "path": "entries.0.physicalKey",
          "message": "Invalid S3 URI format"
        }
      ]
    }
  }
}
```

**Error Response (Compute Failure):**

```json
{
  "data": {
    "packageConstruct": {
      "__typename": "PackagePushComputeFailure",
      "message": "Lambda execution failed: Timeout"
    }
  }
}
```

### Update Package Example

**Step 1: Query existing package**

```graphql
query {
  package(bucket: "my-bucket", name: "my-package") {
    revision(hashOrTag: "latest") {
      hash
      userMeta
      contentsFlatMap(max: 10000)
    }
  }
}
```

**Response:**

```json
{
  "data": {
    "package": {
      "revision": {
        "hash": "existing-hash",
        "userMeta": {
          "author": "Jane Doe",
          "version": "1.0"
        },
        "contentsFlatMap": {
          "data/file1.csv": {
            "physicalKey": "s3://bucket/.quilt/packages/existing-hash/file1",
            "size": 1024
          }
        }
      }
    }
  }
}
```

**Step 2: Create new revision with merged data**

```graphql
mutation {
  packageConstruct(
    params: {
      bucket: "my-bucket"
      name: "my-package"
      message: "Add file2"
      userMeta: {
        "author": "Jane Doe",
        "version": "2.0"  # New version overrides
      }
    }
    src: {
      entries: [
        # Existing file (preserved)
        {
          logicalKey: "data/file1.csv"
          physicalKey: "s3://bucket/.quilt/packages/existing-hash/file1"
          size: 1024
        }
        # New file (added)
        {
          logicalKey: "data/file2.csv"
          physicalKey: "s3://source-bucket/file2.csv"
        }
      ]
    }
  ) {
    __typename
    ... on PackagePushSuccess {
      revision { hash }
    }
  }
}
```

---

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-02-02 | Ernest Prabhakar | Initial specification |
