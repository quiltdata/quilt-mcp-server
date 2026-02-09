# Analysis: Registry Format Bug in _backend_push_package

## The Error

```
Error: Failed to create package: Package creation failed:
Can only 'push' to remote registries in S3, but 'quilt-ernest-staging' is a local file.
To store a package in the local registry, use 'build' instead.
```

## Key Facts

1. **`quilt-ernest-staging` IS AN S3 BUCKET** - not a local file path
2. **Nobody should be building local packages** - this is a server, not a local dev tool
3. **`selector_fn_copy_local`** is a built-in Quilt function with specific semantics:
   - Copies LOCAL files (file:// paths) to the destination bucket
   - Does NOT copy S3 objects - they retain their existing physical keys
   - This is the correct way to handle mixed local/S3 sources

## The Real Problem

The error message reveals that `quilt3.Package.push()` is receiving the registry parameter as:
- ❌ `'quilt-ernest-staging'` (bare bucket name)
- ✅ Should be: `'s3://quilt-ernest-staging'`

## Code Flow Analysis

### 1. Entry Point: `package_create()` in `src/quilt_mcp/tools/packages.py`

Lines 1175-1202:
```python
normalized_registry = _normalize_registry(registry)  # Adds s3:// prefix

# Use QuiltOps.create_package_revision method
quilt_ops = QuiltOpsFactory.create()
result = quilt_ops.create_package_revision(
    package_name=package_name,
    s3_uris=s3_uris,
    metadata=processed_metadata,
    registry=normalized_registry,  # ✅ Has s3:// prefix here
    message=message,
    auto_organize=False,
    copy=copy,
)
```

### 2. Template Method: `create_package_revision()` in `src/quilt_mcp/ops/quilt_ops.py`

Lines 1410-1411:
```python
# STEP 5: PUSH PACKAGE (backend primitive)
top_hash = self._backend_push_package(package, package_name, registry, message, copy)
```

Registry is passed through unchanged - still has `s3://` prefix.

### 3. Backend: `_backend_push_package()` in `src/quilt_mcp/backends/quilt3_backend.py`

Lines 143-152:
```python
# Push the package
if copy:
    # Deep copy objects to registry bucket
    top_hash = quilt3_pkg.push(package_name, registry=registry, message=message)
else:
    # Shallow references only (no copy)
    # selector_fn returns False to preserve original physical keys without copying
    top_hash = quilt3_pkg.push(
        package_name, registry=registry, message=message, selector_fn=lambda logical_key, entry: False
    )
```

**This is where the registry is passed to quilt3.** If the error is happening here, then either:
1. The `registry` parameter arriving here doesn't have the `s3://` prefix, OR
2. There's code somewhere that strips it, OR
3. Something else is calling this with a bare bucket name

## Hypothesis: Where is the s3:// Prefix Being Stripped?

Need to check:
1. Is there any code in the call chain that extracts bucket name from registry URI?
2. Is there any platform backend code that transforms the registry?
3. Is the test configuration passing bare bucket names?

## Misunderstanding About selector_fn

The current code uses:
```python
selector_fn=lambda logical_key, entry: False
```

This tells Quilt: "Don't copy anything, keep all original physical keys"

But Quilt provides `selector_fn_copy_local` which:
- Copies LOCAL files to the target bucket
- Preserves S3 physical keys (doesn't copy S3→S3)

**Question:** Should we be using `quilt3.util.selector_fn_copy_local` instead of the lambda?

## Next Steps for Investigation

1. Add debug logging to track registry parameter through the entire call chain
2. Check if test configuration is passing bare bucket names without s3:// prefix
3. Look for any code that might be extracting bucket name from s3:// URI
4. Check if platform_backend has different behavior
5. Verify what the test environment's QUILT_TEST_BUCKET value is set to

## What We Should NOT Do

❌ Add code to detect if registry starts with s3:// and switch between push() and build()
❌ This is not about local vs remote - all registries are S3 buckets
❌ build() is for local development, not for this MCP server

## What the Fix Likely Is

✅ Find where the s3:// prefix is being stripped from the registry parameter
✅ Ensure registry always arrives at _backend_push_package with s3:// prefix
✅ Possibly replace `selector_fn=lambda: False` with `selector_fn=selector_fn_copy_local`
