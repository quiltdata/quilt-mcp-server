# Tool Loops: Reality Check

**Status**: Analysis Document
**Sprint**: A18
**Date**: 2026-02-07
**Context**: Verification of [13-tool-loops-simple.md](13-tool-loops-simple.md) against actual codebase

---

## Summary

The "simple" tool loops design (doc 13) has **critical practical problems** when checked against the actual MCP server implementation.

---

## Problem 1: Context Data Structure Unclear

### What the design says

```python
context = {}
result = execute_tool("admin_user_create", {"name": "test-user"})
context.update(result)  # Merge results into context
```

### What actually happens

**admin_user_create** returns:

```python
{
    "success": True,
    "user": {
        "name": "test-user-123",
        "email": "test@example.com",
        "role": "viewer",
        "extra_roles": [],
        "active": True,
        # ... more fields
    },
    "message": "Successfully created user 'test-user-123' with role 'viewer'"
}
```

**admin_user_get** signature:

```python
async def admin_user_get(name: str) -> Dict[str, Any]
```

**admin_user_delete** signature:

```python
async def admin_user_delete(name: str) -> Dict[str, Any]
```

### The problem

If we do `context.update(result)`, context becomes:

```python
{
    "success": True,
    "user": {...},
    "message": "..."
}
```

But the next tool needs `name`, not `user`. Where does `name` come from?

**Options:**

1. Extract from result: `context["user"]["name"]` (requires knowing structure)
2. Keep from original args: `context["name"]` = `"test-user-123"` (requires preserving input args)
3. Both: Merge input args AND result (can cause conflicts if tool returns a different `name`)

**The design doesn't specify which approach to use.**

---

## Problem 2: Argument Sources Not Specified

### The design shows

```python
TOOL_LOOPS = {
    "admin_user": [
        "admin_user_create",
        "admin_user_get",
        "admin_user_delete"
    ]
}
```

### What's missing

For **admin_user_create**, arguments are provided by test config:

- `name`: Generate unique (e.g., `"test-loop-abc123"`)
- `email`: Literal (e.g., `"test@example.com"`)
- `role`: Literal (e.g., `"viewer"`)

For **admin_user_get**, arguments come from WHERE?

- `name`: From create's input? Or create's output `result["user"]["name"]`?

For **admin_user_delete**, arguments come from WHERE?

- `name`: Same as get? Or from some other source?

**The design says "auto-match by name" but doesn't explain:**

- Match from result fields?
- Match from original arguments?
- Prefer one over the other?

---

## Problem 3: Multi-Parameter Cleanup

### Real-world example: package_delete

**package_create** signature:

```python
def package_create(
    package_name: str,
    s3_uris: list[str],
    registry: str,  # REQUIRED
    metadata: Optional[dict] = None,
    message: str = "Created via package_create tool",
    flatten: bool = True,
    copy: bool = False,
) -> PackageCreateSuccess | PackageCreateError
```

**package_delete** signature:

```python
def package_delete(
    package_name: str,
    registry: str,  # ALSO REQUIRED
) -> PackageDeleteSuccess | PackageDeleteError
```

### The problem

package_delete needs **TWO** parameters: `package_name` AND `registry`.

- `package_name` is passed to create, and presumably also in the result
- `registry` is passed to create, but is it in the result?

**If we only keep result data in context, we lose `registry`.**
**If we only keep original arguments, we might miss transformed values.**

**Solution:** Context must include BOTH input arguments and results.

But then: What if create's input `package_name="test/pkg"` but result has `package_name="test/pkg-with-hash"`? Which one do we use?

---

## Problem 4: Nested Operations (Add/Remove Roles)

### The design shows

```python
TOOL_LOOPS = {
    "admin_user_with_roles": [
        "admin_user_create",
        "admin_user_get",
        "admin_user_add_roles",   # Add roles
        "admin_user_get",          # Verify
        "admin_user_remove_roles", # Remove roles
        "admin_user_get",          # Verify
        "admin_user_delete",
    ]
}
```

### Real signatures

```python
async def admin_user_add_roles(
    name: str,
    roles: List[str],  # Which roles to add?
) -> Dict[str, Any]

async def admin_user_remove_roles(
    name: str,
    roles: List[str],  # Which roles to remove?
) -> Dict[str, Any]
```

### The problem

- add_roles needs `roles=["data-scientist", "analyst"]` (literal from test config)
- remove_roles needs `roles=["data-scientist", "analyst"]` (THE SAME VALUES)

How does remove_roles know which roles were added?

**Options:**

1. Hard-code in test config (remove_roles uses same literal values)
2. Capture from add_roles arguments (context preserves input args)
3. Capture from add_roles result (if result includes what was added)

**The design assumes this "just works" but doesn't explain how.**

---

## Problem 5: Verification Without Assertions

### The design shows

```python
"admin_user": [
    "admin_user_create",
    "admin_user_get",    # Verify creation
    "admin_user_delete",
]
```

### The assumption

Running `admin_user_get` after create "verifies" the user exists.

### The problem

**What does "verify" mean here?**

- Does get need to succeed (not return error)?
- Does get need to return specific fields?
- Does get need to return the same data as create?

**If get returns an error, does the loop fail?**

- Yes → Then get is not just read-only, it's a validation step
- No → Then why include it?

**The design treats verification as implicit but doesn't specify success criteria.**

---

## Problem 6: Real Tool Signatures Don't Match Assumptions

### Discovered from actual code

**72 total tools** in test config, including:

**Admin tools (14):**

- admin_sso_config_remove
- admin_sso_config_set
- admin_tabulator_open_query_set
- admin_user_add_roles
- admin_user_create
- admin_user_delete
- admin_user_get
- admin_user_remove_roles
- admin_user_reset_password
- admin_user_set_active
- admin_user_set_admin
- admin_user_set_email
- admin_user_set_role

**Package tools (6):**

- package_browse
- package_create
- package_delete
- package_diff
- package_update

**Bucket tools (6):**

- bucket_object_fetch
- bucket_object_info
- bucket_object_link
- bucket_object_text
- bucket_objects_list
- bucket_objects_put

**Observations:**

1. **No bucket_objects_delete** - Doc 12 identified this as missing, still missing
2. **admin_user_reset_password** - Reversible via delete (user deletion cleans up)
3. **admin_user_set_email** - Can test in loop: create → set_email → verify → delete
4. **package_update** - Can test in loop: create → update → verify → delete

**Most tools CAN fit "create → modify → verify → delete" pattern.**

---

## Problem 7: Current Test Infrastructure Skips Writes

### From mcp-test-setup.py

```python
# Safety guard: Skip write operations
if effect in ['create', 'update', 'remove']:
    return DiscoveryResult(
        tool_name=tool_name,
        status='SKIPPED',
        duration_ms=0,
        error=f"Skipped: write operation (effect={effect})"
    )
```

**Current behavior:** All write operations have `status='SKIPPED'` in test config.

### To implement tool loops

1. Remove the skip guard for write operations
2. Add loop orchestration to test runner
3. Deal with real credentials and permissions
4. Deal with real state changes (created resources)
5. Deal with cleanup failures (resources left behind)

**The design underestimates the implementation lift.**

---

## What Would Actually Be Practical

### Option A: Explicit Argument Mapping

Define WHERE each argument comes from:

```python
TOOL_LOOPS = {
    "admin_user": {
        "steps": [
            {
                "tool": "admin_user_create",
                "args": {
                    "name": {"source": "literal", "value": "test-loop-{uuid}"},
                    "email": {"source": "literal", "value": "test@example.com"},
                    "role": {"source": "literal", "value": "viewer"},
                }
            },
            {
                "tool": "admin_user_get",
                "args": {
                    "name": {"source": "step", "step_index": 0, "path": "user.name"}
                }
            },
            {
                "tool": "admin_user_delete",
                "args": {
                    "name": {"source": "step", "step_index": 0, "path": "user.name"}
                }
            }
        ]
    }
}
```

**Pros:** Explicit, unambiguous, no guessing
**Cons:** VERBOSE AS HELL (this is what we wanted to avoid!)

---

### Option B: Simplified Context with Conventions

**Convention:** Context includes BOTH input arguments and result data, with namespacing:

```python
context = {
    "args": {  # Input arguments from each step
        "admin_user_create": {"name": "test-user-123", "email": "...", "role": "..."},
    },
    "results": {  # Output results from each step
        "admin_user_create": {"success": True, "user": {...}, "message": "..."},
    },
    "latest": {  # Flattened view of most recent relevant data
        "name": "test-user-123",
        "email": "...",
        "role": "...",
        "user": {...},
    }
}
```

**Argument resolution:**

1. Check if param exists in `context["latest"]`
2. If not found, check `context["args"][<most recent matching step>]`
3. If not found, error

**Pros:** Automatic for common cases
**Cons:** Still need fallback rules, can be confusing

---

### Option C: Just Pass Arguments Through

**Simplest approach:** Test config defines arguments for EACH tool in loop:

```yaml
tool_loops:
  admin_user_basic:
    - tool: admin_user_create
      args:
        name: test-loop-user-{uuid}
        email: test@example.com
        role: viewer

    - tool: admin_user_get
      args:
        name: test-loop-user-{uuid}  # Same value

    - tool: admin_user_delete
      args:
        name: test-loop-user-{uuid}  # Same value
```

**Template substitution:** `{uuid}` replaced with unique ID at runtime.

**Pros:**

- Dead simple to understand
- No magic context passing
- YAML is the single source of truth

**Cons:**

- Repetitive (name appears 3 times)
- Can't reference result data (e.g., if create returns modified name)

---

### Option D: Hybrid - Explicit Args + Smart Defaults

```yaml
tool_loops:
  admin_user_basic:
    shared_args:  # Arguments used across steps
      name: test-loop-user-{uuid}

    steps:
      - tool: admin_user_create
        args:
          # name: inherited from shared_args
          email: test@example.com
          role: viewer

      - tool: admin_user_get
        # args.name: inherited from shared_args

      - tool: admin_user_delete
        # args.name: inherited from shared_args
```

**Pros:**

- Less repetition
- Still explicit
- Easy to override per-step if needed

**Cons:**

- Still can't reference result data
- Adds one more concept (shared_args)

---

## Decision: Option C (Just Pass Arguments Through)

**Chosen approach: Option C with template substitution**

### Why Option C

1. **Transparent** - YAML config is single source of truth
2. **Debuggable** - No hidden context passing or magic resolution
3. **Explicit** - Each tool's arguments clearly specified
4. **Simple** - Repetition is better than complexity

### Implementation Plan

Core features:

```yaml
tool_loops:
  admin_user_basic:
    - tool: admin_user_create
      args:
        name: test-loop-user-{uuid}
        email: test-{uuid}@example.com
        role: viewer

    - tool: admin_user_get
      args:
        name: test-loop-user-{uuid}

    - tool: admin_user_reset_password
      args:
        name: test-loop-user-{uuid}

    - tool: admin_user_delete
      args:
        name: test-loop-user-{uuid}
```

Template substitution:

- `{uuid}` → unique ID per test run (e.g., `abc123`)
- `{env.BUCKET}` → from environment variable
- `{env.REGISTRY}` → from environment variable

Optional (if needed later):

- `{step[0].result.user.name}` → reference previous step result
- Only add if tools transform values in ways we can't predict

### Estimated Implementation

- YAML parsing and loop definition: **~50 lines**
- Template substitution engine: **~50 lines**
- Loop executor (run tools in sequence): **~100 lines**
- Coverage checker (ensure all tools tested): **~50 lines**

**Total: ~250 lines** (simple, testable, maintainable)

---

## Next Steps

1. **Define TOOL_LOOPS in YAML** (scripts/tests/tool-loops.yaml)
2. **Implement template substitution** in mcp-test.py
3. **Implement loop executor** in mcp-test.py
4. **Add coverage validation** to ensure 100% tool coverage
5. **Test with real credentials** (start with admin_user loop)
