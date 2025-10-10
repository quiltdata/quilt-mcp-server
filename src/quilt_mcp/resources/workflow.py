"""Workflow MCP Resources.

This module implements MCP resources for workflow orchestration functions.
"""

from typing import Dict, Any, List
import logging
from .base import MCPResource

logger = logging.getLogger(__name__)


class WorkflowResource(MCPResource):
    """MCP resource for workflow listing."""

    def __init__(self):
        """Initialize WorkflowResource."""
        super().__init__("workflow://workflows")

    async def list_items(self, **params) -> Dict[str, Any]:
        """List all workflows with their current status.

        Returns:
            Workflow data with summary information for all workflows
        """
        from ..tools.workflow_orchestration import _workflows
        from ..utils import format_error_response

        try:
            workflows_summary = []

            for workflow_id, workflow in _workflows.items():
                summary = {
                    "id": workflow_id,
                    "name": workflow["name"],
                    "status": workflow["status"],
                    "progress": {
                        "completed_steps": workflow["completed_steps"],
                        "total_steps": workflow["total_steps"],
                        "percentage": (
                            round(
                                (workflow["completed_steps"] / workflow["total_steps"]) * 100,
                                1,
                            )
                            if workflow["total_steps"] > 0
                            else 0
                        ),
                    },
                    "created_at": workflow["created_at"],
                    "updated_at": workflow["updated_at"],
                }
                workflows_summary.append(summary)

            # Sort by updated_at (most recent first)
            workflows_summary.sort(key=lambda x: x["updated_at"], reverse=True)

            return {
                "success": True,
                "workflows": workflows_summary,
                "total_workflows": len(workflows_summary),
                "active_workflows": sum(1 for w in workflows_summary if w["status"] in ["created", "in_progress"]),
                "completed_workflows": sum(1 for w in workflows_summary if w["status"] == "completed"),
            }

        except Exception as e:
            logger.error(f"Failed to list workflows: {e}")
            return format_error_response(f"Failed to list workflows: {str(e)}")

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
