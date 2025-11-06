<!-- markdownlint-disable MD013 -->
# Issue #227: High-Risk/High-Reward Follow-On Actions

**Status:** 🔮 Speculative
**Timeline:** Post v0.8.4 (v0.9.x - v2.0)
**Risk Level:** High (Breaking Changes Likely)

## Overview

This document explores aggressive follow-on actions that could dramatically improve LLM usability but require breaking changes or substantial refactoring. These are informed by the conservative approach in v0.8.4 and represent "what if we could start fresh?"

---

## Action 1: Hard Parameter Limits

### Proposal

Enforce strict limits on tool complexity:

- **Maximum 3 required parameters** per tool
- **Maximum 5 total parameters** per tool
- **Zero nesting** - all parameters must be top-level primitives or simple lists

### Implementation

**Before (PackageCreateFromS3Params - 15 params):**

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

**After (Split into 3 focused tools):**

```python
# Tool 1: Simple import (90% of use cases)
class PackageCreateFromS3SimpleParams(BaseModel):
    """Create package from entire S3 bucket with smart defaults."""
    source_bucket: str  # required
    package_name: str   # required
    description: str = ""  # optional

# Tool 2: Filtered import
class PackageCreateFromS3FilteredParams(BaseModel):
    """Create package from filtered S3 bucket contents."""
    source_bucket: str  # required
    package_name: str   # required
    prefix: str = ""    # optional
    include: list[str] = []  # optional (e.g., ["*.csv"])
    exclude: list[str] = []  # optional (e.g., ["*.tmp"])

# Tool 3: Advanced import (10% of use cases)
class PackageCreateFromS3AdvancedParams(BaseModel):
    """Full control over package creation from S3."""
    source_bucket: str  # required
    package_name: str   # required
    config: PackageImportConfig  # required (all advanced options moved here)
```

### Risk Assessment

**🔴 Breaking Changes:**

- All existing `package_create_from_s3()` calls break
- Migration required for all users
- Documentation must be completely rewritten

**🟢 Benefits:**

- Each tool is trivially simple for LLMs
- Clear separation of concerns
- 90% of users need only the simple tool

**Risk Level:** ⚠️ **CRITICAL** - Requires major version bump (v2.0)

**Mitigation:**

1. Deprecate old tool in v0.9.x with warnings
2. Provide automatic migration script
3. Support both old and new for 6 months
4. Document migration path clearly

### Success Metrics

- LLM success rate >95% on simple tool
- Zero confusion about which tool to use
- <5% of users need advanced tool

---

## Action 2: Context-Aware Parameter Reduction

### Proposal

Make parameters contextually optional based on environment or previous calls.

### Implementation

**Concept: Sticky Defaults**

```python
class QuiltContext:
    """Global context that remembers user preferences."""
    default_registry: str = "s3://quilt-ernest-staging"
    default_metadata_template: str = "standard"
    default_copy_mode: str = "all"

    @classmethod
    def set_defaults(cls, **kwargs):
        """Set default values for future tool calls."""
        for key, value in kwargs.items():
            setattr(cls, key, value)

# First call - user sets preferences
QuiltContext.set_defaults(
    registry="s3://my-bucket",
    metadata_template="ml",
)

# Subsequent calls - parameters inferred from context
package_create_from_s3(
    source_bucket="data-bucket",
    package_name="team/dataset",
    # registry="s3://my-bucket" <- INFERRED
    # metadata_template="ml" <- INFERRED
)
```

**Concept: Smart Inference**

```python
class PackageCreateFromS3Params(BaseModel):
    source_bucket: str
    package_name: str
    target_registry: Optional[str] = None  # Infer from source_bucket if None

    @model_validator(mode="after")
    def infer_registry(self):
        """If no registry provided, use source bucket as registry."""
        if self.target_registry is None:
            self.target_registry = f"s3://{self.source_bucket}"
        return self
```

### Risk Assessment

**🟡 Medium Risk:**

- Adds statefulness to currently stateless tools
- Could cause surprising behavior if context not reset
- Harder to debug ("why is this using the wrong registry?")

**🟢 Benefits:**

- Reduces parameters from 15 → 5-7 for repeat users
- Better DX for power users
- Progressive refinement of defaults

**Risk Level:** ⚠️ **MODERATE** - Requires careful state management

**Mitigation:**

1. Make context explicit and visible
2. Add `reset_context()` command
3. Log when context is applied
4. Allow override via explicit parameters

### Success Metrics

- Average parameters per call drops by 40%
- Zero bug reports about "wrong defaults"
- Positive user feedback on DX

---

## Action 3: LLM-Optimized Schema Format

### Proposal

Create a parallel, ultra-minimal schema format specifically for LLM consumption, while keeping full schema for human/IDE use.

### Implementation

**Concept: Dual Schemas**

```python
class PackageCreateFromS3Params(BaseModel):
    """Full schema with all parameters and validation."""
    # ... all 15 parameters ...

    @classmethod
    def llm_schema(cls) -> dict:
        """Ultra-minimal schema for LLM tool calling."""
        return {
            "type": "object",
            "properties": {
                "source_bucket": {"type": "string"},
                "package_name": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["source_bucket", "package_name"],
            "additionalProperties": True,  # Allow advanced params
        }
```

**Concept: Progressive Schema Loading**

```json
// Initial schema sent to LLM (minimal)
{
  "name": "package_create_from_s3",
  "description": "Create package from S3 bucket",
  "parameters": {
    "source_bucket": "string (required)",
    "package_name": "string (required)",
    "description": "string (optional)"
  },
  "has_advanced_options": true,
  "schema_level": "basic"
}

// If LLM needs advanced options, it requests full schema
{
  "action": "get_full_schema",
  "tool": "package_create_from_s3"
}

// Server returns complete schema
{
  "schema_level": "full",
  "parameters": { /* all 15 parameters */ }
}
```

### Risk Assessment

**🟡 Medium Risk:**

- Requires MCP/FastMCP support for dynamic schemas
- Two schemas could diverge over time
- Adds complexity to schema generation

**🟢 Benefits:**

- Best of both worlds: simple for LLMs, full for power users
- No breaking changes to API
- Can optimize each schema independently

**Risk Level:** ⚠️ **MODERATE** - Depends on MCP capabilities

**Mitigation:**

1. Auto-generate LLM schema from full schema
2. Add CI tests to ensure schemas stay in sync
3. Start with 3 tools as proof of concept

### Success Metrics

- LLM token usage reduced by 60%
- LLM call errors reduced by 40%
- Zero schema drift issues

---

## Action 4: Natural Language Parameters

### Proposal

Accept natural language strings for complex parameters, parse them server-side.

### Implementation

**Concept: Fuzzy Parameter Parsing**

```python
# Current: LLM must construct complex list
include_patterns=["*.csv", "*.json", "data/**/*.parquet"]
exclude_patterns=["*.tmp", "*.log", "temp/*"]

# Proposed: LLM uses natural language
filter="include CSV and JSON files, and Parquet files in data folder, but exclude temp files and logs"
```

**Server-side parsing:**

```python
class PackageCreateFromS3Params(BaseModel):
    source_bucket: str
    package_name: str
    filter: Optional[str] = None  # Natural language filter

    # Legacy parameters still supported
    include_patterns: Optional[list[str]] = None
    exclude_patterns: Optional[list[str]] = None

    @model_validator(mode="after")
    def parse_natural_language_filter(self):
        """Convert natural language filter to glob patterns."""
        if self.filter and not (self.include_patterns or self.exclude_patterns):
            parsed = parse_file_filter(self.filter)
            self.include_patterns = parsed.include
            self.exclude_patterns = parsed.exclude
        return self

def parse_file_filter(text: str) -> FilterPatterns:
    """Parse natural language into glob patterns using LLM."""
    # Use small fast model to parse
    prompt = f"""
    Convert this file filter description into glob patterns:
    "{text}"

    Return JSON: {{"include": ["pattern1", ...], "exclude": ["pattern1", ...]}}
    """
    result = llm_call(prompt, model="claude-3-haiku")
    return FilterPatterns.model_validate_json(result)
```

### Risk Assessment

**🔴 High Risk:**

- Adds LLM dependency to tool execution
- Parsing could fail or be incorrect
- Latency increase (extra LLM call)
- Costs increase

**🟢 Benefits:**

- Dramatically simpler for LLMs to call
- More intuitive for human users too
- Can evolve parsing without changing API

**Risk Level:** ⚠️ **HIGH** - Adds complexity and failure modes

**Mitigation:**

1. Keep structured parameters as fallback
2. Cache common natural language patterns
3. Use fast/cheap model for parsing
4. Add validation step before execution

### Success Metrics

- 80% of calls use natural language successfully
- Parsing accuracy >95%
- Latency increase <500ms
- User satisfaction improves

---

## Action 5: Tool Composition Framework

### Proposal

Instead of complex tools, provide simple building blocks that LLMs can chain together.

### Implementation

**Current: Monolithic Tool**

```python
# Single complex tool does everything
package_create_from_s3(
    source_bucket="data",
    package_name="team/dataset",
    include_patterns=["*.csv"],
    auto_organize=True,
    generate_readme=True,
    metadata_template="ml",
    copy_mode="all",
)
```

**Proposed: Composable Pipeline**

```python
# Step 1: List files
files = s3_list_files(
    bucket="data",
    include=["*.csv"],
)

# Step 2: Organize files
organized = organize_files(
    files=files,
    template="ml",  # ML-specific organization
)

# Step 3: Generate metadata
metadata = generate_package_metadata(
    files=organized,
    template="ml",
    auto_readme=True,
)

# Step 4: Create package
package = package_create(
    name="team/dataset",
    files=organized,
    metadata=metadata,
)
```

**Each tool is trivially simple:**

```python
class S3ListFilesParams(BaseModel):
    bucket: str  # 1 required
    include: list[str] = []  # 1 optional
    exclude: list[str] = []  # 1 optional

class OrganizeFilesParams(BaseModel):
    files: list[str]  # 1 required
    template: str = "standard"  # 1 optional

class GenerateMetadataParams(BaseModel):
    files: dict[str, list[str]]  # 1 required (organized structure)
    template: str = "standard"  # 1 optional
    auto_readme: bool = True  # 1 optional

class PackageCreateParams(BaseModel):
    name: str  # 1 required
    files: dict[str, list[str]]  # 1 required
    metadata: dict = {}  # 1 optional
```

### Risk Assessment

**🟡 Medium Risk:**

- Requires LLMs to understand workflows
- More tool calls = more latency
- Could be confusing for simple use cases

**🟢 Benefits:**

- Each tool is dead simple (≤3 params)
- Extremely flexible compositions
- Can skip unnecessary steps
- Easier to debug (see each step)

**Risk Level:** ⚠️ **MODERATE** - Requires LLM to orchestrate

**Mitigation:**

1. Keep high-level convenience tools for common cases
2. Provide workflow templates
3. Add `package_create_from_s3_quick()` that internally does composition
4. Document common patterns

### Success Metrics

- LLMs can successfully chain 3-4 tools
- Each individual tool has >95% success rate
- Users appreciate flexibility
- Median workflow length ≤4 steps

---

## Action 6: Schema Compression via Abbreviations

### Proposal

Use abbreviated parameter names to reduce schema size, with automatic expansion.

### Implementation

**Current Schema (verbose):**

```json
{
  "source_bucket": "string",
  "package_name": "string",
  "source_prefix": "string",
  "include_patterns": "array",
  "exclude_patterns": "array",
  "metadata_template": "string",
  "auto_organize": "boolean",
  "generate_readme": "boolean"
}
```

**Compressed Schema (abbreviated):**

```json
{
  "src": "string (source_bucket)",
  "pkg": "string (package_name)",
  "pfx": "string (source_prefix)",
  "inc": "array (include_patterns)",
  "exc": "array (exclude_patterns)",
  "tmpl": "string (metadata_template)",
  "org": "boolean (auto_organize)",
  "readme": "boolean (generate_readme)"
}
```

**Server-side expansion:**

```python
PARAM_ALIASES = {
    "src": "source_bucket",
    "pkg": "package_name",
    "pfx": "source_prefix",
    "inc": "include_patterns",
    "exc": "exclude_patterns",
    "tmpl": "metadata_template",
    "org": "auto_organize",
}

@field_validator("*", mode="before")
@classmethod
def expand_abbreviations(cls, v, info):
    """Accept abbreviated parameter names."""
    field_name = info.field_name
    if field_name in PARAM_ALIASES.values():
        # Already using full name, OK
        return v
    return v
```

### Risk Assessment

**🔴 High Risk:**

- Cryptic parameter names hurt readability
- Could confuse human users
- Two names for everything (complexity)
- Not standard practice

**🟢 Benefits:**

- Schema size reduced by 30-40%
- Token costs reduced
- Faster LLM processing

**Risk Level:** ⚠️ **HIGH** - Poor developer experience

**Recommendation:** ❌ **DO NOT IMPLEMENT**

This trades minor token savings for major usability loss. The cognitive cost of abbreviations outweighs token savings.

**Better Alternative:** Use Action 3 (LLM-Optimized Schema Format) instead

---

## Action 7: Intelligent Parameter Presets

### Proposal

Provide named presets that bundle common parameter combinations.

### Implementation

**Concept: Named Presets**

```python
class PackageImportPresets:
    """Common parameter combinations for package creation."""

    SIMPLE = {
        "auto_organize": True,
        "generate_readme": True,
        "metadata_template": "standard",
        "copy_mode": "all",
    }

    FILTERED_CSV = {
        "include_patterns": ["*.csv"],
        "auto_organize": True,
        "generate_readme": True,
        "metadata_template": "analytics",
        "copy_mode": "all",
    }

    ML_EXPERIMENT = {
        "include_patterns": ["*.pkl", "*.h5", "*.json"],
        "exclude_patterns": ["*.tmp", "checkpoints/*"],
        "auto_organize": True,
        "generate_readme": True,
        "metadata_template": "ml",
        "copy_mode": "all",
    }

    GENOMICS_DATA = {
        "include_patterns": ["*.fastq", "*.bam", "*.vcf", "*.h5ad"],
        "auto_organize": True,
        "generate_readme": True,
        "metadata_template": "genomics",
        "copy_mode": "same_bucket",  # Large files
    }

# Usage
class PackageCreateFromS3Params(BaseModel):
    source_bucket: str
    package_name: str
    preset: Optional[str] = None  # "simple", "filtered_csv", "ml_experiment", etc.

    # Can still override individual params
    include_patterns: Optional[list[str]] = None
    exclude_patterns: Optional[list[str]] = None
    # ... other params ...

    @model_validator(mode="after")
    def apply_preset(self):
        """Apply preset, then override with explicit params."""
        if self.preset:
            preset_config = getattr(PackageImportPresets, self.preset.upper(), {})
            for key, value in preset_config.items():
                if getattr(self, key, None) is None:  # Don't override explicit params
                    setattr(self, key, value)
        return self
```

**LLM Usage:**

```python
# Before: LLM must specify 8 parameters
package_create_from_s3(
    source_bucket="ml-experiments",
    package_name="team/model-v1",
    include_patterns=["*.pkl", "*.h5", "*.json"],
    exclude_patterns=["*.tmp", "checkpoints/*"],
    auto_organize=True,
    generate_readme=True,
    metadata_template="ml",
    copy_mode="all",
)

# After: LLM uses preset + overrides
package_create_from_s3(
    source_bucket="ml-experiments",
    package_name="team/model-v1",
    preset="ml_experiment",  # Bundles 7 common ML settings
    # Can still override: include_patterns=["*.pkl", "*.json"]
)
```

### Risk Assessment

**🟢 Low Risk:**

- Backward compatible (presets are optional)
- Easy to add/remove presets
- Clear naming and documentation

**🟢 Benefits:**

- Reduces parameters from 15 → 3-4 for common cases
- Encodes best practices
- Domain-specific (ML, genomics, analytics)
- LLMs learn presets quickly

**Risk Level:** ✅ **LOW** - Safe to implement

**Recommendation:** ✅ **IMPLEMENT IN v0.9.x**

This is low-risk, high-reward. Presets can be added incrementally based on usage patterns.

### Success Metrics

- 60% of calls use a preset
- LLMs successfully choose correct preset
- Users request additional presets
- Average parameters per call drops to 3-5

---

## Comparative Analysis

| Action | Risk | Reward | Effort | Timeline | Breaking? |
|--------|------|--------|--------|----------|-----------|
| 1. Hard Parameter Limits | 🔴 Critical | 🟢🟢🟢 High | 🔧🔧🔧 High | v2.0 | ✅ Yes |
| 2. Context-Aware Params | 🟡 Moderate | 🟢🟢 Medium | 🔧🔧 Medium | v0.9.x | ❌ No |
| 3. LLM-Optimized Schemas | 🟡 Moderate | 🟢🟢🟢 High | 🔧🔧 Medium | v0.9.x | ❌ No |
| 4. Natural Language Params | 🔴 High | 🟢🟢 Medium | 🔧🔧🔧 High | v2.0+ | ❌ No |
| 5. Tool Composition | 🟡 Moderate | 🟢🟢🟢 High | 🔧🔧🔧🔧 Very High | v2.0 | ✅ Yes |
| 6. Schema Abbreviations | 🔴 Critical | 🟢 Low | 🔧 Low | ❌ Never | ❌ No |
| 7. Parameter Presets | 🟢 Low | 🟢🟢🟢 High | 🔧 Low | v0.9.x | ❌ No |

## Recommended Roadmap

### Phase 1: v0.9.x (Low-Risk Wins) - Q1 2025

**Priority 1: Parameter Presets (Action 7)**

- ✅ Low risk, high reward
- Add 5-7 common presets
- Document in tool descriptions
- Measure adoption rate

**Priority 2: LLM-Optimized Schemas (Action 3)**

- Requires MCP capability check
- Start with top 3 complex tools
- A/B test with vs without
- Measure token savings and error rates

### Phase 2: v1.5.x (Moderate-Risk Exploration) - Q2 2025

**Experiment: Context-Aware Params (Action 2)**

- Beta feature flag
- Opt-in for power users
- Gather feedback on statefulness
- Decide whether to promote or abandon

**Experiment: Tool Composition (Action 5)**

- Create proof-of-concept for 1 workflow
- Test with LLM orchestration
- Measure success rate and latency
- Document common patterns

### Phase 3: v2.0 (Breaking Changes) - Q3 2025

**Only if v0.9.x data shows <70% LLM success rate:**

**Option A: Hard Parameter Limits (Action 1)**

- Split top 5 complex tools
- Provide migration scripts
- 6-month deprecation period
- Clear upgrade path

**Option B: Tool Composition (Action 5)**

- Full commitment to composable design
- Rewrite complex tools as workflows
- Keep high-level convenience wrappers
- Document all composition patterns

**Do NOT implement:**

- ❌ Action 4 (Natural Language) - Too complex, too risky
- ❌ Action 6 (Abbreviations) - Poor DX, minimal gain

---

## Decision Framework

### When to Implement an Action

Use this decision tree:

```
Does current LLM success rate meet goals?
├─ YES (>80%) → Don't implement, focus elsewhere
└─ NO (<80%)
   └─ Is the action backward compatible?
      ├─ YES → Implement in v0.9.x
      │   └─ Start with lowest risk (Action 7, 3, 2)
      └─ NO (breaking changes)
          └─ Is improvement worth migration pain?
             ├─ YES → Plan for v2.0, 6-month deprecation
             │   └─ Prefer Action 1 or 5
             └─ NO → Don't implement
```

### Success Criteria for Each Action

Before promoting an experimental action to stable:

1. **A/B Testing:** Compare against baseline for ≥1000 calls
2. **Success Rate:** LLM success rate improves by ≥20%
3. **User Feedback:** Net Promoter Score >7/10
4. **Maintenance:** No increase in bug reports
5. **Performance:** Latency increase <10%

---

## Open Questions

### For the Team

1. **What is our target LLM success rate?**
   - Current: Unknown (need to measure)
   - Goal: 80%? 90%? 95%?

2. **What is our tolerance for breaking changes?**
   - Never? (Stay at v0.x forever)
   - Rarely? (v2.0 in 2026, v3.0 in 2028)
   - Regularly? (Semver major bumps every year)

3. **Who is our primary user?**
   - LLMs calling tools? (Optimize for AI)
   - Developers writing code? (Optimize for DX)
   - Both equally? (Balance)

4. **What is our API stability promise?**
   - "Move fast, break things"
   - "6-month deprecation for breaking changes"
   - "Never break existing code"

5. **Should we invest in LLM-specific optimizations?**
   - Or wait for MCP/FastMCP standards?
   - Or focus on human developer experience?

### For User Research

1. **Which parameters do users actually use?**
   - Instrument tools to log parameter usage
   - Identify rarely-used parameters (candidates for removal)

2. **What workflows are most common?**
   - Single tool calls? (Keep monolithic)
   - Multi-step sequences? (Invest in composition)

3. **What causes LLM call failures?**
   - Too many parameters? → Action 1, 7
   - Complex nested objects? → Action 3, 5
   - Unclear parameter meaning? → Action 3
   - Incorrect value types? → Action 4

4. **Do users prefer simple or powerful tools?**
   - Simple with limitations? → Action 1, 5, 7
   - Complex with flexibility? → Current approach
   - Both options available? → Action 1 + keep advanced

---

## Conclusion

### Top Recommendations

**Implement Now (v0.9.x):**

1. ✅ **Parameter Presets** (Action 7) - Low risk, high reward, easy win
2. ✅ **LLM-Optimized Schemas** (Action 3) - If MCP supports it

**Experiment Cautiously (v0.9.x beta):**
3. 🧪 **Context-Aware Params** (Action 2) - Measure statefulness impact
4. 🧪 **Tool Composition** (Action 5) - Proof-of-concept on 1 workflow

**Consider for v2.0 (Only if needed):**
5. ⏳ **Hard Parameter Limits** (Action 1) - Last resort if LLMs still struggle

**Never Implement:**
6. ❌ **Schema Abbreviations** (Action 6) - Poor cost/benefit ratio
7. ❌ **Natural Language Params** (Action 4) - Too complex for marginal gain

### Guiding Principle

> **"Make the simple things simple, and the complex things possible."**
>
> — Larry Wall (Perl creator)

The v0.8.4 improvements made complex things less complex. These follow-on actions could make simple things even simpler, but we must measure real-world LLM usage first.

**Data-driven decision:** Implement presets in v0.9.x, measure impact, then decide whether more aggressive changes (Actions 1, 5) are justified for v2.0.
