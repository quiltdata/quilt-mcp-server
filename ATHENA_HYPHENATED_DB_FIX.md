# Athena Hyphenated Database Name Fix

## Issue Summary

**Critical Bug**: Athena queries fail when database names contain hyphens (e.g., `userathenadatabase-k60cyxsioyx2`)

**Error Message**:
```
(pyathena.error.DatabaseError) An error occurred (InvalidRequestException) when calling the StartQueryExecution operation: 
line 1:5: mismatched input '"userathenadatabase-k60cyxsioyx2"' expecting {...}
[SQL: USE "userathenadatabase-k60cyxsioyx2"]
```

**Root Cause**: The `execute_query` method in `AthenaQueryService` was using `USE "database-name"` statements, which Athena SQL doesn't support for databases with hyphens or special characters.

## Customer Impact

- **Affected Users**: Customers using Quilt Tabulator with AWS Glue databases that have hyphenated names
- **Example**: Sail Biomedicines customer trying to query `salmon_gene_expression` tabulator table
- **Severity**: **CRITICAL** - Blocks all tabulator queries for affected databases

## Fix Implemented

### Branch: `dev`
### Commits:
1. `46f7519` - Initial fix attempt (USE statement removal with schema_name parameter)
2. `39de7a5` - Improved fix (query rewriting approach)

### Technical Solution

Modified `src/quilt_mcp/services/athena_service.py`:

1. **Removed buggy USE statement** (lines 340-348):
   ```python
   # OLD CODE (BROKEN):
   if database_name:
       if "-" in database_name:
           escaped_db = f'"{database_name}"'
       else:
           escaped_db = database_name
       
       with self.engine.connect() as conn:
           conn.execute(text(f"USE {escaped_db}"))  # ❌ Fails for hyphenated names
   ```

2. **Implemented query rewriting** (new approach):
   ```python
   # NEW CODE (FIXED):
   def _ensure_qualified_table_names(self, query: str, database_name: str) -> str:
       """Automatically qualify table names with database prefix.
       
       Transforms:
           FROM salmon_gene_expression
       To:
           FROM "userathenadatabase-k60cyxsioyx2".salmon_gene_expression
       """
       # Quote database name if it has hyphens
       needs_quoting = "-" in database_name or any(c in database_name for c in [" ", ".", "@", "/"])
       qualified_db = f'"{database_name}"' if needs_quoting else database_name
       
       # Rewrite FROM/JOIN clauses to use fully-qualified table names
       pattern = r'\b(FROM|JOIN)\s+((?:"[^"]+"|[\w$]+))'
       qualified_query = re.sub(pattern, qualify_table, query, flags=re.IGNORECASE)
       
       return qualified_query
   ```

### Why This Works

1. **Athena SQL Requirements**:
   - `USE "database-name"` ❌ Invalid syntax
   - `SELECT * FROM "database-name".table_name` ✅ Valid syntax

2. **Query Rewriting Approach**:
   - Automatically detects unqualified table names
   - Adds database prefix with proper quoting
   - Works with both quoted and unquoted table names
   - Handles special characters ($, hyphens, etc.)

## Testing Status

### Local Testing Limitations

⚠️ **Cannot fully test locally** due to AWS account mismatch:
- Local credentials point to `sales-prod` AWS account (850787717197)
- Test database `userathenadatabase-k60cyxsioyx2` exists in customer's AWS account
- Tabulator table `salmon_gene_expression` only exists in customer environment

### Verified Behaviors

✅ **Query rewriting logic works correctly**:
```python
# Input query:
"SELECT * FROM salmon_gene_expression WHERE study_id = 'A549'"

# With database_name="userathenadatabase-k60cyxsioyx2"
# Output query:
'SELECT * FROM "userathenadatabase-k60cyxsioyx2".salmon_gene_expression WHERE study_id = \'A549\''
```

✅ **No credential signature errors** (previous approach had AWS signature mismatches)

✅ **Handles hyphenated database names** in qualification logic

### Customer Testing Required

The fix needs to be tested in the customer's environment where:
1. Database `userathenadatabase-k60cyxsioyx2` exists
2. Tabulator table `salmon_gene_expression` is configured
3. AWS credentials have proper Glue/Athena permissions

## Deployment Steps

1. **Merge `dev` branch** into `main` (after customer testing)
2. **Create release** (bump version)
3. **Deploy to production** ECS/Docker
4. **Update Cursor MCP config** to use `@main` branch

## Related Files

- `src/quilt_mcp/services/athena_service.py` - Core fix
- `src/quilt_mcp/tools/athena_glue.py` - Tool interface
- `~/.cursor/mcp.json` - Currently configured to use `@dev` branch for testing

## Customer Query Example

```python
# Original failing query:
athena_query_execute(
    query="""SELECT "Name", "TPM", study_id, sample_id
FROM salmon_gene_expression
WHERE study_id = 'A549'
ORDER BY "TPM" DESC
LIMIT 5""",
    database_name="userathenadatabase-k60cyxsioyx2",
    workgroup_name="QuiltTabulatorOpenQuery-quilt-2",
    max_results=5
)
```

**Expected Behavior After Fix**: Query should succeed and return top 5 genes by TPM for A549 study

## Next Steps

1. ✅ Fix implemented on `dev` branch
2. ✅ Cursor configured to test from `dev` branch
3. ⏳ **Customer testing required** with actual tabulator data
4. ⏳ Merge to `main` after verification
5. ⏳ Production deployment

## Notes

- The fix is defensive and handles both hyphenated and non-hyphenated database names
- Backwards compatible with existing queries
- No performance impact (query rewriting is fast)
- Logging added for debugging (database context requests logged)

---

**Date**: 2025-10-09
**Issue**: Critical Athena query bug
**Status**: Fix implemented, awaiting customer testing
**Branch**: `dev`

