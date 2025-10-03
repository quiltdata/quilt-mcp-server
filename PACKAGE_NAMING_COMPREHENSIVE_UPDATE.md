# Package Naming Comprehensive Update (2025-10-03)

## Issue
LLMs were attempting to create packages with invalid names containing periods (e.g., `team/data.csv`, `team/v1.0`) and other invalid patterns.

## Root Cause
While the validation already rejected periods, the tool description and error messages didn't **explicitly mention** all the invalid patterns that LLMs commonly try:
- Periods (`.`) - e.g., `data.csv`, `v1.0`
- Uppercase letters - e.g., `MyTeam/Data`
- Spaces - e.g., `my data`
- Special characters - e.g., `data@v1`, `data#1`

## Solution

### 1. Enhanced Tool Description
Updated the main `packaging()` docstring with explicit warnings about all invalid patterns:

```python
⚠️  CRITICAL: Package names MUST use 'namespace/package-name' format:
    - REQUIRED: Both namespace AND package name separated by exactly one '/'
    - REQUIRED: Lowercase letters, numbers, hyphens (-), underscores (_) ONLY
    - NO uppercase letters allowed
    - NO periods (.) allowed - use hyphens instead
    - NO spaces or special characters
    - Examples: 'demo-team/csv-data', 'myteam/dataset1', 'analytics/q1-reports'
    - WRONG: 'csvdata' (missing namespace), 'MyTeam/Data' (uppercase), 'team/data.csv' (period)
```

### 2. Updated Action Discovery Response
When querying available actions, the response now includes comprehensive examples:

```json
{
  "CRITICAL_NAMING_RULE": "Package names MUST be 'namespace/package-name' format (lowercase, hyphens, underscores only - NO PERIODS)",
  "naming_examples": {
    "valid": [
      "demo-team/csv-data",
      "myteam/dataset1", 
      "analytics/q1-reports",
      "user123/data-v2"
    ],
    "invalid": [
      "csvdata (missing namespace)",
      "MyTeam/Data (uppercase not allowed)",
      "team/data.csv (periods not allowed)",
      "team/my data (spaces not allowed)",
      "team/data@v1 (special chars not allowed)"
    ]
  }
}
```

### 3. Specific Period Validation
Added dedicated validation for periods with helpful suggestions:

```python
if name and "." in name:
    clean_name = name.replace(".", "-")
    return {
        "error": f"Invalid package name: '{name}'. Periods (.) are not allowed.",
        "CRITICAL": "Package names cannot contain periods - use hyphens (-) instead",
        "suggestion": clean_name,
        "tip": f"Use hyphens instead: '{clean_name}'"
    }
```

### 4. Comprehensive Error Messages
Updated `_validate_package_name()` with detailed invalid examples:

```
Rules:
  - Use lowercase letters, numbers, hyphens (-), and underscores (_) ONLY
  - No uppercase letters allowed
  - No periods (.) allowed - use hyphens instead
  - No spaces or special characters
  - Must start with a lowercase letter or number

Valid examples:
  ✓ 'demo-team/csv-data'
  ✓ 'myteam/csvexample2'
  ✓ 'user_123/my_dataset'
  ✓ 'team/data-v2' (use hyphens for versions)

Invalid examples:
  ✗ 'MyTeam/Data' (uppercase not allowed)
  ✗ 'team/data.csv' (periods not allowed)
  ✗ 'team/my data' (spaces not allowed)
  ✗ 'team/data@v1' (special characters not allowed)
  ✗ 'team/csv-' (ends with hyphen)
  ✗ '-team/data' (starts with hyphen)
```

## Common Invalid Patterns Now Explicitly Documented

| Invalid Pattern | Example | Why Invalid | Correct Alternative |
|----------------|---------|-------------|---------------------|
| Periods | `team/data.csv` | Periods not allowed | `team/data-csv` |
| Uppercase | `MyTeam/Data` | Must be lowercase | `myteam/data` |
| Spaces | `team/my data` | Spaces not allowed | `team/my-data` |
| Version periods | `team/v1.0` | Periods not allowed | `team/v1-0` |
| Special chars | `team/data@v1` | Only `-` and `_` allowed | `team/data-v1` |
| Missing namespace | `csvdata` | Need both parts | `team/csvdata` |
| Trailing hyphen | `team/data-` | Can't end with `-` | `team/data` |
| Leading hyphen | `-team/data` | Can't start with `-` | `team/data` |

## Validation Pattern
```python
pattern = r"^[a-z0-9][a-z0-9\-_]*$"
```

This pattern enforces:
- Start with lowercase letter or number
- Only lowercase letters, numbers, hyphens, underscores
- No periods, spaces, uppercase, or special characters

## Files Modified
- `src/quilt_mcp/tools/packaging.py`
  - Updated `packaging()` function docstring (lines 539-546)
  - Enhanced action discovery response (lines 587-597)
  - Added specific period validation (lines 622-636)
  - Updated `_validate_package_name()` error messages (lines 235-257)
  - Updated `package_create()` docstring (lines 326-329)

## Testing

### Valid Names (should pass)
```python
✅ demo-team/csv-data
✅ myteam/dataset1
✅ user_123/my_dataset
✅ analytics/q1-reports
✅ team/data-v2
```

### Invalid Names (should be caught with specific errors)
```python
❌ team/data.csv → "Periods (.) are not allowed. Use hyphens instead: 'team/data-csv'"
❌ MyTeam/Data → "No uppercase letters allowed"
❌ team/my data → "No spaces or special characters"
❌ team/data@v1 → "No spaces or special characters"
❌ csvdata → "Missing namespace separator '/'"
```

## Expected LLM Behavior

**Before**: LLM might try various invalid patterns:
- `team/data.csv` (period)
- `team/v1.0` (period)
- `MyData` (missing namespace + uppercase)

**After**: LLM will see explicit warnings about:
- NO periods → use hyphens
- NO uppercase → use lowercase
- NO spaces → use hyphens
- NO special chars → use hyphens/underscores
- REQUIRED namespace/package format

## Deployment

**Version**: 0.6.57 (revision 154)
- **Status**: ✅ Deployed and running
- **Task Definition**: quilt-mcp-server:154
- **Service**: sales-prod-mcp-server-production
- **Cluster**: sales-prod
- **Completion**: 2025-10-03 15:03:10

## Related Documentation
- Backend validation: `^[a-z0-9][a-z0-9\-_]*$` pattern
- Validation function: `src/quilt_mcp/utils.py:validate_package_name()`
- Error messages: `src/quilt_mcp/tools/packaging.py:_validate_package_name()`

