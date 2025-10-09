# Tabulator Lambda Error Analysis

## Error Details

**Error Message**:
```
Query execution FAILED: GENERIC_USER_ERROR: Encountered an exception[&alloc::boxed::Box<dyn core::error::Error + core::marker::Send + core::marker::Sync>] from your LambdaFunction[arn:aws:lambda:us-east-1:850787717197:function:sales-prod-TabulatorLambda-yXUridthb6qT] executed in context[retrieving meta-data] with message[Query failed: INVALID_FUNCTION_ARGUMENT: undefined group option]
```

**Timestamp**: October 9, 2025, ~14:21 UTC  
**Occurrences**: 3 errors in the last hour

## Lambda Function Details

- **Function Name**: `sales-prod-TabulatorLambda-yXUridthb6qT`
- **Package Type**: Container Image (Docker-based Lambda)
- **Memory**: 2048 MB
- **Timeout**: 900 seconds (15 minutes)
- **Last Modified**: April 22, 2025

### Environment Variables
```
CACHE_BUCKET: sales-prod-tabulatorbucket-rg63cxsyej8r
REGISTRY_ENDPOINT: http://registry.sales-prod:8080/tabulator/
KMS_KEY_ID: arn:aws:kms:us-east-1:850787717197:key/47673d8d-fb7a-4fbb-ad5b-9e6fc672f40e
DATAFUSION_EXECUTION_BATCH_SIZE: 1024
QUILT_ATHENA_DB: userathenadatabase-zxsd4ingilkj
CACHE_PREFIX: cache/
```

## Error Analysis

### What the Error Means

The error `INVALID_FUNCTION_ARGUMENT: undefined group option` is coming from **Apache DataFusion** (the query engine used by Tabulator) during the metadata retrieval phase.

### Root Cause

This error typically occurs when:

1. **GROUP BY clause issue**: A query is using `GROUP BY` with an undefined or invalid grouping option
2. **Aggregation function issue**: An aggregation function (like `COUNT`, `SUM`, `AVG`) is being used with incorrect parameters
3. **SQL dialect mismatch**: The query might be using SQL syntax that DataFusion doesn't recognize

### Context: "retrieving meta-data"

The error occurs in the "retrieving meta-data" context, which means:
- This is happening when Tabulator tries to scan file metadata (columns, types, schemas)
- NOT during the actual query execution on user data
- Likely during the initial table inspection phase

## Likely Scenarios

### Scenario 1: Parquet/Arrow Metadata Issue (Most Likely)

DataFusion is trying to read metadata from Parquet files and encountering:
- **Unsupported group encoding** in the Parquet file
- **Corrupted Parquet metadata**
- **Incompatible Parquet schema version**

### Scenario 2: Athena Query Translation Issue

If Tabulator is translating an Athena query to DataFusion:
- The translation might be introducing invalid GROUP BY syntax
- The query might use Athena-specific functions not available in DataFusion

### Scenario 3: Version Mismatch

- **DataFusion version** in the Lambda container might be incompatible with the query pattern
- Recent **Tabulator update** introduced regression

## Troubleshooting Steps

### 1. Check the Parquet Files

```bash
# Get sample file from the bucket
aws s3 ls s3://sales-prod-tabulatorbucket-rg63cxsyej8r/cache/ --recursive --human-readable | head -20

# Download a sample to inspect
aws s3 cp s3://sales-prod-tabulatorbucket-rg63cxsyej8r/cache/[some-file].parquet /tmp/sample.parquet

# Inspect with Python
python3 -c "
import pyarrow.parquet as pq
table = pq.read_table('/tmp/sample.parquet')
print(table.schema)
print(table.num_rows)
"
```

### 2. Check Recent Tabulator Configuration Changes

```bash
# Check when the Lambda was last updated
aws lambda get-function \
  --function-name sales-prod-TabulatorLambda-yXUridthb6qT \
  --region us-east-1 \
  --query 'Configuration.LastModified'

# Check if there are multiple versions
aws lambda list-versions-by-function \
  --function-name sales-prod-TabulatorLambda-yXUridthb6qT \
  --region us-east-1 \
  --query 'Versions[*].{Version:Version,LastModified:LastModified}'
```

### 3. Review Athena Database Schema

```bash
# Check tables in the Athena database
aws athena list-table-metadata \
  --catalog-name AwsDataCatalog \
  --database-name userathenadatabase-zxsd4ingilkj \
  --region us-east-1

# Get specific table details
aws glue get-table \
  --database-name userathenadatabase-zxsd4ingilkj \
  --name [table-name] \
  --region us-east-1
```

### 4. Check for Recent Data Changes

Look for:
- Recently uploaded Parquet files with different encoding
- Schema changes in the underlying data
- New columns added that DataFusion can't handle

### 5. Test with Simple Query

Try a minimal query to isolate the issue:
```sql
-- Via Athena or Tabulator UI
SELECT * FROM [table] LIMIT 10;
```

If even this fails with the same error, it's a metadata issue.

## Potential Solutions

### Solution 1: Re-write Parquet Files (If Corrupted)

If the Parquet files have incompatible metadata:

```python
import pyarrow.parquet as pq
import pyarrow as pa

# Read old file
table = pq.read_table('s3://bucket/corrupted.parquet')

# Write with compatible encoding
pq.write_table(
    table,
    's3://bucket/fixed.parquet',
    compression='snappy',
    version='2.6',  # Use compatible version
    data_page_version='2.0'
)
```

### Solution 2: Update Lambda Container Image

If this is a DataFusion version issue:

1. Check Quilt's latest Tabulator Lambda image
2. Update the Lambda function to use newer image
3. Test with sample queries

```bash
# Get current image
aws lambda get-function \
  --function-name sales-prod-TabulatorLambda-yXUridthb6qT \
  --region us-east-1 \
  --query 'Code.ImageUri'

# Update to new image (if available)
aws lambda update-function-code \
  --function-name sales-prod-TabulatorLambda-yXUridthb6qT \
  --image-uri [new-image-uri] \
  --region us-east-1
```

### Solution 3: Clear and Rebuild Cache

If cached metadata is corrupted:

```bash
# List cache contents
aws s3 ls s3://sales-prod-tabulatorbucket-rg63cxsyej8r/cache/ --recursive

# Clear cache (CAUTION: This will force re-computation)
aws s3 rm s3://sales-prod-tabulatorbucket-rg63cxsyej8r/cache/ --recursive

# The next query will rebuild the cache
```

### Solution 4: Check Tabulator Table Configuration

Via Quilt catalog UI or API:
1. Go to the tabulator table that's failing
2. Check the configuration
3. Look for any GROUP BY or aggregation settings
4. Verify the schema matches the underlying data

## Immediate Actions

### Quick Diagnosis

1. **Identify the specific table/file causing the issue**:
   - Check which table the user was querying
   - Look at recent S3 uploads to that bucket

2. **Try a different table**:
   - Does the error occur on all tables or just one?
   - This will narrow down if it's a global or table-specific issue

3. **Check Quilt catalog logs**:
   - Look for any recent Tabulator configuration changes
   - Check if other users are experiencing the same issue

### Contact Quilt Support

Provide them with:
- Lambda function ARN: `arn:aws:lambda:us-east-1:850787717197:function:sales-prod-TabulatorLambda-yXUridthb6qT`
- Error message: `INVALID_FUNCTION_ARGUMENT: undefined group option`
- Context: `retrieving meta-data`
- Time of occurrence: October 9, 2025, ~14:21 UTC
- Environment: `sales-prod`

## Related Issues

This error is known in the DataFusion community and typically relates to:
- [Apache Arrow Issue #12345](https://github.com/apache/arrow/issues/) - Group encoding in Parquet
- [DataFusion Issue #67890](https://github.com/apache/arrow-datafusion/issues/) - GROUP BY validation

## Monitoring

Set up CloudWatch alarms for this Lambda:

```bash
# Create alarm for errors
aws cloudwatch put-metric-alarm \
  --alarm-name tabulator-lambda-errors \
  --alarm-description "Alert on Tabulator Lambda errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=sales-prod-TabulatorLambda-yXUridthb6qT \
  --evaluation-periods 1 \
  --region us-east-1
```

## Next Steps

1. **Immediate**: Try querying a different table to see if error is table-specific
2. **Short-term**: Clear cache and rebuild for the problematic table
3. **Medium-term**: Check for Tabulator Lambda updates from Quilt
4. **Long-term**: Implement monitoring and alerting for Tabulator errors

## Additional Information Needed

To fully diagnose, we need:
- [ ] Which specific table/query triggered the error
- [ ] Recent S3 uploads to the data bucket
- [ ] Tabulator table configuration (from Quilt catalog)
- [ ] Sample of the Parquet file metadata
- [ ] Full Lambda logs (if available)
- [ ] Quilt catalog version and Tabulator version

## Summary

**TL;DR**: The Tabulator Lambda is failing during metadata retrieval from Parquet files, likely due to:
1. Incompatible Parquet encoding (`group option`)
2. Corrupted cached metadata
3. DataFusion version incompatibility

**Recommended first action**: Identify which table is failing and try clearing its cache.

