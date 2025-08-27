# Feature Request: S3-to-Package Creation Tool

## Issue Summary
**Feature**: Add MCP tool to create Quilt packages directly from S3 bucket contents

## Problem Statement
Currently, users need to manually download data from S3 and then create Quilt packages using separate tools. This workflow is inefficient and error-prone when working with large datasets stored in S3 buckets.

## Proposed Solution

### New MCP Tool: `package_create_from_s3`

Add a new MCP tool that allows users to:

1. **Browse S3 bucket contents** and select files/folders
2. **Create a new Quilt package** directly from selected S3 objects
3. **Set package metadata** (name, description, tags) during creation
4. **Handle large datasets** efficiently without local downloads
5. **Preserve S3 object metadata** in the package

### Implementation Details

**Tool Signature:**
```python
@mcp.tool()
async def package_create_from_s3(
    source_bucket: str,
    source_prefix: str = "",
    package_name: str,
    target_registry: str,
    target_bucket: str = None,
    description: str = "",
    include_patterns: List[str] = None,
    exclude_patterns: List[str] = None,
    preserve_structure: bool = True,
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Create a Quilt package from S3 bucket contents.
    
    Args:
        source_bucket: S3 bucket containing source data
        source_prefix: Optional prefix to filter source objects
        package_name: Name for the new package (namespace/name format)
        target_registry: Target Quilt registry for the package
        target_bucket: Target S3 bucket (defaults to registry bucket)
        description: Package description
        include_patterns: File patterns to include (glob style)
        exclude_patterns: File patterns to exclude (glob style)  
        preserve_structure: Maintain original S3 folder structure
        metadata: Additional package metadata
        
    Returns:
        Package creation result with package info and stats
    """
```

**Key Features:**
- **Direct S3-to-S3 operations** (no local downloads required)
- **Pattern-based filtering** for selective package creation
- **Metadata preservation** from S3 objects
- **Progress tracking** for large package operations
- **Validation** of package contents before creation
- **Error handling** with rollback capabilities

### User Experience

**Example Usage in Claude:**
```
User: "Create a package from the ML datasets in s3://my-data-bucket/ml-models/ 
       and call it myteam/ml-models-v2"

Claude: "I'll create a Quilt package from your S3 bucket. Let me scan the 
         contents and create the package for you."

[Uses package_create_from_s3 tool]

Claude: "✅ Successfully created package 'myteam/ml-models-v2' with 1,247 files 
         (2.3 GB) from s3://my-data-bucket/ml-models/. 
         Package is available at your Quilt registry."
```

### Benefits

1. **Streamlined Workflow**: Direct S3-to-package creation eliminates manual steps
2. **Efficiency**: No local downloads required for large datasets  
3. **Metadata Preservation**: Maintains S3 object metadata and structure
4. **User-Friendly**: Natural language interface through Claude
5. **Enterprise-Ready**: Supports large-scale data operations

### Acceptance Criteria

- [ ] Tool successfully creates packages from S3 bucket contents
- [ ] Supports pattern-based filtering (include/exclude)
- [ ] Preserves S3 object metadata in package
- [ ] Handles large datasets (>1GB) efficiently
- [ ] Provides progress feedback for long operations
- [ ] Includes comprehensive error handling and validation
- [ ] Maintains package structure options (flat vs. hierarchical)
- [ ] Integrates seamlessly with existing MCP tools
- [ ] Includes unit tests with >90% coverage
- [ ] Documentation and examples provided

### Technical Considerations

**Dependencies:**
- Leverage existing `boto3` integration for S3 operations
- Use `quilt3` package building APIs
- Implement async operations for better performance

**Security:**
- Validates user has read access to source S3 bucket
- Validates user has write access to target registry
- Respects existing IAM permissions and bucket policies

**Performance:**
- Stream S3 objects directly to target without local storage
- Implement parallel processing for multiple objects
- Provide progress callbacks for large operations

### Related Issues

This feature builds upon existing MCP tools:
- `bucket_objects_list` - for S3 content discovery
- `package_create` - for package creation workflow
- `bucket_object_info` - for metadata extraction

### Priority

**High Priority** - This feature addresses a common user workflow and significantly improves the user experience for data scientists and ML engineers working with S3-stored datasets.
