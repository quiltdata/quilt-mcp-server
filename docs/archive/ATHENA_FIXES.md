# Athena MCP Server Fixes

## Issue Analysis

After testing the Athena functionality, I identified several specific issues that need fixes:

### 1. String Formatting Bug
**Problem**: Queries with `%` characters cause Python string formatting errors
**Root Cause**: The error messages suggest format string issues when queries contain `%` characters
**Impact**: Queries with LIKE patterns or percentage calculations fail

### 2. Database Name Escaping
**Problem**: Database names with hyphens can't be properly referenced
**Root Cause**: Athena requires double quotes for identifiers with special characters
**Impact**: Some SHOW TABLES and USE database commands fail

### 3. Error Handling Improvements
**Problem**: Generic error messages don't provide actionable guidance
**Root Cause**: Exception handling doesn't distinguish between different error types
**Impact**: Users can't understand how to fix their queries

## Proposed Fixes

### Fix 1: Resolve String Formatting Issues

The issue appears to be in the error handling or logging where string formatting is applied incorrectly.

**Location**: `app/quilt_mcp/aws/athena_service.py` and error handling

**Problem**: When queries contain `%` characters, Python's string formatting treats them as format specifiers.

**Solution**: Use proper string formatting or raw strings for error messages.

### Fix 2: Improve Database Name Handling

**Location**: `app/quilt_mcp/aws/athena_service.py` - `discover_tables` method

**Current Code**:
```python
query = f"SHOW TABLES IN {database_name}"
```

**Fixed Code**:
```python
# Properly escape database names with special characters
if '-' in database_name or any(c in database_name for c in [' ', '.', '@']):
    query = f'SHOW TABLES IN "{database_name}"'
else:
    query = f"SHOW TABLES IN {database_name}"
```

### Fix 3: Enhanced Error Messages

**Location**: `app/quilt_mcp/tools/athena_glue.py` - `athena_query_execute`

**Add specific error handling for common issues**:
- Permission errors → suggest IAM fixes
- Syntax errors → provide corrected syntax
- Table not found → suggest discovery commands

### Fix 4: Query Validation and Sanitization

**Location**: `app/quilt_mcp/tools/athena_glue.py` - `athena_query_execute`

**Add pre-execution validation**:
- Check for unsupported syntax patterns
- Validate identifier quoting
- Suggest corrections for common mistakes
