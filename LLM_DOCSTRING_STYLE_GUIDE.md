# LLM-Friendly Docstring Style Guide

## Purpose

When LLMs (Large Language Models) interact with MCP tools, **docstrings are their primary source of information**. Unlike human developers who can read extensive documentation, tutorials, and examples, LLMs see only:

1. Function name
2. Function signature (parameters + types)
3. **Docstring content**

This guide provides patterns for writing docstrings that help LLMs understand:
- **What** the tool does
- **When** to use it
- **How** it fits into multi-step workflows
- **What to do** with the response

## Core Principles

### 1. First Line = Purpose + Context (The "Elevator Pitch")

The first line is the most important. It should answer: "What does this do and when would I use it?"

❌ **Bad** (too vague):
```python
"""Upload objects to a bucket."""
```

✅ **Good** (purpose + context):
```python
"""Upload files to S3 bucket - typically used BEFORE package creation."""
```

✅ **Better** (adds relationship to other tools):
```python
"""Upload files to S3 bucket - Step 1 of 2 for creating packages from local files."""
```

### 2. Show Workflows, Not Just Operations

If your tool is part of a multi-step process, make it explicit with a WORKFLOW section.

❌ **Bad** (isolated description):
```python
def upload_files(...):
    """Upload files to storage.
    
    Args:
        files: List of files to upload
    Returns:
        Upload results
    """
```

✅ **Good** (shows context in workflow):
```python
def upload_files(...):
    """Upload files to storage - Step 1 before processing.
    
    WORKFLOW: 
        1. upload_files() → Get file IDs from response
        2. process_files(file_ids) → Process uploaded files
        3. get_results(job_id) → Retrieve final results
    
    Args:
        files: List of files to upload
    Returns:
        Dict with file IDs needed for next step: process_files()
    """
```

### 3. Explain Returns in Terms of Next Actions

Don't just describe the return structure - tell the LLM what to DO with it.

❌ **Bad** (describes structure only):
```python
Returns:
    Dict with 'status', 'results', and 'metadata' fields.
```

✅ **Good** (actionable guidance):
```python
Returns:
    Dict with upload results. Extract 'results[].id' values and pass to process_files().
    
    Response format:
    {
        "status": "success",
        "results": [
            {"id": "file_001", "name": "data.csv", "size": 1024},
            {"id": "file_002", "name": "readme.md", "size": 512}
        ]
    }
    
    Next step: 
        ids = [item["id"] for item in response["results"]]
        process_files(ids)
```

### 4. Use Visual Hierarchy for Important Information

Use formatting to make critical information stand out to LLMs:

- **ALL CAPS** for critical warnings: `IMPORTANT:`, `WORKFLOW:`, `NOTE:`
- **Bold** for key concepts (in markdown): `**required**`, `**before**`, `**after**`
- **Code examples** for concrete usage
- **Lists** for multiple options or steps

✅ **Example**:
```python
"""Create analysis report from processed data.

IMPORTANT: Data must be processed first using process_files().
WORKFLOW: process_files() → THIS TOOL → export_results()

Args:
    data_ids: List of processed data IDs (from process_files() response)
          **Required format**: ["id_001", "id_002"]
          **Get from**: response["results"][]["id"]
"""
```

### 5. Provide Decision Trees for Tool Selection

When multiple tools solve similar problems, help the LLM choose the right one.

✅ **Example**:
```python
"""Create package from S3 files (MAIN TOOL - use this for most package creation).

WHEN TO USE:
    ✓ Creating package from 1-10 specific S3 files
    ✓ Need precise control over which files to include
    ✓ Files already in S3

WHEN NOT TO USE:
    ✗ Need to package entire S3 prefix → Use bulk_package_create() instead
    ✗ Files on local filesystem → Use upload_then_package() instead
    ✗ Files not yet in S3 → Upload first with upload_files()

ALTERNATIVES:
    - bulk_package_create(): For entire S3 prefixes (100+ files)
    - upload_then_package(): For local files (handles upload automatically)
"""
```

### 6. Include Concrete Examples

LLMs learn patterns from examples. Include realistic, copy-pasteable examples.

✅ **Good example format**:
```python
"""Upload files to S3 bucket.

Example:
    # Upload text and binary files
    result = upload_files(
        bucket="my-bucket",
        files=[
            {"name": "data.csv", "content": "col1,col2\nval1,val2", "type": "text/csv"},
            {"name": "image.png", "content_base64": "iVBORw0KG...", "type": "image/png"}
        ]
    )
    
    # Extract file IDs for next step
    file_ids = [item["id"] for item in result["files"]]
    
    # Process uploaded files
    process_result = process_files(file_ids)
"""
```

### 7. Describe Error Cases and Solutions

Help LLMs handle errors gracefully.

✅ **Example**:
```python
"""Process uploaded files.

Args:
    file_ids: List of file IDs from upload_files() response

Returns:
    Processing results or error details
    
    Success: {"status": "complete", "results": [...]}
    Error: {"status": "error", "message": "...", "suggested_fix": "..."}

Common Errors:
    - "File not found": File IDs invalid or expired (re-upload files)
    - "Permission denied": Check bucket_access_check() for permissions
    - "Format unsupported": Use supported formats (CSV, JSON, Parquet)
"""
```

## Template Patterns

### Pattern A: Simple Single-Step Tool

```python
def tool_name(required_param: str, optional_param: int = 10) -> Dict[str, Any]:
    """[Action] [Object] - [Primary use case].
    
    [One sentence explaining what this does and why you'd use it]
    
    Args:
        required_param: [Description with example]
                       Example: "user@example.com"
        optional_param: [Description] (default: 10)
    
    Returns:
        [Description of structure and what to do with it]
        
        Response format:
        {
            "field1": "value",
            "field2": 123
        }
    
    Example:
        result = tool_name("example@email.com", optional_param=20)
        value = result["field1"]  # Use this value for...
    """
```

### Pattern B: Multi-Step Workflow Tool

```python
def tool_name(...) -> Dict[str, Any]:
    """[Action] [Object] - Step N of M in [workflow name].
    
    WORKFLOW:
        Step 1: first_tool() → Get X from response
        Step 2: THIS TOOL → Get Y from response  
        Step 3: third_tool(Y) → Complete workflow
    
    PREREQUISITES:
        - Must call first_tool() before this
        - Requires X from first_tool() response
    
    Args:
        input_from_previous_step: [Description]
                                  Get from: previous_tool()["field_name"]
    
    Returns:
        Data needed for next step in workflow.
        
        Response format:
        {
            "next_step_input": "value_to_pass_forward",
            "status": "ready"
        }
        
        Next step: third_tool(response["next_step_input"])
    
    Example workflow:
        # Step 1
        step1_result = first_tool("input")
        x_value = step1_result["x"]
        
        # Step 2 (this tool)
        step2_result = tool_name(x_value)
        y_value = step2_result["next_step_input"]
        
        # Step 3
        final_result = third_tool(y_value)
    """
```

### Pattern C: Tool with Multiple Modes/Options

```python
def tool_name(
    mode: str,
    input_data: str,
    ...
) -> Dict[str, Any]:
    """[Action] [Object] - Supports multiple modes for different use cases.
    
    MODE SELECTION:
    ┌──────────────────────────────────────────────────────────┐
    │ Mode: "quick"                                            │
    │ Use when: Need fast results, lower accuracy acceptable  │
    │ Example: tool_name(mode="quick", input_data="...")      │
    ├──────────────────────────────────────────────────────────┤
    │ Mode: "thorough"                                         │
    │ Use when: Need high accuracy, time not critical         │
    │ Example: tool_name(mode="thorough", input_data="...")   │
    ├──────────────────────────────────────────────────────────┤
    │ Mode: "custom"                                           │
    │ Use when: Need specific configuration                   │
    │ Requires: Additional config parameters                  │
    │ Example: tool_name(mode="custom", config={...})         │
    └──────────────────────────────────────────────────────────┘
    
    Args:
        mode: Processing mode: "quick", "thorough", or "custom"
        input_data: [Description]
    
    Returns:
        Results vary by mode (see MODE SELECTION above)
    
    Example (quick mode):
        result = tool_name(mode="quick", input_data="sample text")
        # Fast processing, lower accuracy
    
    Example (thorough mode):
        result = tool_name(mode="thorough", input_data="sample text")
        # Slower but more accurate
    """
```

### Pattern D: Discovery/List Tool

```python
def list_available_resources(...) -> Dict[str, Any]:
    """List all available [resources] - Use to discover what's accessible.
    
    USE BEFORE: Operations that need resource names/IDs
    TYPICAL WORKFLOW:
        1. THIS TOOL → Discover available resources
        2. filter_results() → Find specific resources
        3. operate_on_resource(id) → Perform actual operation
    
    Args:
        filter_param: Optional filter (default: "" for all resources)
    
    Returns:
        List of resources with IDs needed for other operations.
        
        Response format:
        {
            "resources": [
                {"id": "res_001", "name": "Resource 1", "type": "..."},
                {"id": "res_002", "name": "Resource 2", "type": "..."}
            ],
            "total": 2
        }
        
        Use resource IDs: response["resources"][0]["id"]
    
    Example workflow:
        # Discover resources
        discovery = list_available_resources()
        
        # Find specific resource
        target = [r for r in discovery["resources"] if r["name"] == "My Resource"][0]
        target_id = target["id"]
        
        # Operate on resource
        result = operate_on_resource(target_id)
    """
```

## Checklist for Every Docstring

Use this checklist when writing or updating docstrings:

### Essential Elements
- [ ] First line: Clear purpose + context (when to use this)
- [ ] Args: Each parameter explained with examples
- [ ] Returns: Structure + what to do with the data
- [ ] Example: Concrete, copy-pasteable usage

### Workflow Context
- [ ] Multi-step workflows shown explicitly
- [ ] Prerequisites listed (what to do first)
- [ ] Next steps indicated (what to do after)
- [ ] Related tools mentioned

### Decision Support
- [ ] WHEN TO USE section (positive indicators)
- [ ] WHEN NOT TO USE section (negative indicators)
- [ ] ALTERNATIVES section (other tools for similar tasks)

### Error Handling
- [ ] Common errors documented
- [ ] Suggested fixes provided
- [ ] Validation requirements stated

### Examples
- [ ] Success case example
- [ ] Multi-step workflow example (if applicable)
- [ ] Error handling example (if applicable)

## Before/After Examples

### Example 1: File Upload Tool

❌ **Before** (tool-centric, no workflow):
```python
def upload_file(path: str, destination: str) -> dict:
    """Upload a file to the destination.
    
    Args:
        path: File path
        destination: Destination location
    
    Returns:
        Upload result dictionary
    """
```

✅ **After** (workflow-aware, actionable):
```python
def upload_file(path: str, destination: str) -> dict:
    """Upload file to storage - Required first step before processing or analysis.
    
    WORKFLOW: Upload file → Get file_id from response → Pass to process_file()
    
    Args:
        path: Local file path to upload
              Example: "/data/experiment_results.csv"
        destination: Target storage location
                    Format: "bucket-name/folder/subfolder"
                    Example: "my-bucket/experiments/2024"
    
    Returns:
        Upload confirmation with file_id needed for processing.
        
        Response format:
        {
            "success": true,
            "file_id": "file_abc123",
            "location": "s3://my-bucket/experiments/2024/experiment_results.csv",
            "size_bytes": 1024
        }
        
        Next step: process_file(response["file_id"])
    
    Example workflow:
        # Upload file
        upload_result = upload_file(
            path="/data/results.csv",
            destination="my-bucket/experiments/exp-001"
        )
        
        # Get file ID from response
        file_id = upload_result["file_id"]
        
        # Process uploaded file
        process_result = process_file(file_id)
    
    Common errors:
        - "File not found": Check path is absolute or relative to working directory
        - "Permission denied": Verify destination bucket permissions with check_permissions()
    """
```

### Example 2: Data Processing Tool

❌ **Before** (technical, isolated):
```python
def process_data(data_id: str, options: dict) -> dict:
    """Process data with specified options.
    
    Args:
        data_id: Data identifier
        options: Processing options
    
    Returns:
        Processing results
    """
```

✅ **After** (contextual, helpful):
```python
def process_data(data_id: str, options: dict | None = None) -> dict:
    """Process uploaded data - Step 2 of 3 in data analysis workflow.
    
    PREREQUISITES:
        - Data must be uploaded first using upload_file()
        - Use data_id from upload_file() response
    
    WORKFLOW:
        1. upload_file() → Get data_id
        2. THIS TOOL → Get job_id from response
        3. get_results(job_id) → Retrieve processed data
    
    Args:
        data_id: Data identifier from upload_file() response
                Get from: upload_result["file_id"]
                Format: "file_abc123" or "data_xyz789"
        options: Processing options (optional)
                Default behavior: Standard processing with all features
                Custom options: {
                    "format": "csv"|"json"|"parquet",
                    "validate": true|false,
                    "transformations": ["normalize", "dedupe"]
                }
    
    Returns:
        Job status with job_id for tracking and result retrieval.
        
        Response format:
        {
            "status": "processing",
            "job_id": "job_456def",
            "estimated_seconds": 30,
            "next_action": "Call get_results(job_id) after 30 seconds"
        }
        
        Next step: 
            Wait for processing, then call get_results(response["job_id"])
    
    Example workflow:
        # Upload data first
        upload_result = upload_file("/data/raw.csv", "my-bucket/data")
        data_id = upload_result["file_id"]
        
        # Process data
        process_result = process_data(
            data_id=data_id,
            options={"format": "parquet", "validate": true}
        )
        
        # Wait and get results
        import time
        time.sleep(process_result["estimated_seconds"])
        
        final_result = get_results(process_result["job_id"])
    
    Common errors:
        - "Data not found": data_id may be invalid or expired (re-upload)
        - "Invalid format": Check options["format"] is supported
        - "Processing failed": Check source data quality with validate_data()
    """
```

### Example 3: Configuration Tool

❌ **Before** (minimal):
```python
def set_config(key: str, value: str) -> dict:
    """Set configuration value.
    
    Args:
        key: Config key
        value: Config value
    
    Returns:
        Confirmation
    """
```

✅ **After** (informative):
```python
def set_config(key: str, value: str) -> dict:
    """Configure system settings - Affects behavior of all subsequent operations.
    
    IMPORTANT: Configuration changes apply immediately and persist across sessions.
    SCOPE: Affects all tools in this session and future sessions.
    
    COMMON CONFIGURATIONS:
    ┌─────────────────────────────────────────────────────────────┐
    │ Key: "default_bucket"                                       │
    │ Value: S3 bucket name (e.g., "my-data-bucket")             │
    │ Effect: Sets default bucket for all file operations        │
    ├─────────────────────────────────────────────────────────────┤
    │ Key: "output_format"                                        │
    │ Value: "json"|"csv"|"parquet"                               │
    │ Effect: Changes default output format for exports          │
    ├─────────────────────────────────────────────────────────────┤
    │ Key: "log_level"                                            │
    │ Value: "debug"|"info"|"warning"|"error"                     │
    │ Effect: Controls verbosity of operation logs               │
    └─────────────────────────────────────────────────────────────┘
    
    Args:
        key: Configuration key (see COMMON CONFIGURATIONS above)
            View all keys: get_config_schema()
        value: Configuration value (type depends on key)
              Validation: Auto-validated against schema
    
    Returns:
        Confirmation with old and new values.
        
        Response format:
        {
            "success": true,
            "key": "default_bucket",
            "old_value": "previous-bucket",
            "new_value": "my-data-bucket",
            "effect": "All file operations will now use my-data-bucket by default"
        }
    
    Example - Set default bucket:
        result = set_config("default_bucket", "my-production-bucket")
        # Now all upload/download operations use this bucket by default
        upload_file("data.csv")  # Uploads to my-production-bucket
    
    Example - Change output format:
        set_config("output_format", "parquet")
        export_data(data_id)  # Will export as Parquet instead of JSON
    
    Common errors:
        - "Invalid key": Key not recognized (use get_config_schema() to see valid keys)
        - "Invalid value": Value type mismatch (check schema for expected type)
        - "Read-only": Some keys cannot be changed (marked as read_only in schema)
    """
```

## Special Cases

### 1. Admin/Privileged Tools

Make privilege requirements crystal clear:

```python
def admin_delete_user(user_id: str) -> dict:
    """[ADMIN ONLY] Permanently delete user account - Requires admin credentials.
    
    ⚠️  WARNING: This action is IRREVERSIBLE and requires admin privileges.
    
    PREREQUISITES:
        - Admin credentials must be configured
        - Check admin status: get_auth_status()["is_admin"]
        - Use with extreme caution
    
    SAFER ALTERNATIVES:
        - Prefer deactivate_user() for temporary suspension
        - Use revoke_access() to remove permissions without deletion
    
    Args:
        user_id: User ID to delete (get from list_users())
    
    Returns:
        Deletion confirmation or error if not authorized
    """
```

### 2. Deprecated Tools

Clearly guide LLMs away from deprecated tools:

```python
def legacy_upload(file_path: str) -> dict:
    """[DEPRECATED] Old upload method - Use upload_file() instead.
    
    ⚠️  This tool is deprecated and will be removed in v2.0
    
    MIGRATION: Use upload_file() for new code
        Old: legacy_upload("/path/to/file.csv")
        New: upload_file("/path/to/file.csv", "bucket-name/folder")
    
    REASONS TO MIGRATE:
        - Better error handling
        - Support for binary files
        - Automatic retry logic
        - Progress tracking
    
    See: upload_file() for replacement
    """
```

### 3. Experimental/Beta Tools

Set proper expectations:

```python
def experimental_ai_analyze(data_id: str) -> dict:
    """[EXPERIMENTAL] AI-powered data analysis - May change without notice.
    
    🧪 This tool is experimental and may produce inconsistent results.
    
    STATUS: Beta - API may change between versions
    STABILITY: Moderate - Results may vary
    RECOMMENDED FOR: Testing and exploration only
    
    FOR PRODUCTION: Use standard_analyze() for stable, predictable results
    
    Args:
        data_id: Data to analyze
    
    Returns:
        Analysis results (schema may change)
    """
```

## Validation Checklist

Before finalizing a docstring, verify:

### For LLM Comprehension
- [ ] Could an LLM understand this without reading other docs?
- [ ] Are multi-step workflows explicit?
- [ ] Are next steps clearly indicated?
- [ ] Are common errors addressed?
- [ ] Are examples realistic and complete?

### For Human Readability
- [ ] Is it scannable (good visual hierarchy)?
- [ ] Are examples copy-pasteable?
- [ ] Is terminology consistent?
- [ ] Are edge cases documented?

### For Maintenance
- [ ] Are referenced tools named correctly?
- [ ] Do examples match current API?
- [ ] Are parameter types current?
- [ ] Is deprecation status accurate?

## Common Mistakes to Avoid

### ❌ Mistake 1: Assuming Context
```python
"""Process the data."""  # What data? What processing? When would I use this?
```

### ✅ Fix: Provide Full Context
```python
"""Process uploaded CSV data - Validates, transforms, and prepares for analysis."""
```

### ❌ Mistake 2: Technical Jargon Without Explanation
```python
"""Performs ETL on the ingested data streams."""
```

### ✅ Fix: Explain Terms or Use Plain Language
```python
"""Extract, Transform, Load (ETL): Cleans and restructures uploaded data for analysis."""
```

### ❌ Mistake 3: Vague Returns
```python
Returns:
    Dictionary containing results
```

### ✅ Fix: Specific, Actionable Returns
```python
Returns:
    Dictionary with processed_file_id needed for export_results().
    Extract with: response["processed_file_id"]
```

### ❌ Mistake 4: No Workflow Context
```python
def step_two(...):
    """Execute step two of the process."""
```

### ✅ Fix: Show Complete Workflow
```python
def step_two(...):
    """Execute step 2: Transform data - Run after step_one(), before step_three().
    
    WORKFLOW:
        step_one() → THIS TOOL → step_three()
    """
```

### ❌ Mistake 5: Examples That Don't Run
```python
Example:
    result = tool(...)  # Fill in parameters
```

### ✅ Fix: Complete, Runnable Examples
```python
Example:
    result = tool(
        required_param="actual_value",
        optional_param=42
    )
    output = result["field_name"]
```

## Summary: The LLM Docstring Formula

```
[First Line: Action + Object + Context/Use Case]

[WORKFLOW section if multi-step]
[PREREQUISITES section if dependencies exist]
[WHEN TO USE / WHEN NOT TO USE for tool selection]

Args:
    param1: [Description with example and format]
            Example: "concrete_example"
            Get from: related_tool()["field"]
    param2: [Description] (default: X)

Returns:
    [What it contains + What to do with it]
    
    Response format:
    {
        "field1": "value",
        "field2": 123
    }
    
    Next step: next_tool(response["field1"])

Example:
    [Complete, realistic, copy-pasteable example]
    [Show extracting values from response]
    [Show passing to next tool if applicable]

Common errors:
    - "Error message": What it means and how to fix
```

## Implementation Guide

When applying this to existing tools:

1. **Audit Current Docstrings**: Identify tools with minimal/unclear docstrings
2. **Prioritize High-Traffic Tools**: Start with most-used tools first
3. **Update in Batches**: Group related tools (e.g., all upload tools)
4. **Test with LLM**: Verify LLM can follow workflows correctly
5. **Gather Feedback**: Monitor LLM behavior and user feedback
6. **Iterate**: Refine based on actual usage patterns

## Tools for Validation

After updating docstrings:

```bash
# Regenerate tool metadata
make mcp-list

# Test with MCP Inspector
make run-inspector

# Verify no signature changes
git diff src/quilt_mcp/tools/

# Test with real LLM client
# (Claude Desktop, Continue, or custom client)
```

## Conclusion

LLM-friendly docstrings are not just documentation—they're **instructions** that guide LLMs through complex workflows. By following these patterns, you ensure that LLMs can:

1. ✅ Choose the right tool for the task
2. ✅ Understand multi-step workflows
3. ✅ Handle responses correctly
4. ✅ Recover from errors gracefully
5. ✅ Provide better assistance to users

Remember: **If an LLM can't understand your docstring, it can't use your tool effectively.**


