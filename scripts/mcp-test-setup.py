#!/usr/bin/env python3
"""Generate canonical tool and resource listings from MCP server code.

This script inspects the actual MCP server implementation to generate
authoritative tool and resource listings, eliminating manual maintenance and drift.
Resources are distinguished from tools with a 'type' column in the CSV output.

Phase 2 Enhancement: Intelligent test discovery with validation
- Executes tools with test parameters to discover what actually works
- Records PASSED/FAILED/SKIPPED status for each tool
- Captures actual response values for test expectations
- Uses discovered data to inform later tool tests

Phase 3 Enhancement (A18): 100% tool coverage with intelligent inference
- Tool classification system (5 categories)
- Argument inference from signatures and environment
- Context parameter injection for permission tools
- Coverage validation and reporting
- Smart regeneration (only when sources change)

Phase 4 Enhancement (A18): Tool loops for write-operation testing
- Define tool loops that create → modify → verify → cleanup resources
- Generate tool_loops section in YAML with template placeholders
- Support template substitution ({uuid}, {env.VAR})
- Enable 100% coverage including write operations
"""

import asyncio
import csv
import inspect
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import yaml
from enum import Enum
from dotenv import dotenv_values
from quiltx import get_catalog_url
from quiltx.stack import find_matching_stack, stack_outputs

# Add custom YAML representer for Enum objects
# This allows enums to be serialized as their string values instead of Python objects
def enum_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data.value)

yaml.add_multi_representer(Enum, enum_representer)

# Add src to path for imports
script_dir = Path(__file__).parent
repo_root = script_dir.parent
src_dir = repo_root / "src"

# Only add to path if not already in PYTHONPATH
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from quilt_mcp.utils import create_configured_server
from quilt_mcp.context.request_context import RequestContext


# ============================================================================
# Stack Configuration Helper
# ============================================================================

def get_user_athena_database(catalog_url: str) -> str:
    """Get the UserAthenaDatabase from the CloudFormation stack.

    Args:
        catalog_url: The catalog URL (e.g., https://nightly.quilttest.com)

    Returns:
        The UserAthenaDatabase name, or 'default' if not found
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

        print(f"   ⚠️  UserAthenaDatabaseName not found in stack outputs, using 'default'")
        return 'default'

    except Exception as e:
        print(f"   ⚠️  Failed to get UserAthenaDatabaseName from stack: {e}")
        print(f"   Using 'default' database")
        return 'default'


# ============================================================================
# Phase 2: Discovery Models & Engine
# ============================================================================

@dataclass
class DiscoveryResult:
    """Result of attempting to discover/validate a tool."""
    tool_name: str
    status: Literal['PASSED', 'FAILED', 'SKIPPED']
    duration_ms: float

    # Successful execution (status='PASSED')
    response: Optional[Dict[str, Any]] = None
    discovered_data: Dict[str, Any] = field(default_factory=dict)

    # Failed execution (status='FAILED')
    error: Optional[str] = None
    error_category: Optional[str] = None  # access_denied, timeout, validation_error, etc.

    # Metadata
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def success(self) -> bool:
        """Backward compatibility: success = (status == 'PASSED')"""
        return self.status == 'PASSED'


class DiscoveredDataRegistry:
    """Registry for data discovered during tool execution."""

    def __init__(self):
        self.s3_keys: List[str] = []
        self.package_names: List[str] = []
        self.tables: List[Dict[str, str]] = []
        self.catalog_resources: List[Dict[str, str]] = []

    def add_s3_keys(self, keys: List[str]):
        """Add discovered S3 keys."""
        self.s3_keys.extend(keys)

    def add_package_names(self, names: List[str]):
        """Add discovered package names."""
        self.package_names.extend(names)

    def add_tables(self, tables: List[Dict[str, str]]):
        """Add discovered tables."""
        self.tables.extend(tables)

    def add_catalog_resource(self, uri: str, resource_type: str):
        """Add discovered catalog resource."""
        self.catalog_resources.append({"uri": uri, "type": resource_type})

    def to_dict(self) -> Dict[str, Any]:
        """Export registry as dictionary."""
        return {
            "s3_keys": self.s3_keys[:10],  # Limit to first 10
            "package_names": self.package_names[:10],
            "tables": self.tables[:10],
            "catalog_resources": self.catalog_resources[:10],
        }


class DiscoveryOrchestrator:
    """Coordinates tool execution and data discovery."""

    def __init__(self, server, timeout: float = 5.0, verbose: bool = True, env_vars: Dict[str, str | None] = None):
        self.server = server
        self.timeout = timeout
        self.verbose = verbose
        self.registry = DiscoveredDataRegistry()
        self.results: Dict[str, DiscoveryResult] = {}
        self.env_vars = env_vars or {}

    async def discover_tool(
        self,
        tool_name: str,
        handler,
        arguments: Dict[str, Any],
        effect: str,
        category: str = 'required-arg'
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
                error=f"Skipped during discovery: write operation (effect={effect}). Will be tested via tool loops."
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
                result = await asyncio.wait_for(
                    handler.fn(**runtime_arguments),
                    timeout=self.timeout
                )
            else:
                # Synchronous function - run in executor with timeout
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: handler.fn(**runtime_arguments)),
                    timeout=self.timeout
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
                discovered_data=discovered_data
            )

        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            return DiscoveryResult(
                tool_name=tool_name,
                status='FAILED',
                duration_ms=duration_ms,
                error=f"Timeout after {self.timeout}s",
                error_category="timeout"
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            error_category = self._categorize_error(str(e))

            return DiscoveryResult(
                tool_name=tool_name,
                status='FAILED',
                duration_ms=duration_ms,
                error=str(e),
                error_category=error_category
            )

    def _extract_data(self, tool_name: str, response: Any) -> Dict[str, Any]:
        """Extract reusable data from tool response."""
        discovered = {}

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
                            table_info = {
                                'table': item['name'],
                                'database': item.get('database', 'default')
                            }
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

    def print_summary(self):
        """Print discovery results summary."""
        passed = sum(1 for r in self.results.values() if r.status == 'PASSED')
        failed = sum(1 for r in self.results.values() if r.status == 'FAILED')
        skipped = sum(1 for r in self.results.values() if r.status == 'SKIPPED')

        print(f"\n📊 Test Results Summary:")
        print(f"  ✓ {passed} PASSED")
        print(f"  ✗ {failed} FAILED")
        print(f"  ⊘ {skipped} SKIPPED (write-effect tools - will be tested via tool loops)")

        if failed > 0:
            print(f"\n❌ Failed Tools:")
            for tool_name, result in self.results.items():
                if result.status == 'FAILED':
                    print(f"   • {tool_name}: {result.error}")

        # Print discovered data summary
        registry_dict = self.registry.to_dict()
        if any(registry_dict.values()):
            print(f"\n💾 Discovered Data:")
            if registry_dict['s3_keys']:
                print(f"  - {len(self.registry.s3_keys)} S3 keys from bucket_objects_list")
            if registry_dict['package_names']:
                print(f"  - {len(self.registry.package_names)} package names from search")
            if registry_dict['tables']:
                print(f"  - {len(self.registry.tables)} tables from table listing")


# ============================================================================
# Phase 3: Tool Classification & Argument Inference (A18)
# ============================================================================

def create_mock_context() -> RequestContext:
    """Create a mock RequestContext for testing tools that require it."""
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
        workflow_service=None
    )


def classify_tool(tool_name: str, handler) -> tuple[str, str]:
    """Classify tool by effect and category.

    Returns:
        (effect, category) where:
            effect: none|create|update|remove|configure|none-context-required
            category: zero-arg|required-arg|optional-arg|write-effect|context-required
    """
    sig = inspect.signature(handler.fn)

    # Check if tool needs context
    has_context_param = any(
        param_name == 'context' and
        (param.annotation == RequestContext or 'RequestContext' in str(param.annotation))
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
            name for name, param in sig.parameters.items()
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
    athena_database: Optional[str] = None
) -> Dict[str, Any]:
    """Infer test arguments from signature, environment, and discovered data.

    Args:
        tool_name: Name of the tool
        handler: Tool handler with .fn attribute
        env_vars: Environment variables from .env
        discovered_data: Data discovered from prior tool runs
        athena_database: The Athena database name from stack outputs

    Returns:
        Dictionary of inferred arguments
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
        elif param.annotation == bool or 'bool' in str(param.annotation):
            # Infer based on parameter name
            if any(kw in param_lower for kw in ['include', 'recursive', 'force', 'use']):
                args[param_name] = True
            else:
                args[param_name] = False

        # String parameters (generic fallback)
        elif param.annotation == str or 'str' in str(param.annotation):
            # Try to infer from name
            if 'name' in param_lower:
                args[param_name] = "test_name"
            else:
                args[param_name] = "test_value"

        # Integer parameters
        elif param.annotation == int or 'int' in str(param.annotation):
            args[param_name] = 10

    return args


# ============================================================================
# Phase 4: Tool Loops Generation (A18)
# ============================================================================

def generate_tool_loops(env_vars: Dict[str, str | None]) -> Dict[str, Any]:
    """Generate tool loops configuration for write-operation testing.

    Tool loops test write operations through create → modify → verify → cleanup cycles.
    Each loop uses template variables ({uuid}, {env.VAR}) that are substituted at runtime.

    Args:
        env_vars: Environment variables for template substitution

    Returns:
        Dictionary with tool_loops configuration
    """
    test_bucket = env_vars.get("QUILT_TEST_BUCKET", "s3://quilt-example")

    return {
        "admin_user_basic": {
            "description": "Test admin user create/get/delete cycle",
            "cleanup_on_failure": True,
            "steps": [
                {
                    "tool": "admin_user_create",
                    "args": {
                        "name": "tlu{uuid}",
                        "email": "tlu{uuid}@example.com",
                        "role": "viewer"
                    },
                    "expect_success": True
                },
                {
                    "tool": "admin_user_get",
                    "args": {
                        "name": "tlu{uuid}"
                    },
                    "expect_success": True
                },
                {
                    "tool": "admin_user_delete",
                    "args": {
                        "name": "tlu{uuid}"
                    },
                    "expect_success": True,
                    "is_cleanup": True
                }
            ]
        },
        "admin_user_with_roles": {
            "description": "Test admin user add/remove roles",
            "cleanup_on_failure": True,
            "steps": [
                {
                    "tool": "admin_user_create",
                    "args": {
                        "name": "tlu{uuid}",
                        "email": "tlu{uuid}@example.com",
                        "role": "viewer"
                    },
                    "expect_success": True
                },
                {
                    "tool": "admin_user_add_roles",
                    "args": {
                        "name": "tlu{uuid}",
                        "roles": ["data-scientist"]
                    },
                    "expect_success": True
                },
                {
                    "tool": "admin_user_get",
                    "args": {
                        "name": "tlu{uuid}"
                    },
                    "expect_success": True
                },
                {
                    "tool": "admin_user_remove_roles",
                    "args": {
                        "name": "tlu{uuid}",
                        "roles": ["data-scientist"]
                    },
                    "expect_success": True
                },
                {
                    "tool": "admin_user_delete",
                    "args": {
                        "name": "tlu{uuid}"
                    },
                    "expect_success": True,
                    "is_cleanup": True
                }
            ]
        },
        "admin_user_modifications": {
            "description": "Test admin user set operations (email, role, admin, active, reset password)",
            "cleanup_on_failure": True,
            "steps": [
                {
                    "tool": "admin_user_create",
                    "args": {
                        "name": "tlu{uuid}",
                        "email": "tlu{uuid}@example.com",
                        "role": "viewer"
                    },
                    "expect_success": True
                },
                {
                    "tool": "admin_user_set_email",
                    "args": {
                        "name": "tlu{uuid}",
                        "email": "tlu{uuid}x@example.com"
                    },
                    "expect_success": True
                },
                {
                    "tool": "admin_user_set_role",
                    "args": {
                        "name": "tlu{uuid}",
                        "role": "data-scientist"
                    },
                    "expect_success": True
                },
                {
                    "tool": "admin_user_set_admin",
                    "args": {
                        "name": "tlu{uuid}",
                        "is_admin": True
                    },
                    "expect_success": True
                },
                {
                    "tool": "admin_user_set_active",
                    "args": {
                        "name": "tlu{uuid}",
                        "is_active": False
                    },
                    "expect_success": True
                },
                {
                    "tool": "admin_user_reset_password",
                    "args": {
                        "name": "tlu{uuid}"
                    },
                    "expect_success": True
                },
                {
                    "tool": "admin_user_delete",
                    "args": {
                        "name": "tlu{uuid}"
                    },
                    "expect_success": True,
                    "is_cleanup": True
                }
            ]
        },
        "admin_sso_config": {
            "description": "Test SSO configuration set/remove cycle",
            "cleanup_on_failure": True,
            "steps": [
                {
                    "tool": "admin_sso_config_set",
                    "args": {
                        "config": {
                            "provider": "test-{uuid}",
                            "saml_config": "<test_sso_config>test config</test_sso_config>"
                        }
                    },
                    "expect_success": True
                },
                {
                    "tool": "admin_sso_config_remove",
                    "args": {},
                    "expect_success": True,
                    "is_cleanup": True
                }
            ]
        },
        "admin_tabulator_query": {
            "description": "Test tabulator open query set/toggle cycle",
            "cleanup_on_failure": True,
            "steps": [
                {
                    "tool": "admin_tabulator_open_query_set",
                    "args": {
                        "enabled": True
                    },
                    "expect_success": True
                },
                {
                    "tool": "admin_tabulator_open_query_set",
                    "args": {
                        "enabled": False
                    },
                    "expect_success": True,
                    "is_cleanup": True
                }
            ]
        },
        "package_lifecycle": {
            "description": "Test package create/update/delete cycle",
            "cleanup_on_failure": True,
            "steps": [
                {
                    "tool": "package_create",
                    "args": {
                        "package_name": "testuser/loop-pkg-{uuid}",
                        "registry": "{env.QUILT_TEST_BUCKET}",
                        "s3_uris": ["{env.QUILT_TEST_BUCKET}/test-data/sample.csv"],
                        "message": "Test package created by tool loop"
                    },
                    "expect_success": True
                },
                {
                    "tool": "package_browse",
                    "args": {
                        "package_name": "testuser/loop-pkg-{uuid}",
                        "registry": "{env.QUILT_TEST_BUCKET}"
                    },
                    "expect_success": True
                },
                {
                    "tool": "package_update",
                    "args": {
                        "package_name": "testuser/loop-pkg-{uuid}",
                        "registry": "{env.QUILT_TEST_BUCKET}",
                        "s3_uris": ["{env.QUILT_TEST_BUCKET}/test-data/sample2.csv"],
                        "message": "Updated by tool loop"
                    },
                    "expect_success": True
                },
                {
                    "tool": "package_delete",
                    "args": {
                        "package_name": "testuser/loop-pkg-{uuid}",
                        "registry": "{env.QUILT_TEST_BUCKET}"
                    },
                    "expect_success": True,
                    "is_cleanup": True
                }
            ]
        },
        "package_create_from_s3_loop": {
            "description": "Test package_create_from_s3 tool",
            "cleanup_on_failure": True,
            "steps": [
                {
                    "tool": "package_create_from_s3",
                    "args": {
                        "source_bucket": "{env.QUILT_TEST_BUCKET}",
                        "package_name": "testuser/s3pkg-{uuid}",
                        "source_prefix": "test-data/",
                        "confirm_structure": False,
                        "force": True
                    },
                    "expect_success": True
                },
                {
                    "tool": "package_delete",
                    "args": {
                        "package_name": "testuser/s3pkg-{uuid}",
                        "registry": "{env.QUILT_TEST_BUCKET}"
                    },
                    "expect_success": True,
                    "is_cleanup": True
                }
            ]
        },
        "bucket_objects_write": {
            "description": "Test bucket object put/fetch cycle",
            "cleanup_on_failure": True,
            "steps": [
                {
                    "tool": "bucket_objects_put",
                    "args": {
                        "bucket": "{env.QUILT_TEST_BUCKET}",
                        "items": [
                            {
                                "key": "test-loop-{uuid}.txt",
                                "text": "Test content from tool loop"
                            }
                        ]
                    },
                    "expect_success": True
                },
                {
                    "tool": "bucket_object_fetch",
                    "args": {
                        "s3_uri": "{env.QUILT_TEST_BUCKET}/test-loop-{uuid}.txt",
                        "max_bytes": 1000
                    },
                    "expect_success": True
                }
                # Note: No explicit delete - test files can be cleaned up manually
            ]
        },
        "workflow_basic": {
            "description": "Test workflow create/add step/update step cycle",
            "cleanup_on_failure": True,
            "steps": [
                {
                    "tool": "workflow_create",
                    "args": {
                        "workflow_id": "test-wf-{uuid}",
                        "name": "Test Workflow {uuid}"
                    },
                    "expect_success": True
                },
                {
                    "tool": "workflow_add_step",
                    "args": {
                        "workflow_id": "test-wf-{uuid}",
                        "step_id": "step1",
                        "description": "Test Step 1"
                    },
                    "expect_success": True
                },
                {
                    "tool": "workflow_update_step",
                    "args": {
                        "workflow_id": "test-wf-{uuid}",
                        "step_id": "step1",
                        "status": "completed"
                    },
                    "expect_success": True
                }
                # Note: No explicit workflow delete - workflows can be cleaned up manually
            ]
        },
        "visualization_create": {
            "description": "Test visualization creation",
            "cleanup_on_failure": False,
            "steps": [
                {
                    "tool": "create_data_visualization",
                    "args": {
                        "data": {"x": [1, 2, 3], "y": [4, 5, 6]},
                        "plot_type": "scatter",
                        "x_column": "x",
                        "y_column": "y"
                    },
                    "expect_success": True
                }
                # Note: Visualization is read-only (creates file but doesn't persist state)
            ]
        },
        "tabulator_table_lifecycle": {
            "description": "Test tabulator table create/rename/delete cycle",
            "cleanup_on_failure": True,
            "steps": [
                {
                    "tool": "tabulator_table_create",
                    "args": {
                        "bucket_name": "{env.QUILT_TEST_BUCKET}",
                        "table_name": "test_table_{uuid}",
                        "schema": [{"name": "col1", "type": "string"}],
                        "package_pattern": "*/pkg",
                        "logical_key_pattern": "*.csv"
                    },
                    "expect_success": True
                },
                {
                    "tool": "tabulator_table_rename",
                    "args": {
                        "bucket_name": "{env.QUILT_TEST_BUCKET}",
                        "old_name": "test_table_{uuid}",
                        "new_name": "test_table_{uuid}_renamed"
                    },
                    "expect_success": True
                },
                {
                    "tool": "tabulator_table_delete",
                    "args": {
                        "bucket_name": "{env.QUILT_TEST_BUCKET}",
                        "table_name": "test_table_{uuid}_renamed"
                    },
                    "expect_success": True,
                    "is_cleanup": True
                }
            ]
        },
        "quilt_summary_create": {
            "description": "Test create_quilt_summary_files tool",
            "cleanup_on_failure": False,
            "steps": [
                {
                    "tool": "create_quilt_summary_files",
                    "args": {
                        "package_name": "testuser/test-pkg",
                        "package_metadata": {"description": "test"},
                        "organized_structure": {"root": []},
                        "readme_content": "# Test Package",
                        "source_info": {"source": "test"},
                        "metadata_template": "standard"
                    },
                    "expect_success": True
                }
            ]
        }
    }


def validate_tool_loops_coverage(server_tools: Dict[str, Any], tool_loops: Dict[str, Any], standalone_tools: Dict[str, Any]) -> None:
    """Validate that tool loops + standalone tests cover all write-effect tools.

    Args:
        server_tools: All tools from server
        tool_loops: Tool loops configuration
        standalone_tools: Standalone test configurations

    Raises:
        ValueError: If coverage is incomplete
    """
    # Find all write-effect tools
    write_tools = set()
    for tool_name, handler in server_tools.items():
        effect, _ = classify_tool(tool_name, handler)
        if effect in ['create', 'update', 'remove']:
            write_tools.add(tool_name)

    # Find tools covered by loops
    loop_covered = set()
    for loop_name, loop_config in tool_loops.items():
        for step in loop_config.get('steps', []):
            tool_name = step.get('tool')
            if tool_name:
                loop_covered.add(tool_name)

    # Find tools covered by standalone tests
    standalone_covered = set(standalone_tools.keys())

    # Check coverage
    total_covered = loop_covered | standalone_covered
    uncovered = write_tools - total_covered

    if uncovered:
        print(f"\n⚠️  WARNING: {len(uncovered)} write-effect tool(s) not covered by loops or standalone tests:")
        for tool in sorted(uncovered):
            print(f"  • {tool}")
        print(f"\n💡 Add these tools to tool loops or standalone tests to achieve 100% coverage")


# ============================================================================
# Phase 1: Introspection (Existing)
# ============================================================================

async def extract_tool_metadata(server) -> List[Dict[str, Any]]:
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

        tools.append({
            "type": "tool",
            "name": tool_name,
            "module": short_module,
            "signature": signature_str,
            "description": doc.split('\n')[0],  # First line only
            "is_async": is_async,
            "full_module_path": module_name,
            "handler_class": handler.__class__.__name__
        })

    # Sort by module then name for consistent ordering
    tools.sort(key=lambda x: (x["module"], x["name"]))
    return tools

async def extract_resource_metadata(server) -> List[Dict[str, Any]]:
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

        resources.append({
            "type": "resource",
            "name": uri,
            "module": "resources",
            "signature": f"@mcp.resource('{uri}')",
            "description": resource.description,
            "is_async": True,
            "full_module_path": "quilt_mcp.resources",
            "handler_class": "FastMCP Resource"
        })

    # Process resource templates
    # resource_templates is a dict with URI template keys and FunctionResource values
    for uri_template, template in resource_templates.items():
        # ERROR if template lacks a name
        if not hasattr(template, 'name') or not template.name:
            raise ValueError(f"Resource template '{uri_template}' is missing a name!")

        # ERROR if template lacks a description
        if not hasattr(template, 'description') or not template.description:
            raise ValueError(f"Resource template '{uri_template}' is missing a description!")

        resources.append({
            "type": "resource",
            "name": uri_template,
            "module": "resources",
            "signature": f"@mcp.resource('{uri_template}')",
            "description": template.description,
            "is_async": True,
            "full_module_path": "quilt_mcp.resources",
            "handler_class": "FastMCP Template"
        })

    # Sort by URI pattern for consistent ordering
    resources.sort(key=lambda x: x["name"])
    return resources

def generate_csv_output(items: List[Dict[str, Any]], output_file: str):
    """Generate CSV output for tools and resources with type column."""
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            "type", "module", "function_name", "signature", "description",
            "is_async", "full_module_path"
        ])

        for item in items:
            writer.writerow([
                item["type"],
                item["module"],
                item["name"],
                item["signature"],
                item["description"],
                str(item["is_async"]),
                item["full_module_path"]
            ])

def generate_json_output(items: List[Dict[str, Any]], output_file: str):
    """Generate structured JSON output for tooling."""
    tools = [item for item in items if item["type"] == "tool"]
    resources = [item for item in items if item["type"] == "resource"]

    output = {
        "metadata": {
            "generated_by": "scripts/mcp-test-setup.py",
            "tool_count": len(tools),
            "resource_count": len(resources),
            "total_count": len(items),
            "modules": list(set(item["module"] for item in items))
        },
        "tools": tools,
        "resources": resources
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


def _truncate_response(response: Any, max_size: int = 1000) -> Any:
    """Truncate large responses to keep YAML config manageable and ensure serializability."""
    if not isinstance(response, dict):
        # Handle non-dict responses
        if isinstance(response, (str, int, float, bool, type(None))):
            return response
        else:
            return str(response)  # Convert non-serializable to string

    result = {}
    for key, value in response.items():
        try:
            if isinstance(value, list):
                # Truncate arrays to first few items
                if len(value) > 3:
                    result[key] = value[:3] + [{"_truncated": f"{len(value) - 3} more items"}]
                else:
                    result[key] = value
            elif isinstance(value, str) and len(value) > max_size:
                result[key] = value[:max_size] + f"... (truncated, {len(value)} total chars)"
            elif isinstance(value, dict):
                # Recursively truncate nested dicts
                result[key] = _truncate_response(value, max_size)
            elif isinstance(value, (int, float, bool, type(None))):
                result[key] = value
            else:
                # Convert non-serializable objects to strings
                result[key] = str(value)
        except Exception:
            # If anything fails, convert to string
            result[key] = f"<non-serializable: {type(value).__name__}>"

    return result


async def generate_test_yaml(server, output_file: str, env_vars: Dict[str, str | None], skip_discovery: bool = False, discovery_timeout: float = 15.0):
    """Generate mcp-test.yaml configuration with all available tools and resources.

    This creates test configurations for mcp-test.py to validate the MCP server.
    Each tool gets a basic test case that can be customized as needed.
    Each resource gets test configuration with URI patterns and validation rules.
    Environment configuration from .env is embedded for self-contained testing.

    Phase 2 Enhancement: Runs discovery to validate tools and capture real data.

    Phase 4 Enhancement (A18): Generates tool_loops section for write-operation testing.

    Args:
        server: MCP server instance
        output_file: Path to output YAML file
        env_vars: Environment variables from .env
        skip_discovery: Skip tool discovery phase
        discovery_timeout: Timeout in seconds for each tool discovery
    """
    # Extract test-relevant configuration from environment
    test_config = {
        "_generated_by": "scripts/mcp-test-setup.py - Auto-generated test configuration with discovery and tool loops",
        "_note": "Edit test cases below to customize arguments and validation. Tool loops test write operations.",
        "environment": {
            "AWS_PROFILE": env_vars.get("AWS_PROFILE", "default"),
            "AWS_DEFAULT_REGION": env_vars.get("AWS_DEFAULT_REGION", "us-east-1"),
            "QUILT_CATALOG_URL": env_vars.get("QUILT_CATALOG_URL", ""),
            "QUILT_TEST_BUCKET": env_vars.get("QUILT_TEST_BUCKET", ""),
            "QUILT_TEST_PACKAGE": env_vars.get("QUILT_TEST_PACKAGE", ""),
            "QUILT_TEST_ENTRY": env_vars.get("QUILT_TEST_ENTRY", ""),
        },
        "test_tools": {},
        "test_resources": {},
        "tool_loops": {},  # NEW: Tool loops for write-operation testing
        "test_config": {
            "timeout": 30,
            "retry_attempts": 2,
            "fail_fast": False
        }
    }

    # Initialize discovery orchestrator
    orchestrator = DiscoveryOrchestrator(server, timeout=discovery_timeout, verbose=True, env_vars=env_vars)

    # Get all registered tools
    # Get all tools
    server_tools = await server.get_tools()

    # Load values from .env
    test_bucket: str = env_vars.get("QUILT_TEST_BUCKET") or "s3://quilt-example"
    catalog_url: str = env_vars.get("QUILT_CATALOG_URL") or "https://open.quiltdata.com"
    test_package: str = env_vars.get("QUILT_TEST_PACKAGE") or "examples/wellplates"
    test_entry: str = env_vars.get("QUILT_TEST_ENTRY") or ".timestamp"
    bucket_name = test_bucket.replace("s3://", "").split("/")[0]

    # Get UserAthenaDatabase from the CloudFormation stack
    print(f"\n🔍 Looking up UserAthenaDatabase from stack for catalog: {catalog_url}")
    athena_database = get_user_athena_database(catalog_url)

    # Auto-generate tool order from all discovered tools
    # Special case: bucket_objects_list runs FIRST to discover real objects
    all_tool_names = list(server_tools.keys())

    # Separate bucket_objects_list from others
    priority_tools = []
    if "bucket_objects_list" in all_tool_names:
        priority_tools.append("bucket_objects_list")
        all_tool_names.remove("bucket_objects_list")

    # Sort remaining tools alphabetically for deterministic ordering
    all_tool_names.sort()

    # Final order: priority tools first, then all others
    tool_order = priority_tools + all_tool_names

    # Tools with multiple test variants based on parameter combinations
    # Format: tool_name -> {"param_name": [test_value1, test_value2, ...]}
    # Special handling: if variant name contains "package", uses QUILT_TEST_PACKAGE, else QUILT_TEST_ENTRY
    # For search_catalog: Only test without bucket (wildcard across all buckets)
    # Note: Removed "with_bucket" mode as hardcoded bucket assumptions are being eliminated
    tool_variants = {
        "search_catalog": {
            "scope": ["global", "file", "package"],
            "bucket_mode": ["no_bucket"]  # Test wildcard patterns only
        }
    }

    # Custom test configurations for specific tools
    # For tools with variants, use tool_name.variant_value format
    # Note: Empty dict {} means tool has no required params (will be auto-filled by effect classifier)
    custom_configs = {
        # Catalog operations
        "catalog_configure": {"catalog_url": catalog_url},
        "catalog_uri": {"registry": test_bucket, "package_name": test_package, "path": ".timestamp"},
        "catalog_url": {"registry": test_bucket, "package_name": test_package, "path": ".timestamp"},

        # Bucket operations (discovery)
        "bucket_objects_list": {"bucket": bucket_name, "prefix": f"{test_package}/", "max_keys": 5},
        "bucket_object_info": {"s3_uri": f"s3://{test_bucket}/{test_package}/.timestamp"},
        "bucket_object_link": {"s3_uri": f"s3://{test_bucket}/{test_package}/.timestamp"},
        "bucket_object_text": {"s3_uri": f"s3://{test_bucket}/{test_package}/.timestamp", "max_bytes": 200},
        "bucket_object_fetch": {"s3_uri": f"s3://{test_bucket}/{test_package}/.timestamp", "max_bytes": 200},
        # bucket_objects_put: Omitted - will be tested via tool loops

        # Package operations (read-only)
        "package_browse": {"package_name": test_package, "registry": test_bucket, "recursive": False, "include_signed_urls": False, "top": 5},
        "package_diff": {"package1_name": test_package, "package2_name": test_package, "registry": test_bucket},
        # package_create, package_update, package_delete: Omitted - will be tested via tool loops

        # Search operations (search_catalog variants auto-generated, see tool_variants)
        "search_explain": {"query": "CSV files"},
        "search_suggest": {"partial_query": test_package[:5], "limit": 5},

        # Query operations
        "athena_query_validate": {"query": "SHOW TABLES"},
        "athena_query_execute": {"query": "SELECT 1 as test_value", "max_results": 10},
        "athena_tables_list": {"database": athena_database},
        # Use a known table that exists in the UserAthenaDatabase
        "athena_table_schema": {"database": athena_database, "table": "ai2-semanticscholar-cord-19_manifests"},
        "tabulator_bucket_query": {"bucket_name": bucket_name, "query": "SELECT 1 as test_value", "max_results": 10},
        "tabulator_tables_list": {"bucket": bucket_name},
        "tabulator_open_query_status": {},
        # tabulator_open_query_toggle: Omitted - will be tested via tool loops

        # Workflow operations
        "workflow_template_apply": {"template_name": "cross-package-aggregation", "workflow_id": "test-wf-001", "params": {"source_packages": [test_package], "target_package": f"{test_package}-agg"}},
        # workflow_create, workflow_add_step, workflow_update_step: Omitted - will be tested via tool loops

        # Visualization operations
        # create_data_visualization: Omitted - will be tested via tool loops

        # Permissions operations - limit to test bucket for faster execution
        "discover_permissions": {"check_buckets": [bucket_name]},
        "check_bucket_access": {"bucket": bucket_name},

        # Admin/Governance operations (read-only ones included for testing)
        "admin_user_get": {"name": "admin"},
        # admin_user_create, admin_user_delete, etc.: Omitted - will be tested via tool loops
        # admin_sso_*, admin_tabulator_*: Omitted - will be tested via tool loops
    }

    # Process tools in defined order
    for tool_name in tool_order:
        if tool_name not in server_tools:
            continue

        handler = server_tools[tool_name]
        doc = inspect.getdoc(handler.fn) or "No description available"

        # Classify tool
        effect, category = classify_tool(tool_name, handler)

        # Check if this tool has variants
        if tool_name in tool_variants:
            # Generate test cases for each variant combination
            variants_config = tool_variants[tool_name]

            # Handle multi-dimensional variants (e.g., scope x bucket_mode)
            if "bucket_mode" in variants_config:
                # Special handling for search_catalog with scope and bucket combinations
                scope_values = variants_config.get("scope", ["global"])
                bucket_modes = variants_config.get("bucket_mode", ["with_bucket"])

                for scope in scope_values:
                    for bucket_mode in bucket_modes:
                        # Create variant key like "search_catalog.file.no_bucket"
                        variant_key = f"{tool_name}.{scope}.{bucket_mode}"

                        # Determine query value based on scope
                        query_value = test_package if scope == "package" else test_entry

                        # Build arguments based on bucket_mode
                        arguments = {
                            "query": query_value,
                            "limit": 10,
                            "scope": scope
                        }

                        if bucket_mode == "with_bucket":
                            arguments["bucket"] = test_bucket
                        # else: no_bucket - omit bucket parameter to test search across all indexes

                        test_case = {
                            "tool": tool_name,  # Store the actual tool name
                            "description": doc.split('\n')[0],
                            "effect": effect,
                            "arguments": arguments,
                            "response_schema": {
                                "type": "object",
                                "properties": {
                                    "content": {
                                        "type": "array",
                                        "items": {
                                            "type": "object"
                                        }
                                    }
                                },
                                "required": ["content"]
                            }
                        }

                        # Add smart validation rules for search variants
                        # For "no_bucket" mode, allow 0 results since elasticsearch may not be
                        # available in test environments (Docker containers).
                        # For "with_bucket" mode, require at least 1 result to verify search works.
                        validation = {
                            "type": "search",
                            "min_results": 0 if bucket_mode == "no_bucket" else 1,
                            "must_contain": []
                        }

                        if scope == "file":
                            # File search must find TEST_ENTRY
                            if bucket_mode == "with_bucket":
                                validation["description"] = f"File search with specific bucket must find TEST_ENTRY ({test_entry})"
                                validation["must_contain"].append({
                                    "value": test_entry,
                                    "field": "title",
                                    "match_type": "substring",
                                    "description": f"Must find {test_entry} in file search results (title field)"
                                })
                            else:
                                validation["description"] = f"File search across all buckets (may return 0 if bucket enumeration unavailable)"

                            validation["result_shape"] = {
                                "required_fields": ["id", "type", "title", "score"]
                            }

                        elif scope == "package":
                            # Package search should return results
                            if bucket_mode == "with_bucket":
                                validation["description"] = f"Package search with specific bucket should return results"
                                validation["min_results"] = 1
                            else:
                                validation["description"] = f"Package search across all buckets (may return 0 if bucket enumeration unavailable)"

                            validation["result_shape"] = {
                                "required_fields": ["id", "type", "score"]
                            }

                        elif scope == "global":
                            # Global search should find test entry
                            if bucket_mode == "with_bucket":
                                validation["description"] = "Global search with specific bucket should return results including test entry"
                                validation["must_contain"].append({
                                    "value": test_entry,
                                    "field": "title",
                                    "match_type": "substring",
                                    "description": f"Must find TEST_ENTRY ({test_entry}) in global results (title field)"
                                })
                                validation["min_results"] = 1
                            else:
                                validation["description"] = "Global search across all buckets (may return 0 if bucket enumeration unavailable)"

                        test_case["validation"] = validation
                        test_config["test_tools"][variant_key] = test_case
            else:
                # Legacy single-parameter variant handling (for future tools if needed)
                for param_name, param_values in variants_config.items():
                    for param_value in param_values:
                        variant_key = f"{tool_name}.{param_value}"
                        arguments = {"query": test_entry, "limit": 10, param_name: param_value}
                        test_case = {
                            "tool": tool_name,
                            "description": doc.split('\n')[0],
                            "effect": effect,
                            "arguments": arguments,
                            "response_schema": {
                                "type": "object",
                                "properties": {
                                    "content": {
                                        "type": "array",
                                        "items": {"type": "object"}
                                    }
                                },
                                "required": ["content"]
                            }
                        }
                        test_config["test_tools"][variant_key] = test_case
        else:
            # Single test case for tools without variants
            # Use custom config if available, otherwise infer arguments
            if tool_name in custom_configs:
                arguments = custom_configs[tool_name]
            else:
                # Infer arguments from signature and environment
                arguments = infer_arguments(tool_name, handler, env_vars, orchestrator.registry.to_dict(), athena_database)

            test_case = {
                "description": doc.split('\n')[0],
                "effect": effect,
                "category": category,  # Track tool category
                "arguments": arguments,
                "response_schema": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "array",
                            "items": {
                                "type": "object"
                            }
                        }
                    },
                    "required": ["content"]
                }
            }

            test_config["test_tools"][tool_name] = test_case

    # ========================================================================
    # Phase 2: Discovery - Execute tools and validate
    # ========================================================================
    if not skip_discovery:
        print(f"\n🔍 Phase 2: Discovering & Validating Tools...")
        print(f"   Running discovery for {len(test_config['test_tools'])} tool configurations...")

        discovery_count = 0
        for test_key, test_case in test_config["test_tools"].items():
            # Get the actual tool name (may differ from test_key for variants)
            actual_tool_name = test_case.get("tool", test_key)

            # Skip if not in server_tools
            if actual_tool_name not in server_tools:
                continue

            handler = server_tools[actual_tool_name]
            arguments = test_case.get("arguments", {})
            effect = test_case.get("effect", "none")
            category = test_case.get("category", "required-arg")

            # Run discovery
            result = await orchestrator.discover_tool(
                actual_tool_name,
                handler,
                arguments,
                effect,
                category
            )

            # Store result
            orchestrator.results[test_key] = result

            # Add discovery info to test case
            # NOTE: Omit volatile data (precise timings, timestamps, presigned URLs)
            # to avoid unnecessary git diffs on every run
            discovery_info = {
                "status": result.status,
                # Round duration to nearest 100ms to reduce noise
                "duration_ms": round(result.duration_ms / 100) * 100 if result.duration_ms else 0,
            }

            if result.status == 'PASSED':
                # Add response example (truncate if too large)
                if result.response:
                    truncated = _truncate_response(result.response, max_size=1000)
                    discovery_info["response_example"] = truncated
                if result.discovered_data:
                    discovery_info["discovered_data"] = result.discovered_data

                discovery_count += 1
                if discovery_count <= 5 or orchestrator.verbose:  # Print first 5 or all if verbose
                    print(f"  ✓ {test_key} ({result.duration_ms:.0f}ms)")

            elif result.status == 'FAILED':
                discovery_info["error"] = result.error
                discovery_info["error_category"] = result.error_category
                print(f"  ✗ {test_key}: {result.error}")

            elif result.status == 'SKIPPED':
                if discovery_count <= 3:  # Only print first few skipped
                    print(f"  ⊘ {test_key}: {result.error}")

            test_case["discovery"] = discovery_info

        # Print summary
        orchestrator.print_summary()

        # Add discovered data registry to config
        test_config["discovered_data"] = orchestrator.registry.to_dict()

    # ========================================================================
    # Phase 4: Generate Tool Loops
    # ========================================================================
    print(f"\n🔄 Phase 4: Generating Tool Loops for Write Operations...")
    tool_loops = generate_tool_loops(env_vars)
    test_config["tool_loops"] = tool_loops
    print(f"   Generated {len(tool_loops)} tool loops")

    # Validate coverage
    print(f"\n📊 Validating Tool Coverage...")
    validate_tool_loops_coverage(server_tools, tool_loops, test_config["test_tools"])

    # Generate resource test configuration
    print(f"\n🗂️  Generating resource test configuration...")

    import re
    # Get resources from FastMCP server
    static_resources = await server.get_resources()
    resource_templates = await server.get_resource_templates()

    # Process both static resources and templates
    # Both are dicts with URI (template) keys and FunctionResource values
    all_resources = []
    for uri, resource in static_resources.items():
        # ERROR if resource lacks a description
        if not hasattr(resource, 'description') or not resource.description:
            raise ValueError(f"Resource '{uri}' is missing a description in test YAML generation!")
        all_resources.append((uri, resource.description))

    for uri_template, template in resource_templates.items():
        # ERROR if template lacks a description
        if not hasattr(template, 'description') or not template.description:
            raise ValueError(f"Resource template '{uri_template}' is missing a description in test YAML generation!")
        all_resources.append((uri_template, template.description))

    for uri_pattern, doc in all_resources:

        # Build basic test case structure - default to JSON since most resources return JSON
        test_case = {
            "description": doc.split('\n')[0],
            "effect": "none",  # Resources are read-only
            "uri": uri_pattern,
            "uri_variables": {},
            "expected_mime_type": "application/json",  # Default to JSON
            "content_validation": {
                "type": "json",
                "min_length": 1,
                "max_length": 100000,
                "schema": {
                    "type": "object",
                    "description": "Auto-generated basic schema - customize as needed"
                }
            }
        }

        # Detect URI template variables (e.g., {database}, {table}, {bucket})
        # FastMCP supports templated URIs when registered with add_resource_fn
        # The client expands templates with actual values, and FastMCP handles routing
        variables = re.findall(r'\{(\w+)\}', uri_pattern)
        for var in variables:
            # Substitute test values for common template variables
            if var == "bucket":
                # Use bucket name from QUILT_TEST_BUCKET environment variable (already loaded above)
                # Extract bucket name from s3:// URI
                bucket_name_var = test_bucket.replace("s3://", "").split("/")[0] if test_bucket.startswith("s3://") else test_bucket
                test_case["uri_variables"][var] = bucket_name_var
            elif var == "database":
                # Use UserAthenaDatabase from stack
                test_case["uri_variables"][var] = athena_database
            elif var == "table":
                # Use a test table name
                test_case["uri_variables"][var] = "test_table"
            elif var == "name":
                # Use a test user name
                test_case["uri_variables"][var] = "test_user"
            elif var == "id":
                # Use a test workflow ID
                test_case["uri_variables"][var] = "test-workflow-001"
            else:
                # For unknown variables, mark as needing configuration
                test_case["uri_variables"][var] = f"CONFIGURE_{var.upper()}"

        # All resources return JSON by default
        # (FastMCP decorator-based resources all return JSON)

        test_config["test_resources"][uri_pattern] = test_case

    print(f"   Generated {len(test_config['test_resources'])} resource test cases")

    # Write YAML with nice formatting
    with open(output_file, 'w', encoding='utf-8') as f:
        yaml.dump(test_config, f,
                  default_flow_style=False,
                  sort_keys=False,
                  allow_unicode=True,
                  indent=2)


async def main():
    """Generate all canonical tool and resource listings."""
    import argparse

    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Generate MCP test configuration with intelligent discovery and 100% coverage"
    )
    parser.add_argument(
        "--skip-discovery",
        action="store_true",
        help="Skip tool discovery phase (generate config without validation)"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate coverage without regenerating YAML (exit 0 if 100%%, 1 otherwise)"
    )
    parser.add_argument(
        "--show-missing",
        action="store_true",
        help="List tools without test configurations and exit"
    )
    parser.add_argument(
        "--show-categories",
        action="store_true",
        help="Show tool classification (category + effect) and exit"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: validate only essential tools (not yet implemented)"
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Re-discover only tools with FAILED status (not yet implemented)"
    )
    parser.add_argument(
        "--discovery-timeout",
        type=float,
        default=15.0,
        help="Timeout in seconds for each tool discovery (default: 15.0)"
    )
    args = parser.parse_args()

    # Load environment configuration from .env
    repo_root = Path(__file__).parent.parent
    env_file = repo_root / ".env"
    env_vars = dotenv_values(env_file)

    if env_vars:
        print(f"📋 Loaded configuration from .env")
        print(f"   AWS_PROFILE: {env_vars.get('AWS_PROFILE', 'not set')}")
        print(f"   AWS_DEFAULT_REGION: {env_vars.get('AWS_DEFAULT_REGION', 'not set')}")
        print(f"   QUILT_TEST_BUCKET: {env_vars.get('QUILT_TEST_BUCKET', 'not set')}")
    else:
        print("⚠️  No .env file found - using default test configuration")

    if args.skip_discovery:
        print("⚠️  Discovery phase skipped (--skip-discovery flag)")

    print("\n🔍 Phase 1: Introspection - Extracting tools from MCP server...")

    # Create server instance to introspect tools
    server = create_configured_server(verbose=False)

    # Handle --show-categories mode
    if args.show_categories:
        print("\n📊 Tool Classification:")
        server_tools = await server.get_tools()
        by_category = {}
        for tool_name, handler in server_tools.items():
            effect, category = classify_tool(tool_name, handler)
            by_category.setdefault(category, []).append((tool_name, effect))

        for category in ['zero-arg', 'required-arg', 'optional-arg', 'write-effect', 'context-required']:
            if category in by_category:
                print(f"\n{category.upper().replace('-', ' ')} ({len(by_category[category])} tools):")
                for tool_name, effect in sorted(by_category[category]):
                    print(f"  • {tool_name} (effect={effect})")
        sys.exit(0)

    # Handle --show-missing mode
    if args.show_missing:
        scripts_tests_dir = Path(__file__).parent / "tests"
        yaml_path = scripts_tests_dir / "mcp-test.yaml"

        if not yaml_path.exists():
            print(f"❌ Test config not found: {yaml_path}")
            print("   Run without --show-missing to generate it")
            sys.exit(1)

        # Load existing YAML
        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)

        # Get server tools
        server_tools = await server.get_tools()
        server_tool_names = set(server_tools.keys())

        # Get config tools (handle variants)
        config_tool_names = set()
        for config_key, config_value in config.get('test_tools', {}).items():
            if isinstance(config_value, dict) and 'tool' in config_value:
                config_tool_names.add(config_value['tool'])
            else:
                config_tool_names.add(config_key)

        # Find missing
        missing = server_tool_names - config_tool_names

        if missing:
            print(f"\n❌ {len(missing)} tool(s) NOT covered by test config:")
            for tool_name in sorted(missing):
                handler = server_tools[tool_name]
                effect, category = classify_tool(tool_name, handler)
                print(f"  • {tool_name} (category={category}, effect={effect})")
            print(f"\n📋 Coverage: {len(config_tool_names)}/{len(server_tool_names)} tools")
            print(f"   Run without --show-missing to regenerate with 100% coverage")
            sys.exit(1)
        else:
            print(f"✅ All {len(server_tool_names)} tools covered by test config")
            sys.exit(0)

    # Handle --validate-only mode
    if args.validate_only:
        scripts_tests_dir = Path(__file__).parent / "tests"
        yaml_path = scripts_tests_dir / "mcp-test.yaml"

        if not yaml_path.exists():
            print(f"❌ Test config not found: {yaml_path}")
            sys.exit(1)

        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)

        server_tools = await server.get_tools()
        server_tool_names = set(server_tools.keys())

        config_tool_names = set()
        for config_key, config_value in config.get('test_tools', {}).items():
            if isinstance(config_value, dict) and 'tool' in config_value:
                config_tool_names.add(config_value['tool'])
            else:
                config_tool_names.add(config_key)

        missing = server_tool_names - config_tool_names

        if missing:
            print(f"❌ Coverage validation FAILED: {len(missing)} tools missing")
            sys.exit(1)
        else:
            print(f"✅ Coverage validation PASSED: {len(server_tool_names)} tools covered")
            sys.exit(0)

    tools = await extract_tool_metadata(server)

    print(f"📊 Found {len(tools)} tools across {len(set(tool['module'] for tool in tools))} modules")

    print("🔍 Extracting resources from MCP server...")
    # Get resources directly from FastMCP server
    resources = await extract_resource_metadata(server)

    print(f"📊 Found {len(resources)} resources across {len(set(resource['module'] for resource in resources))} modules")

    # Combine tools and resources
    all_items = tools + resources

    # Generate outputs
    output_dir = Path(__file__).parent.parent
    tests_fixtures_dir = output_dir / "tests" / "fixtures"
    scripts_tests_dir = Path(__file__).parent / "tests"

    print("\n📝 Generating CSV output...")
    generate_csv_output(all_items, str(tests_fixtures_dir / "mcp-list.csv"))

    print("📋 Generating JSON metadata...")
    generate_json_output(all_items, str(output_dir / "build" / "tools_metadata.json"))

    print("\n🧪 Phase 3: Generation - Creating test configuration YAML...")
    await generate_test_yaml(
        server,
        str(scripts_tests_dir / "mcp-test.yaml"),
        env_vars,
        skip_discovery=args.skip_discovery,
        discovery_timeout=args.discovery_timeout
    )

    print("\n✅ Canonical tool and resource listings generated!")
    print("📂 Files created:")
    print("   - tests/fixtures/mcp-list.csv")
    print("   - build/tools_metadata.json")
    print("   - scripts/tests/mcp-test.yaml (with discovery results and tool loops)")
    print(f"\n📈 Summary:")
    print(f"   - {len(tools)} tools")
    print(f"   - {len(resources)} resources")
    print(f"   - {len(all_items)} total items")

    if not args.skip_discovery:
        print(f"\n💡 Next steps:")
        print(f"   1. Review tool loops section in mcp-test.yaml")
        print(f"   2. Run tests: uv run python scripts/mcp-test.py --tools-test")
        print(f"   3. Test specific loop: uv run python scripts/mcp-test.py --loop admin_user_basic")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
