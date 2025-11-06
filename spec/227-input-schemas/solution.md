# Issue #227: Solution - Simplifying Input Schemas

## Executive Summary

After analyzing all 29 tool parameter models, the issue is clear: **excessive optional parameters** (not nesting) is the primary problem. The top 3 tools have 8-13 optional parameters each, creating cognitive overload for LLMs.

## Recommended Solution: Use Pydantic Defaults More Effectively

Instead of creating duplicate `_simple` functions (which would double our API surface), we should leverage Pydantic's built-in features to make complex tools easier to call.

### Key Insight

LLMs struggle not because the schema is "nested" (only 1 tool has nesting), but because there are **too many choices**. When a tool has 15 parameters with only 2 required, the LLM must consider all 13 optional parameters for every call.

### Strategy: Make Schemas "Progressive"

The solution is to **reorganize parameter ordering** and **improve descriptions** to guide LLMs toward the essential parameters first:

1. **Group parameters by importance** in the model definition
2. **Use clear descriptions** that indicate when parameters are needed
3. **Leverage Pydantic Field() metadata** to mark advanced options
4. **Add JSON schema examples** showing minimal vs full usage

## Implementation Plan

### Phase 1: Improve Existing Schemas (Low Risk, High Impact)

#### 1.1 Reorder Parameters by Importance

**Before:**
```python
class PackageCreateFromS3Params(BaseModel):
    source_bucket: str
    package_name: str
    source_prefix: str = ""
    target_registry: Optional[str] = None
    description: str = ""
    include_patterns: Optional[list[str]] = None
    exclude_patterns: Optional[list[str]] = None
    auto_organize: bool = True
    generate_readme: bool = True
    confirm_structure: bool = True
    metadata_template: Literal["standard", "ml", "analytics"] = "standard"
    dry_run: bool = False
    metadata: Optional[dict] = None
    copy_mode: Literal["all", "same_bucket", "none"] = "all"
    force: bool = False
```

**After:**
```python
class PackageCreateFromS3Params(BaseModel):
    """Parameters for creating a Quilt package from S3 bucket contents.

    Basic usage requires only source_bucket and package_name.
    All other parameters have sensible defaults.
    """

    # === REQUIRED: Core Parameters ===
    source_bucket: Annotated[
        str,
        Field(
            description="S3 bucket name containing source data (without s3:// prefix)",
            examples=["my-data-bucket", "research-data"],
            json_schema_extra={"importance": "required"},
        ),
    ]
    package_name: Annotated[
        str,
        Field(
            description="Name for the new package in namespace/name format",
            examples=["username/dataset", "team/research-data"],
            pattern=r"^[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+$",
            json_schema_extra={"importance": "required"},
        ),
    ]

    # === COMMON: Frequently Used Options ===
    source_prefix: Annotated[
        str,
        Field(
            default="",
            description="Optional prefix to filter source objects (e.g., 'data/' to include only data folder)",
            examples=["", "data/2024/", "experiments/"],
            json_schema_extra={"importance": "common"},
        ),
    ]
    description: Annotated[
        str,
        Field(
            default="",
            description="Human-readable description of the package contents",
            json_schema_extra={"importance": "common"},
        ),
    ]

    # === ADVANCED: Fine-tuning Options ===
    target_registry: Annotated[
        Optional[str],
        Field(
            default=None,
            description="[ADVANCED] Target Quilt registry (auto-suggested if not provided)",
            json_schema_extra={"importance": "advanced"},
        ),
    ]
    include_patterns: Annotated[
        Optional[list[str]],
        Field(
            default=None,
            description="[ADVANCED] File patterns to include (glob style, e.g., ['*.csv', '*.json'])",
            examples=[["*.csv", "*.json"], ["data/*.parquet"]],
            json_schema_extra={"importance": "advanced"},
        ),
    ]
    exclude_patterns: Annotated[
        Optional[list[str]],
        Field(
            default=None,
            description="[ADVANCED] File patterns to exclude (glob style, e.g., ['*.tmp', '*.log'])",
            examples=[["*.tmp", "*.log"], ["temp/*"]],
            json_schema_extra={"importance": "advanced"},
        ),
    ]
    metadata_template: Annotated[
        Literal["standard", "ml", "analytics"],
        Field(
            default="standard",
            description="[ADVANCED] Metadata template to use for package organization",
            json_schema_extra={"importance": "advanced"},
        ),
    ]
    copy_mode: Annotated[
        Literal["all", "same_bucket", "none"],
        Field(
            default="all",
            description="[ADVANCED] Copy policy: 'all' (copy everything), 'same_bucket' (copy only if different bucket), 'none' (reference only)",
            json_schema_extra={"importance": "advanced"},
        ),
    ]

    # === INTERNAL: Developer/Testing Flags ===
    auto_organize: Annotated[
        bool,
        Field(
            default=True,
            description="[INTERNAL] Enable smart folder organization (keep True for best results)",
            json_schema_extra={"importance": "internal"},
        ),
    ]
    generate_readme: Annotated[
        bool,
        Field(
            default=True,
            description="[INTERNAL] Generate comprehensive README.md (keep True for best results)",
            json_schema_extra={"importance": "internal"},
        ),
    ]
    confirm_structure: Annotated[
        bool,
        Field(
            default=True,
            description="[INTERNAL] Require user confirmation of structure (set False for automation)",
            json_schema_extra={"importance": "internal"},
        ),
    ]
    dry_run: Annotated[
        bool,
        Field(
            default=False,
            description="[INTERNAL] Preview structure without creating package (for testing)",
            json_schema_extra={"importance": "internal"},
        ),
    ]
    force: Annotated[
        bool,
        Field(
            default=False,
            description="[INTERNAL] Skip confirmation prompts (useful for automated ingestion)",
            json_schema_extra={"importance": "internal"},
        ),
    ]
    metadata: Annotated[
        Optional[dict[str, Any]],
        Field(
            default=None,
            description="[INTERNAL] Additional user-provided metadata (rarely needed)",
            json_schema_extra={"importance": "internal"},
        ),
    ]

    model_config = {
        "json_schema_extra": {
            "examples": [
                # Minimal example (most common)
                {
                    "source_bucket": "my-data-bucket",
                    "package_name": "team/dataset",
                },
                # With description
                {
                    "source_bucket": "research-data",
                    "package_name": "team/experiment-results",
                    "description": "Results from Q1 2024 experiments",
                },
                # With filtering
                {
                    "source_bucket": "my-data-bucket",
                    "package_name": "team/csv-data",
                    "source_prefix": "data/",
                    "include_patterns": ["*.csv"],
                },
            ]
        }
    }
```

#### Benefits of This Approach:
1. **No new functions** - Keeps API surface small
2. **Clear hierarchy** - LLMs see which params are essential
3. **Better descriptions** - `[ADVANCED]` and `[INTERNAL]` tags guide usage
4. **Examples in schema** - Shows minimal vs full usage
5. **Metadata hints** - `importance` field can be used by clients

### Phase 2: Simplify BucketObjectsPutParams (Address Nesting)

The only tool with actual nesting is `BucketObjectsPutParams`. Solution:

```python
class BucketObjectsPutParams(BaseModel):
    """Parameters for uploading multiple objects to S3.

    You can provide items as either:
    1. A list of dicts with keys: key, text/data, content_type, encoding, metadata
    2. A list of BucketObjectsPutItem objects

    For simple use cases, use dicts:
    items=[{"key": "file.txt", "text": "content"}]
    """

    bucket: Annotated[
        str,
        Field(
            description="S3 bucket name or s3:// URI",
            examples=["my-bucket", "s3://my-bucket"],
        ),
    ]
    items: Annotated[
        list[BucketObjectsPutItem | dict[str, Any]],  # Accept BOTH
        Field(
            description="List of objects to upload. Each can be a dict with keys: key (required), text OR data (required), content_type, encoding, metadata",
            min_length=1,
            examples=[
                # Dict example (simpler for LLMs)
                [{"key": "hello.txt", "text": "Hello World"}],
                # Full example
                [
                    {
                        "key": "data.csv",
                        "text": "col1,col2\n1,2",
                        "content_type": "text/csv",
                    }
                ],
            ],
        ),
    ]

    @field_validator("items", mode="before")
    @classmethod
    def convert_dicts_to_items(cls, v):
        """Convert dict items to BucketObjectsPutItem objects."""
        if not isinstance(v, list):
            return v
        result = []
        for item in v:
            if isinstance(item, dict):
                result.append(BucketObjectsPutItem(**item))
            else:
                result.append(item)
        return result
```

This approach:
- Accepts both dicts and Pydantic models
- LLMs can use simple dicts without understanding nested structures
- Schema remains clean and flat
- Full validation still happens via `field_validator`

### Phase 3: Add Schema Metadata for Tool Selection (Future)

Add metadata to help LLMs choose the right tool:

```python
class ToolMetadata(BaseModel):
    complexity: Literal["simple", "moderate", "complex"]
    use_cases: list[str]
    common_params: list[str]
    related_tools: list[str]

# In model_config:
model_config = {
    "json_schema_extra": {
        "tool_metadata": {
            "complexity": "moderate",
            "use_cases": [
                "Bulk import S3 data into Quilt",
                "Create organized packages from raw data",
            ],
            "common_params": ["source_bucket", "package_name", "source_prefix"],
            "related_tools": ["package_create", "bucket_objects_list"],
        }
    }
}
```

## Comparison: New Approach vs Creating _simple Functions

### ❌ Creating _simple Functions (Original Idea)

**Pros:**
- Easier for LLMs to understand at first glance
- Smaller schemas

**Cons:**
- **Doubles API surface** (29 tools → 58 tools)
- **High maintenance burden** (every change needs 2 updates)
- **User confusion** ("Which version do I use?")
- **Duplication of logic** (same code, different signatures)
- **Version skew risk** (simple and advanced versions diverge)

### ✅ Improving Existing Schemas (Recommended)

**Pros:**
- **No API proliferation** (stays at 29 tools)
- **Low maintenance** (single implementation)
- **No breaking changes** (backward compatible)
- **Progressive disclosure** (params grouped by importance)
- **Better UX** (clear guidance in descriptions)

**Cons:**
- Requires some schema engineering
- May need client support for `importance` metadata

## Implementation Checklist

### Step 1: Update Top 3 Complex Tools
- [ ] PackageCreateFromS3Params (15 params → group into required/common/advanced/internal)
- [ ] DataVisualizationParams (11 params → group by importance)
- [ ] BucketObjectsPutParams (nested → accept dicts too)

### Step 2: Update Documentation
- [ ] Add "Quick Start" section to each complex tool's docstring
- [ ] Show minimal example first, advanced example second
- [ ] Update CLAUDE.md with guidance on using complex tools

### Step 3: Add JSON Schema Examples
- [ ] Add 2-3 examples per complex tool (minimal, common, full)
- [ ] Include examples in `model_config["json_schema_extra"]["examples"]`

### Step 4: Test with Real LLM
- [ ] Use Claude in inspector to call complex tools
- [ ] Verify LLM uses only required params by default
- [ ] Verify LLM can find advanced params when needed

### Step 5: Document Pattern
- [ ] Create SCHEMA_DESIGN_GUIDE.md for future tool development
- [ ] Establish rules: max 5 required params, group by importance, use examples

## Expected Results

### Before (Current State)
- PackageCreateFromS3Params: 15 params, no guidance, 2,921 char schema
- LLM sees all 15 params as equal choices
- High cognitive load → errors and confusion

### After (With Improvements)
- PackageCreateFromS3Params: 15 params, clear hierarchy, ~3,000 char schema (similar size)
- LLM sees 2 required, 2 common, rest marked [ADVANCED]/[INTERNAL]
- Low cognitive load → correct calls on first try

### Schema Size Impact
Schema size won't change much (may even increase slightly with better descriptions), but **cognitive complexity drops dramatically** through:
1. Clear parameter hierarchy
2. Descriptive labels ([ADVANCED], [INTERNAL])
3. Helpful examples in schema
4. Better field descriptions

## Alternative Considered: FastMCP Features

FastMCP may support "parameter groups" or "progressive disclosure" natively. We should check the FastMCP docs before implementing custom `importance` metadata.

If FastMCP has built-in support for marking parameters as "advanced" or "rarely used", we should use that instead of custom `json_schema_extra`.

## Conclusion

The issue isn't that Pydantic schemas are too complex - it's that we're not using Pydantic's features effectively to guide LLMs. By reorganizing parameters, adding clear labels, and providing examples, we can make complex tools much easier to call without doubling our API surface.

**Recommendation:** Implement Phase 1 (reorder + improve descriptions) for the top 3 tools and measure impact before proceeding further.
