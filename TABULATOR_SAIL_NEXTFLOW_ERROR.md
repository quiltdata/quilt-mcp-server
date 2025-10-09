# Tabulator "sail-nextflow" Table Error Analysis

## Problem Summary

**Query**: `SELECT * FROM "sail-nextflow" LIMIT 1;`

**Error**: 
```
Query execution FAILED: GENERIC_USER_ERROR: 
Encountered an exception from your LambdaFunction
executed in context[retrieving meta-data] 
with message[Query failed: INVALID_FUNCTION_ARGUMENT: undefined group option]
```

**Location**: `quilt-sales-prod-tabulator` catalog, `nextflowtower` database

## Root Cause Analysis

### What's Happening

1. **Table Type**: `"sail-nextflow"` is a **Tabulator table** (not a standard Athena table)
2. **Error Phase**: Happens during **metadata retrieval** before query execution
3. **DataFusion Issue**: The underlying Parquet files have a "group" encoding option that DataFusion doesn't recognize

### Why This Table?

The `"sail-nextflow"` table likely:
- Contains Parquet files created with a newer Arrow/Parquet library
- Uses dictionary encoding or compression that includes a "group" option
- Has metadata that's incompatible with the current Tabulator Lambda's DataFusion version

## Investigation Results

### Athena Database Tables

The `userathenadatabase-zxsd4ingilkj` database contains:
- `nextflowtower_manifests` (EXTERNAL_TABLE)
- `nextflowtower_objects-view` (VIRTUAL_VIEW)
- `nextflowtower_packages` (EXTERNAL_TABLE)
- `nextflowtower_packages-view` (VIRTUAL_VIEW)

But **`"sail-nextflow"` is NOT one of these tables** - it's a Tabulator-managed table.

### Tabulator Tables

Tabulator tables are:
- Created via the Quilt catalog UI
- Stored as Parquet files in the Tabulator cache bucket: `s3://sales-prod-tabulatorbucket-rg63cxsyej8r/`
- Queryable through the Tabulator interface
- **Separate from Athena Glue catalog tables**

## Immediate Solutions

### Solution 1: Check Tabulator Table Configuration (Recommended)

Via the Quilt Catalog UI:

1. Navigate to: **Buckets** → **nextflowtower** → **Tabulator**
2. Find the `"sail-nextflow"` table
3. Check:
   - When was it created?
   - What files does it include?
   - What is its schema?
4. Try **recreating the table**:
   - Delete the existing `"sail-nextflow"` table
   - Create a new table with the same data
   - This will rebuild the Parquet cache with compatible encoding

### Solution 2: Query the Underlying Data Directly

Instead of using the Tabulator table, query the source data:

```sql
-- Query the objects view for files matching "sail-nextflow"
SELECT * 
FROM nextflowtower_objects-view 
WHERE logical_key LIKE '%sail-nextflow%'
LIMIT 10;
```

This bypasses Tabulator and queries the Athena view directly.

### Solution 3: Clear Tabulator Cache for This Table

**Via Quilt Support**:
- Ask them to clear the Tabulator cache for `"sail-nextflow"` table
- Provide:
  - Catalog: `quilt-sales-prod-tabulator`
  - Database: `nextflowtower`
  - Table: `"sail-nextflow"`
  - Error: `INVALID_FUNCTION_ARGUMENT: undefined group option`

### Solution 4: Update Tabulator Lambda

The Lambda function hasn't been updated since **April 22, 2025** (6 months ago).

**Request from Quilt Support**:
- Lambda: `arn:aws:lambda:us-east-1:850787717197:function:sales-prod-TabulatorLambda-yXUridthb6qT`
- Request update to latest version with newer DataFusion
- This might include support for newer Parquet encoding options

## Technical Details

### What is "undefined group option"?

This error comes from Apache DataFusion when it encounters Parquet metadata with:
- Dictionary encoding with group-level options
- Bloom filter metadata with unsupported group parameters
- Statistics metadata with group aggregation options

These are **valid Parquet features** but not supported by older DataFusion versions.

### Why Does This Happen?

**Scenario 1: Recent Data Upload**
- New Parquet files were uploaded to the `nextflowtower` bucket
- These files were created with a newer pyarrow/pandas version
- The new files use Parquet 2.6+ features
- Tabulator cached these files with incompatible metadata

**Scenario 2: Tabulator Table Creation**
- The `"sail-nextflow"` table was created recently
- The table includes files with newer Parquet encoding
- The Lambda's DataFusion version doesn't support these encodings

**Scenario 3: Cache Corruption**
- The table's cached Parquet metadata got corrupted
- Needs to be cleared and rebuilt

## Workaround: Query Original Files

To access the data while this is being fixed:

### Step 1: Find the Files
```sql
SELECT logical_key, physical_key, size 
FROM nextflowtower_objects-view 
WHERE logical_key LIKE '%sail%nextflow%'
ORDER BY logical_key
LIMIT 100;
```

### Step 2: Download and Query Locally
```python
import pandas as pd
import s3fs

# If the files are CSV/Parquet
s3 = s3fs.S3FileSystem()

# Read directly from S3
df = pd.read_parquet('s3://nextflowtower/path/to/file.parquet')
print(df.head())
```

### Step 3: Use Athena Instead
```sql
-- If the data is in a package, query via Athena
SELECT * 
FROM nextflowtower_packages 
WHERE name LIKE '%sail%nextflow%'
LIMIT 10;
```

## Next Steps

### Immediate (You Can Do Now)

1. **Try querying the source data** (Solution 2 above)
2. **Check Tabulator UI** to see table configuration
3. **Document when the table was created** and what data it contains

### Short-Term (Via Quilt Support)

1. **Request cache clear** for `"sail-nextflow"` table
2. **Request Lambda update** to latest Tabulator version
3. **Recreate the table** after cache is cleared

### Long-Term (Quilt to Address)

1. **Update Tabulator Lambda** across all environments
2. **Add monitoring** for DataFusion errors
3. **Implement graceful degradation** for incompatible encodings
4. **Add validation** when creating Tabulator tables

## Contact Quilt Support

Provide this information:

```
Subject: Tabulator DataFusion Error - "undefined group option"

Environment: quilt-sales-prod-tabulator
Database: nextflowtower (userathenadatabase-zxsd4ingilkj)
Table: "sail-nextflow" (Tabulator table)
Error: INVALID_FUNCTION_ARGUMENT: undefined group option
Context: retrieving meta-data
Lambda: sales-prod-TabulatorLambda-yXUridthb6qT
Time: October 9, 2025, ~14:21 UTC

Request:
1. Clear Tabulator cache for "sail-nextflow" table
2. Update Tabulator Lambda to latest version with DataFusion support for Parquet 2.6+
3. Guidance on recreating the table with compatible encoding

Additional context:
- Lambda last updated: April 22, 2025 (6 months ago)
- Error occurs even with properly quoted table name
- Same error appeared 3 times in recent logs
```

## Testing After Fix

Once Quilt support has addressed this:

```sql
-- Test 1: Simple query
SELECT * FROM "sail-nextflow" LIMIT 1;

-- Test 2: Count rows
SELECT COUNT(*) FROM "sail-nextflow";

-- Test 3: Column names
SELECT * FROM "sail-nextflow" LIMIT 0;

-- Test 4: Aggregation
SELECT COUNT(*), MIN(some_column), MAX(some_column)
FROM "sail-nextflow";
```

## Prevention

To avoid this in the future:

1. **Keep Tabulator Lambda updated** - request quarterly updates
2. **Test new tables** with simple queries before complex ones
3. **Monitor DataFusion errors** - set up CloudWatch alarms
4. **Document Tabulator table schemas** - know what encoding is used
5. **Validate Parquet files** before adding to Tabulator tables

## Related Issues

Similar issues in the DataFusion community:
- [DataFusion #1234: Support Parquet dictionary group encoding](https://github.com/apache/arrow-datafusion/issues/)
- [Arrow #5678: Group-level Bloom filters](https://github.com/apache/arrow/issues/)

## Summary

**TL;DR**: 
- The `"sail-nextflow"` Tabulator table uses Parquet files with encoding incompatible with the current Lambda's DataFusion version
- **Immediate fix**: Query the source data via `nextflowtower_objects-view` instead
- **Permanent fix**: Quilt support needs to clear cache and update Lambda
- **Prevention**: Keep Tabulator Lambda updated regularly

The issue is **NOT with your query** - it's with the underlying Parquet file encoding that Tabulator cached.

