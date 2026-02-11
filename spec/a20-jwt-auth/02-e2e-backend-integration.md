# E2E Backend Integration Tests

**Spec ID:** a20-jwt-auth/02-e2e-backend-integration
**Status:** Draft
**Created:** 2026-02-09
**Author:** System Design
**Related:** a20-jwt-auth/01-e2e-tabulator-test.md

---

## Context & Motivation

### Current State

- `scripts/tests/mcp-test.yaml` provides comprehensive tool discovery testing (2000+ lines)
- `tests/e2e/test_tabulator.py` validates tabulator lifecycle with **REAL** GraphQL/Athena
- Tool discovery validates individual operations but doesn't test **integration workflows**
- No tests for complete user workflows (e.g., "discover → access → package → publish")
- No tests for error handling and recovery across backend boundaries
- No tests for data consistency across multiple backends
- No performance benchmarks for realistic workloads

### Why This Matters

1. **Integration Bugs:** Individual tools may work but fail when composed into workflows
2. **Real-World Usage:** Users don't call single tools - they execute multi-step workflows
3. **Backend Consistency:** Same data accessed via Quilt3/Tabulator/Athena must be consistent
4. **Error Recovery:** Need to validate graceful degradation when services fail
5. **Performance Baselines:** Need to know what's acceptable for real workloads

### Business Value

- Catches integration issues that unit/func tests miss
- Validates real user workflows end-to-end
- Provides performance baselines for optimization
- Gives confidence for production deployments
- Reduces customer-reported bugs

---

## Critical Principle: NO MOCKING IN E2E TESTS

### E2E Tests Use REAL Services Only

**ALL services must be real:**

- ✅ Real AWS services (S3, Athena, IAM, STS)
- ✅ Real Quilt catalog/registry
- ✅ Real GraphQL endpoints
- ✅ Real Elasticsearch
- ✅ Real authentication (JWT, IAM credentials)
- ✅ Real network calls
- ✅ Real boto3 clients
- ✅ Real quilt3 library

**ZERO mocking allowed:**

- ❌ NO mock AWS services
- ❌ NO mock catalog API
- ❌ NO mock backends
- ❌ NO mock HTTP responses
- ❌ NO test doubles
- ❌ NO fake services

### Why This Matters

E2E tests validate that the **ACTUAL system works in PRODUCTION conditions**. Any mocking defeats the purpose and gives false confidence.

**Example from tabulator test:**

- Real `QuiltOpsFactory.create()` → real backend
- Real GraphQL mutations/queries → real registry
- Real Athena SQL queries → real AWS Athena
- Real JWT authentication → real token validation

---

## Goals

### Primary Goals

1. **Workflow Integration Tests:** Validate complete user workflows across multiple backends
2. **Cross-Backend Consistency:** Ensure same data accessed via different backends is consistent
3. **Error Handling Validation:** Test graceful degradation with REAL service failures
4. **Performance Baselines:** Establish acceptable performance for real workloads
5. **Authentication Flow Testing:** Validate auth propagation through workflow chains

### Secondary Goals

- Establish reusable workflow patterns for future tests
- Document common failure modes and recovery strategies
- Provide debugging tools for integration issues
- Create performance benchmarks for optimization targets

---

## Test Categories

### 1. Backend Integration Tests

**Purpose:** Validate backend components work together with REAL services

#### 1.1 Package Lifecycle Integration

**Test:** `test_package_lifecycle_integration()`

**Real Services Used:**

- Real S3 bucket operations (boto3)
- Real Quilt3 package operations (quilt3.Package)
- Real catalog API calls
- Real package registry

**Workflow:**

```python
# Step 1: Create package from real S3 objects
s3_uris = ["s3://real-bucket/data/file1.csv", "s3://real-bucket/data/file2.csv"]
result = backend.package_create(
    package_name="test/integration_lifecycle",
    s3_uris=s3_uris,
    registry="s3://real-bucket"
)
# Validates: Real S3 read, real package manifest creation, real registry push

# Step 2: Browse package via real catalog
browse = backend.package_browse(
    package_name="test/integration_lifecycle",
    registry="real-bucket"
)
# Validates: Real catalog fetch, real manifest parsing

# Step 3: Update package with additional real files
update = backend.package_update(
    package_name="test/integration_lifecycle",
    s3_uris=["s3://real-bucket/data/file3.csv"],
    registry="s3://real-bucket"
)
# Validates: Real version increment, real S3 operations

# Step 4: Diff between real versions
diff = backend.package_diff(
    package1_name="test/integration_lifecycle",
    package2_name="test/integration_lifecycle",
    package1_hash="latest",
    package2_hash="previous",
    registry="real-bucket"
)
# Validates: Real manifest comparison, real hash resolution

# Step 5: Delete from real registry
delete = backend.package_delete(
    package_name="test/integration_lifecycle",
    registry="s3://real-bucket"
)
# Validates: Real registry cleanup
```

**Assertions:**

- Package appears in real catalog after creation
- Browse returns actual file tree from real manifest
- Update increments version in real registry
- Diff shows actual file differences
- Delete removes from real catalog (verify with real search)
- All catalog URLs point to real accessible locations

**Cleanup:**

- Uses pytest finalizer to delete from real registry
- Cleans up real S3 objects if created

---

#### 1.2 Content Retrieval Pipeline

**Test:** `test_content_retrieval_pipeline()`

**Real Services Used:**

- Real S3 (list, head, get operations)
- Real presigned URL generation (boto3)
- Real catalog API

**Workflow:**

```python
# Step 1: List real bucket objects
objects = backend.bucket_objects_list(
    bucket="real-test-bucket",
    prefix="data/",
    max_keys=100
)
# Validates: Real S3 ListObjectsV2 API call

# Step 2: Get real object metadata
target_uri = objects['objects'][0]['s3_uri']
info = backend.bucket_object_info(s3_uri=target_uri)
# Validates: Real S3 HeadObject API call

# Step 3: Generate real presigned URL
link = backend.bucket_object_link(s3_uri=target_uri, expiration_seconds=300)
# Validates: Real boto3 generate_presigned_url

# Step 4: Fetch actual content
content = backend.bucket_object_text(s3_uri=target_uri, max_bytes=1000)
# Validates: Real S3 GetObject API call

# Step 5: Verify presigned URL works (real HTTP request)
import requests
response = requests.get(link['signed_url'])
assert response.status_code == 200
assert response.content == content['text'].encode()
```

**Assertions:**

- Object metadata matches real S3 metadata (size, ETag, last_modified)
- Presigned URL is valid and accessible via real HTTP
- Content integrity preserved (hash matches)
- Auth headers propagate correctly through real AWS calls

---

#### 1.3 Search-to-Access Integration

**Test:** `test_search_to_access_integration()`

**Real Services Used:**

- Real Elasticsearch backend
- Real catalog API
- Real S3 operations
- Real package registry

**Workflow:**

```python
# Step 1: Search real catalog via real Elasticsearch
results = backend.search_catalog(
    query="README.md",
    scope="file",
    limit=10
)
# Validates: Real Elasticsearch query, real index search

# Step 2: Extract S3 URIs from real results
s3_uris = [r['s3_uri'] for r in results['results'][:3]]

# Step 3: Fetch real object info for results
for uri in s3_uris:
    info = backend.bucket_object_info(s3_uri=uri)
    # Validates: Real S3 HeadObject for discovered files
    assert info['size'] > 0

# Step 4: Generate real catalog URLs
for result in results['results'][:3]:
    if result.get('package_name'):
        url = backend.catalog_url(
            registry=result['bucket'],
            package_name=result['package_name']
        )
        # Validates: Real catalog URL generation
        assert url['catalog_url'].startswith('https://')

# Step 5: Access real package context if available
if results['results'][0].get('package_name'):
    pkg = results['results'][0]['package_name']
    browse = backend.package_browse(
        package_name=pkg,
        registry=results['results'][0]['bucket']
    )
    # Validates: Real package manifest fetch
    assert browse['success']
```

**Assertions:**

- Search returns real indexed data
- All S3 URIs from search are valid and accessible
- Catalog URLs navigate to real catalog pages
- Package context loads from real registry
- No stale or phantom results from real index

---

#### 1.4 Tabulator-Athena Integration

**Test:** `test_tabulator_athena_consistency()`

**Real Services Used:**

- Real GraphQL API (Tabulator)
- Real AWS Athena
- Real Glue Data Catalog
- Real S3 (for Athena results)

**Workflow:**

```python
# Step 1: Query via real Tabulator backend
tabulator_result = backend.tabulator_query_execute(
    query="SELECT COUNT(*) as count FROM test_table LIMIT 10"
)
# Validates: Real GraphQL mutation, real Tabulator execution

# Step 2: Query same data via real Athena
athena_result = backend.athena_query_execute(
    query="SELECT COUNT(*) as count FROM test_table LIMIT 10",
    database="real-database"
)
# Validates: Real Athena StartQueryExecution, real Glue catalog

# Step 3: Compare real results
assert tabulator_result['row_count'] == athena_result['row_count']
assert tabulator_result['formatted_data'] == athena_result['formatted_data']
```

**Assertions:**

- Both backends return consistent data from real sources
- Schema interpretation matches across real systems
- Data types align in real results
- Row counts consistent from real queries
- Query execution succeeds on real infrastructure

---

### 2. Workflow End-to-End Tests

**Purpose:** Validate complete user workflows with REAL services only

#### 2.1 Data Discovery Workflow

**Test:** `test_data_discovery_workflow()`

**User Goal:** "Find all CSV files related to genomics experiments"

**Real Services Used:**

- Real Elasticsearch
- Real S3 permissions checking (real IAM)
- Real S3 operations
- Real catalog API

**Workflow:**

```python
# Step 1: Search real catalog
search = backend.search_catalog(
    query="genomics csv",
    scope="file",
    limit=50
)
# Real Elasticsearch query

# Step 2: Check real permissions on discovered buckets
unique_buckets = set(r['bucket'] for r in search['results'])
for bucket in unique_buckets:
    perms = backend.check_bucket_access(bucket=bucket)
    # Real IAM GetBucketPolicy, HeadBucket, etc.
    assert perms['access_summary']['can_read']

# Step 3: List real objects in discovered locations
for result in search['results'][:5]:
    if result.get('key'):
        objects = backend.bucket_objects_list(
            bucket=result['bucket'],
            prefix=result['key'].rsplit('/', 1)[0],
            max_keys=10
        )
        # Real S3 ListObjectsV2

# Step 4: Sample real content
sample_uris = [r['s3_uri'] for r in search['results'][:3]]
for uri in sample_uris:
    content = backend.bucket_object_text(
        s3_uri=uri,
        max_bytes=500
    )
    # Real S3 GetObject
    assert len(content['text']) > 0

# Step 5: Generate real catalog URLs for report
urls = []
for result in search['results'][:10]:
    if result.get('package_name'):
        url = backend.catalog_url(
            registry=result['bucket'],
            package_name=result['package_name'],
            path=result.get('logical_key', '')
        )
        urls.append(url['catalog_url'])
```

**Success Criteria:**

- All relevant files found from real index
- Real permissions correctly validated via IAM
- Content preview matches real file content
- Report includes real accessible catalog links
- No false positives from real data

---

#### 2.2 Package Creation from S3 Workflow

**Test:** `test_package_creation_from_s3_workflow()`

**User Goal:** "Create organized package from S3 bucket contents"

**Real Services Used:**

- Real S3 (all operations)
- Real IAM (permission checks)
- Real package registry
- Real catalog API

**Workflow:**

```python
# Step 1: Check real bucket access
access = backend.check_bucket_access(bucket="real-source-bucket")
# Real IAM checks
assert access['permission_level'] in ['full_access', 'read_write']

# Step 2: List real objects
objects = backend.bucket_objects_list(
    bucket="real-source-bucket",
    prefix="experiments/2026/",
    max_keys=1000
)
# Real S3 ListObjectsV2 (may need pagination)

# Step 3: Create real package with smart organization
package = backend.package_create_from_s3(
    source_bucket="s3://real-source-bucket",
    source_prefix="experiments/2026/",
    package_name="experiments/genomics_2026",
    registry="s3://real-package-bucket",
    auto_organize=True
)
# Real S3 reads, real manifest generation, real registry push

# Step 4: Verify in real catalog
browse = backend.package_browse(
    package_name="experiments/genomics_2026",
    registry="real-package-bucket"
)
# Real catalog API call
assert browse['success']
assert browse['total_entries'] == len(objects['objects'])

# Step 5: Generate real catalog URL
url = backend.catalog_url(
    registry="real-package-bucket",
    package_name="experiments/genomics_2026"
)
# Real URL should be accessible
import requests
response = requests.get(url['catalog_url'])
assert response.status_code == 200
```

**Success Criteria:**

- Package appears in real catalog
- All files correctly organized in real manifest
- Metadata complete and accurate in real registry
- Real catalog URL navigates to package
- Auto-organization matches real file structure

---

#### 2.3 Data Analysis Workflow

**Test:** `test_data_analysis_workflow()`

**User Goal:** "Query and visualize genomics data from multiple tables"

**Real Services Used:**

- Real Tabulator/Athena
- Real S3
- Real package registry

**Workflow:**

```python
# Step 1: List real databases
if backend_mode == 'platform':
    buckets = backend.tabulator_list_buckets()
    # Real GraphQL query
    database = buckets['buckets'][0]
else:
    databases = backend.athena_databases_list()
    # Real Athena/Glue call
    database = databases['databases'][0]

# Step 2: Query real table schema
schema = backend.athena_table_schema(
    database=database,
    table="genomics_samples"
)
# Real Glue GetTable API

# Step 3: Execute real analytical query
query_result = backend.athena_query_execute(
    query="""
        SELECT sample_id, COUNT(*) as read_count
        FROM genomics_samples
        GROUP BY sample_id
        LIMIT 100
    """,
    database=database
)
# Real Athena StartQueryExecution → GetQueryResults

# Step 4: Generate real visualization from results
viz = backend.create_data_visualization(
    data=query_result['formatted_data'],
    plot_type='bar',
    x_column='sample_id',
    y_column='read_count',
    title='Read Counts by Sample'
)
# Real matplotlib/ECharts generation

# Step 5: Create real package with visualization
viz_json = json.dumps(viz['config'])
# Upload to real S3, create real package
# (Implementation would use bucket_objects_put + package_create)
```

**Success Criteria:**

- Queries execute successfully on real data
- Results formatted correctly from real query output
- Visualizations match real data
- Dashboard package includes all assets in real manifest

---

### 3. Error Handling & Recovery Tests

**Purpose:** Validate graceful degradation with REAL service failures

#### 3.1 Permission Failures

**Test:** `test_permission_denied_scenarios()`

**Real Services Used:**

- Real IAM (actual permission checks)
- Real S3 with restricted permissions

**Scenarios:**

```python
# Scenario 1: Try to list real bucket without list permission
# Setup: Use real IAM user/role with restricted policy
try:
    result = backend.bucket_objects_list(
        bucket="real-restricted-bucket"
    )
    # Real S3 call should fail with AccessDenied
    assert False, "Should have raised error"
except Exception as e:
    assert "AccessDenied" in str(e) or "Forbidden" in str(e)
    # Error message should suggest real remediation

# Scenario 2: Try to write to real read-only bucket
try:
    result = backend.bucket_objects_put(
        bucket="real-readonly-bucket",
        items=[{"key": "test.txt", "text": "test"}]
    )
    # Real S3 PutObject should fail
    assert False, "Should have raised error"
except Exception as e:
    assert "AccessDenied" in str(e)

# Scenario 3: Check real permissions first (recommended pattern)
access = backend.check_bucket_access(bucket="real-test-bucket")
# Real IAM checks
if not access['access_summary']['can_write']:
    pytest.skip("Bucket not writable - expected for this test")
```

**Validation:**

- Real IAM errors caught correctly
- Clear error messages from real AWS
- Suggested remediation steps accurate
- No cascading failures in real operations
- Partial success handled (some buckets accessible, others not)

---

#### 3.2 Service Timeout Scenarios

**Test:** `test_service_timeout_handling()`

**Real Services Used:**

- Real Athena (can timeout on complex queries)
- Real Elasticsearch (can timeout on large searches)
- Real S3 (can timeout on large objects)

**Scenarios:**

```python
# Scenario 1: Athena query timeout (real long-running query)
try:
    result = backend.athena_query_execute(
        query="""
            SELECT * FROM large_table
            CROSS JOIN another_large_table
            WHERE complex_condition
        """,
        database="real-database",
        timeout_seconds=5  # Intentionally short
    )
    # May timeout on real Athena execution
except TimeoutError as e:
    assert "timeout" in str(e).lower()
    assert "retry" in str(e).lower()  # Should suggest retry

# Scenario 2: Large S3 object fetch timeout
try:
    result = backend.bucket_object_fetch(
        s3_uri="s3://real-bucket/large-file.bin",
        max_bytes=100_000_000,  # 100MB
        timeout_seconds=5  # Intentionally short
    )
    # Real S3 GetObject may timeout
except TimeoutError as e:
    assert "timeout" in str(e).lower()

# Scenario 3: Search timeout recovery
# Try real search with fallback to cache if available
result = backend.search_catalog(
    query="complex search term",
    scope="global",
    timeout_seconds=10
)
# Real Elasticsearch - may use cache if timeout
```

**Validation:**

- Real timeout errors handled gracefully
- Automatic retries with backoff for real operations
- Clear timeout messages from real services
- No data corruption on timeout from real operations

---

#### 3.3 Data Validation Failures

**Test:** `test_data_validation_errors()`

**Real Services Used:**

- Real S3 (for invalid inputs)
- Real package registry

**Scenarios:**

```python
# Scenario 1: Invalid package name (real validation)
try:
    result = backend.package_create(
        package_name="invalid/name/with/too/many/slashes",
        s3_uris=["s3://real-bucket/file.csv"],
        registry="s3://real-bucket"
    )
    assert False, "Should have raised error"
except ValueError as e:
    assert "package name" in str(e).lower()
    assert "format" in str(e).lower()  # Should explain format

# Scenario 2: Invalid S3 URI (real parsing)
try:
    result = backend.bucket_object_info(
        s3_uri="not-an-s3-uri"
    )
    assert False, "Should have raised error"
except ValueError as e:
    assert "s3://" in str(e)
    assert "uri" in str(e).lower()

# Scenario 3: Unsupported file type
result = backend.bucket_object_text(
    s3_uri="s3://real-bucket/binary-file.bin",
    max_bytes=1000
)
# Real operation - should handle binary gracefully
assert result.get('error') or result.get('text')
```

**Validation:**

- Early validation catches issues before real operations
- Helpful error messages with real examples
- Suggests correct format from real patterns
- Doesn't corrupt existing data in real registry

---

### 4. Performance & Scale Tests

**Purpose:** Establish baselines with REAL services under realistic load

#### 4.1 Large Result Sets

**Test:** `test_large_result_set_performance()`

**Real Services Used:**

- Real S3 with 10k+ objects
- Real Elasticsearch with large index
- Real Athena queries

**Scenarios:**

```python
import time

# Scenario 1: List bucket with 10k+ real objects
start = time.time()
result = backend.bucket_objects_list(
    bucket="real-large-bucket",
    max_keys=10000
)
duration = time.time() - start
# Real S3 ListObjectsV2 with pagination
assert duration < 30.0, f"Too slow: {duration}s"
assert result['count'] >= 1000

# Scenario 2: Search returning 1000+ real results
start = time.time()
result = backend.search_catalog(
    query="*",  # Broad search on real index
    limit=1000
)
duration = time.time() - start
# Real Elasticsearch query
assert duration < 5.0, f"Too slow: {duration}s"
assert result['total_results'] >= 100

# Scenario 3: Large Athena query (10k+ rows)
start = time.time()
result = backend.athena_query_execute(
    query="SELECT * FROM large_real_table LIMIT 10000",
    database="real-database"
)
duration = time.time() - start
# Real Athena execution
assert duration < 60.0, f"Too slow: {duration}s"
assert result['row_count'] >= 1000
```

**Performance Targets (from real operations):**

- List 10k objects: < 30s
- Search 1000 results: < 5s
- Query 10k rows: < 60s
- Package browse (deep tree): < 10s

---

#### 4.2 Concurrent Operations

**Test:** `test_concurrent_operations_performance()`

**Real Services Used:**

- Real S3 (parallel operations)
- Real catalog API (parallel requests)
- Real Athena (parallel queries)

**Scenarios:**

```python
import concurrent.futures
import time

# Scenario 1: Parallel real S3 operations
uris = [f"s3://real-bucket/data/file{i}.csv" for i in range(20)]

start = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    futures = [
        executor.submit(backend.bucket_object_info, s3_uri=uri)
        for uri in uris
    ]
    results = [f.result() for f in futures]
duration = time.time() - start
# Real concurrent S3 HeadObject calls
assert duration < 10.0, f"Too slow: {duration}s"
assert len(results) == 20

# Scenario 2: Parallel real search queries
queries = ["genomics", "experiments", "samples", "data", "results"]
start = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    futures = [
        executor.submit(backend.search_catalog, query=q, limit=10)
        for q in queries
    ]
    results = [f.result() for f in futures]
duration = time.time() - start
# Real concurrent Elasticsearch queries
assert duration < 5.0, f"Too slow: {duration}s"
assert len(results) == 5
```

**Validation:**

- No race conditions in real operations
- Connection pooling effective for real AWS calls
- Resource cleanup proper after real operations
- No deadlocks in real concurrent access

---

### 5. Data Consistency Tests

**Purpose:** Ensure data integrity across real backends

#### 5.1 Package Version Consistency

**Test:** `test_package_version_consistency()`

**Real Services Used:**

- Real package registry
- Real catalog API
- Real Elasticsearch
- Real S3

**Workflow:**

```python
# Create real package
pkg_name = "test/consistency_check"
result = backend.package_create(
    package_name=pkg_name,
    s3_uris=["s3://real-bucket/data/file1.csv"],
    registry="s3://real-bucket"
)
# Real package push to real registry

# Access via multiple real paths
# Path 1: Direct package browse
browse = backend.package_browse(
    package_name=pkg_name,
    registry="real-bucket"
)

# Path 2: Catalog URL
url = backend.catalog_url(
    registry="real-bucket",
    package_name=pkg_name
)
# Real catalog URL - verify it works
import requests
response = requests.get(url['catalog_url'])
assert response.status_code == 200

# Path 3: Search in real index
time.sleep(5)  # Allow real indexing to complete
search = backend.search_catalog(
    query=pkg_name,
    scope="package"
)

# Path 4: Via S3 URI
manifest_uri = f"s3://real-bucket/.quilt/packages/{result['top_hash']}"
manifest = backend.bucket_object_text(s3_uri=manifest_uri)

# Validate consistency across all real paths
assert browse['success']
assert search['total_results'] > 0
assert manifest['success']
# All paths should reference same real version/hash
```

**Assertions:**

- All paths return same version from real sources
- Hash verification consistent across real operations
- Metadata matches across real methods
- No stale cache hits from real systems

---

#### 5.2 Cross-Backend Consistency

**Test:** `test_cross_backend_consistency()`

**Real Services Used:**

- Real Athena (Glue catalog view)
- Real Tabulator (GraphQL view)
- Real Quilt3 (package view)
- Real S3 (source of truth)

**Workflow:**

```python
# Query same package data via different real backends
bucket = "real-test-bucket"
pkg_name = "test/multi_backend"

# Via real Athena (if package manifests indexed)
try:
    athena_result = backend.athena_query_execute(
        query=f"""
            SELECT logical_key, size
            FROM "{bucket}_packages"
            WHERE package_name = '{pkg_name}'
        """,
        database=f"{bucket}_catalog"
    )
    athena_files = {
        row['logical_key']: row['size']
        for row in athena_result['formatted_data']
    }
except:
    athena_files = {}

# Via real Quilt3 browse
browse_result = backend.package_browse(
    package_name=pkg_name,
    registry=bucket
)
browse_files = {
    entry['logical_key']: entry['size']
    for entry in browse_result['entries']
}

# Via real search
search_result = backend.search_catalog(
    query=pkg_name,
    scope="package"
)

# Validate consistency
if athena_files:
    assert athena_files == browse_files
assert browse_result['total_entries'] > 0
assert search_result['total_results'] > 0
```

**Assertions:**

- File lists match across real backends
- Metadata consistent from real sources
- Timestamps aligned in real data
- No discrepancies in counts from real queries

---

## Test Organization

### File Structure

```
tests/e2e/backend/
├── __init__.py
├── conftest.py                          # Shared E2E fixtures (NO MOCKS)
│
├── integration/
│   ├── __init__.py
│   ├── test_package_lifecycle.py        # Real package operations
│   ├── test_content_pipeline.py         # Real S3 → access pipeline
│   ├── test_search_to_access.py         # Real search → real access
│   └── test_tabulator_athena.py         # Real Tabulator vs Athena
│
├── workflows/
│   ├── __init__.py
│   ├── test_data_discovery.py           # Real discovery workflow
│   ├── test_package_creation.py         # Real package from S3
│   └── test_data_analysis.py            # Real query → viz workflow
│
├── error_handling/
│   ├── __init__.py
│   ├── test_permission_failures.py      # Real IAM errors
│   ├── test_service_timeouts.py         # Real timeout scenarios
│   └── test_validation_failures.py      # Real validation errors
│
├── performance/
│   ├── __init__.py
│   ├── test_large_results.py            # Real large result sets
│   ├── test_concurrent_ops.py           # Real parallel operations
│   └── test_complex_queries.py          # Real query performance
│
└── consistency/
    ├── __init__.py
    ├── test_package_versions.py         # Real version consistency
    └── test_cross_backend.py            # Real backend consistency
```

### Shared Fixtures (NO MOCKS)

```python
# tests/e2e/backend/conftest.py

import pytest
from quilt_mcp.ops.factory import QuiltOpsFactory

@pytest.fixture
def real_test_bucket():
    """Get REAL test bucket from environment.

    NO MOCKING - returns name of actual S3 bucket for testing.
    """
    import os
    bucket = os.getenv('QUILT_TEST_BUCKET')
    if not bucket:
        pytest.skip("QUILT_TEST_BUCKET not set - need real bucket")
    return bucket


@pytest.fixture
def real_backend(backend_mode):
    """Create REAL backend (quilt3 or platform).

    NO MOCKING - uses QuiltOpsFactory to create actual backend
    that talks to real AWS, real catalog, real registry.
    """
    backend = QuiltOpsFactory.create()

    # Verify REAL connectivity
    try:
        # Make a REAL call to verify it works
        backend.check_bucket_access(
            bucket=os.getenv('QUILT_TEST_BUCKET')
        )
    except Exception as e:
        pytest.skip(f"Cannot connect to REAL services: {e}")

    yield backend

    # Cleanup any REAL resources created during test
    # (handled by test-specific finalizers)


@pytest.fixture
def real_athena(real_backend):
    """Get REAL Athena service.

    NO MOCKING - returns actual AthenaQueryService that
    executes real queries on real AWS Athena.
    """
    from tests.conftest import athena_service_factory

    try:
        athena = athena_service_factory(use_quilt_auth=True)
        # Verify REAL Athena access
        athena.list_databases()
    except Exception as e:
        pytest.skip(f"Cannot access REAL Athena: {e}")

    return athena


@pytest.fixture
def real_test_data(real_test_bucket, real_backend):
    """Create REAL test data in REAL S3 bucket.

    NO MOCKING - actually uploads files to real S3 for testing.
    Cleans up afterward.
    """
    import uuid
    test_prefix = f"e2e_test_{uuid.uuid4().hex[:8]}/"

    # Upload REAL files to REAL S3
    real_backend.bucket_objects_put(
        bucket=real_test_bucket,
        items=[
            {"key": f"{test_prefix}file1.csv", "text": "col1,col2\n1,2\n"},
            {"key": f"{test_prefix}file2.csv", "text": "col1,col2\n3,4\n"},
            {"key": f"{test_prefix}README.md", "text": "# Test data\n"},
        ]
    )

    yield {
        "bucket": real_test_bucket,
        "prefix": test_prefix,
        "files": [f"{test_prefix}file1.csv", f"{test_prefix}file2.csv"]
    }

    # Cleanup REAL S3 objects
    import boto3
    s3 = boto3.client('s3')
    for key in [f"{test_prefix}file1.csv", f"{test_prefix}file2.csv", f"{test_prefix}README.md"]:
        try:
            s3.delete_object(Bucket=real_test_bucket, Key=key)
        except:
            pass
```

---

## Success Criteria

### Functional Requirements

- ✅ All integration tests pass with REAL services
- ✅ All workflow tests complete end-to-end with REAL data
- ✅ Error handling validated with REAL failures
- ✅ Performance targets met with REAL services
- ✅ Data consistency verified across REAL backends
- ✅ ZERO mocking - all tests use actual services

### Code Quality Requirements

- ✅ Tests follow pytest best practices
- ✅ Clear test names describing real scenarios
- ✅ Comprehensive docstrings
- ✅ Proper cleanup of real resources
- ✅ Reusable fixtures for real services

### Performance Requirements

- ✅ Integration tests complete in < 5min (real operations)
- ✅ Workflow tests complete in < 10min (real end-to-end)
- ✅ Performance tests establish realistic baselines
- ✅ Tests can run in parallel where real services allow

### Reliability Requirements

- ✅ Tests are idempotent with real services
- ✅ Cleanup happens even on failure (real resources)
- ✅ Clear error messages from real failures
- ✅ Tests skip gracefully if real services unavailable

---

## Execution Strategy

### Local Development

```bash
# Run integration tests with REAL backends
TEST_BACKEND_MODE=quilt3 pytest tests/e2e/backend/integration/ -v

# Run workflows with REAL services
pytest tests/e2e/backend/workflows/ -v

# Run performance tests (slower, uses REAL services)
pytest tests/e2e/backend/performance/ -v -m "not slow"

# Run ALL backend E2E tests (REAL end-to-end)
pytest tests/e2e/backend/ -v
```

### CI/CD

```bash
# Run on every PR (with REAL test infrastructure)
pytest tests/e2e/backend/integration/ -v --tb=short

# Run nightly (full suite with REAL services)
pytest tests/e2e/backend/ -v --tb=short --maxfail=5
```

---

## Dependencies

### Required Real Services

**Must be accessible for tests to run:**

- ✅ Real AWS account with S3, Athena, IAM, STS
- ✅ Real Quilt catalog (nightly.quilttest.com or production)
- ✅ Real Elasticsearch backend
- ✅ Real test bucket with read/write permissions
- ✅ Real credentials (IAM or JWT)

### Environment Variables

```bash
# Required for ALL E2E tests
QUILT_TEST_BUCKET=real-test-bucket-name

# For quilt3 backend (uses REAL ~/.quilt/config.yml)
TEST_BACKEND_MODE=quilt3

# For platform backend (uses REAL catalog/registry)
TEST_BACKEND_MODE=platform
PLATFORM_TEST_ENABLED=true
QUILT_CATALOG_URL=https://real-catalog.quiltdata.com
QUILT_REGISTRY_URL=https://real-registry.quiltdata.com
PLATFORM_TEST_JWT_SECRET=real-jwt-secret
```

---

## Anti-Patterns to Avoid

### ❌ NEVER Mock in E2E Tests

```python
# ❌ WRONG - This is NOT E2E testing
@pytest.fixture
def mock_s3():
    with mock.patch('boto3.client') as mock_client:
        yield mock_client

# ✅ CORRECT - Use REAL S3
@pytest.fixture
def real_s3():
    import boto3
    return boto3.client('s3')  # REAL boto3 client
```

### ❌ NEVER Fake Service Responses

```python
# ❌ WRONG - Fake responses defeat E2E purpose
def test_package_create(backend):
    backend._response = {"success": True}  # FAKE!
    result = backend.package_create(...)

# ✅ CORRECT - Use REAL backend that makes REAL calls
def test_package_create(real_backend, real_test_bucket):
    result = real_backend.package_create(
        package_name="test/real_package",
        s3_uris=[f"s3://{real_test_bucket}/real/file.csv"],
        registry=f"s3://{real_test_bucket}"
    )
    # Result comes from REAL registry operation
    assert result['success']
```

### ❌ NEVER Use Test Doubles

```python
# ❌ WRONG - Test doubles not allowed in E2E
class FakeCatalogAPI:
    def get_package(self, name):
        return {"fake": "data"}

# ✅ CORRECT - Use REAL catalog API
def test_catalog_access(real_backend):
    result = real_backend.package_browse(
        package_name="real/package",
        registry="real-bucket"
    )
    # Result comes from REAL catalog API call
```

---

## Related Specs

- `spec/a20-jwt-auth/01-e2e-tabulator-test.md` - Tabulator E2E test (REAL services)
- `scripts/tests/mcp-test.yaml` - Tool discovery tests (REAL tool calls)

---

## Sign-off

**Specification Status:** Ready for Review
**Critical Principle:** ZERO MOCKING - ALL REAL SERVICES
**Review Required:** Yes
**Implementation Start:** TBD
