# Search and Packaging Fixes (2025-10-03)

## Issues Fixed

### 1. Package Naming Validation
**Problem**: Package names were being rejected by the backend even when they appeared valid.

**Root Cause**: 
- Backend requires **lowercase only** (`^[a-z0-9][a-z0-9\-_]*$`)
- Our validation was allowing uppercase letters
- Package names MUST be in `namespace/packagename` format with BOTH parts

**Solution**:
- Updated `src/quilt_mcp/utils.py:validate_package_name()` to match backend validation
- Improved error messages in `src/quilt_mcp/tools/packaging.py` to clearly explain:
  - Must have exactly one `/` separator
  - Must be lowercase only
  - Examples of valid names: `demo-team/csv-data`, `myteam/dataset1`
- Enhanced docstring in `package_create()` to emphasize the `namespace/packagename` requirement

**Valid Package Names**:
- ✅ `demo-team/csv-data`
- ✅ `myteam/csvexample2`
- ✅ `user123/my_dataset`
- ❌ `csvdata` (missing namespace)
- ❌ `MyTeam/Data` (uppercase not allowed)
- ❌ `team/csv-` (ends with hyphen)

### 2. Search File Extension Filtering
**Problem**: Searching for "csv" was returning all files containing "csv" in their content, not just `.csv` files.

**Root Cause**:
- Query parser didn't extract file extensions from standalone queries like "csv"
- It only worked for "csv files", "*.csv", ".csv files", etc.

**Solution**:
- Updated `src/quilt_mcp/search/core/query_parser.py:_extract_file_extensions()` to:
  - Recognize standalone common file extensions (`csv`, `json`, `parquet`, etc.)
  - Support longer extensions (increased length limit from 5 to 10 characters)
  - Added common extensions: `csv`, `json`, `parquet`, `txt`, `md`, `pdf`, `xlsx`, `xls`, `xml`, `yaml`, `yml`, `tsv`, `avro`, `orc`, `feather`, `hdf5`, `h5`, `html`, `ipynb`

**Now Works**:
- ✅ `csv` → filters by `.csv` extension
- ✅ `*.csv` → filters by `.csv` extension
- ✅ `csv files` → filters by `.csv` extension
- ✅ `json` → filters by `.json` extension
- ✅ `parquet` → filters by `.parquet` extension

## Files Modified

1. **src/quilt_mcp/utils.py**
   - `validate_package_name()` - Updated regex pattern to `^[a-z0-9][a-z0-9\-_]*$` (lowercase only)
   
2. **src/quilt_mcp/tools/packaging.py**
   - `_validate_package_name()` - Comprehensive error messages with examples
   - `package_create()` - Enhanced docstring with clear requirements and examples

3. **src/quilt_mcp/search/core/query_parser.py**
   - `_extract_file_extensions()` - Added standalone extension detection
   - Increased extension length limit to 10 characters
   - Added comprehensive list of common file extensions

## Testing

### Package Naming Tests
```python
# Valid names (should pass)
validate_package_name("demo-team/csv-data")  # ✅
validate_package_name("myteam/csvexample2")  # ✅
validate_package_name("user_123/my_dataset")  # ✅

# Invalid names (should fail)
validate_package_name("csvdata")  # ❌ Missing namespace
validate_package_name("MyTeam/Data")  # ❌ Uppercase
validate_package_name("team/csv-")  # ❌ Ends with hyphen
```

### Search Extension Tests
```python
from quilt_mcp.search.core.query_parser import QueryParser
parser = QueryParser()

# All should extract 'csv' extension
parser.parse("csv", scope="bucket", target="bucket")
parser.parse("*.csv", scope="bucket", target="bucket")
parser.parse("csv files", scope="bucket", target="bucket")
parser.parse(".csv files", scope="bucket", target="bucket")
```

## Deployment

Version: 0.6.57-fixed
- Docker Image: `850787717197.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:0.6.57`
- Task Definition: `quilt-mcp-server:151`
- Service: `sales-prod-mcp-server-production`
- Cluster: `sales-prod`

## Expected Behavior

### Package Creation
When an LLM attempts to create a package, it will now receive clear guidance:

**Before**:
```
"error": "Invalid package name: csvexample2"
```

**After** (if namespace missing):
```
"error": "Invalid package name: 'csvdata'. Missing namespace separator '/'.
Package names MUST be in format 'namespace/packagename'
Examples:
  ✓ 'demo-team/csv-data'
  ✓ 'myteam/csvexample2'
  ✗ 'csvdata' (missing namespace)
  ✗ 'MyTeam/Data' (uppercase not allowed)"
```

### Search
When searching for CSV files:

**Before**: Search for "csv" returned JSON files, README files, and any file containing "csv" in content (19 results, mostly irrelevant)

**After**: Search for "csv" returns only `.csv` files (3 results):
- `demo-user/csv-collection/1_Cells.csv`
- `demo-user/csv-collection/gene_expression.csv`
- `demo-user/csv-collection/Cells.csv`

## Related Documentation

- Quilt Package Naming: Must follow `^[a-z0-9][a-z0-9\-_]*$` pattern
- Backend validation in: `enterprise/registry/quilt_server/pkgpush.py`
- GraphQL mutation: `packageConstruct`

