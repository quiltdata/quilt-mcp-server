# Migration Guide: v0.8.x → v0.9.0

## Overview

Version 0.9.0 introduces **breaking changes** to dramatically simplify tool schemas for better LLM usability. This guide helps you migrate from v0.8.x to v0.9.0.

---

## Summary of Breaking Changes

### 1. Removed Internal Testing Flags

**All internal testing/automation flags have been removed:**
- `dry_run` - Preview mode removed
- `force` - Confirmation skipping removed
- `confirm_structure` - User confirmation workflows removed
- `auto_organize` - Now always enabled (best practice)
- `generate_readme` - Now always enabled (best practice)

### 2. PackageCreateFromS3Params Simplified (15 → 5 parameters)

**Removed parameters:**
- `target_registry` - Now auto-discovered based on bucket patterns
- `include_patterns` - Use `preset` or `filter` instead
- `exclude_patterns` - Use `preset` or `filter` instead
- `metadata_template` - Bundled in presets
- `copy_mode` - Bundled in presets

**Renamed parameters:**
- `source_prefix` → `prefix` (brevity)

**New parameters:**
- `preset` - Apply predefined configuration bundles
- `filter` - Natural language file filtering

### 3. BucketObjectsPutParams Flattened

**Removed nested model:**
- `BucketObjectsPutItem` class removed

**Changed parameter type:**
- `items: list[BucketObjectsPutItem | dict]` → `items: list[dict[str, Any]]`

---

## Migration Examples

### Removing `dry_run`

**Before (v0.8.x):**
```python
from quilt_mcp.tools import package_create_from_s3

# Preview mode
result = package_create_from_s3(
    source_bucket="my-bucket",
    package_name="team/dataset",
    dry_run=True  # Preview only, don't create
)

if result.action == "preview":
    print("Preview:", result.structure)
    # User confirms, then run again with dry_run=False
```

**After (v0.9.0):**
```python
from quilt_mcp.tools import package_create_from_s3

# Tools now always execute - no preview mode
# Use package_browse() to inspect existing packages instead
result = package_create_from_s3(
    source_bucket="my-bucket",
    package_name="team/dataset"
)

# Package is created immediately
print("Created:", result.package_url)
```

**Alternative:** For complex workflows requiring confirmation, use tool composition:
1. List files with `bucket_objects_list()`
2. Preview structure in your application
3. Create package with `package_create_from_s3()`

---

### PackageCreateFromS3Params: Using Presets

**Before (v0.8.x) - 9 parameters:**
```python
package_create_from_s3(
    source_bucket="ml-experiments",
    package_name="team/model-v1",
    source_prefix="models/",
    include_patterns=["*.pkl", "*.h5", "*.json", "*.pt"],
    exclude_patterns=["*.tmp", "*.log", "checkpoints/*"],
    metadata_template="ml",
    copy_mode="all",
    target_registry="s3://ml-registry",
    description="Best model from experiment 42"
)
```

**After (v0.9.0) - 3 parameters with preset:**
```python
package_create_from_s3(
    source_bucket="ml-experiments",
    package_name="team/model-v1",
    prefix="models/",  # Renamed from source_prefix
    preset="ml-model",  # Bundles 7 settings above
    description="Best model from experiment 42"
)
```

**Available Presets:**

| Preset | Bundles | Use Case |
|--------|---------|----------|
| `simple` | Basic settings | General data (90% of use cases) |
| `csv-only` | CSV patterns + analytics | CSV reports/datasets |
| `ml-model` | ML file patterns (6 types) + ml template | ML models/experiments |
| `genomics` | Genomics patterns (10 types) + reference-only | Large genomics files |
| `analytics` | Analytics patterns (8 types) + analytics template | Analytics pipelines |

---

### PackageCreateFromS3Params: Using Natural Language Filters

**Before (v0.8.x) - Complex glob patterns:**
```python
package_create_from_s3(
    source_bucket="data-bucket",
    package_name="team/analysis",
    include_patterns=["*.csv", "*.json", "*.parquet"],
    exclude_patterns=["*.tmp", "*temp*", "temp/*", "*.log"]
)
```

**After (v0.9.0) - Natural language:**
```python
package_create_from_s3(
    source_bucket="data-bucket",
    package_name="team/analysis",
    filter="include CSV, JSON, and Parquet files but exclude temp files and logs"
)
```

**Natural Language Filter Examples:**

| Natural Language | Result |
|------------------|--------|
| "only CSV files" | `include: ["*.csv"]` |
| "include images except thumbnails" | `include: ["*.jpg", "*.png", "*.gif"], exclude: ["*thumb*", "*thumbnail*"]` |
| "Python files excluding tests" | `include: ["*.py"], exclude: ["test_*.py", "tests/*"]` |

**Requirements:**
- Set `ANTHROPIC_API_KEY` environment variable
- ~200-500ms latency for parsing (one-time cost)
- ~$0.0001 per parse using Claude Haiku

---

### PackageCreateFromS3Params: Parameter Priority

Understanding the priority order when multiple options are used:

**Priority: Explicit Params > Filter > Preset**

```python
# Example: All three specified
package_create_from_s3(
    source_bucket="bucket",
    package_name="team/pkg",
    preset="csv-only",  # Sets include_patterns=["*.csv"]
    filter="only JSON files",  # Overrides preset, sets include_patterns=["*.json"]
    include_patterns=["*.parquet"]  # Explicit wins, final: ["*.parquet"]
)
```

**Result:** `include_patterns = ["*.parquet"]` (explicit parameter wins)

---

### BucketObjectsPutParams: Flattening Nested Models

**Before (v0.8.x) - Nested Pydantic model:**
```python
from quilt_mcp.models import BucketObjectsPutItem, BucketObjectsPutParams
from quilt_mcp.tools import bucket_objects_put

items = [
    BucketObjectsPutItem(
        key="file1.txt",
        text="Hello World",
        content_type="text/plain"
    ),
    BucketObjectsPutItem(
        key="data.json",
        text='{"key": "value"}',
        content_type="application/json"
    ),
]

params = BucketObjectsPutParams(bucket="my-bucket", items=items)
result = bucket_objects_put(params)
```

**After (v0.9.0) - Simple dicts:**
```python
from quilt_mcp.models import BucketObjectsPutParams
from quilt_mcp.tools import bucket_objects_put

params = BucketObjectsPutParams(
    bucket="my-bucket",
    items=[
        {
            "key": "file1.txt",
            "text": "Hello World",
            "content_type": "text/plain"
        },
        {
            "key": "data.json",
            "text": '{"key": "value"}',
            "content_type": "application/json"
        },
    ]
)
result = bucket_objects_put(params)
```

**Changes:**
- No need to import `BucketObjectsPutItem`
- Use dict literals instead of Pydantic model instantiation
- Simpler, more Pythonic API

---

## Automated Migration

### Find and Replace Patterns

Use these regex patterns to help automate migration:

**1. Remove `dry_run` parameter:**
```bash
# Find
dry_run\s*=\s*(True|False),?\s*

# Replace (delete)
```

**2. Rename `source_prefix` to `prefix`:**
```bash
# Find
source_prefix\s*=\s*

# Replace
prefix=
```

**3. Convert `BucketObjectsPutItem` to dict:**
```bash
# Find
BucketObjectsPutItem\(\s*key\s*=\s*"([^"]+)",\s*text\s*=\s*"([^"]+)"\s*\)

# Replace
{"key": "$1", "text": "$2"}
```

---

## Testing Your Migration

### 1. Update Imports

Remove imports for deleted classes:
```python
# Remove these imports
from quilt_mcp.models import BucketObjectsPutItem  # Removed in v0.9.0
```

### 2. Run Your Tests

```bash
# Run your test suite
pytest tests/ -v

# Common errors to watch for:
# - AttributeError: 'PackageCreateFromS3Params' object has no attribute 'dry_run'
# - TypeError: BucketObjectsPutItem() takes no arguments
# - ValidationError: Field required: auto_organize
```

### 3. Check for Deprecated Patterns

```bash
# Search your codebase for removed parameters
grep -r "dry_run" .
grep -r "force=" .
grep -r "BucketObjectsPutItem" .
grep -r "source_prefix" .
```

---

## Preset Configuration Reference

### PackageImportPresets

**`simple`** - Basic import (90% of use cases):
```python
{
    "metadata_template": "standard",
    "copy_mode": "all",
    "registry_hint": "primary"
}
```

**`csv-only`** - CSV files with analytics:
```python
{
    "include_patterns": ["*.csv"],
    "metadata_template": "analytics",
    "copy_mode": "all",
    "registry_hint": "analytics"
}
```

**`ml-model`** - ML artifacts:
```python
{
    "include_patterns": ["*.pkl", "*.h5", "*.json", "*.pt", "*.ckpt", "*.safetensors"],
    "exclude_patterns": ["*.tmp", "checkpoints/*"],
    "metadata_template": "ml",
    "copy_mode": "all",
    "registry_hint": "ml-packages"
}
```

**`genomics`** - Genomics files:
```python
{
    "include_patterns": ["*.fastq", "*.fastq.gz", "*.bam", "*.vcf", "*.vcf.gz",
                        "*.h5ad", "*.loom", "*.zarr", "*.fcs", "*.gff"],
    "metadata_template": "genomics",
    "copy_mode": "none",  # Reference only for large files
    "registry_hint": "genomics-data"
}
```

**`analytics`** - Analytics data:
```python
{
    "include_patterns": ["*.csv", "*.parquet", "*.json", "*.jsonl",
                        "*.xlsx", "*.tsv", "*.arrow", "*.feather"],
    "metadata_template": "analytics",
    "copy_mode": "all",
    "registry_hint": "analytics"
}
```

---

## Common Migration Issues

### Issue 1: Missing `dry_run` Behavior

**Problem:** Code relied on preview mode before creating packages

**Solution:** Use tool composition pattern:
```python
# Step 1: List files to preview
files = bucket_objects_list(bucket="my-bucket", prefix="data/")

# Step 2: Show user the files (your app logic)
if user_confirms(files.objects):
    # Step 3: Create package
    result = package_create_from_s3(...)
```

---

### Issue 2: Complex Filter Patterns

**Problem:** Advanced glob patterns not covered by presets

**Solution:** Use explicit `include_patterns` / `exclude_patterns`:
```python
package_create_from_s3(
    source_bucket="bucket",
    package_name="team/pkg",
    preset="simple",  # Base configuration
    include_patterns=["data/**/*.parquet", "*.json"],  # Explicit patterns override
    exclude_patterns=["**/temp/**"]
)
```

---

### Issue 3: Registry Auto-Discovery

**Problem:** `target_registry` removed, need specific registry

**Solution:** Registry is auto-discovered based on patterns:
- Bucket name contains "ml" → `s3://ml-packages`
- Bucket name contains "genomics" → `s3://genomics-data`
- Default → `s3://{source_bucket}`

To override, use preset with `registry_hint` or contact support for custom registry mapping.

---

## Rollback Plan

If you encounter issues with v0.9.0:

### Option 1: Pin to v0.8.4

```toml
# pyproject.toml
[tool.poetry.dependencies]
quilt-mcp = "==0.8.4"
```

```bash
# Or with pip
pip install quilt-mcp==0.8.4
```

### Option 2: Gradual Migration

1. Keep v0.8.4 in production
2. Test v0.9.0 in development/staging
3. Migrate one tool at a time
4. Deploy to production when confident

---

## Support

If you need help migrating:

1. **Check Examples:** See [examples/migration/](../examples/migration/) for complete code samples
2. **Report Issues:** [GitHub Issues](https://github.com/quiltdata/quilt-mcp-server/issues)
3. **Ask Questions:** [Discussions](https://github.com/quiltdata/quilt-mcp-server/discussions)

---

## Timeline

- **v0.9.0 (Now):** Breaking changes introduced, both old and new supported with deprecation warnings
- **v0.9.x (6 months):** Deprecation period, migration assistance available
- **v1.0.0 (Future):** Old patterns removed entirely

**Recommendation:** Migrate within 6 months to avoid breaking changes in v1.0.0.
