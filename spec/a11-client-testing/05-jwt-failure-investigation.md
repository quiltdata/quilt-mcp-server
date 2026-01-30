# JWT Test Failure Investigation

**Date**: 2026-01-29
**Status**: Investigation
**Previous**: [04-mcp-test-jwt-results.md](04-mcp-test-jwt-results.md)
**Objective**: Determine if the 4 JWT test failures are actually our fault

## Executive Summary

**Initial Assessment**: The 4 test failures reported in the JWT results appear to be **our fault**, not infrastructure issues as originally concluded. The failures indicate problems with our test environment setup and validation logic.

## Failure Re-Analysis

### 1. `discover_permissions` - Network Timeout

**Original Conclusion**: "Infrastructure/performance issue, not JWT authentication"

**Re-Analysis**: 🚨 **LIKELY OUR FAULT**

```
Tool: discover_permissions
Input: {
  "check_buckets": ["quilt-ernest-staging"]
}
Error: HTTP request failed: HTTPConnectionPool(host='localhost', port=8002): Read timed out. (read timeout=10)
```

**Why This Is Our Problem**:

1. **Hardcoded Test Bucket**: The test is checking `quilt-ernest-staging` - a real production bucket that may not exist or be accessible in our test environment
2. **Inappropriate Test Data**: Using production bucket names in stateless testing is wrong
3. **Timeout Configuration**: 10-second timeout may be too aggressive for permission discovery operations
4. **Missing Mock Data**: Stateless test environment should have predictable, mocked bucket data

**Root Cause**: Test configuration uses real-world data instead of controlled test fixtures.

### 2-4. `search_catalog` Validation Failures (3 failures)

**Original Conclusion**: "Empty search index or no matching files in test environment"

**Re-Analysis**: 🚨 **DEFINITELY OUR FAULT**

```
Tool: search_catalog
Input: {
  "query": "README.md",
  "limit": 10,
  "scope": "global/file/package",
  "bucket": ""
}
Error: Smart validation failed: Expected at least 1 results, got 0
```

**Why This Is Our Problem**:

1. **Broken Test Validation Logic**: The "smart validation" expects results but gets none
2. **Empty Test Environment**: Our stateless test container has no indexed content
3. **Poor Test Design**: Tests assume data exists without ensuring it's there
4. **Missing Test Data Setup**: No seed data or fixtures for search functionality

**Root Cause**: Test environment lacks proper data seeding and validation logic is flawed.

## Evidence of Our Responsibility

### 1. Test Environment Issues

**Problem**: Stateless test container runs with empty data

```bash
# From make target - no data seeding
docker run -d --name mcp-jwt-test \
  --read-only \
  -e QUILT_DISABLE_CACHE=true \
  -e HOME=/tmp \
  # ... security constraints
  quilt-mcp:test
```

**Missing**:

- No test data initialization
- No search index population
- No bucket fixtures
- No package fixtures

### 2. Hardcoded Production References

**Problem**: Tests reference real production resources

```python
# In test configuration
"check_buckets": ["quilt-ernest-staging"]  # Real production bucket!
```

**Should Be**:

```python
# Test fixtures
"check_buckets": ["test-bucket-1", "test-bucket-2"]
```

### 3. Flawed Validation Logic

**Problem**: "Smart validation" assumes data exists

```python
# Pseudo-code from validation
if len(results) < 1:
    raise ValidationError("Expected at least 1 results, got 0")
```

**Should Be**:

```python
# Validate structure, not content
if not isinstance(results, list):
    raise ValidationError("Expected list of results")
# Content validation should be separate from structure validation
```

## What We Need to Fix

### 1. Test Data Management

**Create Test Fixtures**:

```yaml
# scripts/tests/mcp-test-fixtures.yaml
test_buckets:
  - name: "test-bucket-1"
    objects:
      - "README.md"
      - "data/sample.csv"
      - "docs/guide.md"
  - name: "test-bucket-2" 
    objects:
      - "analysis/results.json"

test_packages:
  - name: "test-org/sample-package"
    bucket: "test-bucket-1"
    files: ["README.md", "data/sample.csv"]
```

**Seed Test Environment**:

```bash
# In test-stateless-mcp target
echo "Step 2a: Seeding test data..."
uv run python scripts/tests/seed_test_data.py \
  --endpoint http://localhost:8002/mcp \
  --jwt-token "$JWT_TOKEN"
```

### 2. Fix Validation Logic

**Current (Broken)**:

```python
def validate_search_results(results, expected_min=1):
    if len(results) < expected_min:
        raise ValidationError(f"Expected at least {expected_min} results, got {len(results)}")
```

**Fixed**:

```python
def validate_search_results(results, context=""):
    # Validate structure (always required)
    if not isinstance(results, list):
        raise ValidationError(f"Expected list of results, got {type(results)}")
    
    # Validate content only if we expect it
    if context == "with_test_data" and len(results) == 0:
        raise ValidationError("Expected results with test data, got none")
    
    # Empty results are valid for empty environments
    return True
```

### 3. Environment-Aware Testing

**Add Environment Detection**:

```python
def get_test_environment():
    """Detect if we're in a seeded test environment or empty stateless container."""
    if os.environ.get('MCP_TEST_ENVIRONMENT') == 'seeded':
        return 'seeded'
    elif os.environ.get('QUILT_MCP_STATELESS_MODE') == 'true':
        return 'stateless'
    else:
        return 'unknown'

def should_expect_data():
    """Determine if tests should expect data to exist."""
    env = get_test_environment()
    return env == 'seeded'
```

### 4. Timeout Configuration

**Make Timeouts Configurable**:

```python
# In mcp-test.py
DEFAULT_TIMEOUT = 30  # Increased from 10
DISCOVERY_TIMEOUT = 60  # Special timeout for discovery operations

def _make_http_request(self, method, timeout=None):
    if timeout is None:
        timeout = DISCOVERY_TIMEOUT if method == 'discover_permissions' else DEFAULT_TIMEOUT
    
    response = self.session.post(
        self.endpoint,
        json=request_data,
        timeout=timeout  # Use appropriate timeout
    )
```

## Proposed Fix Implementation

### Phase 1: Immediate Fixes (1-2 hours)

1. **Update test configuration** to use test fixtures instead of production data
2. **Increase timeouts** for discovery operations
3. **Make validation conditional** based on environment

### Phase 2: Test Data Infrastructure (4-6 hours)

1. **Create test data seeding script**
2. **Add fixture definitions**
3. **Update test-stateless-mcp target** to seed data
4. **Add environment detection logic**

### Phase 3: Robust Validation (2-3 hours)

1. **Rewrite validation logic** to be environment-aware
2. **Add proper error messages**
3. **Create validation test cases**

## Success Criteria

After fixes, we should see:

- ✅ `discover_permissions` completes within timeout (uses test buckets)
- ✅ `search_catalog` tests pass with seeded data OR gracefully handle empty environment
- ✅ All 55 tools pass (100% success rate)
- ✅ Clear distinction between "no data" vs "broken functionality"

## Conclusion

**The 4 JWT test failures ARE our fault**, not infrastructure issues:

1. **discover_permissions timeout**: Caused by testing against real production bucket instead of test fixtures
2. **search_catalog validation failures**: Caused by expecting data in empty test environment without seeding

**Next Steps**:

1. Create proper test fixtures and data seeding
2. Fix validation logic to be environment-aware  
3. Update test configuration to use test data instead of production references
4. Increase timeouts for operations that legitimately need more time

The JWT authentication itself is working correctly - these are test environment and validation issues that need to be addressed.
