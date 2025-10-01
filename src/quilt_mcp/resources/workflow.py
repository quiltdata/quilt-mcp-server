"""Workflow MCP Resources.

This module implements MCP resources for workflow orchestration functions.
"""

from typing import Dict, Any, List
from .base import MCPResource


class WorkflowResource(MCPResource):
    """MCP resource for workflow listing."""

    def __init__(self):
        """Initialize WorkflowResource."""
        super().__init__("workflow://workflows")

    async def list_items(self, **params) -> Dict[str, Any]:
        """List workflows.

        Returns:
            Workflow data in original format
        """
        # Import here to avoid circular imports and maintain compatibility
        from ..tools.workflow_orchestration import workflow_list

        # Call the original sync function
        return workflow_list()

    def _extract_items(self, raw_data: Dict[str, Any]) -> List[Any]:
        """Extract workflows list from workflow data."""
        return raw_data.get("workflows", [])

    def _extract_metadata(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from workflow data."""
        metadata = super()._extract_metadata(raw_data)

        # Add workflow-specific metadata
        if "total_workflows" in raw_data:
            metadata["total_workflows"] = raw_data["total_workflows"]
        if "active_workflows" in raw_data:
            metadata["active_workflows"] = raw_data["active_workflows"]
        if "completed_workflows" in raw_data:
            metadata["completed_workflows"] = raw_data["completed_workflows"]

        return metadata
