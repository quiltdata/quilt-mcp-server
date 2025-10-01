"""Athena MCP Resources.

This module implements MCP resources for Athena-related functions like
database and workgroup discovery.
"""

import logging
import os
from typing import Dict, Any, List
from .base import MCPResource
from ..services.athena_service import AthenaQueryService
from ..utils import format_error_response

logger = logging.getLogger(__name__)


class AthenaDatabasesResource(MCPResource):
    """MCP resource for Athena databases listing."""

    def __init__(self):
        """Initialize AthenaDatabasesResource."""
        super().__init__("athena://databases")

    async def list_items(self, catalog_name: str = "AwsDataCatalog", service: Any = None, **params) -> Dict[str, Any]:
        """List Athena databases.

        Args:
            catalog_name: AWS Glue Data Catalog name
            service: Optional service instance for dependency injection

        Returns:
            Athena databases data in original format
        """
        try:
            service = service or AthenaQueryService()
            return service.discover_databases(catalog_name)
        except Exception as e:
            logger.error(f"Failed to list databases: {e}")
            return format_error_response(f"Failed to list databases: {str(e)}")

    def _extract_items(self, raw_data: Dict[str, Any]) -> List[Any]:
        """Extract databases list from Athena databases data."""
        return raw_data.get("databases", [])

    def _extract_metadata(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from Athena databases data."""
        metadata = super()._extract_metadata(raw_data)

        # Add Athena-specific metadata
        if "catalog_name" in raw_data:
            metadata["catalog_name"] = raw_data["catalog_name"]

        return metadata


class AthenaWorkgroupsResource(MCPResource):
    """MCP resource for Athena workgroups listing."""

    def __init__(self):
        """Initialize AthenaWorkgroupsResource."""
        super().__init__("athena://workgroups")

    async def list_items(self, use_quilt_auth: bool = True, service: Any = None, **params) -> Dict[str, Any]:
        """List Athena workgroups.

        Args:
            use_quilt_auth: Whether to use Quilt authentication
            service: Optional service instance for dependency injection

        Returns:
            Athena workgroups data in original format
        """
        try:
            # Use consolidated AthenaQueryService for consistent authentication patterns
            service = service or AthenaQueryService(use_quilt_auth=use_quilt_auth)

            # Get workgroups using the service's consolidated method
            workgroups = service.list_workgroups()

            # Determine region for response metadata
            region = "us-east-1" if use_quilt_auth else os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

            result = {
                "success": True,
                "workgroups": workgroups,
                "region": region,
                "count": len(workgroups),
            }

            # Enhance with table formatting for better readability
            from ..formatting import enhance_result_with_table_format

            result = enhance_result_with_table_format(result)

            return result

        except Exception as e:
            logger.error(f"Failed to list workgroups: {e}")
            return format_error_response(f"Failed to list workgroups: {str(e)}")

    def _extract_items(self, raw_data: Dict[str, Any]) -> List[Any]:
        """Extract workgroups list from Athena workgroups data."""
        return raw_data.get("workgroups", [])

    def _extract_metadata(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from Athena workgroups data."""
        metadata = super()._extract_metadata(raw_data)

        # Add Athena-specific metadata
        if "use_quilt_auth" in raw_data:
            metadata["use_quilt_auth"] = raw_data["use_quilt_auth"]

        return metadata
