# MCP Test Config Compatibility Errors

**Status**: Configuration errors in mcp-test.yaml
**Date**: 2026-02-08
**Severity**: HIGH - Tests failing due to config/API signature mismatches

## Problem Summary

The `mcp-test.yaml` configuration file contains parameters that don't match the actual MCP tool signatures, causing 6 test loops to fail. This is a **config generation issue** in `mcp-test-setup.py`.

---

## Failing Loops & Root Causes

### 1. admin_user_modifications ❌

**Error**:
```
2 validation errors for call[admin_user_set_admin]
admin
  Missing required argument
is_admin
  Unexpected keyword argument
```

**Loop Configuration** (line ~1830):
```yaml
- tool: admin_user_set_admin
  args:
    name: tlu{uuid}
    is_admin: true  # ❌ WRONG PARAMETER NAME
```

**Actual Function Signature** ([governance_service.py:535](../../src/quilt_mcp/services/governance_service.py#L535)):
```python
async def admin_user_set_admin(
    name: str,
    admin: bool,  # ✅ Expects 'admin', not 'is_admin'
    ...
)
```

**Fix**: Change `is_admin` → `admin` in loop definition.

---

### 2. admin_sso_config ❌

**Error**:
```
InvalidInput: errors=[
  ValidationError(path='config.version', message='field required'),
  ValidationError(path='config.mappings', message='field required'),
  ValidationError(path='config.default_role', message='field required')
]
```

**Loop Configuration** (line ~1857):
```yaml
- tool: admin_sso_config_set
  args:
    config:
      provider: test-{uuid}
      saml_config: <test_sso_config>test config</test_sso_config>
      # ❌ MISSING: version, mappings, default_role
```

**Actual Backend Requirements**:
The Quilt platform backend expects SSO configs to have:
- `version` (required)
- `mappings` (required)
- `default_role` (required)

**Fix**: Add minimal required fields to config dictionary:
```yaml
config:
  version: 1
  provider: test-{uuid}
  saml_config: <test_sso_config>test config</test_sso_config>
  mappings: []
  default_role: User
```

---

### 3. package_lifecycle ❌

**Error**:
```
Failed to create package: Invalid S3 URI at index 0: must start with 's3://'
```

**Loop Configuration** (line ~1711):
```yaml
- tool: package_create
  args:
    package_name: testuser/loop-pkg-{uuid}
    registry: '{env.QUILT_TEST_BUCKET}'
    s3_uris:
    - '{env.QUILT_TEST_BUCKET}/test-data/sample.csv'  # ❌ MISSING s3:// PREFIX
```

**Function Signature** ([packages.py:1039](../../src/quilt_mcp/tools/packages.py#L1039)):
```python
def package_create(
    ...
    s3_uris: Annotated[
        list[str],
        Field(
            description="List of S3 URIs to include in the package",
            examples=[["s3://bucket/file1.csv", "s3://bucket/file2.json"]],  # ✅ Must have s3:// prefix
        ),
    ],
    ...
)
```

**Fix**: Add `s3://` prefix:
```yaml
s3_uris:
- 's3://{env.QUILT_TEST_BUCKET}/test-data/sample.csv'
```

---

### 4. package_create_from_s3_loop ❌

**Error**:
```
Cannot create package in target registry
```

**Loop Configuration** (line ~1738):
```yaml
- tool: package_create_from_s3
  args:
    source_bucket: '{env.QUILT_TEST_BUCKET}'
    package_name: testuser/s3-pkg-{uuid}
    # ❌ MISSING: target_registry (required parameter)
```

**Function Signature** ([packages.py:1554](../../src/quilt_mcp/tools/packages.py#L1554)):
```python
def package_create_from_s3(
    source_bucket: str,
    package_name: str,
    target_registry: str,  # ✅ REQUIRED - no default value
    ...
)
```

**Fix**: Add target_registry parameter:
```yaml
args:
  source_bucket: '{env.QUILT_TEST_BUCKET}'
  package_name: testuser/s3-pkg-{uuid}
  target_registry: '{env.QUILT_TEST_BUCKET}'
```

---

### 5. bucket_objects_write ❌

**Error**:
```
1 validation error for call[bucket_object_fetch]
s3_uri
  String should match pattern '^s3://[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]/.+'
```

**Loop Configuration** (line ~1752):
```yaml
- tool: bucket_object_fetch
  args:
    s3_uri: '{env.QUILT_TEST_BUCKET}/test-loop-{uuid}.txt'  # ❌ MISSING s3:// PREFIX
    max_bytes: 1000
```

**Function Signature** ([buckets.py:570](../../src/quilt_mcp/tools/buckets.py#L570)):
```python
def bucket_object_fetch(
    s3_uri: Annotated[
        str,
        Field(
            pattern=r"^s3://[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]/.+",  # ✅ Must start with s3://
        ),
    ],
    ...
)
```

**Fix**: Add `s3://` prefix:
```yaml
s3_uri: 's3://{env.QUILT_TEST_BUCKET}/test-loop-{uuid}.txt'
```

---

### 6. tabulator_table_lifecycle ❌

**Error**:
```
Invalid configuration: config.schema.0.type: unexpected value;
permitted: 'BOOLEAN', 'TINYINT', 'SMALLINT', 'INT', 'BIGINT', 'FLOAT', 'DOUBLE', 'STRING', 'BINARY', 'DATE', 'TIMESTAMP'
```

**Loop Configuration** (line ~1799):
```yaml
- tool: tabulator_table_create
  args:
    bucket_name: '{env.QUILT_TEST_BUCKET}'
    table_name: test_table_{uuid}
    schema:
    - name: col1
      type: string  # ❌ lowercase 'string' - should be uppercase 'STRING'
```

**Backend Requirement**:
Tabulator expects SQL-style uppercase type names matching AWS Athena/Glue data types.

**Fix**: Change to uppercase:
```yaml
schema:
- name: col1
  type: STRING  # ✅ Uppercase
```

---

## Root Cause Analysis

### Where the Problem Originates

The issues stem from **`mcp-test-setup.py`** which generates `mcp-test.yaml`. The setup script:

1. **Doesn't validate S3 URI format** - generates bare bucket/key paths without `s3://` prefix
2. **Uses incorrect parameter names** - maps to `is_admin` instead of `admin`
3. **Doesn't include required fields** - missing SSO config fields, target_registry parameter
4. **Uses wrong case conventions** - lowercase SQL types instead of uppercase

### Why This Happened

The setup script likely:
- Uses template values (`test_value`) that aren't replaced with valid data
- Doesn't parse function signatures to extract actual parameter names
- Doesn't validate generated configs against actual tool schemas
- Copies old/outdated parameter names from previous iterations

---

## Solution Approaches

### Option 1: Fix mcp-test-setup.py (Recommended)

Update the setup script to generate correct configs:

1. **Add S3 URI validation** - Ensure all S3 paths have `s3://` prefix
2. **Parse actual tool signatures** - Extract parameter names from tool definitions
3. **Include all required params** - Don't omit parameters like target_registry
4. **Use correct enum values** - Uppercase SQL types for tabulator

### Option 2: Manual YAML Fixes

Directly edit `mcp-test.yaml` to fix the 6 failing loops (quick fix for immediate testing).

### Option 3: Hybrid Approach

1. Manual fixes to unblock testing NOW
2. Update setup script to prevent regression

---

## Immediate Action Items

**Priority 1 (Manual Fixes)**:
- [ ] Fix `admin_user_modifications`: change `is_admin` → `admin`
- [ ] Fix `package_lifecycle`: add `s3://` to s3_uris
- [ ] Fix `bucket_objects_write`: add `s3://` to s3_uri
- [ ] Fix `tabulator_table_lifecycle`: uppercase schema type
- [ ] Fix `admin_sso_config`: add version/mappings/default_role
- [ ] Fix `package_create_from_s3_loop`: add target_registry

**Priority 2 (Prevent Regression)**:
- [ ] Update `mcp-test-setup.py` to generate valid configs
- [ ] Add validation step that checks generated YAML against tool schemas
- [ ] Add unit tests for config generation

---

## Related Issues

- See [spec/a18-mcp-test/19-test-config-fixes.md](19-test-config-fixes.md) for earlier SSO config discussion
- See [spec/a10-no-default-registry.md](../a10-no-default-registry.md) for registry parameter requirements

---

## Decision

**Recommendation**: Use **Option 3 (Hybrid)** - manual fixes NOW + setup script fixes to prevent future issues.

This unblocks testing immediately while ensuring the root cause is addressed.
