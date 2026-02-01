# Smarter Test Fixes: Patterns 3 & 4

## Problem with Original Plan

**Pattern 3 (QuiltOps):** Proposed adding 4 stub methods to every mock class
- If 14 failures = ~10 different mock classes
- That's 40+ lines of boilerplate
- Still breaks on next interface change
- **Root cause:** Fragile hand-written mocks

**Pattern 4 (Pydantic):** Proposed adding `arbitrary_types_allowed=True`
- Doesn't work: `PermissionDiscoveryService` isn't a Pydantic model
- Can't add config to non-BaseModel classes
- **Root cause:** Non-serializable type in tool signature

---

## Pattern 3: Use MagicMock for QuiltOps Tests

### Current State

Multiple hand-written mock classes implementing QuiltOps:

- Each test file has its own mocks
- Each mock must implement all abstract methods
- Interface changes break all mocks

### Better Solution: Use MagicMock with create_autospec

**Why MagicMock is better here:**

- Tests are checking **interface structure**, not business logic
- No need for realistic return values - just checking methods exist
- Automatically adapts to signature changes
- Less maintenance, more flexibility

**Current (broken):**

```python
class ConcreteQuiltOps(QuiltOps):
    def get_auth_status(self, registry: str):
        return Auth_Status(...)
    def search_packages(self, query: str, registry: str):
        return []
    # ... must implement ALL methods
```

**Fixed:**

```python
from unittest.mock import create_autospec

def test_something():
    ops = create_autospec(QuiltOps, instance=True)
    ops.get_auth_status.return_value = {"authenticated": True}
    # Only configure what this test needs
```

### Implementation Steps

1. **Update [tests/unit/ops/test_quilt_ops.py](tests/unit/ops/test_quilt_ops.py)**
   - Replace all hand-written mock classes with `create_autospec(QuiltOps, instance=True)`
   - Configure return values per test as needed
   - For tests checking "can be instantiated", use partial implementations:

   ```python
   # For concrete implementation tests
   class MinimalQuiltOps(QuiltOps):
       def __init__(self):
           pass
       # Use __getattr__ to return MagicMock for any method
       def __getattr__(self, name):
           return MagicMock()
   ```

2. **Benefits:**
   - Zero maintenance when interface changes
   - Tests become simpler and clearer
   - No boilerplate method implementations
   - Still validates against actual interface (with autospec)

### Validation
```bash
uv run pytest tests/unit/ops/test_quilt_ops.py -v
```

---

## Pattern 4: Fix Pydantic Schema Issue

### Root Cause Analysis

**Error:** Pydantic can't generate schema for `PermissionDiscoveryService` during tool registration

**Why:** FastMCP introspects tool function signatures and expects Pydantic-serializable types

**Where:** Three functions in [src/quilt_mcp/services/permissions_service.py](src/quilt_mcp/services/permissions_service.py)

### Problematic Functions

**All registered as tools via [src/quilt_mcp/tools/__init__.py:45](src/quilt_mcp/tools/__init__.py#L45)**

1. **`discover_permissions()`** - Lines 68-88
   ```python
   def discover_permissions(
       check_buckets: Optional[List[str]] = None,
       include_cross_account: bool = False,
       force_refresh: bool = False,
       *,
       permission_service: Optional[PermissionDiscoveryService] = None,  # ❌ Problem
       auth_service: Optional[AuthService] = None,  # ❌ Problem
   ) -> Dict[str, Any]:
   ```

2. **`check_bucket_access()`** - Lines 90-108
   ```python
   def check_bucket_access(
       bucket: str,
       operations: Optional[List[str]] = None,
       *,
       permission_service: Optional[PermissionDiscoveryService] = None,  # ❌ Problem
       auth_service: Optional[AuthService] = None,  # ❌ Problem
   ) -> Dict[str, Any]:
   ```

3. **`bucket_recommendations_get()`** - Lines 110-129
   ```python
   def bucket_recommendations_get(
       source_bucket: Optional[str] = None,
       operation_type: str = "package_creation",
       user_context: Optional[Dict[str, Any]] = None,
       *,
       permission_service: Optional[PermissionDiscoveryService] = None,  # ❌ Problem
       auth_service: Optional[AuthService] = None,  # ❌ Problem
   ) -> Dict[str, Any]:
   ```

**The Pattern:**

- All three have keyword-only parameters for `permission_service` and `auth_service`
- These are meant for **internal dependency injection**, not user input
- FastMCP tries to generate Pydantic schemas for them → fails
- There's already a helper `_resolve_permission_service()` (lines 59-65) that handles this internally

### The Fix: Use Context from wrap_tool_with_context

**Good news:** The codebase already has infrastructure for this!

In [src/quilt_mcp/utils.py:183](src/quilt_mcp/utils.py#L183), tools are wrapped with:

```python
wrapped = wrap_tool_with_context(func, context_factory)
```

This wrapper provides `RequestContext` which includes `permission_service`. The current implementation bypasses this by accepting services as parameters.

**Solution:** Remove service parameters, get services from injected context instead.

**Current (broken):**

```python
def discover_permissions(
    check_buckets: Optional[List[str]] = None,
    include_cross_account: bool = False,
    force_refresh: bool = False,
    *,
    permission_service: Optional[PermissionDiscoveryService] = None,  # ❌
    auth_service: Optional[AuthService] = None,  # ❌
) -> Dict[str, Any]:
    service = _resolve_permission_service(permission_service, auth_service)
    return service.discover_permissions(...)
```

**Fixed:**

```python
def discover_permissions(
    check_buckets: Optional[List[str]] = None,
    include_cross_account: bool = False,
    force_refresh: bool = False,
    *,
    context: RequestContext,  # ✅ Injected by wrap_tool_with_context
) -> Dict[str, Any]:
    return context.permission_service.discover_permissions(...)
```

### Why This Works

1. **Context injection already exists** - `wrap_tool_with_context` injects `RequestContext`
2. **Permission service already in context** - See [src/quilt_mcp/context/factory.py:58-60](src/quilt_mcp/context/factory.py#L58-L60)
3. **No Pydantic schema needed** - `RequestContext` is never serialized to user
4. **Proper architecture** - Services come from request context, not parameters

### Implementation Steps

1. **Update three functions in [src/quilt_mcp/services/permissions_service.py](src/quilt_mcp/services/permissions_service.py)**
   - `discover_permissions()` (lines 68-88)
   - `check_bucket_access()` (lines 90-108)
   - `bucket_recommendations_get()` (lines 110-129)
   - Remove `permission_service` and `auth_service` parameters
   - Add `context: RequestContext` parameter instead
   - Use `context.permission_service` directly
   - Remove `_resolve_permission_service()` calls (no longer needed)

2. **Update tests** that call these functions
   - [tests/unit/test_health_integration.py](tests/unit/test_health_integration.py)
   - [tests/unit/test_resources.py](tests/unit/test_resources.py)
   - [tests/unit/test_utils.py](tests/unit/test_utils.py)
   - Mock `RequestContext` with `permission_service` attribute
   - Remove service parameter passing from test calls

### Validation
```bash
uv run pytest tests/unit/test_health_integration.py -v
uv run pytest tests/unit/test_resources.py -v
uv run pytest tests/unit/test_utils.py -v
```

---

## Comparison: Band-Aid vs Real Fix

### Pattern 3: QuiltOps Mocks

| Approach                              | Lines Changed   | Future-Proof     | Maintenance |
|---------------------------------------|-----------------|------------------|-------------|
| **Band-aid:** Add stubs to each mock  | 40+ lines       | ❌ Breaks again  | High        |
| **Real fix:** Use MagicMock/autospec  | ~20 lines total | ✅ Auto-adapts   | Zero        |

### Pattern 4: Pydantic Schema

| Approach | Works? | Architectural | Maintainable |
|----------|--------|---------------|--------------|
| **Band-aid:** `arbitrary_types_allowed` | ❌ No | ❌ Hack | N/A |
| **Real fix:** Remove from signatures | ✅ Yes | ✅ Clean | ✅ Yes |

---

## Execution Order

1. **Pattern 4 investigation** (5 min) - Find problematic tools
2. **Pattern 4 fix** (15 min) - Refactor tool signatures
3. **Pattern 3 fixture** (20 min) - Create shared StubQuiltOps
4. **Pattern 3 migration** (10 min) - Update test_quilt_ops.py

**Total:** ~50 minutes vs 2+ hours of boilerplate

---

## Philosophy

**Stop fixing tests to match bad patterns.**

If multiple tests break from small interface changes:
- ❌ Don't copy-paste fixes
- ✅ Fix the underlying structure

**Good tests are:**
- Resilient to refactoring
- Easy to maintain
- Focused on behavior, not implementation
