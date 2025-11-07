# Enhanced Validation Messages - Summary

## Overview

Enhanced validation messages for dict-to-Pydantic conversions in `src/quilt_mcp/models/inputs.py` to provide better user experience when validation fails.

## Enhanced Models

### 1. BucketObjectsPutParams.items

**Field Type:** `list[dict[str, Any]]`

**Enhanced Validator:** `validate_items`

## Before and After Examples

### Example 1: Missing 'key' field

#### Before Enhancement
```
ValidationError: 1 validation error for BucketObjectsPutParams
items.0.key
  Field required [type=missing, input_value={'text': 'content'}, input_type=dict]
```

#### After Enhancement
```
1 validation error for BucketObjectsPutParams
items
  Value error, Invalid item at index 0: Missing required 'key' field

Each item must have:
  - 'key' (required): S3 key/path for the object
  - 'text' OR 'data' (required): Content to upload

Example:
  {"key": "file.txt", "text": "Hello World"}
```

### Example 2: Missing content (text/data)

#### Before Enhancement
```
ValidationError: 1 validation error for BucketObjectsPutParams
items.0.text
  Field required [type=missing, input_value={'key': 'file.txt'}, input_type=dict]
```

#### After Enhancement
```
1 validation error for BucketObjectsPutParams
items
  Value error, Item at index 0: Must provide either 'text' or 'data' field
Provided keys: ['key']
```

### Example 3: Both text and data provided

#### Before Enhancement
```
ValidationError: (no specific error for this case - would fail at runtime)
```

#### After Enhancement
```
1 validation error for BucketObjectsPutParams
items
  Value error, Item at index 0: Cannot provide both 'text' and 'data' fields
Use only one: 'text' for strings, 'data' for base64-encoded binary
```

### Example 4: Valid input (no error)

```python
from quilt_mcp.models.inputs import BucketObjectsPutParams

params = BucketObjectsPutParams(
    bucket='s3://test-bucket',
    items=[{'key': 'file.txt', 'text': 'Hello World'}]
)

# ✅ Success! Returns:
# Bucket: s3://test-bucket
# Items: [{'key': 'file.txt', 'text': 'Hello World'}]
```

## Key Improvements

1. **Clear Error Location**: Identifies exactly which item (by index) has the problem
2. **Explicit Requirements**: Lists required and optional fields with explanations
3. **Inline Examples**: Shows correct usage right in the error message
4. **Specific Guidance**: Tells users exactly what's wrong and how to fix it
5. **Common Mistake Detection**:
   - Missing required 'key' field
   - Missing content (neither 'text' nor 'data')
   - Both 'text' and 'data' provided (conflicting)
   - Wrong data type (not a dict)

## Testing

All validation cases tested and working:

```bash
✅ Test 1 PASSED - Missing key error
✅ Test 2 PASSED - Missing content error
✅ Test 3 PASSED - Both text and data error
✅ Test 4 PASSED - Valid input accepted
```

## Benefits

- **Reduced debugging time**: Users immediately understand what went wrong
- **Better DX**: Clear, actionable error messages reduce frustration
- **Fewer support requests**: Self-explanatory errors enable self-service
- **Maintainable**: Simple inline validation is easy to understand and modify

## Implementation Pattern

The enhanced validation pattern can be replicated for other dict-to-Pydantic conversions:

```python
@field_validator("field_name")
@classmethod
def validate_field(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate field structure with enhanced error messages."""

    # 1. Validate container type
    if not isinstance(v, list):
        raise ValueError("field must be a list")

    # 2. Validate each item
    for idx, item in enumerate(v):
        # 2a. Check item type
        if not isinstance(item, dict):
            raise ValueError(f"Item at index {idx} must be a dict")

        # 2b. Check required fields
        if "required_field" not in item:
            error_lines = [
                f"Invalid item at index {idx}: Missing required field",
                "",
                "Each item must have:",
                "  - required_field: description",
                "",
                "Example:",
                '  {"required_field": "value"}',
            ]
            raise ValueError("\n".join(error_lines))

        # 2c. Check field constraints
        if some_constraint_violated:
            raise ValueError(
                f"Item at index {idx}: Specific error message\n"
                "Helpful guidance on how to fix"
            )

    return v
```

## Future Work

Consider applying this pattern to:

1. **DataVisualizationParams.data** - Multiple format validation
2. **WorkflowTemplateApplyParams.params** - Template-specific validation
3. Other union types involving dicts throughout the codebase

## Files Modified

- `/Users/ernest/GitHub/quilt-mcp-server/src/quilt_mcp/models/inputs.py`
  - Enhanced `BucketObjectsPutParams.validate_items()` validator
  - Improved field documentation and examples
  - Removed intermediate `BucketObjectsPutItem` model (simplified by linter)
