# Task 2: Read-Only Filesystem - Analysis & Resolution

**Status**: ✅ Complete
**Created**: 2026-01-28
**Task**: Fix `test_no_filesystem_writes_outside_tmpfs` failure

## Problem Statement

The test `test_no_filesystem_writes_outside_tmpfs` was failing, reporting that the container wrote files to `/app` directory despite read-only filesystem constraints.

## Investigation

### Initial Hypothesis

The spec suggested multiple potential causes:

- quilt3 creating cache/config directories
- Application writing logs or temporary files
- Missing `HOME=/tmp` environment variable redirection

### Actual Findings

After running `docker diff` on a stateless container:

```bash
C /app
A /app/.cache
```

**Analysis**:

- `C /app` - Directory metadata changed (not a write violation)
- `A /app/.cache` - Tmpfs mount added (expected, allowed)

The `/app` directory shows as "Changed" because mounting tmpfs at `/app/.cache` modifies the parent directory's metadata (timestamps, inode changes). This is a **false positive** - no actual files were written outside tmpfs.

## Root Cause

The test helper `get_container_filesystem_writes()` in [tests/stateless/conftest.py](../../tests/stateless/conftest.py) was:

1. Correctly filtering out tmpfs directories (`/tmp`, `/app/.cache`, `/run`)
2. **Incorrectly** flagging `/app` metadata changes as a violation

## Solution

Added logic to ignore parent directory metadata changes when tmpfs is mounted inside:

```python
# Ignore parent directory metadata changes (C) when tmpfs is mounted inside
# e.g., "C /app" is expected when "/app/.cache" tmpfs is mounted
if change_type == "C" and path == "/app":
    continue
```

### Files Modified

1. **[tests/stateless/conftest.py:206-209](../../tests/stateless/conftest.py#L206-L209)**
   - Added check to ignore `/app` metadata changes from tmpfs mounts

2. **[tests/stateless/conftest.py:82](../../tests/stateless/conftest.py#L82)**
   - Added `MCP_JWT_SECRET` for container startup (unrelated fix discovered during testing)

3. **[make.dev:146](../../make.dev#L146)**
   - Added `QUILT_DISABLE_CACHE=true` to test environment (belt-and-suspenders)

## Verification

```bash
$ export TEST_DOCKER_IMAGE=quilt-mcp:test && \
  export QUILT_DISABLE_CACHE=true && \
  export PYTHONPATH="src" && \
  uv run python -m pytest tests/stateless/test_basic_execution.py::test_no_filesystem_writes_outside_tmpfs -v

tests/stateless/test_basic_execution.py::test_no_filesystem_writes_outside_tmpfs PASSED [100%]
```

✅ Test now passes.

## Why This Matters

**False positives are dangerous in security tests** - they can lead to:

1. Ignoring real issues ("it's just another false positive")
2. Wasted time investigating non-issues
3. Loss of confidence in the test suite

This fix ensures the test accurately detects **actual** filesystem write violations while ignoring expected metadata changes.

## Assumptions & Configuration

### Current Configuration ✅

The stateless container is already correctly configured:

1. **Read-only root filesystem**: `--read-only` flag enabled
2. **Tmpfs mounts**:
   - `/tmp` (100M)
   - `/app/.cache` (50M)
   - `/run` (10M)
3. **Environment variables**:
   - `HOME=/tmp` - Redirects user files to tmpfs
   - `QUILT_DISABLE_CACHE=true` - Prevents cache writes
   - `MCP_JWT_SECRET` - Required for JWT mode

### No Application Changes Required ✅

The application code does NOT need modification:

- No actual filesystem writes are occurring outside tmpfs
- quilt3 is behaving correctly with `QUILT_DISABLE_CACHE=true`
- The container runs successfully with `--read-only` flag
- All legitimate writes go to tmpfs directories

## Related Work

This fix completes Phase 3 of [03-fix-stateless.md](./03-fix-stateless.md):

- ✅ **Task 2**: Enforce read-only filesystem
- ⏳ **Task 1**: Fix MCP protocol endpoint routing (remaining)
- ⏳ **Tasks 3 & 4**: JWT error messages (remaining)

## Docker Diff Output Reference

For future debugging, expected `docker diff` output for stateless containers:

```bash
# Expected changes (all in tmpfs):
C /tmp                    # Metadata change (tmpfs mount)
A /tmp/...               # Files written to tmpfs

C /app                    # Metadata change (tmpfs mounted inside)
A /app/.cache            # Tmpfs mount
A /app/.cache/...        # Files written to tmpfs

C /run                    # Metadata change (tmpfs mount)
A /run/...               # Files written to tmpfs
```

Any other paths indicate an actual write violation.

## Testing Recommendations

1. **Run full suite**: `make test-stateless` should pass this test
2. **Manual verification**: `docker diff <container>` should show only tmpfs changes
3. **Regression testing**: Add this scenario to CI/CD pipeline

## Conclusion

**The filesystem write test was failing due to a false positive, not an actual violation.**

The container was already properly configured with:

- Read-only root filesystem
- Appropriate tmpfs mounts
- Correct environment variables

The fix improved test accuracy without requiring any application code changes.
