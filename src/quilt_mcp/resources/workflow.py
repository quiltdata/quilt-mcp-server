"""Workflow resources for MCP."""

from typing import Dict, Optional

from quilt_mcp.resources.base import MCPResource, ResourceResponse
from quilt_mcp.tools.workflow_orchestration import workflow_list_all, workflow_get_status


class WorkflowsResource(MCPResource):
    """List all workflows."""

    @property
    def uri_scheme(self) -> str:
        return "workflow"

    @property
    def uri_pattern(self) -> str:
        return "workflow://workflows"

    @property
    def name(self) -> str:
        return "Workflows"

    @property
    def description(self) -> str:
        return "List all workflows with their current status"

    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        if uri != self.uri_pattern:
            raise ValueError(f"Invalid URI: {uri}")

        result = await workflow_list_all()

        if not result.get("success"):
            raise Exception(f"Failed to list workflows: {result.get('error', 'Unknown error')}")

        return ResourceResponse(
            uri=uri,
            content={
                "items": result.get("workflows", []),
                "metadata": {
                    "total_count": len(result.get("workflows", [])),
                    "has_more": False,
                },
            },
        )


class WorkflowStatusResource(MCPResource):
    """Get specific workflow status."""

    @property
    def uri_scheme(self) -> str:
        return "workflow"

    @property
    def uri_pattern(self) -> str:
        return "workflow://workflows/{id}"

    @property
    def name(self) -> str:
        return "Workflow Status"

    @property
    def description(self) -> str:
        return "Get current status of a specific workflow"

    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        if not params or "id" not in params:
            raise ValueError("Workflow ID required in URI")

        workflow_id = params["id"]
        result = await workflow_get_status(workflow_id=workflow_id)

        if not result.get("success"):
            raise Exception(f"Failed to get workflow status: {result.get('error', 'Unknown error')}")

        return ResourceResponse(uri=uri, content=result)
