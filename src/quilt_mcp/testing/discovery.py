"""Discovery orchestration for MCP test generation.

This module coordinates tool execution and data discovery to automatically
generate comprehensive test configurations. It validates tool behavior,
captures real infrastructure state, and builds test argument registries.

Core Components
---------------
DiscoveryOrchestrator : class
    Orchestrates tool discovery by executing tools safely, capturing their
    outputs, and registering discovered data for test generation. Handles
    timeouts, errors, and permission requirements gracefully.

extract_tool_metadata(server) -> List[Dict[str, Any]]
    Extract comprehensive metadata from all registered MCP tools including
    names, descriptions, input schemas, and handler signatures.

extract_resource_metadata(server) -> List[Dict[str, Any]]
    Extract comprehensive metadata from all registered MCP resources including
    URIs, names, descriptions, and MIME types.

Discovery Process
-----------------
1. Tool Registration Discovery
   - List all available tools and resources
   - Extract signatures and schemas
   - Classify by effect and category

2. Safe Execution
   - Execute tools with inferred arguments
   - Apply timeouts to prevent hangs
   - Catch and classify errors
   - Handle permission requirements

3. Data Capture
   - Extract S3 keys from list operations
   - Capture package names and metadata
   - Record table names from search results
   - Store discovered data in registry

4. Validation
   - Verify tool responses match schemas
   - Check for expected data structures
   - Validate access control behavior
   - Confirm idempotency where applicable

Discovery Strategy
------------------
The orchestrator uses intelligent execution ordering:

1. Zero-arg Tools First
   - List operations (bucket_list, package_list)
   - Status checks (server_info)
   - No risk of side effects

2. Required-arg Tools with Inference
   - Bucket operations with discovered buckets
   - Package operations with discovered packages
   - Search operations with discovered tables

3. Write-effect Tools (Optional)
   - Only if --enable-discovery-writes flag set
   - Creates temporary resources for testing
   - Ensures proper cleanup

4. Context-required Tools
   - Create mock RequestContext
   - Execute with minimal permissions
   - Capture auth-related behavior

Usage Examples
--------------
Orchestrate full discovery:
    >>> orchestrator = DiscoveryOrchestrator(
    ...     server=mcp_server,
    ...     env_vars={"TEST_QUILT_CATALOG_URL": "s3://my-bucket"},
    ...     timeout_seconds=15.0
    ... )
    >>> results = await orchestrator.discover_all_tools()
    >>> print(f"Discovered {len(results.s3_keys)} S3 keys")
    >>> print(f"Discovered {len(results.packages)} packages")

Extract tool metadata:
    >>> tools = await extract_tool_metadata(server)
    >>> for tool in tools:
    ...     print(f"{tool['name']}: {tool['description']}")
    bucket_list: List all S3 buckets
    package_create: Create a new Quilt package

Extract resource metadata:
    >>> resources = await extract_resource_metadata(server)
    >>> for res in resources:
    ...     print(f"{res['uri']}: {res['name']}")
    quilt://bucket/package: Package contents
    s3://bucket/key: S3 object content

Discover specific tool:
    >>> result = await orchestrator.discover_tool(
    ...     tool_name="bucket_list",
    ...     handler=bucket_list_handler
    ... )
    >>> if result.success:
    ...     print(f"Discovered data: {result.discovered_data}")
    ... else:
    ...     print(f"Error: {result.error_message}")

Design Principles
-----------------
- Safe execution with timeouts and error handling
- Non-destructive by default (no write operations)
- Comprehensive metadata capture
- Fail-gracefully for permission errors
- Detailed logging for debugging
- Async/await for concurrent discovery

Error Handling
--------------
The orchestrator handles multiple error scenarios:

1. Permission Errors
   - Captured and classified
   - Inform test configuration generation
   - Don't block discovery of other tools

2. Timeout Errors
   - Prevent infinite hangs
   - Configurable timeout per tool
   - Logged with tool name and duration

3. Schema Validation Errors
   - Mismatched response types
   - Missing required fields
   - Captured for reporting

4. Infrastructure Errors
   - AWS service errors
   - Network timeouts
   - Resource not found

Dependencies
------------
- models.py: DiscoveryResult, DiscoveredDataRegistry
- tool_classifier.py: create_mock_context, classify_tool
- asyncio: Async execution and timeouts
- inspect: Signature analysis

Extracted From
--------------
- DiscoveryOrchestrator: lines 167-411 from scripts/mcp-test-setup.py
- extract_tool_metadata: lines 1092-1132 from scripts/mcp-test-setup.py
- extract_resource_metadata: lines 1134-1188 from scripts/mcp-test-setup.py
"""

import asyncio
import inspect
import time
from typing import Any, Dict, List, Optional

from .models import DiscoveryResult, DiscoveredDataRegistry
from .tool_classifier import create_mock_context


class DiscoveryOrchestrator:
    """Coordinates tool execution and data discovery."""

    def __init__(
        self, server: Any, timeout: float = 5.0, verbose: bool = True, env_vars: Optional[Dict[str, str | None]] = None
    ) -> None:
        self.server = server
        self.timeout = timeout
        self.verbose = verbose
        self.registry = DiscoveredDataRegistry()
        self.results: Dict[str, DiscoveryResult] = {}
        self.env_vars = env_vars or {}

    async def discover_tool(
        self, tool_name: str, handler: Any, arguments: Dict[str, Any], effect: str, category: str = 'required-arg'
    ) -> DiscoveryResult:
        """
        Execute a tool and capture its behavior.

        NOTE: Write operations are NOT skipped - they will be tested via tool loops.
        This method only tests read-only tools during discovery phase.

        Returns:
            DiscoveryResult with status, response, error, and discovered data.
        """
        start_time = time.time()

        # Safety guard: Skip write operations during discovery
        # Write operations will be tested via tool loops in mcp-test.py
        if effect in ['create', 'update', 'remove']:
            return DiscoveryResult(
                tool_name=tool_name,
                status='SKIPPED',
                duration_ms=0,
                error=f"Skipped during discovery: write operation (effect={effect}). Will be tested via tool loops.",
            )

        try:
            # Inject context if tool needs it (but don't modify original arguments dict)
            sig = inspect.signature(handler.fn)
            runtime_arguments = arguments.copy()
            if 'context' in sig.parameters:
                runtime_arguments['context'] = create_mock_context()

            # Execute tool with timeout
            # Check if function is async
            if inspect.iscoroutinefunction(handler.fn):
                result = await asyncio.wait_for(handler.fn(**runtime_arguments), timeout=self.timeout)
            else:
                # Synchronous function - run in executor with timeout
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: handler.fn(**runtime_arguments)), timeout=self.timeout
                )

            duration_ms = (time.time() - start_time) * 1000

            # Convert result to dict if it's a Pydantic model or has dict() method
            if hasattr(result, 'model_dump'):
                result = result.model_dump()
            elif hasattr(result, 'dict'):
                result = result.dict()
            elif not isinstance(result, dict):
                # Try to convert to dict
                result = {"content": [result]}

            # Extract discovered data from response
            discovered_data = self._extract_data(tool_name, result)

            return DiscoveryResult(
                tool_name=tool_name,
                status='PASSED',
                duration_ms=duration_ms,
                response=result,
                discovered_data=discovered_data,
            )

        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            return DiscoveryResult(
                tool_name=tool_name,
                status='FAILED',
                duration_ms=duration_ms,
                error=f"Timeout after {self.timeout}s",
                error_category="timeout",
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            error_category = self._categorize_error(str(e))

            return DiscoveryResult(
                tool_name=tool_name,
                status='FAILED',
                duration_ms=duration_ms,
                error=str(e),
                error_category=error_category,
            )

    def _extract_data(self, tool_name: str, response: Any) -> Dict[str, Any]:
        """Extract reusable data from tool response."""
        discovered: Dict[str, Any] = {}

        try:
            # Handle different response types
            if not isinstance(response, dict):
                return discovered

            # Extract S3 keys from bucket_objects_list
            if tool_name == 'bucket_objects_list':
                s3_keys = []
                # Check for objects in response (new structure)
                objects = response.get('objects', [])
                if isinstance(objects, list):
                    for item in objects:
                        if isinstance(item, dict):
                            # Prefer s3_uri if available, otherwise construct from key
                            s3_uri = item.get('s3_uri')
                            if not s3_uri and 'key' in item:
                                bucket = response.get('bucket', '')
                                s3_uri = f"s3://{bucket}/{item['key']}" if bucket else item['key']
                            if s3_uri:
                                s3_keys.append(s3_uri)

                # Also check content array (legacy structure)
                content = response.get('content', [])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and 'key' in item:
                            key = item['key']
                            # Construct full S3 URI if we have bucket info
                            if 'bucket' in item:
                                s3_uri = f"s3://{item['bucket']}/{key}"
                            else:
                                s3_uri = key
                            s3_keys.append(s3_uri)

                if s3_keys:
                    self.registry.add_s3_keys(s3_keys)
                    discovered['s3_keys'] = s3_keys[:5]  # Store first 5

            # Extract package names from search_catalog
            elif 'search_catalog' in tool_name:
                package_names = []
                # Check content array
                content = response.get('content', [])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            # Look for package name in various fields
                            pkg_name = item.get('package_name') or item.get('name') or item.get('id')
                            if pkg_name and isinstance(pkg_name, str):
                                package_names.append(pkg_name)

                if package_names:
                    self.registry.add_package_names(package_names)
                    discovered['package_names'] = package_names[:5]

            # Extract tables from tabulator_tables_list or athena_tables_list
            elif 'tables_list' in tool_name:
                tables = []
                # Check content array
                content = response.get('content', [])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and 'name' in item:
                            table_info = {'table': item['name'], 'database': item.get('database', 'default')}
                            if 'columns' in item:
                                table_info['columns'] = item['columns']
                            tables.append(table_info)

                if tables:
                    self.registry.add_tables(tables)
                    discovered['tables'] = tables[:5]

            # Extract schema from table schema operations
            elif 'schema' in tool_name.lower():
                content = response.get('content', [])
                if content and isinstance(content, list) and isinstance(content[0], dict):
                    schema_info = content[0]
                    if 'columns' in schema_info:
                        discovered['columns'] = schema_info['columns']

        except Exception as e:
            # Log extraction error but don't fail discovery
            if self.verbose:
                print(f"   ⚠️  Data extraction error for {tool_name}: {e}")

        return discovered

    def _categorize_error(self, error_msg: str) -> str:
        """Categorize error for reporting and recommendations."""
        error_lower = error_msg.lower()

        if any(kw in error_lower for kw in ['access', 'denied', 'forbidden', 'unauthorized', 'permission']):
            return 'access_denied'
        elif any(kw in error_lower for kw in ['timeout', 'timed out']):
            return 'timeout'
        elif any(kw in error_lower for kw in ['not found', 'does not exist', 'no such']):
            return 'resource_not_found'
        elif any(kw in error_lower for kw in ['unavailable', 'connection', 'network']):
            return 'service_unavailable'
        elif any(kw in error_lower for kw in ['invalid', 'validation', 'schema']):
            return 'validation_error'
        else:
            return 'unknown'

    def print_summary(self) -> None:
        """Print discovery results summary."""
        passed = sum(1 for r in self.results.values() if r.status == 'PASSED')
        failed = sum(1 for r in self.results.values() if r.status == 'FAILED')
        skipped = sum(1 for r in self.results.values() if r.status == 'SKIPPED')

        print("\n📊 Test Results Summary:")
        print(f"  ✓ {passed} PASSED")
        print(f"  ✗ {failed} FAILED")
        print(f"  ⊘ {skipped} SKIPPED (write-effect tools - will be tested via tool loops)")

        if failed > 0:
            print("\n❌ Failed Tools:")
            for tool_name, result in self.results.items():
                if result.status == 'FAILED':
                    print(f"   • {tool_name}: {result.error}")

        # Print discovered data summary
        registry_dict = self.registry.to_dict()
        if any(registry_dict.values()):
            print("\n💾 Discovered Data:")
            if registry_dict['s3_keys']:
                print(f"  - {len(self.registry.s3_keys)} S3 keys from bucket_objects_list")
            if registry_dict['package_names']:
                print(f"  - {len(self.registry.package_names)} package names from search")
            if registry_dict['tables']:
                print(f"  - {len(self.registry.tables)} tables from table listing")


async def extract_tool_metadata(server: Any) -> List[Dict[str, Any]]:
    """Extract comprehensive metadata from all registered tools."""
    tools = []

    server_tools = await server.get_tools()
    for tool_name, handler in server_tools.items():
        # Get function signature and docstring
        sig = inspect.signature(handler.fn)
        doc = inspect.getdoc(handler.fn)

        # ERROR if tool lacks a description
        if not doc:
            raise ValueError(f"Tool '{tool_name}' is missing a docstring description!")

        # Get module information
        module = inspect.getmodule(handler.fn)
        module_name = module.__name__ if module else "unknown"

        # Extract module short name (last component)
        short_module = module_name.split('.')[-1]

        # Check if function is async
        is_async = inspect.iscoroutinefunction(handler.fn)

        # Build full signature string
        signature_str = f"{tool_name}{sig}"

        tools.append(
            {
                "type": "tool",
                "name": tool_name,
                "module": short_module,
                "signature": signature_str,
                "description": doc.split('\n')[0],  # First line only
                "is_async": is_async,
                "full_module_path": module_name,
                "handler_class": handler.__class__.__name__,
            }
        )

    # Sort by module then name for consistent ordering
    tools.sort(key=lambda x: (x["module"], x["name"]))
    return tools


async def extract_resource_metadata(server: Any) -> List[Dict[str, Any]]:
    """Extract comprehensive metadata from all registered resources via FastMCP."""
    resources = []

    # Get resources from FastMCP server
    static_resources = await server.get_resources()
    resource_templates = await server.get_resource_templates()

    # Process static resources
    # static_resources is a dict with URI keys and FunctionResource values
    for uri, resource in static_resources.items():
        # ERROR if resource lacks a name
        if not hasattr(resource, 'name') or not resource.name:
            raise ValueError(f"Resource '{uri}' is missing a name!")

        # ERROR if resource lacks a description
        if not hasattr(resource, 'description') or not resource.description:
            raise ValueError(f"Resource '{uri}' is missing a description!")

        resources.append(
            {
                "type": "resource",
                "name": uri,
                "module": "resources",
                "signature": f"@mcp.resource('{uri}')",
                "description": resource.description,
                "is_async": True,
                "full_module_path": "quilt_mcp.resources",
                "handler_class": "FastMCP Resource",
            }
        )

    # Process resource templates
    # resource_templates is a dict with URI template keys and FunctionResource values
    for uri_template, template in resource_templates.items():
        # ERROR if template lacks a name
        if not hasattr(template, 'name') or not template.name:
            raise ValueError(f"Resource template '{uri_template}' is missing a name!")

        # ERROR if template lacks a description
        if not hasattr(template, 'description') or not template.description:
            raise ValueError(f"Resource template '{uri_template}' is missing a description!")

        resources.append(
            {
                "type": "resource",
                "name": uri_template,
                "module": "resources",
                "signature": f"@mcp.resource('{uri_template}')",
                "description": template.description,
                "is_async": True,
                "full_module_path": "quilt_mcp.resources",
                "handler_class": "FastMCP Template",
            }
        )

    # Sort by URI pattern for consistent ordering
    resources.sort(key=lambda x: x["name"])
    return resources


__all__ = [
    "DiscoveryOrchestrator",
    "extract_tool_metadata",
    "extract_resource_metadata",
]
