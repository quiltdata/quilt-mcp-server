<!-- markdownlint-disable MD013 -->
# Gap Analysis - QuiltService Abstraction Coverage

**GitHub Issue**: #155 "[isolate quilt3](https://github.com/quiltdata/quilt-mcp-server/issues/155)"

**Context**: Analysis of missing quilt3 dependencies from [05-missing-items.md](./05-missing-items.md) against current QuiltService abstractions in [quilt_service.py](../../src/quilt_mcp/services/quilt_service.py).

**Reference Design Pattern**: [04-create-package-spec.md](./04-create-package-spec.md) demonstrates the successful abstraction approach with complete operations replacing object manipulation.

## Executive Summary

**Current Coverage**: The existing QuiltService provides abstractions for **~65%** of identified missing dependencies, primarily covering authentication, package operations, and admin modules.

**Critical Gaps**: **~35%** of missing dependencies require new QuiltService methods, concentrated in:

- AWS credential/session management (7 missing items)
- Search backend infrastructure (6 missing items)
- Utility functions for client factories (4 missing items)

**Recommended Approach**: Follow the `create_package_revision()` pattern with complete operation methods that hide quilt3 implementation details rather than exposing raw objects.

## Detailed Gap Analysis

### 1. AWS Athena Service Dependencies

**Missing Items from 05-missing-items.md**: Lines 68, 70, 155, 157, 169, 449, 451

**Current QuiltService Coverage**: ❌ **No Coverage**

**Gap Details**:

```python
# Current athena_service.py usage (7 locations)
import quilt3
botocore_session = quilt3.session.create_botocore_session()  # Lines 68, 155, 449
credentials = botocore_session.get_credentials()            # Lines 70, 157, 451
# Used in multiple credential/region contexts                # Line 169
```

**Missing QuiltService Methods**:

- `create_botocore_session()` - Currently returns `NotImplementedError`
- `get_credentials_from_session(session)` - New method needed
- `get_region_from_session(session)` - New method needed

**Proposed Design Pattern**: **Direct 1:1 Wrapper** (Low-level infrastructure)

**Rationale**: These are foundational AWS authentication primitives needed by multiple services. Direct wrappers maintain compatibility while enabling future backend flexibility.

**Proposed API**:

```python
class QuiltService:
    def create_botocore_session(self) -> Any:
        """Create authenticated botocore session."""
        return quilt3.session.create_botocore_session()

    def get_session_credentials(self, session: Any) -> Any:
        """Extract credentials from botocore session."""
        return session.get_credentials()

    def get_session_region(self, session: Any) -> str:
        """Get region from botocore session."""
        # Implementation logic for region detection
        pass
```

### 2. AWS Permission Discovery Dependencies

**Missing Items from 05-missing-items.md**: Lines 15, 74-90, 588-592, 620-624

**Current QuiltService Coverage**: ✅ **Partial Coverage** - `get_boto3_session()` method exists but returns `NotImplementedError`

**Gap Details**:

```python
# Current permission_discovery.py usage (4 distinct patterns)
session = quilt3.get_boto3_session()        # Lines 74-90, 588-592, 620-624
registry_url = quilt3.session.get_registry_url()  # Line 15 (already covered)
session = quilt3.session.get_session()      # Lines 74-90 (already covered)
```

**Missing QuiltService Implementation**:

- `get_boto3_session()` - Method signature exists but not implemented

**Proposed Design Pattern**: **Direct 1:1 Implementation** (Complete existing API)

**Rationale**: Method already designed and used by multiple consumer modules. Need to complete the implementation.

**Proposed Implementation**:

```python
def get_boto3_session(self) -> Any:
    """Get authenticated boto3 session."""
    if not self.is_authenticated():
        raise Exception("Not authenticated - login required")
    return quilt3.get_boto3_session()
```

### 3. Utils Module Dependencies

**Missing Items from 05-missing-items.md**: Lines 191, 194-198, 217, 220-224

**Current QuiltService Coverage**: ✅ **Full Coverage** - All patterns already abstracted

**Gap Details**:

```python
# Current utils.py usage (all covered by existing methods)
if hasattr(quilt3, "logged_in") and quilt3.logged_in():    # → is_authenticated()
    session = quilt3.get_boto3_session()                   # → get_boto3_session()
```

**Status**: ✅ **No Action Required** - Existing `is_authenticated()` and `get_boto3_session()` methods cover all usage patterns.

### 4. GraphQL Search Backend Dependencies

**Missing Items from 05-missing-items.md**: Lines 13, 46, 72-74, 589-592

**Current QuiltService Coverage**: ✅ **Full Coverage** - All patterns already abstracted

**Gap Details**:

```python
# Current graphql.py usage (all covered by existing methods)
registry_url = quilt3.session.get_registry_url()  # → get_registry_url()
session = quilt3.session.get_session()            # → get_session()
```

**Status**: ✅ **No Action Required** - Existing `get_registry_url()` and `get_session()` methods cover all usage patterns.

### 5. Elasticsearch Search Backend Dependencies

**Missing Items from 05-missing-items.md**: Lines 11, 36, 49, 126

**Current QuiltService Coverage**: ❌ **No Coverage**

**Gap Details**:

```python
# Current elasticsearch.py usage (4 locations)
registry_url = quilt3.session.get_registry_url()  # Line 11 (covered)
bucket_obj = quilt3.Bucket(bucket_uri)            # Lines 36, 49, 126 (missing)
```

**Missing QuiltService Usage**:

- Lines 36, 49, 126 use `quilt3.Bucket()` directly but current `create_bucket()` method already covers this

**Status**: ✅ **Actually Covered** - The `create_bucket()` method already provides this functionality. The analysis in 05-missing-items.md may have missed this existing coverage.

## Summary of Required Actions

### Critical Gaps Requiring Implementation

**1. Complete AWS Session Management** (HIGH Priority)

- ✅ `create_botocore_session()` - Implement existing method
- ✅ `get_boto3_session()` - Implement existing method
- ❌ `get_session_credentials()` - New method needed
- ❌ `get_session_region()` - New method needed

### Implementation Priority Matrix

| Priority | Component | Missing Methods | Impact | Effort |
|----------|-----------|----------------|---------|---------|
| HIGH | AWS Athena Service | 4 methods | Blocks SQL queries | Medium |
| MEDIUM | Permission Discovery | 1 method | Limits bucket discovery | Low |
| LOW | Search Backends | 0 methods | Already covered | None |

### Design Pattern Recommendations

**For AWS Infrastructure (HIGH Priority)**:

- **Pattern**: Direct 1:1 wrappers for low-level primitives
- **Rationale**: These are foundational AWS authentication mechanisms used across multiple services
- **API Style**: Simple method delegation with error handling

**For Search Operations (Complete)**:

- **Pattern**: Current abstractions are sufficient
- **Status**: All missing items already covered by existing methods

**For Admin Operations (Complete)**:

- **Pattern**: Module delegation (current approach working well)
- **Status**: All admin functionality properly abstracted

## Integration Testing Requirements

### New Methods to Test

```python
# Required integration tests for new/updated methods
def test_create_botocore_session_integration():
    """Test botocore session creation with real AWS credentials"""

def test_get_boto3_session_integration():
    """Test boto3 session creation and client instantiation"""

def test_athena_service_full_workflow():
    """Test complete athena workflow using new QuiltService methods"""
```

### Backward Compatibility Verification

```python
# Verify existing tools continue working
def test_existing_package_creation_tools():
    """All 4 package creation tools still function correctly"""

def test_search_backends_still_work():
    """GraphQL and Elasticsearch search maintain functionality"""
```

## Migration Timeline

### Phase 1: Complete AWS Session Infrastructure (Sprint 1)

- Implement `create_botocore_session()`
- Implement `get_boto3_session()`
- Add helper methods for credential/region extraction
- Test with athena_service.py integration

### Phase 2: Validation & Testing (Sprint 1)

- Comprehensive integration testing
- Verify all 7 athena_service.py dependency points work
- Validate permission_discovery.py functionality
- Confirm search backends maintain full functionality

### Phase 3: Documentation & Cleanup (Sprint 2)

- Update QuiltService documentation
- Create migration guide for any remaining direct quilt3 usage
- Final verification of complete quilt3 isolation

## Success Criteria

**Complete Isolation Achieved When**:

- ✅ All missing items from 05-missing-items.md have QuiltService abstractions
- ✅ No direct `import quilt3` statements in service/search modules
- ✅ All existing functionality preserved through integration tests
- ✅ AWS Athena service fully functional through QuiltService
- ✅ Permission discovery maintains bucket access capabilities
- ✅ Search backends (GraphQL/Elasticsearch) fully operational

**Quality Gates**:

- 100% test coverage for new QuiltService methods
- Integration tests pass for all affected services
- No regression in existing MCP tool functionality
- Performance benchmarks maintained (no significant slowdown)
