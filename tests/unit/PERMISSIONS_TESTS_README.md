# Permissions Unit Tests - Real GraphQL Integration

## Overview

The permissions unit tests in `test_permissions_stateless.py` make **real GraphQL calls** to `demo.quiltdata.com` to validate the permissions tool behavior end-to-end. This provides high confidence that the tool works correctly with the actual Quilt Catalog API.

## Why Real Calls Instead of Mocks?

1. **End-to-End Validation**: Tests verify the complete flow from tool invocation → GraphQL query → response parsing → result formatting
2. **API Contract Validation**: Ensures we're using the correct GraphQL schema and field names
3. **Real-World Scenarios**: Tests against actual demo catalog data and behavior
4. **Regression Prevention**: Catches breaking changes in the Quilt Catalog API

## Running the Tests

### With Authentication (Full Test Suite)

To run all 13 tests including those requiring authentication:

```bash
# Set token as environment variable
export QUILT_TEST_TOKEN="your-jwt-token-here"
pytest tests/unit/test_permissions_stateless.py -v
```

Or inline:

```bash
QUILT_TEST_TOKEN="your-jwt-token" pytest tests/unit/test_permissions_stateless.py -v
```

**Expected Result**: 13 passed ✅

### Without Authentication (Partial Test Suite)

Tests that don't require authentication will still run:

```bash
pytest tests/unit/test_permissions_stateless.py -v
```

**Expected Result**: 6 passed, 7 skipped ⚠️

The skipped tests are those requiring a valid JWT token:
- `test_permissions_discover_success`
- `test_permissions_discover_filtered_buckets`
- `test_bucket_access_check_existing_bucket`
- `test_bucket_access_check_nonexistent`
- `test_bucket_access_check_missing_bucket_name`
- `test_recommendations_get`
- `test_invalid_action`

## Test Coverage

### Test Discovery (5 tests)
- ✅ **Module info** (no auth) - Returns available actions
- ✅ **Successful discovery** - Gets user identity + buckets from demo
- ✅ **No token** - Proper error handling
- ✅ **Invalid token** - Handles 401 errors correctly
- ✅ **Filtered discovery** - Tests bucket filtering with real/nonexistent buckets

### Bucket Access Check (4 tests)
- ✅ **Existing bucket** - Checks `quilt-example-bucket` on demo
- ✅ **Nonexistent bucket** - Validates `definitely-does-not-exist-xyz-123` returns no access
- ✅ **No token** - Proper error handling
- ✅ **Missing bucket name** - Parameter validation

### Recommendations (2 tests)
- ✅ **Get recommendations** - Generates recommendations from real user data
- ✅ **No token** - Proper error handling

### Error Handling (2 tests)
- ✅ **Invalid action** - Validates unknown action handling
- ✅ **Catalog URL not configured** - Tests missing catalog URL scenario

## What Makes These "Unit" Tests?

While these tests make real API calls, they're still considered unit tests because:

1. **Fast Execution**: Complete in ~3 seconds
2. **Isolated Scope**: Test only the permissions tool, not the entire system
3. **Deterministic**: Use known demo catalog state
4. **No Side Effects**: Read-only operations, no data modification
5. **Independent**: Each test is self-contained

## Getting a Test Token

To get a valid JWT token for demo.quiltdata.com:

1. **Via Browser**:
   - Visit https://demo.quiltdata.com
   - Open browser DevTools → Application → Cookies
   - Find the JWT token cookie

2. **Via Python** (if you have credentials):
   ```python
   import quilt3
   # Configure for demo catalog
   quilt3.config("https://demo.quiltdata.com")
   # Login (if not already logged in)
   # Token is stored in quilt3 config
   ```

3. **Use Existing Token**:
   ```bash
   # Token from your local development (see task-definition files)
   export QUILT_TEST_TOKEN="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
   ```

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Test Permissions

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install uv
        uses: astral-sh/setup-uv@v3
      
      - name: Run permissions tests
        env:
          QUILT_TEST_TOKEN: ${{ secrets.DEMO_CATALOG_JWT }}
        run: |
          uv run pytest tests/unit/test_permissions_stateless.py -v
```

Store the JWT token as a GitHub secret named `DEMO_CATALOG_JWT`.

### Without Token in CI

If you don't want to store the token as a secret, tests will still run partially:

```yaml
- name: Run permissions tests (partial)
  run: |
    uv run pytest tests/unit/test_permissions_stateless.py -v
  # 6 tests pass, 7 skipped
```

## Test Maintenance

### Updating Tests

When the Quilt Catalog API changes:

1. Update the GraphQL queries in the tool itself
2. Run tests with token to validate
3. Update test assertions if response structure changes

### Adding New Tests

To add a new test that calls the real API:

```python
def test_new_feature(self, test_token, catalog_url):
    """Test new permissions feature."""
    with request_context(test_token, metadata={"path": "/permissions"}):
        result = permissions(action="new_action", params={...})
    
    assert result["success"] is True
    # Add assertions based on expected behavior
```

Tests without authentication don't need fixtures:

```python
def test_new_validation(self):
    """Test new validation logic."""
    result = permissions(action="discover")  # Will fail without token
    assert result["success"] is False
```

## Troubleshooting

### Tests Fail with "QUILT_TEST_TOKEN not set"

**Problem**: Token not provided.

**Solution**: Set the environment variable:
```bash
export QUILT_TEST_TOKEN="your-token"
```

### Tests Fail with "401 UNAUTHORIZED"

**Problem**: Token is expired or invalid.

**Solution**: Get a fresh token from demo.quiltdata.com:
1. Login to demo catalog in browser
2. Extract JWT from cookies or browser storage
3. Update `QUILT_TEST_TOKEN`

### Tests Timeout

**Problem**: Network issues or demo catalog unavailable.

**Solution**: 
- Check internet connection
- Verify demo.quiltdata.com is accessible
- Try again later if service is down

### Unexpected Test Failures

**Problem**: Catalog API changed or demo data changed.

**Solution**:
1. Check if demo catalog buckets changed
2. Update test assertions for new expected values
3. Verify GraphQL schema hasn't changed
4. Check tool implementation for bugs

## Comparison with Integration Tests

We also have integration tests in `tests/integration/test_permissions.py`. Here's how they differ:

| Aspect | Unit Tests | Integration Tests |
|--------|-----------|-------------------|
| **Location** | `tests/unit/` | `tests/integration/` |
| **Speed** | Fast (~3s) | Slower (~10s+) |
| **Scope** | Permissions tool only | Full system integration |
| **Markers** | None (run by default) | `@pytest.mark.integration` |
| **Purpose** | Validate tool behavior | Validate system integration |
| **Network** | Real calls to demo | Real calls to demo |
| **CI** | Always run | Run with `pytest -m integration` |

Both test suites use real API calls, but unit tests focus on the tool itself while integration tests validate how it works within the larger system.

## Summary

✅ **13 comprehensive tests** covering all permissions tool functionality  
✅ **Real GraphQL validation** against demo.quiltdata.com  
✅ **Graceful degradation** - Partial test suite runs without token  
✅ **Fast execution** - Complete in ~3 seconds  
✅ **CI/CD ready** - Works in automated pipelines  

These tests provide high confidence that the permissions tool works correctly with the actual Quilt Catalog API!

