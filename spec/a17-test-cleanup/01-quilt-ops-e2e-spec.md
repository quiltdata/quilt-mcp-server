# Comprehensive E2E Test Specification: QuiltOps API

**Version:** 1.0
**Date:** 2026-02-05
**Status:** Design Specification

## Executive Summary

This specification defines comprehensive end-to-end (e2e) tests for the **QuiltOps abstract API** that validate real-world functionality against live AWS infrastructure. Tests are **backend-agnostic**, verifying the QuiltOps interface contract rather than implementation details.

**Key Principles:**
- **Real AWS only** - No mocks, stubs, or simulated services
- **Backend agnostic** - Test the abstract interface, not Quilt3_Backend or Platform_Backend specifics
- **Workflow-focused** - Test complete user journeys, not just isolated methods
- **Reproducible** - Generate deterministic test data with versioned scripts
- **Observable** - Clear pass/fail criteria with diagnostic output

---

## 1. Scope & Objectives

### 1.1 API Surface Coverage

**Total Methods to Test: 50+**

| Component | Methods | Priority |
|-----------|---------|----------|
| QuiltOps Core | 27 | Critical |
| AdminOps | 19 | High |
| TabulatorMixin | 8 | High |
| Factory | 1 | Critical |

**Domain Objects: 9**
- Package_Info, Content_Info, Bucket_Info
- Auth_Status, Catalog_Config, Package_Creation_Result
- User, Role, SSOConfig

**Exception Types: 5**
- AuthenticationError, BackendError, ValidationError, NotFoundError, PermissionError

### 1.2 Testing Objectives

1. **Functional Correctness** - All methods return expected results for valid inputs
2. **Error Handling** - Proper exceptions raised with meaningful context
3. **Cross-Backend Consistency** - Both backends honor the same contract
4. **Authentication Workflows** - Local and multiuser modes work correctly
5. **Data Integrity** - Package creation/updates preserve content accurately
6. **Performance** - Operations complete within acceptable timeframes
7. **Concurrency** - Multiple simultaneous operations don't corrupt state
8. **AWS Integration** - Boto3 clients, S3 access, GraphQL work correctly

### 1.3 Out of Scope

- **Unit testing** - Already covered in `tests/unit/`
- **Backend implementation details** - Test interface, not internal logic
- **UI/UX testing** - MCP tools tested separately
- **Load/stress testing** - Performance validation is light (basic benchmarking only)

---

## 2. Test Infrastructure

### 2.1 AWS Test Environment

**Requirements:**
- **S3 Bucket(s):** Dedicated test buckets with known content
  - `quilt-mcp-test-data` - Immutable reference data (versioned datasets)
  - `quilt-mcp-test-scratch` - Ephemeral workspace (cleaned between test runs)
  - `quilt-mcp-test-packages` - Package registry storage
- **IAM Permissions:** Test role with read/write access to test buckets
- **Athena/Tabulator:** Database catalog for table operations
- **Quilt Catalog Instance:** Running catalog for Platform backend tests
  - With admin API enabled
  - With GraphQL endpoint accessible
  - With test users/roles configured

**Infrastructure as Code:**
- CloudFormation/Terraform templates for test environment
- Automated setup/teardown scripts
- Cost monitoring (auto-cleanup after 24h)

### 2.2 Authentication Strategy

**Dual-Mode Support:**

1. **Local Mode (Quilt3_Backend)**
   - Use quilt3 CLI session: `quilt3 login s3://quilt-mcp-test-packages`
   - Session stored in `~/.config/quilt/`
   - Tests check for valid local session before running

2. **Multiuser Mode (Platform_Backend)**
   - Use JWT token from catalog
   - Store token + GraphQL endpoint in `.env.test`
   - Tests check for valid JWT before running

**Environment Variables (.env.test):**
```bash
# Mode selection
QUILT_MULTIUSER_MODE=false  # or true

# Local mode
QUILT_TEST_REGISTRY_URL=s3://quilt-mcp-test-packages

# Multiuser mode
QUILT_TEST_CATALOG_URL=https://test-catalog.quiltdata.com
QUILT_TEST_JWT_TOKEN=eyJhbGc...
QUILT_TEST_GRAPHQL_ENDPOINT=https://api.test-catalog.quiltdata.com/graphql

# Shared
AWS_PROFILE=quilt-mcp-tests
AWS_REGION=us-east-1
QUILT_TEST_BUCKET_DATA=quilt-mcp-test-data
QUILT_TEST_BUCKET_SCRATCH=quilt-mcp-test-scratch
QUILT_TEST_BUCKET_PACKAGES=quilt-mcp-test-packages
```

### 2.3 Test Data Generation

**Approach:** Deterministic generation with versioned datasets

**Script:** `tests/e2e/fixtures/generate_test_data.py`

**Generated Datasets:**

| Dataset | Purpose | Size | Files |
|---------|---------|------|-------|
| `simple-csv` | Basic package operations | 1 MB | 5 CSV files |
| `nested-structure` | Directory hierarchy testing | 10 MB | 50 files (10 folders) |
| `large-package` | Performance validation | 500 MB | 100 files |
| `mixed-formats` | Content type handling | 50 MB | JSON, CSV, Parquet, images |
| `versioned-data` | Diff operations | 20 MB | 2 versions with changes |
| `metadata-rich` | Package metadata testing | 5 MB | 10 files with complex metadata |
| `empty-package` | Edge case handling | 0 bytes | 0 files (metadata only) |
| `single-file` | Minimal package | 100 KB | 1 CSV file |

**Script Requirements:**
- Idempotent (can run multiple times without side effects)
- Versioned (tracks data schema changes)
- Documented (README explaining each dataset)
- Validated (checksums for data integrity)

**Upload Strategy:**
```bash
# Generate data locally
uv run python tests/e2e/fixtures/generate_test_data.py

# Upload to S3 (immutable reference data)
aws s3 sync tests/e2e/fixtures/data/ s3://quilt-mcp-test-data/ --delete

# Create baseline packages
uv run python tests/e2e/fixtures/create_baseline_packages.py
```

### 2.4 Test Execution Framework

**Test Runner:** `pytest` with custom plugins

**Test Organization:**
```
tests/e2e/quilt_ops/
├── conftest.py                    # Shared fixtures, setup/teardown
├── test_01_authentication.py      # Auth flows (both modes)
├── test_02_package_discovery.py   # Search, list, browse
├── test_03_package_content.py     # Content access, download URLs
├── test_04_package_creation.py    # Create packages (all strategies)
├── test_05_package_updates.py     # Update existing packages
├── test_06_package_diff.py        # Version comparison
├── test_07_catalog_config.py      # Catalog operations
├── test_08_graphql_queries.py     # Direct GraphQL execution
├── test_09_aws_integration.py     # Boto3 clients, S3 access
├── test_10_admin_users.py         # User CRUD operations
├── test_11_admin_roles.py         # Role management
├── test_12_admin_sso.py           # SSO configuration
├── test_13_tabulator_tables.py    # Table operations
├── test_14_tabulator_queries.py   # Open query feature
├── test_15_error_handling.py      # Exception types, error context
├── test_16_concurrency.py         # Parallel operations
├── test_17_performance.py         # Timing benchmarks
└── test_18_end_to_end_workflows.py # Complete user journeys
```

**Fixture Strategy:**
- `quilt_ops` fixture: Factory-created QuiltOps instance (mode-aware)
- `admin_ops` fixture: AdminOps instance (requires admin permissions)
- `test_bucket_data` fixture: Path to immutable test data bucket
- `test_bucket_scratch` fixture: Path to ephemeral workspace (auto-cleanup)
- `test_registry` fixture: Path to package registry bucket
- `cleanup_packages` fixture: Auto-cleanup created packages after test

**Markers:**
```python
@pytest.mark.e2e             # All e2e tests
@pytest.mark.slow            # Tests >10s runtime
@pytest.mark.requires_admin  # Tests needing admin permissions
@pytest.mark.local_mode      # Tests only for Quilt3_Backend
@pytest.mark.multiuser_mode  # Tests only for Platform_Backend
@pytest.mark.backend_agnostic # Tests for both backends
```

### 2.5 CI/CD Integration

**GitHub Actions Workflow:**
- Trigger: Manual (on-demand), nightly scheduled
- Duration: 30-60 minutes for full suite
- Cost: ~$2-5 per run (AWS resources)
- Artifacts: Test reports, logs, coverage data

**Prerequisites Check:**
- AWS credentials valid
- Test environment accessible
- Authentication configured (local session or JWT)
- Test buckets exist and accessible
- Baseline packages present

**Failure Handling:**
- Slack notification on failures
- Detailed logs uploaded as artifacts
- Automatic cleanup on failure
- Cost alerts if resources not cleaned up

---

## 3. Test Scenarios

### 3.1 Authentication & Status (test_01_authentication.py)

**Objective:** Verify authentication works in both modes and status is correctly reported

#### Test: Local Mode Authentication
```
GIVEN: Valid quilt3 CLI session configured
WHEN: QuiltOps factory creates backend with multiuser_mode=False
THEN:
  - Backend is Quilt3_Backend instance
  - get_auth_status() returns is_authenticated=True
  - registry_url matches local session registry
  - catalog_name is None (local mode has no catalog)
```

#### Test: Multiuser Mode Authentication
```
GIVEN: Valid JWT token and GraphQL endpoint in config
WHEN: QuiltOps factory creates backend with multiuser_mode=True
THEN:
  - Backend is Platform_Backend instance
  - get_auth_status() returns is_authenticated=True
  - logged_in_url matches catalog URL
  - catalog_name is populated
  - registry_url matches GraphQL registry
```

#### Test: Missing Authentication (Local Mode)
```
GIVEN: No quilt3 CLI session configured
WHEN: QuiltOps factory attempts to create backend with multiuser_mode=False
THEN:
  - Raises AuthenticationError
  - Error context includes auth_method='local'
  - Error context includes remediation steps
```

#### Test: Missing Authentication (Multiuser Mode)
```
GIVEN: No JWT token in configuration
WHEN: QuiltOps factory attempts to create backend with multiuser_mode=True
THEN:
  - Raises AuthenticationError
  - Error context includes auth_method='jwt'
  - Error context includes remediation steps
```

#### Test: Expired JWT Token
```
GIVEN: Expired JWT token in configuration
WHEN: Platform backend makes first API call
THEN:
  - Raises AuthenticationError on first operation
  - Error message indicates token expired
  - Error context includes token expiration timestamp
```

#### Test: GraphQL Endpoint Headers
```
GIVEN: Authenticated backend (either mode)
WHEN: get_graphql_auth_headers() called
THEN:
  - Returns dict with Authorization header
  - Header format is valid (Bearer token or API key)
  - Headers work for direct GraphQL query
```

### 3.2 Package Discovery (test_02_package_discovery.py)

**Objective:** Verify package search, listing, and metadata retrieval

#### Test: Search Packages by Keyword
```
GIVEN: Registry with 10 known packages
WHEN: search_packages(query="test", registry=registry_url)
THEN:
  - Returns List[Package_Info] with expected packages
  - Each Package_Info has required fields populated
  - Results are sorted by relevance or modified_date
  - Search is case-insensitive
```

#### Test: Search with No Results
```
GIVEN: Registry with packages
WHEN: search_packages(query="nonexistent-xyz-123", registry=registry_url)
THEN:
  - Returns empty list []
  - Does not raise exception
```

#### Test: List All Packages
```
GIVEN: Registry with 10 known packages
WHEN: list_all_packages(registry=registry_url)
THEN:
  - Returns list of package names (strings)
  - Count matches expected baseline (10)
  - Names are fully qualified (user/package format)
```

#### Test: Get Package Info by Name
```
GIVEN: Known package "test-user/simple-csv" in registry
WHEN: get_package_info(package_name="test-user/simple-csv", registry=registry_url)
THEN:
  - Returns Package_Info with correct metadata
  - name = "test-user/simple-csv"
  - top_hash is valid SHA256 hash
  - modified_date is valid ISO 8601 datetime
  - registry matches input registry
  - bucket is correct S3 bucket name
  - description matches expected value
  - tags list matches expected tags
```

#### Test: Get Package Info - Not Found
```
GIVEN: Registry with packages
WHEN: get_package_info(package_name="nonexistent/package", registry=registry_url)
THEN:
  - Raises NotFoundError
  - Error context includes resource_type='package'
  - Error context includes identifier='nonexistent/package'
  - Error context includes search_location=registry_url
```

#### Test: Get Package Info - Invalid Name Format
```
GIVEN: Authenticated backend
WHEN: get_package_info(package_name="invalid-format", registry=registry_url)
THEN:
  - Raises ValidationError
  - Error context includes field_name='package_name'
  - Error context includes validation_rule (user/package format)
```

### 3.3 Package Content Access (test_03_package_content.py)

**Objective:** Verify browsing package contents and accessing download URLs

#### Test: Browse Root Directory
```
GIVEN: Package "test-user/nested-structure" with known file tree
WHEN: browse_content(package_name="test-user/nested-structure", registry=registry_url, path="")
THEN:
  - Returns List[Content_Info] with root-level items
  - Contains both files and directories
  - Each Content_Info has required fields
  - Directories have type='directory', size=None
  - Files have type='file', size=<bytes>
  - All items have valid modified_date
```

#### Test: Browse Subdirectory
```
GIVEN: Package "test-user/nested-structure" with folder "data/raw/"
WHEN: browse_content(package_name="test-user/nested-structure", registry=registry_url, path="data/raw/")
THEN:
  - Returns List[Content_Info] for items in "data/raw/" only
  - Does not include parent directory items
  - Paths are relative to package root
```

#### Test: Browse Non-Existent Path
```
GIVEN: Package "test-user/simple-csv"
WHEN: browse_content(package_name="test-user/simple-csv", registry=registry_url, path="nonexistent/")
THEN:
  - Raises NotFoundError
  - Error context includes resource_type='path'
  - Error context includes identifier='nonexistent/'
```

#### Test: Get Download URL for File
```
GIVEN: Package "test-user/simple-csv" with file "data.csv"
WHEN: get_content_url(package_name="test-user/simple-csv", registry=registry_url, path="data.csv")
THEN:
  - Returns presigned S3 URL (string)
  - URL is accessible (HTTP GET succeeds)
  - Downloaded content matches expected checksum
  - URL expires after configured time (typically 1 hour)
```

#### Test: Get Download URL for Directory
```
GIVEN: Package "test-user/nested-structure" with directory "data/"
WHEN: get_content_url(package_name="test-user/nested-structure", registry=registry_url, path="data/")
THEN:
  - Raises ValidationError (cannot download directories)
  - Error context indicates path must be a file
```

#### Test: Get Download URL - File Not Found
```
GIVEN: Package "test-user/simple-csv"
WHEN: get_content_url(package_name="test-user/simple-csv", registry=registry_url, path="missing.csv")
THEN:
  - Raises NotFoundError
  - Error context includes resource_type='file'
  - Error context includes identifier='missing.csv'
```

#### Test: Browse Large Package (Performance)
```
GIVEN: Package "test-user/large-package" with 100 files
WHEN: browse_content(package_name="test-user/large-package", registry=registry_url, path="")
THEN:
  - Returns all 100 Content_Info items
  - Completes within 5 seconds
  - Memory usage remains reasonable (<100 MB spike)
```

### 3.4 Package Creation (test_04_package_creation.py)

**Objective:** Verify creating new packages with various strategies

#### Test: Create Simple Package from S3 URIs
```
GIVEN: 5 CSV files in s3://quilt-mcp-test-data/simple-csv/
WHEN: create_package_revision(
    package_name="test-user/new-simple-csv",
    registry=registry_url,
    entries=[{"logical_key": "file1.csv", "physical_key": "s3://..."}],
    message="Initial commit"
  )
THEN:
  - Returns Package_Creation_Result with success=True
  - top_hash is valid SHA256 hash
  - file_count = 5
  - catalog_url is populated (if applicable)
  - Package is searchable via search_packages()
  - Package contents match input entries
```

#### Test: Create Package with Auto-Organize
```
GIVEN: Files with nested structure in S3
WHEN: create_package_revision(
    package_name="test-user/organized-package",
    registry=registry_url,
    entries=[...],
    auto_organize=True
  )
THEN:
  - Returns success=True
  - Package preserves original folder structure
  - browse_content() shows nested directories
```

#### Test: Create Package with Metadata
```
GIVEN: Files and package metadata (description, tags)
WHEN: create_package_revision(
    package_name="test-user/metadata-package",
    registry=registry_url,
    entries=[...],
    message="Test package",
    metadata={"description": "Test package", "tags": ["test", "e2e"]}
  )
THEN:
  - Returns success=True
  - get_package_info() returns Package_Info with metadata
  - description matches "Test package"
  - tags include "test" and "e2e"
```

#### Test: Create Package - Duplicate Name
```
GIVEN: Existing package "test-user/simple-csv"
WHEN: create_package_revision(package_name="test-user/simple-csv", ...)
THEN:
  - Raises ValidationError (package already exists)
  - Error message indicates use update_package_revision() instead
  - Original package is unchanged
```

#### Test: Create Empty Package (Metadata Only)
```
GIVEN: No files, only metadata
WHEN: create_package_revision(
    package_name="test-user/empty-package",
    registry=registry_url,
    entries=[],
    message="Empty package"
  )
THEN:
  - Returns success=True
  - file_count = 0
  - Package exists and is searchable
  - get_package_info() returns valid Package_Info
```

#### Test: Create Package with Invalid Entries
```
GIVEN: Entries with missing required fields
WHEN: create_package_revision(
    package_name="test-user/invalid",
    registry=registry_url,
    entries=[{"logical_key": "file.csv"}]  # Missing physical_key
  )
THEN:
  - Raises ValidationError
  - Error context includes field_name='physical_key'
  - No package is created
```

#### Test: Create Large Package (Performance)
```
GIVEN: 100 files (500 MB total) in S3
WHEN: create_package_revision(package_name="test-user/large", ...)
THEN:
  - Returns success=True
  - Completes within 60 seconds
  - Package is fully accessible afterward
```

### 3.5 Package Updates (test_05_package_updates.py)

**Objective:** Verify updating existing packages

#### Test: Update Package - Add Files
```
GIVEN: Existing package "test-user/simple-csv" with 5 files
WHEN: update_package_revision(
    package_name="test-user/simple-csv",
    registry=registry_url,
    entries=[<5 original files>, <2 new files>],
    message="Add 2 files"
  )
THEN:
  - Returns Package_Creation_Result with success=True
  - top_hash is different from original
  - file_count = 7
  - browse_content() shows all 7 files
  - Original package is preserved (old top_hash still accessible)
```

#### Test: Update Package - Remove Files
```
GIVEN: Existing package "test-user/simple-csv" with 5 files
WHEN: update_package_revision(
    package_name="test-user/simple-csv",
    registry=registry_url,
    entries=[<3 files only>],
    message="Remove 2 files"
  )
THEN:
  - Returns success=True
  - file_count = 3
  - browse_content() shows only 3 files
  - Removed files not accessible in new version
```

#### Test: Update Package - Modify File Content
```
GIVEN: Existing package with file "data.csv"
WHEN: update_package_revision(
    package_name="test-user/simple-csv",
    registry=registry_url,
    entries=[{"logical_key": "data.csv", "physical_key": "s3://.../data_v2.csv"}],
    message="Update data.csv"
  )
THEN:
  - Returns success=True
  - get_content_url("data.csv") returns URL for new content
  - Downloaded content matches data_v2.csv checksum
```

#### Test: Update Package - Merge Metadata
```
GIVEN: Existing package with metadata {"tags": ["test"]}
WHEN: update_package_revision(
    ...,
    metadata={"tags": ["test", "updated"], "description": "New description"}
  )
THEN:
  - get_package_info() returns Package_Info with merged metadata
  - tags = ["test", "updated"]
  - description = "New description"
```

#### Test: Update Non-Existent Package
```
GIVEN: No package "test-user/nonexistent"
WHEN: update_package_revision(package_name="test-user/nonexistent", ...)
THEN:
  - Raises NotFoundError
  - Error message indicates package doesn't exist
  - Suggests using create_package_revision() instead
```

### 3.6 Package Diff (test_06_package_diff.py)

**Objective:** Verify comparing package versions

#### Test: Diff Two Package Versions
```
GIVEN: Two versions of "test-user/versioned-data" (hash1, hash2)
WHEN: diff_packages(
    package1_name="test-user/versioned-data",
    package2_name="test-user/versioned-data",
    registry=registry_url,
    package1_hash=hash1,
    package2_hash=hash2
  )
THEN:
  - Returns Dict[str, List[str]] with keys: "added", "removed", "modified"
  - "added" lists files in hash2 not in hash1
  - "removed" lists files in hash1 not in hash2
  - "modified" lists files with different checksums
```

#### Test: Diff Two Different Packages
```
GIVEN: Two different packages "test-user/package-a" and "test-user/package-b"
WHEN: diff_packages(
    package1_name="test-user/package-a",
    package2_name="test-user/package-b",
    registry=registry_url
  )
THEN:
  - Returns diff showing differences between packages
  - Works even though packages are unrelated
```

#### Test: Diff Package with Itself
```
GIVEN: Package "test-user/simple-csv" (current version)
WHEN: diff_packages(
    package1_name="test-user/simple-csv",
    package2_name="test-user/simple-csv",
    registry=registry_url
  )
THEN:
  - Returns empty diff (no changes)
  - "added", "removed", "modified" are all empty lists
```

#### Test: Diff with Invalid Hash
```
GIVEN: Package "test-user/simple-csv"
WHEN: diff_packages(
    package1_name="test-user/simple-csv",
    package2_name="test-user/simple-csv",
    registry=registry_url,
    package1_hash="invalid-hash-123"
  )
THEN:
  - Raises ValidationError or NotFoundError
  - Error indicates hash is invalid or not found
```

### 3.7 Catalog Configuration (test_07_catalog_config.py)

**Objective:** Verify catalog configuration operations

#### Test: Get Catalog Config
```
GIVEN: Catalog URL "https://test-catalog.quiltdata.com"
WHEN: get_catalog_config(catalog_url="https://test-catalog.quiltdata.com")
THEN:
  - Returns Catalog_Config with all fields populated
  - region is valid AWS region
  - api_gateway_endpoint is valid URL
  - registry_url is valid S3 URL
  - analytics_bucket exists
  - stack_prefix is non-empty
  - tabulator_data_catalog is valid Athena catalog name
```

#### Test: Configure Default Catalog
```
GIVEN: Catalog URL "https://test-catalog.quiltdata.com"
WHEN: configure_catalog(catalog_url="https://test-catalog.quiltdata.com")
THEN:
  - Operation succeeds (no exception)
  - get_registry_url() returns registry for this catalog
  - Subsequent operations use this catalog by default
```

#### Test: Get Registry URL
```
GIVEN: Configured catalog
WHEN: get_registry_url()
THEN:
  - Returns S3 URL (s3://bucket-name format)
  - URL is accessible for package operations
```

#### Test: Get Catalog Config - Invalid URL
```
GIVEN: Invalid catalog URL "https://invalid-catalog-xyz.com"
WHEN: get_catalog_config(catalog_url="https://invalid-catalog-xyz.com")
THEN:
  - Raises BackendError or NotFoundError
  - Error indicates catalog is unreachable or doesn't exist
```

### 3.8 GraphQL Queries (test_08_graphql_queries.py)

**Objective:** Verify direct GraphQL query execution

#### Test: Execute Simple Query
```
GIVEN: Authenticated backend
WHEN: execute_graphql_query(
    query="{ packages { name } }",
    variables=None,
    registry=None
  )
THEN:
  - Returns Dict[str, Any] with query results
  - Contains "data" key with packages list
  - No "errors" key present
```

#### Test: Execute Query with Variables
```
GIVEN: Authenticated backend
WHEN: execute_graphql_query(
    query="query GetPackage($name: String!) { package(name: $name) { name description } }",
    variables={"name": "test-user/simple-csv"},
    registry=registry_url
  )
THEN:
  - Returns Dict with package data
  - package.name = "test-user/simple-csv"
  - package.description matches expected value
```

#### Test: Execute Invalid Query
```
GIVEN: Authenticated backend
WHEN: execute_graphql_query(
    query="{ invalid_field { bad_query } }",
    variables=None,
    registry=None
  )
THEN:
  - Returns Dict with "errors" key
  - Does not raise exception
  - Error message indicates invalid field
```

#### Test: Execute Query - Unauthenticated
```
GIVEN: Backend without valid authentication
WHEN: execute_graphql_query(query="{ packages { name } }", ...)
THEN:
  - Raises AuthenticationError
  - Error context indicates missing or invalid credentials
```

#### Test: Execute Query with Timeout
```
GIVEN: Authenticated backend
WHEN: execute_graphql_query(query=<complex expensive query>, ...)
THEN:
  - Either completes within reasonable time (30s)
  - Or raises BackendError with timeout indication
```

### 3.9 AWS Integration (test_09_aws_integration.py)

**Objective:** Verify boto3 client provisioning and S3 access

#### Test: Get Boto3 S3 Client
```
GIVEN: Authenticated backend
WHEN: get_boto3_client(service_name="s3")
THEN:
  - Returns boto3 S3 client object
  - Client is authenticated (can list buckets)
  - Client uses correct AWS region
```

#### Test: Get Boto3 Client - Custom Region
```
GIVEN: Authenticated backend
WHEN: get_boto3_client(service_name="s3", region="us-west-2")
THEN:
  - Returns S3 client configured for us-west-2
  - Client can access us-west-2 resources
```

#### Test: Get Boto3 Client - Multiple Services
```
GIVEN: Authenticated backend
WHEN:
  - s3_client = get_boto3_client("s3")
  - athena_client = get_boto3_client("athena")
  - sts_client = get_boto3_client("sts")
THEN:
  - All clients are valid and authenticated
  - Clients are independent instances
```

#### Test: Boto3 Client - S3 List Operation
```
GIVEN: S3 client from get_boto3_client("s3")
WHEN: client.list_objects_v2(Bucket="quilt-mcp-test-data")
THEN:
  - Returns dict with Contents list
  - Can access test bucket successfully
```

#### Test: Boto3 Client - S3 Get Object
```
GIVEN: S3 client and known file "s3://quilt-mcp-test-data/simple-csv/data.csv"
WHEN: client.get_object(Bucket="quilt-mcp-test-data", Key="simple-csv/data.csv")
THEN:
  - Returns object with Body stream
  - Content matches expected checksum
```

#### Test: Get Boto3 Client - Invalid Service
```
GIVEN: Authenticated backend
WHEN: get_boto3_client(service_name="invalid-service-xyz")
THEN:
  - Raises ValidationError or BackendError
  - Error indicates invalid service name
```

### 3.10 Admin: User Management (test_10_admin_users.py)

**Objective:** Verify user CRUD operations (requires admin permissions)

#### Test: List All Users
```
GIVEN: Catalog with known users
WHEN: admin_ops.list_users()
THEN:
  - Returns List[User] with all users
  - Each User has required fields populated
  - List includes admin and non-admin users
```

#### Test: Get User by Name
```
GIVEN: Existing user "testuser"
WHEN: admin_ops.get_user(name="testuser")
THEN:
  - Returns User object with correct details
  - name = "testuser"
  - email is populated
  - is_active, is_admin, is_sso_only, is_service are booleans
  - role is populated (if user has role)
```

#### Test: Create New User
```
GIVEN: Admin permissions
WHEN: admin_ops.create_user(
    name="new-test-user",
    email="newuser@test.com",
    role="user"
  )
THEN:
  - Returns User object with created user details
  - get_user("new-test-user") succeeds
  - User is active by default
  - User has assigned role
```

#### Test: Create User - Duplicate Name
```
GIVEN: Existing user "testuser"
WHEN: admin_ops.create_user(name="testuser", email="test@test.com", role="user")
THEN:
  - Raises ValidationError (user already exists)
  - Original user is unchanged
```

#### Test: Update User Email
```
GIVEN: Existing user "testuser" with email "old@test.com"
WHEN: admin_ops.set_user_email(name="testuser", email="new@test.com")
THEN:
  - Returns updated User with email="new@test.com"
  - get_user("testuser").email = "new@test.com"
```

#### Test: Grant Admin Privileges
```
GIVEN: Non-admin user "testuser"
WHEN: admin_ops.set_user_admin(name="testuser", admin=True)
THEN:
  - Returns updated User with is_admin=True
  - User can access admin operations
```

#### Test: Revoke Admin Privileges
```
GIVEN: Admin user "testuser"
WHEN: admin_ops.set_user_admin(name="testuser", admin=False)
THEN:
  - Returns updated User with is_admin=False
  - User cannot access admin operations
```

#### Test: Deactivate User
```
GIVEN: Active user "testuser"
WHEN: admin_ops.set_user_active(name="testuser", active=False)
THEN:
  - Returns updated User with is_active=False
  - User cannot authenticate
```

#### Test: Reactivate User
```
GIVEN: Inactive user "testuser"
WHEN: admin_ops.set_user_active(name="testuser", active=True)
THEN:
  - Returns updated User with is_active=True
  - User can authenticate
```

#### Test: Reset User Password
```
GIVEN: Existing user "testuser"
WHEN: admin_ops.reset_user_password(name="testuser")
THEN:
  - Operation succeeds (no exception)
  - User receives password reset notification
```

#### Test: Delete User
```
GIVEN: Existing user "testuser"
WHEN: admin_ops.delete_user(name="testuser")
THEN:
  - Operation succeeds
  - get_user("testuser") raises NotFoundError
  - User is removed from list_users()
```

#### Test: Delete Non-Existent User
```
GIVEN: No user "nonexistent"
WHEN: admin_ops.delete_user(name="nonexistent")
THEN:
  - Raises NotFoundError
  - Error context includes resource_type='user'
```

### 3.11 Admin: Role Management (test_11_admin_roles.py)

**Objective:** Verify role operations

#### Test: List All Roles
```
GIVEN: Catalog with configured roles
WHEN: admin_ops.list_roles()
THEN:
  - Returns List[Role] with all available roles
  - Each Role has name, type fields
  - List includes built-in roles (e.g., "user", "admin")
```

#### Test: Set User Primary Role
```
GIVEN: User "testuser" with role="user"
WHEN: admin_ops.set_user_role(name="testuser", role="power-user")
THEN:
  - Returns updated User
  - get_user("testuser").role.name = "power-user"
```

#### Test: Add Extra Roles to User
```
GIVEN: User "testuser" with role="user"
WHEN: admin_ops.add_user_roles(name="testuser", roles=["analyst", "viewer"])
THEN:
  - Returns updated User
  - extra_roles includes "analyst" and "viewer"
```

#### Test: Remove Extra Roles
```
GIVEN: User "testuser" with extra_roles=["analyst", "viewer"]
WHEN: admin_ops.remove_user_roles(name="testuser", roles=["analyst"])
THEN:
  - Returns updated User
  - extra_roles = ["viewer"] (analyst removed)
```

#### Test: Remove Role with Fallback
```
GIVEN: User "testuser" with only role="user" (no extra roles)
WHEN: admin_ops.remove_user_roles(name="testuser", roles=["user"], fallback="viewer")
THEN:
  - Returns updated User
  - role.name = "viewer" (fallback assigned)
```

#### Test: Set User Role with Append
```
GIVEN: User "testuser" with extra_roles=["viewer"]
WHEN: admin_ops.set_user_role(
    name="testuser",
    role="analyst",
    extra_roles=["editor"],
    append=True
  )
THEN:
  - Returns updated User
  - role.name = "analyst"
  - extra_roles includes both "viewer" (original) and "editor" (new)
```

### 3.12 Admin: SSO Configuration (test_12_admin_sso.py)

**Objective:** Verify SSO configuration management

#### Test: Get SSO Config
```
GIVEN: Catalog with SSO configured
WHEN: admin_ops.get_sso_config()
THEN:
  - Returns SSOConfig object
  - config field contains YAML/JSON configuration
  - Configuration is parseable
```

#### Test: Get SSO Config - Not Configured
```
GIVEN: Catalog without SSO configured
WHEN: admin_ops.get_sso_config()
THEN:
  - Returns None
  - Does not raise exception
```

#### Test: Set SSO Config
```
GIVEN: Valid SSO configuration YAML
WHEN: admin_ops.set_sso_config(config=<yaml_string>)
THEN:
  - Returns SSOConfig object
  - get_sso_config() returns same configuration
  - SSO authentication works with new config
```

#### Test: Set SSO Config - Invalid YAML
```
GIVEN: Invalid YAML string
WHEN: admin_ops.set_sso_config(config="invalid: yaml: syntax:")
THEN:
  - Raises ValidationError
  - Error indicates YAML parsing failure
  - Original config is unchanged
```

#### Test: Remove SSO Config
```
GIVEN: Catalog with SSO configured
WHEN: admin_ops.remove_sso_config()
THEN:
  - Operation succeeds
  - get_sso_config() returns None
  - SSO authentication no longer works
```

### 3.13 Tabulator: Table Operations (test_13_tabulator_tables.py)

**Objective:** Verify Tabulator table management

#### Test: List Tables in Bucket
```
GIVEN: Bucket with 3 Tabulator tables
WHEN: list_tabulator_tables(bucket="quilt-mcp-test-data")
THEN:
  - Returns List[Dict] with 3 table configs
  - Each dict has "name", "config" keys
  - Configs are valid YAML strings
```

#### Test: List Tables - Empty Bucket
```
GIVEN: Bucket with no Tabulator tables
WHEN: list_tabulator_tables(bucket="quilt-mcp-test-scratch")
THEN:
  - Returns empty list []
  - Does not raise exception
```

#### Test: Get Table by Name
```
GIVEN: Bucket with table "test-table"
WHEN: get_tabulator_table(bucket="quilt-mcp-test-data", table_name="test-table")
THEN:
  - Returns Dict with "name" and "config"
  - name = "test-table"
  - config is valid YAML
```

#### Test: Get Table - Not Found
```
GIVEN: Bucket with tables
WHEN: get_tabulator_table(bucket="quilt-mcp-test-data", table_name="nonexistent")
THEN:
  - Raises NotFoundError
  - Error context includes resource_type='table'
```

#### Test: Create Table
```
GIVEN: Bucket "quilt-mcp-test-scratch" without table "new-table"
WHEN: create_tabulator_table(
    bucket="quilt-mcp-test-scratch",
    table_name="new-table",
    config=<valid_yaml_config>
  )
THEN:
  - Returns Dict with creation result
  - get_tabulator_table("new-table") succeeds
  - Table is listed in list_tabulator_tables()
```

#### Test: Create Table - Invalid Config
```
GIVEN: Bucket
WHEN: create_tabulator_table(
    bucket="quilt-mcp-test-scratch",
    table_name="invalid-table",
    config="invalid: yaml: syntax:"
  )
THEN:
  - Raises ValidationError
  - Error indicates config is invalid
  - No table is created
```

#### Test: Update Table Config
```
GIVEN: Existing table "test-table" with config1
WHEN: update_tabulator_table(
    bucket="quilt-mcp-test-data",
    table_name="test-table",
    config=config2
  )
THEN:
  - Returns Dict with update result
  - get_tabulator_table("test-table").config = config2
```

#### Test: Rename Table
```
GIVEN: Existing table "old-name"
WHEN: rename_tabulator_table(
    bucket="quilt-mcp-test-data",
    old_name="old-name",
    new_name="new-name"
  )
THEN:
  - Returns Dict with rename result
  - get_tabulator_table("new-name") succeeds
  - get_tabulator_table("old-name") raises NotFoundError
```

#### Test: Rename Table - Name Conflict
```
GIVEN: Existing tables "table-a" and "table-b"
WHEN: rename_tabulator_table(
    bucket="quilt-mcp-test-data",
    old_name="table-a",
    new_name="table-b"
  )
THEN:
  - Raises ValidationError (name already exists)
  - Original table "table-a" is unchanged
```

#### Test: Delete Table
```
GIVEN: Existing table "test-table"
WHEN: delete_tabulator_table(bucket="quilt-mcp-test-data", table_name="test-table")
THEN:
  - Returns Dict with deletion result
  - get_tabulator_table("test-table") raises NotFoundError
  - Table not in list_tabulator_tables()
```

#### Test: Delete Table - Not Found
```
GIVEN: Bucket with tables
WHEN: delete_tabulator_table(bucket="quilt-mcp-test-data", table_name="nonexistent")
THEN:
  - Raises NotFoundError
  - Other tables are unchanged
```

### 3.14 Tabulator: Open Query (test_14_tabulator_queries.py)

**Objective:** Verify open query feature management

#### Test: Get Open Query Status
```
GIVEN: Catalog with open query configured
WHEN: get_open_query_status()
THEN:
  - Returns Dict with status information
  - Contains "enabled" boolean key
  - May include additional metadata
```

#### Test: Enable Open Query
```
GIVEN: Open query currently disabled
WHEN: set_open_query(enabled=True)
THEN:
  - Returns Dict with updated status
  - get_open_query_status()["enabled"] = True
  - Users can execute open queries
```

#### Test: Disable Open Query
```
GIVEN: Open query currently enabled
WHEN: set_open_query(enabled=False)
THEN:
  - Returns Dict with updated status
  - get_open_query_status()["enabled"] = False
  - Open queries are restricted
```

#### Test: Set Open Query - Idempotent
```
GIVEN: Open query already enabled
WHEN: set_open_query(enabled=True)
THEN:
  - Succeeds without error
  - Status remains enabled
```

### 3.15 Error Handling (test_15_error_handling.py)

**Objective:** Verify exception types and error context

#### Test: AuthenticationError - Context Fields
```
GIVEN: Backend with no authentication
WHEN: Any operation attempted
THEN:
  - Raises AuthenticationError
  - Exception has context dict
  - context["auth_method"] is populated
  - context["remediation"] provides guidance
```

#### Test: BackendError - Context Fields
```
GIVEN: Backend with simulated API failure
WHEN: Operation attempted
THEN:
  - Raises BackendError
  - context["backend_type"] is "quilt3" or "platform"
  - context["operation"] identifies failed method
  - context["original_exception"] preserved (if applicable)
```

#### Test: ValidationError - Context Fields
```
GIVEN: Invalid input (e.g., malformed package name)
WHEN: Operation with invalid input
THEN:
  - Raises ValidationError
  - context["field_name"] identifies invalid field
  - context["field_value"] shows provided value
  - context["validation_rule"] explains requirement
```

#### Test: NotFoundError - Context Fields
```
GIVEN: Request for non-existent resource
WHEN: get_package_info("nonexistent/package")
THEN:
  - Raises NotFoundError
  - context["resource_type"] = "package"
  - context["identifier"] = "nonexistent/package"
  - context["search_location"] indicates registry
```

#### Test: PermissionError - Context Fields
```
GIVEN: User without admin permissions
WHEN: admin_ops.create_user(...)
THEN:
  - Raises PermissionError
  - context["required_permissions"] lists needed perms
  - context["user_role"] shows current role
  - context["access_level"] shows current level
```

#### Test: Exception Message Clarity
```
GIVEN: Any QuiltOps exception
WHEN: Exception raised
THEN:
  - str(exception) is human-readable
  - Message includes actionable guidance
  - Technical details in context, not message
```

### 3.16 Concurrency (test_16_concurrency.py)

**Objective:** Verify thread-safety of parallel operations

#### Test: Concurrent Package Reads
```
GIVEN: 5 different packages in registry
WHEN: 10 threads simultaneously call get_package_info() for different packages
THEN:
  - All threads succeed
  - No data corruption or mixed results
  - All returned Package_Info objects are correct
```

#### Test: Concurrent Package Creates
```
GIVEN: 5 unique package names
WHEN: 5 threads simultaneously create different packages
THEN:
  - All 5 packages created successfully
  - No name conflicts or data corruption
  - All packages are searchable afterward
```

#### Test: Concurrent Browse Operations
```
GIVEN: Single package "test-user/large-package"
WHEN: 10 threads simultaneously browse different paths
THEN:
  - All browse operations succeed
  - No data corruption
  - Results are consistent across threads
```

#### Test: Concurrent Admin Operations
```
GIVEN: Admin permissions
WHEN: 3 threads simultaneously:
  - Thread 1: create_user("user-a")
  - Thread 2: create_user("user-b")
  - Thread 3: list_users()
THEN:
  - All operations succeed
  - Both users are created
  - list_users() includes both users
```

#### Test: Concurrent Table Operations
```
GIVEN: Bucket with Tabulator enabled
WHEN: 3 threads simultaneously:
  - Thread 1: create_tabulator_table("table-a")
  - Thread 2: create_tabulator_table("table-b")
  - Thread 3: list_tabulator_tables()
THEN:
  - All operations succeed
  - Both tables are created
  - list_tabulator_tables() includes both
```

#### Test: Concurrent Mixed Operations
```
GIVEN: Authenticated backend
WHEN: 10 threads perform random operations:
  - Package searches
  - Content browsing
  - GraphQL queries
  - Table listing
THEN:
  - All operations succeed
  - No deadlocks or race conditions
  - Results are consistent
```

### 3.17 Performance (test_17_performance.py)

**Objective:** Basic performance benchmarking

#### Test: Search Performance
```
GIVEN: Registry with 100 packages
WHEN: search_packages(query="test")
THEN:
  - Completes within 5 seconds
  - Memory usage < 100 MB
```

#### Test: List All Packages Performance
```
GIVEN: Registry with 100 packages
WHEN: list_all_packages()
THEN:
  - Completes within 10 seconds
  - Returns all 100 package names
```

#### Test: Browse Large Package Performance
```
GIVEN: Package with 1,000 files
WHEN: browse_content(path="")
THEN:
  - Completes within 10 seconds
  - Memory usage < 200 MB
```

#### Test: Create Large Package Performance
```
GIVEN: 100 files (500 MB total)
WHEN: create_package_revision(...)
THEN:
  - Completes within 120 seconds
  - Memory usage < 500 MB
```

#### Test: GraphQL Query Performance
```
GIVEN: Complex GraphQL query (nested data)
WHEN: execute_graphql_query(query=<complex>, ...)
THEN:
  - Completes within 30 seconds
  - Returns valid results
```

#### Test: Concurrent Operations Performance
```
GIVEN: 10 threads performing operations
WHEN: All threads execute simultaneously
THEN:
  - Total time < 2x single-threaded time
  - No performance degradation from concurrency
```

### 3.18 End-to-End Workflows (test_18_end_to_end_workflows.py)

**Objective:** Test complete user journeys from start to finish

#### Workflow: Data Scientist - Create and Share Package
```
GIVEN: Data scientist with data in S3
WHEN:
  1. Authenticate (local or multiuser mode)
  2. Search for existing related packages
  3. Create new package from S3 data
  4. Add metadata (description, tags)
  5. Verify package is searchable
  6. Browse package contents
  7. Get download URL for a file
  8. Download and verify file content
THEN:
  - All steps succeed
  - Package is accessible to other users
  - Metadata is preserved
  - Files are accessible
```

#### Workflow: Collaborator - Update Shared Package
```
GIVEN: Existing package created by colleague
WHEN:
  1. Authenticate
  2. Search for package by name
  3. Browse current contents
  4. Update package with new data files
  5. Compare versions with diff
  6. Verify new version is accessible
THEN:
  - All steps succeed
  - Both versions are preserved
  - Diff shows correct changes
```

#### Workflow: Admin - User Onboarding
```
GIVEN: Admin permissions
WHEN:
  1. Create new user account
  2. Set user email
  3. Assign role
  4. Add extra roles
  5. Verify user in list_users()
  6. Test user can authenticate (if possible)
THEN:
  - All steps succeed
  - User is fully configured
  - User has correct permissions
```

#### Workflow: Analyst - Tabulator Setup
```
GIVEN: Bucket with tabular data
WHEN:
  1. Authenticate
  2. List existing tables
  3. Create new table with config
  4. Rename table
  5. Update table config
  6. Enable open query
  7. Verify table is queryable
THEN:
  - All steps succeed
  - Table is configured correctly
  - Open query works
```

#### Workflow: Developer - Cross-Backend Validation
```
GIVEN: Both local and multiuser mode configured
WHEN:
  1. Create package in local mode
  2. Switch to multiuser mode
  3. Search for same package
  4. Verify metadata matches
  5. Browse contents in both modes
  6. Verify download URLs work
THEN:
  - Package accessible in both modes
  - Data is consistent
  - No discrepancies
```

---

## 4. Test Data Requirements

### 4.1 Baseline Packages

**Generated by:** `tests/e2e/fixtures/create_baseline_packages.py`

| Package Name | Description | Files | Size | Purpose |
|--------------|-------------|-------|------|---------|
| `test-user/simple-csv` | 5 CSV files | 5 | 1 MB | Basic operations |
| `test-user/nested-structure` | Nested folders | 50 | 10 MB | Directory browsing |
| `test-user/large-package` | Performance testing | 100 | 500 MB | Performance validation |
| `test-user/mixed-formats` | Multiple formats | 20 | 50 MB | Content type handling |
| `test-user/versioned-data-v1` | Version 1 | 10 | 10 MB | Diff operations |
| `test-user/versioned-data-v2` | Version 2 (updated) | 12 | 12 MB | Diff operations |
| `test-user/metadata-rich` | Complex metadata | 10 | 5 MB | Metadata testing |
| `test-user/empty-package` | Metadata only | 0 | 0 | Edge cases |
| `test-user/single-file` | Minimal package | 1 | 100 KB | Edge cases |

### 4.2 Test Bucket Structure

**quilt-mcp-test-data/** (Immutable reference data)
```
quilt-mcp-test-data/
├── simple-csv/
│   ├── data1.csv
│   ├── data2.csv
│   ├── data3.csv
│   ├── data4.csv
│   └── data5.csv
├── nested-structure/
│   ├── data/
│   │   ├── raw/
│   │   │   └── ...
│   │   └── processed/
│   │       └── ...
│   └── metadata/
│       └── ...
├── mixed-formats/
│   ├── data.json
│   ├── data.csv
│   ├── data.parquet
│   └── image.png
└── checksums.json (file integrity validation)
```

**quilt-mcp-test-scratch/** (Ephemeral workspace)
- Cleaned before each test run
- Used for package creation tests
- Auto-cleanup after test completion

**quilt-mcp-test-packages/** (Package registry)
- Package manifests and metadata
- Versioned package storage
- Preserved across test runs

### 4.3 Test Users (Multiuser Mode)

| Username | Email | Role | Admin | Purpose |
|----------|-------|------|-------|---------|
| `test-admin` | admin@test.com | admin | Yes | Admin operations |
| `test-user` | user@test.com | user | No | Standard operations |
| `test-readonly` | readonly@test.com | viewer | No | Permission testing |
| `test-service` | service@test.com | service | No | Service account testing |

**Setup:** Pre-created in test catalog via admin API

### 4.4 Data Generation Scripts

**generate_test_data.py:**
- Creates deterministic CSV files (seeded random data)
- Generates nested directory structures
- Creates mixed-format files (JSON, Parquet, images)
- Calculates and stores checksums
- Versions datasets (tracks schema changes)

**create_baseline_packages.py:**
- Uses generate_test_data.py output
- Creates packages in test registry
- Validates package creation
- Stores package metadata for test validation

**cleanup_test_data.py:**
- Removes ephemeral test data
- Preserves baseline packages
- Resets test environment to known state

---

## 5. Implementation Guidelines

### 5.1 Test Structure Template

```python
"""
test_XX_<feature>.py - <Feature> operations

Tests the QuiltOps abstract interface for <feature> functionality.
Backend-agnostic - works with both Quilt3_Backend and Platform_Backend.
"""

import pytest
from quilt_mcp.ops.factory import QuiltOpsFactory
from quilt_mcp.ops.exceptions import *
from quilt_mcp.domain import *


class Test<Feature>:
    """<Feature> operations test suite"""

    def test_<operation>_success(self, quilt_ops, test_data):
        """Test <operation> succeeds with valid inputs"""
        # Arrange
        ...

        # Act
        result = quilt_ops.<operation>(...)

        # Assert
        assert result is not None
        assert isinstance(result, <ExpectedType>)
        assert result.<field> == expected_value

    def test_<operation>_failure(self, quilt_ops):
        """Test <operation> raises exception for invalid inputs"""
        # Arrange
        invalid_input = ...

        # Act & Assert
        with pytest.raises(<ExceptionType>) as exc_info:
            quilt_ops.<operation>(invalid_input)

        # Validate error context
        assert exc_info.value.context["field_name"] == "..."
        assert "expected message" in str(exc_info.value)
```

### 5.2 Fixture Design

**conftest.py:**
```python
import pytest
import os
from quilt_mcp.ops.factory import QuiltOpsFactory


@pytest.fixture(scope="session")
def quilt_ops():
    """Factory-created QuiltOps backend (mode-aware)"""
    ops = QuiltOpsFactory.create()
    yield ops
    # No cleanup - backend is stateless


@pytest.fixture(scope="session")
def admin_ops(quilt_ops):
    """AdminOps instance (requires admin permissions)"""
    if not quilt_ops.get_auth_status().is_authenticated:
        pytest.skip("Admin operations require authentication")
    yield quilt_ops.admin


@pytest.fixture(scope="session")
def test_bucket_data():
    """Immutable test data bucket path"""
    return os.getenv("QUILT_TEST_BUCKET_DATA", "quilt-mcp-test-data")


@pytest.fixture(scope="function")
def test_bucket_scratch():
    """Ephemeral workspace bucket (auto-cleanup)"""
    bucket = os.getenv("QUILT_TEST_BUCKET_SCRATCH", "quilt-mcp-test-scratch")
    yield bucket
    # Cleanup after test (optional)


@pytest.fixture(scope="session")
def test_registry():
    """Test package registry URL"""
    return os.getenv("QUILT_TEST_REGISTRY_URL", "s3://quilt-mcp-test-packages")


@pytest.fixture(scope="function")
def cleanup_package(quilt_ops, test_registry):
    """Auto-cleanup for created packages"""
    created_packages = []

    def register_package(package_name):
        created_packages.append(package_name)

    yield register_package

    # Cleanup (implementation depends on backend)
    for pkg in created_packages:
        try:
            # Delete package (if backend supports it)
            pass
        except Exception:
            pass  # Best-effort cleanup
```

### 5.3 Assertion Patterns

**Domain Object Validation:**
```python
def assert_valid_package_info(pkg: Package_Info):
    """Validate Package_Info has required fields"""
    assert pkg.name is not None
    assert "/" in pkg.name  # user/package format
    assert pkg.top_hash is not None
    assert len(pkg.top_hash) == 64  # SHA256
    assert pkg.registry is not None
    assert pkg.bucket is not None
    assert pkg.modified_date is not None
    # ISO 8601 format
    datetime.fromisoformat(pkg.modified_date.replace("Z", "+00:00"))


def assert_valid_content_info(content: Content_Info):
    """Validate Content_Info has required fields"""
    assert content.path is not None
    assert content.type in ["file", "directory"]
    if content.type == "file":
        assert content.size is not None
        assert content.size >= 0
    if content.type == "directory":
        assert content.size is None
```

**Exception Validation:**
```python
def assert_exception_has_context(exc: Exception, expected_keys: List[str]):
    """Validate exception has expected context fields"""
    assert hasattr(exc, "context")
    assert isinstance(exc.context, dict)
    for key in expected_keys:
        assert key in exc.context, f"Missing context field: {key}"
```

### 5.4 Backend-Agnostic Testing

**Avoid:**
- Checking backend implementation type (`isinstance(ops, Quilt3_Backend)`)
- Accessing internal attributes (`ops._client`, `ops._session`)
- Testing implementation-specific behavior

**Prefer:**
- Testing abstract interface contract
- Validating return types match domain objects
- Checking exception types match defined hierarchy
- Verifying behavior is consistent across backends

### 5.5 Test Execution

**Run all e2e tests:**
```bash
# Local mode
QUILT_MULTIUSER_MODE=false uv run pytest tests/e2e/quilt_ops/ -v

# Multiuser mode
QUILT_MULTIUSER_MODE=true uv run pytest tests/e2e/quilt_ops/ -v

# Both modes sequentially
uv run pytest tests/e2e/quilt_ops/ -v --run-both-modes
```

**Run specific test file:**
```bash
uv run pytest tests/e2e/quilt_ops/test_04_package_creation.py -v
```

**Run with markers:**
```bash
# Only fast tests (exclude slow)
uv run pytest tests/e2e/quilt_ops/ -m "not slow" -v

# Only admin tests
uv run pytest tests/e2e/quilt_ops/ -m requires_admin -v

# Backend-agnostic tests only
uv run pytest tests/e2e/quilt_ops/ -m backend_agnostic -v
```

---

## 6. Success Criteria

### 6.1 Coverage Metrics

- **Method Coverage:** 100% of QuiltOps abstract methods tested
- **Domain Object Coverage:** All 9 domain objects validated
- **Exception Coverage:** All 5 exception types tested
- **Backend Coverage:** Tests pass with both backends

### 6.2 Quality Metrics

- **Pass Rate:** 100% of tests pass against live AWS
- **Flakiness:** <1% flaky test rate (retry 3x, same result)
- **Performance:** All performance benchmarks within thresholds
- **Documentation:** Every test has clear docstring

### 6.3 Operational Metrics

- **Setup Time:** <5 minutes to configure test environment
- **Execution Time:** <60 minutes for full suite
- **Cost:** <$5 per test run (AWS charges)
- **Maintenance:** <2 hours/month to update test data

---

## 7. Risks & Mitigations

### 7.1 AWS Cost Risk

**Risk:** Test runs consume significant AWS resources

**Mitigation:**
- Use lifecycle policies to auto-delete test data after 24h
- Monitor costs with CloudWatch alarms
- Limit test execution to nightly + on-demand
- Use smallest viable test datasets

### 7.2 Authentication Complexity

**Risk:** Managing credentials for both modes is error-prone

**Mitigation:**
- Clear documentation for authentication setup
- Validation scripts to check auth before tests run
- Separate .env.test file with all required credentials
- Automatic skip for tests requiring unavailable auth

### 7.3 Test Data Staleness

**Risk:** Test data becomes outdated or corrupted

**Mitigation:**
- Versioned test data generation scripts
- Checksums for data integrity validation
- Automated baseline package regeneration
- Documentation of test data schema

### 7.4 Backend Divergence

**Risk:** Backends implement interface differently, causing test failures

**Mitigation:**
- Abstract interface is contract, not implementation
- Tests validate behavior, not implementation details
- Clear definition of expected behavior in tests
- Regular testing with both backends

---

## 8. Future Enhancements

### 8.1 Additional Test Scenarios

- **Multi-region testing** - S3 buckets in different regions
- **Large-scale testing** - Packages with 10,000+ files
- **Network resilience** - Simulate transient failures, retries
- **Access control** - Fine-grained permission testing
- **Audit logging** - Verify operations are logged

### 8.2 Test Infrastructure Improvements

- **Docker-based test environment** - Portable, reproducible setup
- **Test data CDN** - Faster downloads of reference datasets
- **Parallel test execution** - Reduce total runtime
- **Visual test reports** - HTML reports with charts, graphs

### 8.3 Integration with Other Test Suites

- **MCP tool tests** - Validate tools use QuiltOps correctly
- **Performance regression tests** - Track performance over time
- **Security tests** - Validate authentication, authorization
- **Compatibility tests** - Test with different AWS SDK versions

---

## 9. Appendices

### 9.1 QuiltOps Method Reference

**Core Operations (27 methods):**
1. get_auth_status()
2. get_graphql_endpoint()
3. get_graphql_auth_headers()
4. search_packages()
5. get_package_info()
6. browse_content()
7. get_content_url()
8. list_all_packages()
9. diff_packages()
10. create_package_revision()
11. update_package_revision()
12. get_catalog_config()
13. configure_catalog()
14. get_registry_url()
15. execute_graphql_query()
16. get_boto3_client()
17. list_tabulator_tables()
18. get_tabulator_table()
19. create_tabulator_table()
20. update_tabulator_table()
21. rename_tabulator_table()
22. delete_tabulator_table()
23. get_open_query_status()
24. set_open_query()
25. admin (property)
26-27. (Reserved for future methods)

**AdminOps Methods (19 methods):**
1. list_users()
2. get_user()
3. create_user()
4. delete_user()
5. set_user_email()
6. set_user_admin()
7. set_user_active()
8. reset_user_password()
9. set_user_role()
10. list_roles()
11. add_user_roles()
12. remove_user_roles()
13. get_sso_config()
14. set_sso_config()
15. remove_sso_config()
16-19. (Reserved for future methods)

### 9.2 Domain Object Schemas

See section 4 of the exploration report for complete domain object definitions.

### 9.3 Exception Hierarchy

See section 5 of the exploration report for complete exception definitions.

### 9.4 Environment Variables Reference

```bash
# Mode Configuration
QUILT_MULTIUSER_MODE=false  # or true

# Local Mode (Quilt3_Backend)
QUILT_TEST_REGISTRY_URL=s3://quilt-mcp-test-packages

# Multiuser Mode (Platform_Backend)
QUILT_TEST_CATALOG_URL=https://test-catalog.quiltdata.com
QUILT_TEST_JWT_TOKEN=eyJhbGc...
QUILT_TEST_GRAPHQL_ENDPOINT=https://api.test-catalog.quiltdata.com/graphql

# AWS Configuration
AWS_PROFILE=quilt-mcp-tests
AWS_REGION=us-east-1

# Test Buckets
QUILT_TEST_BUCKET_DATA=quilt-mcp-test-data
QUILT_TEST_BUCKET_SCRATCH=quilt-mcp-test-scratch
QUILT_TEST_BUCKET_PACKAGES=quilt-mcp-test-packages

# Test Users (Multiuser Mode)
QUILT_TEST_ADMIN_USER=test-admin
QUILT_TEST_ADMIN_EMAIL=admin@test.com
QUILT_TEST_USER=test-user
QUILT_TEST_USER_EMAIL=user@test.com
```

---

## Conclusion

This specification defines a comprehensive e2e test suite for the QuiltOps abstract API that validates real-world functionality against live AWS infrastructure. Tests are backend-agnostic, workflow-focused, and reproducible, ensuring the QuiltOps interface contract is honored by all implementations.

**Next Steps:**
1. Review and approve specification
2. Set up test AWS environment (buckets, catalog, users)
3. Implement test data generation scripts
4. Implement test suite (phased approach, starting with critical operations)
5. Integrate into CI/CD pipeline
6. Monitor and maintain test infrastructure

**Estimated Implementation Effort:**
- Test infrastructure setup: 2-3 days
- Test data generation: 1-2 days
- Test implementation (all 18 files): 5-7 days
- Documentation and CI/CD integration: 1-2 days
- **Total: 9-14 days**
