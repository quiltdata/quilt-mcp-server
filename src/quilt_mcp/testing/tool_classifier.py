"""Tool classification and argument inference for MCP testing.

This module provides intelligent classification of MCP tools based on their
signatures, effects, and runtime behavior. It enables automatic test generation
by inferring appropriate test arguments from tool metadata and environment state.

Core Functions
--------------
classify_tool(tool_name, handler) -> Tuple[str, str]
    Classify a tool by its effect type (create/update/remove/configure/none)
    and argument category (zero-arg/required-arg/optional-arg/write-effect).
    Returns (effect, category) for test planning and coverage analysis.

infer_arguments(tool_name, handler, env_vars, discovered_data, athena_database) -> Dict[str, Any]
    Automatically infer appropriate test arguments from tool signature,
    environment variables, and discovered runtime data (S3 keys, packages, etc).
    Enables zero-configuration test generation.

create_mock_context() -> RequestContext
    Create a mock RequestContext for tools requiring authentication context.
    Provides minimal valid context for permission-required operations.

get_user_athena_database(catalog_url) -> str
    Extract UserAthenaDatabase from CloudFormation stack metadata.
    Used for Athena-based search and query tool testing.

Classification Taxonomy
-----------------------
Effect Types:
    - none: Read-only operations with no side effects
    - create: Creates new resources (packages, roles, buckets)
    - update: Modifies existing resources (metadata, permissions)
    - remove: Deletes resources (packages, roles)
    - configure: System configuration changes
    - none-context-required: Read-only but requires auth context

Argument Categories:
    - zero-arg: No parameters required (list operations)
    - required-arg: Has required parameters
    - optional-arg: All parameters optional
    - write-effect: Has side effects (create/update/remove)
    - context-required: Requires RequestContext injection

Inference Strategy
------------------
The argument inference system uses multiple data sources in priority order:

1. Environment Variables
   - Required catalog URLs, bucket names from TEST_* env vars
   - Falls back to sensible defaults when not provided

2. Discovered Data
   - Real S3 keys, package names, table names from runtime discovery
   - Ensures tests use actual infrastructure state

3. Signature Analysis
   - Parameter names guide inference (bucket -> TEST_QUILT_CATALOG_BUCKET)
   - Type hints inform value generation
   - Optional parameters handled gracefully

4. Tool Name Patterns
   - Operation suffixes guide inference (list, search, get, create)
   - Resource type detection (package, bucket, role, user)

Usage Examples
--------------
Classify tools for test planning:
    >>> effect, category = classify_tool("package_create", create_handler)
    >>> print(f"Effect: {effect}, Category: {category}")
    Effect: create, Category: write-effect

Infer arguments automatically:
    >>> env = {"TEST_QUILT_CATALOG_URL": "s3://my-bucket"}
    >>> discovered = {"packages": ["my-package"], "s3_keys": ["data.json"]}
    >>> args = infer_arguments(
    ...     "package_list",
    ...     list_handler,
    ...     env,
    ...     discovered,
    ...     "my_athena_db"
    ... )
    >>> print(args)
    {'catalog_url': 's3://my-bucket'}

Create mock context for permission tests:
    >>> ctx = create_mock_context()
    >>> assert ctx.user_name == "test-user"

Get Athena database from stack:
    >>> db = get_user_athena_database("s3://my-bucket")
    >>> print(db)
    my_stack_athena_db

Design Principles
-----------------
- Deterministic classification based on signatures and patterns
- Fail-fast with clear error messages for ambiguous cases
- Extensible taxonomy for new tool types
- Zero configuration when possible, explicit when necessary
- Comprehensive logging for debugging inference decisions

Dependencies
------------
- models.py: No dependencies (uses standard library types)
- quilt_mcp.context.request_context: For RequestContext creation
- boto3: For CloudFormation stack queries (optional)

Extracted From
--------------
- classify_tool: lines 439-487 from scripts/mcp-test-setup.py
- infer_arguments: lines 490-622 from scripts/mcp-test-setup.py
- create_mock_context: lines 417-436 from scripts/mcp-test-setup.py
- get_user_athena_database: lines 71-101 from scripts/mcp-test-setup.py
"""

import inspect
from typing import Any, Dict, Optional, Tuple

from quilt_mcp.context.request_context import RequestContext
from quiltx.stack import find_matching_stack, stack_outputs


def create_mock_context() -> RequestContext:
    """Create a mock RequestContext for testing tools that require it.

    Creates a minimal valid RequestContext with mocked authentication and
    permission services. Used during test discovery and generation for tools
    that require context injection.

    Returns:
        RequestContext with test-specific user ID and mocked services

    Example:
        >>> ctx = create_mock_context()
        >>> assert ctx.user_id == "test-user-mcp-test-setup"
        >>> assert ctx.request_id == "test-request-mcp-test-setup"
    """
    from unittest.mock import MagicMock

    # Create mock services
    mock_auth_service = MagicMock()
    mock_auth_service.is_valid.return_value = True
    mock_auth_service.get_boto3_session.return_value = None

    mock_permission_service = MagicMock()
    mock_permission_service.discover_permissions.return_value = {"buckets": []}
    mock_permission_service.check_bucket_access.return_value = {"accessible": True}

    return RequestContext(
        request_id="test-request-mcp-test-setup",
        user_id="test-user-mcp-test-setup",
        auth_service=mock_auth_service,
        permission_service=mock_permission_service,
        workflow_service=None,
    )


def classify_tool(tool_name: str, handler) -> tuple[str, str]:
    """Classify tool by effect and category.

    Analyzes tool signature and name patterns to determine:
    1. Effect type - what kind of side effects the tool has
    2. Category - what kind of arguments it requires

    This classification drives test planning, coverage analysis, and
    determines which tools need special handling (loops, mocking, etc).

    Args:
        tool_name: Name of the tool to classify
        handler: Tool handler with .fn attribute containing the actual function

    Returns:
        Tuple of (effect, category) where:
            effect: none|create|update|remove|configure|none-context-required
            category: zero-arg|required-arg|optional-arg|write-effect|context-required

    Example:
        >>> effect, category = classify_tool("package_create", create_handler)
        >>> assert effect == "create"
        >>> assert category == "write-effect"

        >>> effect, category = classify_tool("bucket_list", list_handler)
        >>> assert effect == "none"
        >>> assert category == "zero-arg"
    """
    sig = inspect.signature(handler.fn)

    # Check if tool needs context
    has_context_param = any(
        param_name == 'context' and (param.annotation == RequestContext or 'RequestContext' in str(param.annotation))
        for param_name, param in sig.parameters.items()
    )

    # Classify effect
    name_lower = tool_name.lower()
    if any(kw in name_lower for kw in ['create', 'put', 'upload', 'set']):
        effect = 'create'
    elif any(kw in name_lower for kw in ['delete', 'remove', 'reset']):
        effect = 'remove'
    elif any(kw in name_lower for kw in ['update', 'add', 'rename']):
        effect = 'update'
    elif any(kw in name_lower for kw in ['configure', 'toggle', 'apply', 'execute', 'generate']):
        effect = 'configure'
    else:
        effect = 'none-context-required' if has_context_param else 'none'

    # Classify category
    if effect in ['create', 'update', 'remove']:
        category = 'write-effect'
    elif has_context_param:
        category = 'context-required'
    else:
        # Check required arguments (excluding context)
        required_args = [
            name
            for name, param in sig.parameters.items()
            if param.default == inspect.Parameter.empty and name != 'context'
        ]
        if not required_args:
            category = 'zero-arg'
        elif len(required_args) > 0 and len(sig.parameters) > len(required_args):
            category = 'optional-arg'
        else:
            category = 'required-arg'

    return effect, category


def infer_arguments(
    tool_name: str,
    handler,
    env_vars: Dict[str, str | None],
    discovered_data: Optional[Dict[str, Any]] = None,
    athena_database: Optional[str] = None,
) -> Dict[str, Any]:
    """Infer test arguments from signature, environment, and discovered data.

    Uses multiple strategies to automatically generate appropriate test arguments:
    1. Parameter name pattern matching (bucket, package, query, etc.)
    2. Environment variable mapping (TEST_BUCKET -> bucket parameter)
    3. Discovered runtime data (real S3 keys, package names)
    4. Type annotation guidance (bool, int, str)
    5. Tool name patterns (athena tools need SQL queries)

    This enables zero-configuration test generation for most tools.

    Args:
        tool_name: Name of the tool
        handler: Tool handler with .fn attribute
        env_vars: Environment variables from .env (TEST_BUCKET, etc.)
        discovered_data: Data discovered from prior tool runs (S3 keys, packages)
        athena_database: The Athena database name from stack outputs

    Returns:
        Dictionary of inferred arguments ready for tool invocation

    Example:
        >>> env = {"QUILT_TEST_BUCKET": "s3://test-bucket"}
        >>> discovered = {"s3_keys": ["data/file.json"]}
        >>> args = infer_arguments(
        ...     "bucket_object_text",
        ...     text_handler,
        ...     env,
        ...     discovered,
        ...     "test_db"
        ... )
        >>> assert "s3_uri" in args
        >>> assert args["s3_uri"] == "s3://test-bucket/data/file.json"
    """
    sig = inspect.signature(handler.fn)
    args = {}
    discovered_data = discovered_data or {}

    # Extract common test values from environment
    test_bucket = env_vars.get("QUILT_TEST_BUCKET", "s3://quilt-example")
    catalog_url = env_vars.get("QUILT_CATALOG_URL", "https://open.quiltdata.com")
    test_package = env_vars.get("QUILT_TEST_PACKAGE", "examples/wellplates")
    test_entry = env_vars.get("QUILT_TEST_ENTRY", ".timestamp")
    bucket_name = test_bucket.replace("s3://", "").split("/")[0]
    db_name = athena_database or "default"

    for param_name, param in sig.parameters.items():
        # Skip context parameter (injected separately)
        if param_name == 'context':
            continue

        # Skip if has default
        if param.default != inspect.Parameter.empty:
            continue

        # Infer by parameter name patterns
        param_lower = param_name.lower()

        # Bucket parameters
        if 'bucket' in param_lower:
            if param_lower == 'bucket' or param_lower == 'bucket_name':
                args[param_name] = bucket_name
            else:
                args[param_name] = test_bucket

        # Package parameters
        elif 'package' in param_lower:
            if 'name' in param_lower:
                args[param_name] = test_package
            else:
                args[param_name] = test_package

        # S3 URI parameters
        elif param_lower in ['s3_uri', 'uri']:
            # Use discovered S3 key if available
            if discovered_data.get('s3_keys'):
                args[param_name] = discovered_data['s3_keys'][0]
            else:
                args[param_name] = f"s3://{bucket_name}/{test_package}/{test_entry}"

        # Path/key parameters
        elif param_lower in ['path', 'logical_key', 'key']:
            args[param_name] = test_entry

        # Query parameters
        elif param_lower == 'query':
            if 'athena' in tool_name or 'tabulator' in tool_name:
                args[param_name] = "SELECT 1 as test_value"
            else:
                args[param_name] = test_entry

        # Database/table parameters
        elif param_lower == 'database' or param_lower == 'database_name':
            args[param_name] = db_name
        elif param_lower == 'table' or param_lower == 'table_name':
            args[param_name] = "test_table"

        # Catalog/registry parameters
        elif param_lower in ['catalog_url', 'registry']:
            args[param_name] = test_bucket

        # Limit/max parameters
        elif 'limit' in param_lower or 'max' in param_lower:
            args[param_name] = 10

        # Visualization parameters (complex structures)
        elif param_lower == 'organized_structure':
            args[param_name] = {"files": [{"name": "test.txt", "size": 100}]}
        elif param_lower == 'file_types':
            args[param_name] = {"txt": 1}
        elif param_lower == 'package_metadata':
            args[param_name] = {"name": test_package}
        elif param_lower == 'readme_content':
            args[param_name] = "# Test Package"
        elif param_lower == 'source_info':
            args[param_name] = {"type": "test"}

        # Data parameters for visualizations
        elif param_lower == 'data':
            args[param_name] = {"x": [1, 2, 3], "y": [4, 5, 6]}
        elif param_lower in ['plot_type', 'chart_type']:
            args[param_name] = "scatter"
        elif param_lower == 'x_column':
            args[param_name] = "x"
        elif param_lower == 'y_column':
            args[param_name] = "y"

        # Boolean parameters
        elif param.annotation is bool or 'bool' in str(param.annotation):
            # Infer based on parameter name
            if any(kw in param_lower for kw in ['include', 'recursive', 'force', 'use']):
                args[param_name] = True
            else:
                args[param_name] = False

        # String parameters (generic fallback)
        elif param.annotation is str or 'str' in str(param.annotation):
            # Try to infer from name
            if 'name' in param_lower:
                args[param_name] = "test_name"
            else:
                args[param_name] = "test_value"

        # Integer parameters
        elif param.annotation is int or 'int' in str(param.annotation):
            args[param_name] = 10

    return args


def get_user_athena_database(catalog_url: str) -> str:
    """Get the UserAthenaDatabase from the CloudFormation stack.

    Queries the CloudFormation stack associated with the given catalog URL
    to extract the UserAthenaDatabaseName output. This database name is
    required for Athena-based search and query tool testing.

    Args:
        catalog_url: The catalog URL (e.g., https://nightly.quilttest.com)

    Returns:
        The UserAthenaDatabase name, or 'default' if not found

    Example:
        >>> db = get_user_athena_database("https://example.quiltdata.com")
        >>> print(db)  # e.g., "quilt_example_athena_db"

    Note:
        This function gracefully handles missing stacks or outputs by
        returning 'default' and logging a warning. It never raises exceptions.
    """
    try:
        # Find the stack for this catalog
        stack = find_matching_stack(catalog_url)

        # Get the outputs
        outputs = stack_outputs(stack)

        # Find the UserAthenaDatabaseName output
        for output in outputs:
            if output.get('OutputKey') == 'UserAthenaDatabaseName':
                db_name = output.get('OutputValue')
                if db_name:
                    print(f"   ✅ Found UserAthenaDatabaseName: {db_name}")
                    return db_name

        print("   ⚠️  UserAthenaDatabaseName not found in stack outputs, using 'default'")
        return 'default'

    except Exception as e:
        print(f"   ⚠️  Failed to get UserAthenaDatabaseName from stack: {e}")
        print("   Using 'default' database")
        return 'default'


__all__ = [
    "classify_tool",
    "infer_arguments",
    "create_mock_context",
    "get_user_athena_database",
]
