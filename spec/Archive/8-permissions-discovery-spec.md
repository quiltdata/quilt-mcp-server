# Phase 8: AWS Permissions Discovery Specification

## Overview

Phase 8 implements intelligent AWS permissions discovery functionality that allows the MCP server to understand user's S3 bucket access levels (read, write, list) and provide smart recommendations for package creation workflows based on actual permissions.

## Requirements

### Functional Requirements

- **Permission Detection**: Automatically discover read/write/list permissions for S3 buckets
- **Smart Bucket Recommendations**: Suggest appropriate buckets based on access levels and naming patterns
- **Interactive Permission Checking**: Real-time validation of bucket access during workflows
- **Permission-aware Workflows**: Adapt package creation flows based on discovered permissions
- **Error Prevention**: Proactively prevent operations that would fail due to insufficient permissions

### Quality Requirements

- **Non-intrusive Discovery**: Permission checking without affecting user's AWS resources
- **Efficient Caching**: Cache permission results to avoid repeated API calls
- **Graceful Degradation**: Function even when some permission checks fail
- **Security Conscious**: Never attempt operations that could modify resources during discovery
- **Performance Optimized**: Minimal AWS API calls with intelligent batching

### Technical Requirements

- **AWS IAM Integration**: Use AWS STS and IAM APIs for permission discovery
- **Bucket Policy Analysis**: Parse and understand S3 bucket policies
- **Resource-based Permissions**: Understand both user-based and resource-based permissions
- **Cross-account Support**: Handle cross-account bucket access scenarios
- **Permission Caching**: Intelligent caching with appropriate TTL

## Implementation Details

### Permission Discovery Workflow

**Discovery Process:**
1. **Identity Discovery**: Determine current AWS identity (user/role)
2. **Policy Enumeration**: List attached policies and inline policies
3. **Bucket Discovery**: Find accessible buckets through listing and inference
4. **Permission Testing**: Safe, non-destructive permission validation
5. **Result Caching**: Store results with appropriate expiration
6. **Smart Recommendations**: Generate bucket suggestions based on permissions

### Permission Levels

**Access Level Classification:**
- **FULL_ACCESS**: Read, write, delete, and manage permissions
- **READ_WRITE**: Read and write objects, but cannot manage bucket
- **READ_ONLY**: Can list and read objects, cannot modify
- **LIST_ONLY**: Can list bucket contents but cannot read objects
- **NO_ACCESS**: No detectable permissions to the bucket

### Smart Recommendation Engine

**Recommendation Logic:**
```python
def recommend_target_buckets(source_bucket: str, operation_type: str) -> List[BucketRecommendation]:
    """
    Recommend appropriate target buckets based on:
    - User's write permissions
    - Naming patterns and conventions
    - Organization policies
    - Source bucket relationships
    """
```

**Recommendation Categories:**
- **Primary Recommendations**: Buckets with full write access and logical naming
- **Alternative Options**: Other writable buckets with explanation
- **Organization Buckets**: Company/team buckets following naming conventions
- **Personal Buckets**: User-owned buckets for individual use

### Permission Discovery Tools

**New MCP Tools:**

#### `aws_permissions_discover`
```python
async def aws_permissions_discover(
    check_buckets: Optional[List[str]] = None,
    include_cross_account: bool = False,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Discover AWS permissions for current user/role.
    
    Args:
        check_buckets: Specific buckets to check (optional)
        include_cross_account: Include cross-account accessible buckets
        force_refresh: Force refresh of cached permissions
        
    Returns:
        Comprehensive permission report with bucket access levels
    """
```

#### `bucket_access_check`
```python
async def bucket_access_check(
    bucket_name: str,
    operations: List[str] = ["read", "write", "list"]
) -> Dict[str, Any]:
    """
    Check specific access permissions for a bucket.
    
    Args:
        bucket_name: S3 bucket to check
        operations: List of operations to validate
        
    Returns:
        Detailed access report for the specified bucket
    """
```

#### `bucket_recommendations_get`
```python
async def bucket_recommendations_get(
    source_bucket: str = None,
    operation_type: str = "package_creation",
    user_context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Get smart bucket recommendations based on permissions and context.
    
    Args:
        source_bucket: Source bucket for context (optional)
        operation_type: Type of operation needing bucket access
        user_context: Additional context (department, project, etc.)
        
    Returns:
        Categorized bucket recommendations with rationale
    """
```

### Permission Discovery Implementation

**Core Permission Discovery Engine:**
```python
class AWSPermissionDiscovery:
    def __init__(self):
        self.sts_client = boto3.client('sts')
        self.iam_client = boto3.client('iam')
        self.s3_client = boto3.client('s3')
        self.permission_cache = TTLCache(maxsize=1000, ttl=3600)  # 1 hour cache
    
    async def discover_user_identity(self) -> Dict[str, Any]:
        """Discover current AWS identity and basic info."""
        
    async def discover_bucket_permissions(self, bucket_name: str) -> PermissionLevel:
        """Discover permission level for specific bucket."""
        
    async def discover_accessible_buckets(self) -> List[BucketInfo]:
        """Discover all buckets user has any level of access to."""
        
    async def test_bucket_operations(self, bucket_name: str) -> Dict[str, bool]:
        """Safely test specific operations on bucket."""
```

### Safe Permission Testing

**Non-destructive Testing Methods:**
- **List Test**: `s3:ListBucket` operation
- **Read Test**: `s3:GetObject` on non-existent key (expect 404, not 403)
- **Write Test**: `s3:PutObject` with dry-run or immediate delete
- **Policy Analysis**: Parse bucket policies and IAM policies
- **STS Simulation**: Use `sts:simulate-principal-policy` when available

### Integration with S3-to-Package Tool

**Enhanced Package Creation Workflow:**
1. **Source Analysis**: Check read permissions on source bucket
2. **Target Discovery**: Discover writable buckets for package storage
3. **Smart Suggestions**: Recommend appropriate target based on naming patterns
4. **Permission Validation**: Validate all required permissions before starting
5. **Fallback Options**: Provide alternatives if primary choice lacks permissions

## User Experience Flow

### 1. Permission Discovery Request
```
User: "What S3 buckets can I write to?"

MCP: "Discovering your AWS permissions...
     
     ✅ Full Access (3 buckets):
     - s3://my-data-packages (recommended for packages)
     - s3://my-ml-experiments 
     - s3://personal-storage
     
     📖 Read-Only Access (5 buckets):
     - s3://company-public-data
     - s3://shared-datasets
     - s3://archived-reports
     - s3://ml-training-data
     - s3://analytics-warehouse
     
     ❌ No Access Detected:
     - s3://restricted-data (access denied)
     
     💡 Recommendations for package creation:
     - Use s3://my-data-packages for new Quilt packages
     - s3://my-ml-experiments for ML-related packages"
```

### 2. Smart Package Creation
```
User: "Create a package from s3://ml-training-data/model-v2/"

MCP: "Analyzing permissions...
     
     Source: s3://ml-training-data/ ✅ (read access confirmed)
     
     Target recommendations:
     1. s3://my-ml-experiments ✅ (full write access, ML naming pattern)
     2. s3://my-data-packages ✅ (full write access, general packages)
     
     Suggested package: ml-team/model-v2-training
     Target registry: s3://my-ml-experiments
     
     Proceed with package creation? (Y/n)"
```

### 3. Permission-Aware Error Prevention
```
User: "Create a package in s3://company-restricted/"

MCP: "❌ Cannot create package in s3://company-restricted/
     
     Issue: Insufficient write permissions
     Details: You have read-only access to this bucket
     
     ✅ Alternative options:
     1. s3://my-data-packages (recommended)
     2. s3://my-ml-experiments
     
     Would you like me to create the package in s3://my-data-packages instead?"
```

## Validation Process

The SPEC-compliant validation follows this 6-step process:

1. **Preconditions** (`make init`): Check AWS credentials and basic connectivity
2. **Execution** (`make run`): Execute permission discovery workflows
3. **Testing** (`make test`): Validate permission detection accuracy
4. **Verification** (`make verify`): Confirm MCP tools respond correctly
5. **Zero** (`make zero`): Clean up test resources and cache
6. **Config** (`make config`): Generate `.config` with discovery results

## Success Criteria

- ✅ Accurately detects read/write permissions for accessible buckets
- ✅ Provides smart bucket recommendations based on naming patterns
- ✅ Integrates seamlessly with S3-to-package creation workflow
- ✅ Caches permission results to minimize AWS API calls
- ✅ Handles permission errors gracefully with helpful alternatives
- ✅ Supports cross-account bucket access scenarios
- ✅ Non-destructive testing methods ensure no unintended modifications
- ✅ Performance optimized with intelligent batching and caching

## Files and Structure

```text
app/quilt_mcp/tools/
├── permissions.py             # AWS permission discovery tools
├── bucket_recommender.py      # Smart bucket recommendation engine
└── permission_cache.py        # Permission result caching

app/quilt_mcp/aws/
├── __init__.py
├── permission_discovery.py    # Core permission discovery engine
├── policy_analyzer.py         # IAM/bucket policy analysis
└── safe_testing.py           # Non-destructive permission testing

spec/
└── 8-permissions-discovery-spec.md  # This specification

tests/
├── test_permissions.py        # Permission discovery tests
├── test_bucket_recommender.py # Recommendation engine tests
└── test_integration_permissions.py # Integration tests
```

## Security Considerations

- **Read-Only Discovery**: Never attempt write operations during discovery
- **Minimal API Calls**: Efficient discovery to avoid rate limiting
- **Error Handling**: Graceful handling of permission denied responses
- **Cache Security**: Secure storage of cached permission data
- **Cross-Account Safety**: Careful handling of cross-account scenarios

## Performance Optimization

- **Intelligent Caching**: TTL-based caching with appropriate expiration
- **Batch Operations**: Group multiple permission checks when possible
- **Lazy Loading**: Discover permissions on-demand rather than upfront
- **Result Streaming**: Stream results for large bucket lists
- **Background Refresh**: Async refresh of cached permissions

## Environment Variables

- `AWS_PERMISSION_CACHE_TTL`: Cache TTL in seconds (default: 3600)
- `AWS_PERMISSION_DISCOVERY_TIMEOUT`: Discovery timeout in seconds (default: 30)
- `ENABLE_CROSS_ACCOUNT_DISCOVERY`: Enable cross-account bucket discovery (default: false)
- `PERMISSION_DISCOVERY_BATCH_SIZE`: Batch size for bulk operations (default: 10)
