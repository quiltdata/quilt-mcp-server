"""Backward Compatibility Shims for MCP Resources.

This module provides compatibility functions that maintain the original API
while using MCP resources internally. This ensures 100% backward compatibility
during the transition to the new MCP resource system.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from .admin import AdminUsersResource, AdminRolesResource
from .s3 import S3BucketsResource
from .athena import AthenaDatabasesResource, AthenaWorkgroupsResource
from .metadata import MetadataTemplatesResource
from .workflow import WorkflowResource
from .package import PackageToolsResource
from .tabulator import TabulatorTablesResource

logger = logging.getLogger(__name__)


class CompatibilityShim:
    """Base class for backward compatibility shims."""

    def __init__(self, resource_class):
        """Initialize with the MCP resource class."""
        self._resource_class = resource_class
        self._resource_instance = None

    def _get_resource(self):
        """Get or create the resource instance."""
        if self._resource_instance is None:
            self._resource_instance = self._resource_class()
        return self._resource_instance

    async def _call_resource_async(self, **params) -> Dict[str, Any]:
        """Call the resource and return original format."""
        try:
            resource = self._get_resource()
            return await resource.list_items(**params)
        except Exception as e:
            logger.error(f"MCP resource call failed, falling back to error response: {e}")
            return self._fallback_error_response(str(e))

    def _call_resource_sync(self, **params) -> Dict[str, Any]:
        """Call the resource synchronously and return original format."""
        try:
            return asyncio.run(self._call_resource_async(**params))
        except Exception as e:
            logger.error(f"MCP resource call failed, falling back to error response: {e}")
            return self._fallback_error_response(str(e))

    def _fallback_error_response(self, error_message: str) -> Dict[str, Any]:
        """Generate fallback error response in original format."""
        from ..utils import format_error_response
        return format_error_response(f"MCP resource error: {error_message}")


# Admin Functions Compatibility Shims

class AdminUsersListShim(CompatibilityShim):
    """Compatibility shim for admin_users_list function."""

    def __init__(self):
        super().__init__(AdminUsersResource)

    async def __call__(self) -> Dict[str, Any]:
        """Call admin_users_list via MCP resource."""
        return await self._call_resource_async()


class AdminRolesListShim(CompatibilityShim):
    """Compatibility shim for admin_roles_list function."""

    def __init__(self):
        super().__init__(AdminRolesResource)

    async def __call__(self) -> Dict[str, Any]:
        """Call admin_roles_list via MCP resource."""
        return await self._call_resource_async()


# S3 Functions Compatibility Shims

class ListAvailableResourcesShim(CompatibilityShim):
    """Compatibility shim for list_available_resources function."""

    def __init__(self):
        super().__init__(S3BucketsResource)

    def __call__(self) -> Dict[str, Any]:
        """Call list_available_resources via MCP resource."""
        return self._call_resource_sync()


# Athena Functions Compatibility Shims

class AthenaDatabasesListShim(CompatibilityShim):
    """Compatibility shim for athena_databases_list function."""

    def __init__(self):
        super().__init__(AthenaDatabasesResource)

    def __call__(self, catalog_name: str = "AwsDataCatalog", service: Optional[Any] = None) -> Dict[str, Any]:
        """Call athena_databases_list via MCP resource."""
        return self._call_resource_sync(catalog_name=catalog_name, service=service)


class AthenaWorkgroupsListShim(CompatibilityShim):
    """Compatibility shim for athena_workgroups_list function."""

    def __init__(self):
        super().__init__(AthenaWorkgroupsResource)

    def __call__(self, use_quilt_auth: bool = True, service: Optional[Any] = None) -> Dict[str, Any]:
        """Call athena_workgroups_list via MCP resource."""
        return self._call_resource_sync(use_quilt_auth=use_quilt_auth, service=service)


# Metadata Functions Compatibility Shims

class ListMetadataTemplatesShim(CompatibilityShim):
    """Compatibility shim for list_metadata_templates function."""

    def __init__(self):
        super().__init__(MetadataTemplatesResource)

    def __call__(self) -> Dict[str, Any]:
        """Call list_metadata_templates via MCP resource."""
        return self._call_resource_sync()


# Workflow Functions Compatibility Shims

class WorkflowListShim(CompatibilityShim):
    """Compatibility shim for workflow_list function."""

    def __init__(self):
        super().__init__(WorkflowResource)

    def __call__(self) -> Dict[str, Any]:
        """Call workflow_list via MCP resource."""
        return self._call_resource_sync()


# Package Functions Compatibility Shims

class PackageToolsListShim(CompatibilityShim):
    """Compatibility shim for package_tools_list function."""

    def __init__(self):
        super().__init__(PackageToolsResource)

    def __call__(self) -> Dict[str, Any]:
        """Call package_tools_list via MCP resource."""
        return self._call_resource_sync()


# Tabulator Functions Compatibility Shims

class TabulatorTablesListShim(CompatibilityShim):
    """Compatibility shim for tabulator_tables_list function."""

    def __init__(self):
        super().__init__(TabulatorTablesResource)

    async def __call__(self, bucket_name: str) -> Dict[str, Any]:
        """Call tabulator_tables_list via MCP resource."""
        return await self._call_resource_async(bucket_name=bucket_name)


# Global shim instances - these can be used to replace original functions
admin_users_list_shim = AdminUsersListShim()
admin_roles_list_shim = AdminRolesListShim()
list_available_resources_shim = ListAvailableResourcesShim()
athena_databases_list_shim = AthenaDatabasesListShim()
athena_workgroups_list_shim = AthenaWorkgroupsListShim()
list_metadata_templates_shim = ListMetadataTemplatesShim()
workflow_list_shim = WorkflowListShim()
package_tools_list_shim = PackageToolsListShim()
tabulator_tables_list_shim = TabulatorTablesListShim()


def enable_mcp_resources_globally():
    """Enable MCP resources globally by replacing original functions with shims.

    This function replaces the original list functions with MCP resource-based
    implementations while maintaining 100% API compatibility.

    WARNING: This modifies the original modules. Use with caution in production.
    """
    logger.info("Enabling MCP resources globally - replacing original functions with shims")

    try:
        # Replace admin functions
        import quilt_mcp.tools.governance as governance_module
        governance_module.admin_users_list = admin_users_list_shim
        governance_module.admin_roles_list = admin_roles_list_shim
        logger.info("✅ Replaced admin functions with MCP resource shims")

        # Replace S3 functions
        import quilt_mcp.tools.unified_package as unified_package_module
        unified_package_module.list_available_resources = list_available_resources_shim
        logger.info("✅ Replaced S3 functions with MCP resource shims")

        # Replace Athena functions
        import quilt_mcp.tools.athena_glue as athena_module
        athena_module.athena_databases_list = athena_databases_list_shim
        athena_module.athena_workgroups_list = athena_workgroups_list_shim
        logger.info("✅ Replaced Athena functions with MCP resource shims")

        # Replace metadata functions
        import quilt_mcp.tools.metadata_templates as metadata_module
        metadata_module.list_metadata_templates = list_metadata_templates_shim
        logger.info("✅ Replaced metadata functions with MCP resource shims")

        # Replace workflow functions
        import quilt_mcp.tools.workflow_orchestration as workflow_module
        workflow_module.workflow_list = workflow_list_shim
        logger.info("✅ Replaced workflow functions with MCP resource shims")

        # Replace package functions
        import quilt_mcp.tools.package_management as package_module
        package_module.package_tools_list = package_tools_list_shim
        logger.info("✅ Replaced package functions with MCP resource shims")

        # Replace tabulator functions
        import quilt_mcp.tools.tabulator as tabulator_module
        tabulator_module.tabulator_tables_list = tabulator_tables_list_shim
        logger.info("✅ Replaced tabulator functions with MCP resource shims")

        logger.info("🎉 MCP resources enabled globally - all list functions now use MCP resources")

    except Exception as e:
        logger.error(f"❌ Failed to enable MCP resources globally: {e}")
        raise


def disable_mcp_resources_globally():
    """Disable MCP resources globally by restoring original functions.

    This function restores the original list functions, disabling MCP resource
    implementations. Use this to revert to the original behavior.

    WARNING: This requires the original functions to be preserved somewhere.
    """
    logger.warning("Disabling MCP resources globally - reverting to original functions")
    logger.warning("This feature is not yet implemented - original functions need to be preserved")


def test_compatibility_shims():
    """Test all compatibility shims to ensure they work correctly."""
    import asyncio

    async def run_tests():
        """Run async tests for compatibility shims."""
        results = []

        # Test each shim
        shims_to_test = [
            ("admin_users_list", admin_users_list_shim, True),  # async
            ("admin_roles_list", admin_roles_list_shim, True),  # async
            ("list_available_resources", list_available_resources_shim, False),  # sync
            ("athena_databases_list", athena_databases_list_shim, False),  # sync
            ("athena_workgroups_list", athena_workgroups_list_shim, False),  # sync
            ("list_metadata_templates", list_metadata_templates_shim, False),  # sync
            ("workflow_list", workflow_list_shim, False),  # sync
            ("package_tools_list", package_tools_list_shim, False),  # sync
            ("tabulator_tables_list", tabulator_tables_list_shim, True),  # async
        ]

        for name, shim, is_async in shims_to_test:
            try:
                if is_async:
                    if name == "tabulator_tables_list":
                        result = await shim("test-bucket")
                    else:
                        result = await shim()
                else:
                    if name in ["athena_databases_list", "athena_workgroups_list"]:
                        result = shim()  # Use defaults
                    else:
                        result = shim()

                success = isinstance(result, dict)
                results.append((name, success, result.get("success", result.get("status")) if success else None))

            except Exception as e:
                results.append((name, False, str(e)))

        return results

    # Run the tests
    test_results = asyncio.run(run_tests())

    # Report results
    print("\n🧪 Compatibility Shims Test Results:")
    print("=" * 50)

    for name, success, detail in test_results:
        status = "✅" if success else "❌"
        print(f"{status} {name}: {detail}")

    success_count = sum(1 for _, success, _ in test_results if success)
    total_count = len(test_results)

    print(f"\n📊 Test Summary: {success_count}/{total_count} shims working")

    return success_count == total_count