# Test-Stateless Performance Fix

**Date:** 2025-02-05
**Issue:** `make test-stateless` was unnecessarily slow due to function-scoped fixtures

## Problem

The `stateless_container` fixture was function-scoped (default), causing:
- **11 test functions** = **11 container starts/stops**
- Each container takes ~2-3 seconds to start + health check + cleanup
- Total overhead: ~30 seconds just for container management

## Root Cause

[tests/conftest.py:515](../../tests/conftest.py#L515):
```python
@pytest.fixture  # ❌ No scope = function scope (default)
def stateless_container(...):
```

## Tests Analysis

Of the 11 tests in `tests/stateless/`:
- **9 tests** make read-only requests - can safely share one container
- **2 tests** in `test_persistent_state.py` create their OWN containers - don't use the fixture

The tests are already idempotent (don't modify state), so sharing is safe.

## Solution

Changed fixture scope to session:
```python
@pytest.fixture(scope="session")  # ✅ One container for all tests
def stateless_container(...):
```

Also updated `container_url` fixture to session scope for consistency.

## Expected Impact

- **Before:** 11 container starts (9 via fixture + 4 via test_persistent_state tests)
- **After:** 1 container start (shared by 9 tests) + 4 (test_persistent_state manages its own)
- **Speedup:** ~50% faster (~15 seconds vs ~30 seconds)

## Note: Tests Currently Broken

While investigating performance, discovered that **test-stateless tests are currently failing** due to JWT authentication issues (separate from this performance fix):

- JWT fixture tokens don't validate properly
- Server returns 403 Forbidden or connection resets
- Root cause: Static JWT fixtures vs real catalog authentication
- See [spec/a18-valid-jwts/01-bogus-jwts.md](01-bogus-jwts.md) for JWT issue details

This performance fix is independent of the JWT issues and improves test execution regardless.

## Files Changed

- [tests/conftest.py](../../tests/conftest.py#L515) - Added `scope="session"` to `stateless_container`
- [tests/conftest.py](../../tests/conftest.py#L600) - Added `scope="session"` to `container_url`
