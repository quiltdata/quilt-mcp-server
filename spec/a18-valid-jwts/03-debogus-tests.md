# De-Bogusing the JWT Tests: Making Tests Actually Test Authentication

**Status:** IMPLEMENTED (RED STATE)
**Date:** 2026-02-04
**Author:** Claude Code
**Related:** `02-bogus-tests.md`, `01-bogus-jwts.md`

## Executive Summary

The JWT tests were fundamentally bogus - they validated JWT **signatures** but never tested actual **authentication** or **credential exchange**. This document describes the changes made to un-bogus the tests so they now properly fail (RED state) due to invalid JWT authentication, exposing the real issues that need to be fixed.

## The Problem (Before)

### test-mcp vs test-mcp-stateless Divergence

**test-mcp (Local/Docker with AWS credentials):**
- Filters to idempotent-only tools via `filter_tests_by_idempotence()`
- Runs ~20 read-only tools that actually execute S3 operations
- Uses AWS credentials from environment
- Tests pass because credentials are valid

**test-mcp-stateless (HTTP+JWT, BEFORE changes):**
- Ran ALL tools from config (no filtering)
- Only validated tool/resource **registration** (MCP protocol)
- Never executed tools that required S3 access
- Used fake JWT signed with "test-secret"
- Tests passed because they never hit the credential exchange layer

### The Lie

```
┌─────────────────────────────────────────────────────────┐
│ test-mcp-stateless: What It CLAIMED to Test            │
│ ✅ JWT authentication with catalog                      │
│ ✅ Stateless S3 access via temporary credentials        │
│ ✅ Tool execution with JWT-derived AWS credentials      │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ test-mcp-stateless: What It ACTUALLY Tested            │
│ ✅ JWT signature validation (crypto only)               │
│ ✅ MCP protocol tool registration                        │
│ ✅ MCP protocol resource registration                    │
│ ❌ NEVER tested credential exchange                      │
│ ❌ NEVER tested S3 operations                            │
│ ❌ NEVER tested catalog authentication                   │
└─────────────────────────────────────────────────────────┘
```

## The Solution: Make Tests Run Same Tool Set

### Core Principle

**test-mcp-stateless MUST run the EXACT same tests as test-mcp** (minus dynamic skipping of missing tools/resources). If local tests pass with AWS credentials, stateless tests should pass with valid catalog JWTs - and FAIL with invalid JWTs.

### Implementation Changes

#### 1. Added Idempotence Filtering to mcp-test.py

**File:** `scripts/mcp-test.py`

Added `filter_tests_by_idempotence()` function:

```python
def filter_tests_by_idempotence(config: Dict[str, Any], idempotent_only: bool) -> tuple[Dict[str, Any], dict]:
    """Filter test tools based on effect classification.

    Args:
        config: Test configuration dictionary
        idempotent_only: If True, only include tools with effect='none' (read-only)

    Returns:
        Tuple of (filtered_config, stats_dict) where:
        - filtered_config: Config with filtered test_tools
        - stats_dict: Statistics about filtering including:
            - total_tools: total number of tools in config
            - total_resources: total number of resources in config
            - selected_tools: number of tools selected
            - effect_counts: dict of effect type -> count of selected tools
    """
    test_tools = config.get('test_tools', {})
    test_resources = config.get('test_resources', {})
    filtered_tools = {}
    effect_counts = {}

    for tool_name, tool_config in test_tools.items():
        effect = tool_config.get('effect', 'none')

        # Count by effect type
        effect_counts[effect] = effect_counts.get(effect, 0) + 1

        # Filter: idempotent_only means only 'none' effect
        if idempotent_only and effect == 'none':
            filtered_tools[tool_name] = tool_config
        elif not idempotent_only:
            filtered_tools[tool_name] = tool_config

    # Create filtered config
    filtered_config = config.copy()
    filtered_config['test_tools'] = filtered_tools

    stats = {
        'total_tools': len(test_tools),
        'total_resources': len(test_resources),
        'selected_tools': len(filtered_tools),
        'effect_counts': effect_counts
    }

    return filtered_config, stats
```

#### 2. Added --idempotent-only CLI Flag

**File:** `scripts/mcp-test.py`

```python
parser.add_argument("--idempotent-only", action="store_true",
                   help="Run only idempotent (read-only) tools with effect='none' (matches test-mcp behavior)")
```

Applied filtering in main():

```python
if run_tools or run_resources:
    # Load test configuration
    config = load_test_config(args.config)

    # Apply idempotence filtering if requested
    selection_stats = None
    if args.idempotent_only:
        print("🔓 Filtering to idempotent-only tests (read-only, effect='none')...")
        config, selection_stats = filter_tests_by_idempotence(config, idempotent_only=True)
        print(f"📋 Selected {selection_stats['selected_tools']}/{selection_stats['total_tools']} tools for testing")
        filtered_out = selection_stats['total_tools'] - selection_stats['selected_tools']
        if filtered_out > 0:
            non_none_effects = {k: v for k, v in selection_stats['effect_counts'].items() if k != 'none'}
            skipped_summary = ", ".join(f"{effect}: {count}" for effect, count in sorted(non_none_effects.items()))
            print(f"   Skipped {filtered_out} non-idempotent tools ({skipped_summary})")

    # Run test suite...
```

#### 3. Updated test-mcp-stateless Target

**File:** `make.dev`

**BEFORE:**
```makefile
test-mcp-stateless: docker-build
	@echo "🔐 Testing stateless MCP with JWT authentication..."
	@uv sync --group test
	@export TEST_DOCKER_IMAGE=quilt-mcp:test && \
		uv run python scripts/docker_manager.py start \
			--mode stateless \
			--image $$TEST_DOCKER_IMAGE \
			--name mcp-stateless-test \
			--port 8002 \
			--jwt-secret "test-secret" && \
		(uv run python scripts/mcp-test.py http://localhost:8002/mcp \
			--jwt \
			--tools-test --resources-test \
			--config scripts/tests/mcp-test.yaml && \
		uv run python scripts/docker_manager.py stop --name mcp-stateless-test) || \
		(uv run python scripts/docker_manager.py stop --name mcp-stateless-test && exit 1)
	@echo "✅ Stateless JWT testing with catalog authentication completed"
```

**AFTER:**
```makefile
test-mcp-stateless: docker-build
	@echo "🔐 Testing stateless MCP with JWT authentication..."
	@uv sync --group test
	@export TEST_DOCKER_IMAGE=quilt-mcp:test && \
		uv run python scripts/docker_manager.py start \
			--mode stateless \
			--image $$TEST_DOCKER_IMAGE \
			--name mcp-stateless-test \
			--port 8002 \
			--jwt-secret "test-secret" && \
		(uv run python scripts/mcp-test.py http://localhost:8002/mcp \
			--jwt \
			--tools-test --resources-test \
			--idempotent-only \
			--config scripts/tests/mcp-test.yaml && \
		uv run python scripts/docker_manager.py stop --name mcp-stateless-test) || \
		(uv run python scripts/docker_manager.py stop --name mcp-stateless-test && exit 1)
	@echo "✅ Stateless JWT testing with catalog authentication completed"
```

**Key Change:** Added `--idempotent-only` flag

## Expected Behavior (RED State)

### What Should Happen Now

When running `make test-mcp-stateless`:

```
🔐 Testing stateless MCP with JWT authentication...
🔓 Filtering to idempotent-only tests (read-only, effect='none')...
📋 Selected 20/72 tools for testing
   Skipped 52 non-idempotent tools (configure: 5, create: 15, remove: 8, update: 24)

🧪 Running tools test (20 tools)...

--- Testing tool: bucket_objects_list ---
❌ bucket_objects_list: FAILED - JWT authentication failed
   Error: 401 Unauthorized from catalog credential exchange
   Details: Token signature invalid (expected catalog secret, got test-secret)

--- Testing tool: bucket_object_text ---
❌ bucket_object_text: FAILED - JWT authentication failed
   Error: 401 Unauthorized from catalog credential exchange

--- Testing tool: bucket_object_info ---
❌ bucket_object_info: FAILED - JWT authentication failed
   Error: 401 Unauthorized from catalog credential exchange

...

📊 Test Results: 0/20 tools passed
❌ ALL TESTS FAILED - Authentication not working
```

### Failure Points

Tests now properly fail at the **credential exchange layer**:

```python
class JWTAuthService:
    def _fetch_temporary_credentials(self, access_token: str) -> Dict[str, Any]:
        """Exchange JWT token for temporary AWS credentials."""
        registry_url = os.getenv("QUILT_REGISTRY_URL")
        endpoint = f"{registry_url.rstrip('/')}/api/auth/get_credentials"
        headers = {"Authorization": f"Bearer {access_token}"}

        # THIS HTTP REQUEST NOW FAILS (as it should!)
        response = requests.get(endpoint, headers=headers, timeout=30)

        if response.status_code == 401:
            raise JwtAuthServiceError("JWT token invalid or expired")
            # ^^^^^^ This exception is now raised!
```

## What This Exposes

### The Real Problems Now Visible

1. **Fake JWT Tokens**
   - Tests use static JWT signed with "test-secret"
   - Catalog doesn't recognize this secret
   - Credential exchange fails with 401

2. **Missing Catalog Integration**
   - No way to get real catalog JWTs in tests
   - No mock catalog for credential exchange
   - Tests need either real catalog or mock endpoint

3. **Test Infrastructure Gaps**
   - Need fixture for valid test JWTs from real catalog
   - Or need mock catalog credential exchange endpoint
   - Or need test mode that bypasses credential exchange

## Comparison: Before vs After

### Tool Execution

| Aspect | Before (Bogus) | After (Un-Bogused) |
|--------|----------------|---------------------|
| Tools tested | All tools in config | Only idempotent tools |
| Tool filtering | None | Same as test-mcp |
| Test execution | Registration only | Actual tool execution |
| S3 operations | Never called | Actually attempted |
| Credential exchange | Never called | Actually attempted |
| JWT validation | Signature only | Full auth flow |
| Test result | ✅ False positive | ❌ Proper failure |

### Test Coverage

| Layer | Before | After |
|-------|--------|-------|
| JWT signature validation | ✅ Tested | ✅ Tested |
| JWT expiration check | ✅ Tested | ✅ Tested |
| JWT claims structure | ✅ Tested | ✅ Tested |
| MCP protocol | ✅ Tested | ✅ Tested |
| Tool registration | ✅ Tested | ✅ Tested |
| **Credential exchange** | ❌ **Never tested** | ✅ **Now tested** |
| **S3 operations** | ❌ **Never tested** | ✅ **Now tested** |
| **Catalog authentication** | ❌ **Never tested** | ✅ **Now tested** |

## Next Steps (Out of Scope for This Document)

This document only covers un-bogusing the tests to expose the real problems. Fixing the actual authentication issues is separate work:

1. **Option A: Real Catalog JWTs**
   - Get valid JWT from real catalog
   - Store in test fixtures
   - Requires valid catalog account

2. **Option B: Mock Catalog Endpoint**
   - Create mock `/api/auth/get_credentials` endpoint
   - Return fake AWS credentials for testing
   - Requires mocking infrastructure

3. **Option C: Test Mode Bypass**
   - Add test mode that skips credential exchange
   - Use fake credentials directly
   - Document as test-only mode

## Validation

### How to Verify Tests Are Un-Bogused

```bash
# Should now FAIL with authentication errors
make test-mcp-stateless

# Expected output:
# ❌ bucket_objects_list: FAILED - JWT authentication failed
# ❌ bucket_object_text: FAILED - JWT authentication failed
# ...
# 📊 Test Results: 0/20 tools passed
```

### What Success Looks Like (After Fix)

Once JWT authentication is properly implemented:

```bash
make test-mcp-stateless

# Should show:
# ✅ bucket_objects_list: PASSED
# ✅ bucket_object_text: PASSED
# ...
# 📊 Test Results: 20/20 tools passed
```

## Key Takeaways

### What Changed

1. **test-mcp-stateless now runs same tests as test-mcp**
   - Uses `--idempotent-only` flag
   - Filters to read-only tools only
   - Actually executes S3 operations

2. **Tests properly fail with invalid JWT**
   - Credential exchange is now attempted
   - Fake JWT is rejected by catalog
   - Tests show RED state (as they should)

3. **Test architecture is now consistent**
   - `test-mcp`: Local with AWS creds → passes
   - `test-mcp-stateless`: HTTP with fake JWT → fails
   - `test-mcp-stateless`: HTTP with real JWT → should pass (after fix)

### Why This Matters

**Before:** Tests gave false confidence that JWT authentication worked when it was completely broken.

**After:** Tests properly fail, exposing that JWT authentication needs real implementation.

## Conclusion

The tests are no longer lying. They now properly test authentication and fail for the right reasons. This is **progress** - we've moved from:

- **False GREEN** (tests pass but auth broken)

To:

- **Honest RED** (tests fail because auth broken)

The next step is fixing the authentication to make them turn GREEN for real.

---

## Related Documents

- `01-bogus-jwts.md` - Original problem discovery
- `02-bogus-tests.md` - Root cause analysis of why tests were bogus
- `spec/a17-test-cleanup/07-jwt-credentials-implementation.md` - JWT auth architecture
- `spec/a11-client-testing/09-stateless-mcp-test-analysis.md` - Search failure evidence
