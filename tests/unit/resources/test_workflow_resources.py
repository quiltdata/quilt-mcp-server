"""Unit tests for workflow resources."""

import pytest
from unittest.mock import Mock, patch

from quilt_mcp.resources.workflow import (
    WorkflowsResource,
    WorkflowStatusResource,
)


class TestWorkflowsResource:
    """Test WorkflowsResource."""

    @pytest.fixture
    def resource(self):
        return WorkflowsResource()

    @pytest.mark.anyio
    async def test_read_success(self, resource):
        """Test successful workflows list retrieval."""
        mock_result = {
            "success": True,  # Changed from "status" to "success"
            "workflows": [
                {"id": "wf1", "name": "Workflow 1", "status": "running"},
                {"id": "wf2", "name": "Workflow 2", "status": "completed"},
            ],
            "count": 2,
        }

        with patch("quilt_mcp.resources.workflow.workflow_list_all") as mock_tool:
            mock_tool.return_value = mock_result

            response = await resource.read("workflow://workflows")

            assert response.uri == "workflow://workflows"
            assert response.content["items"] == mock_result["workflows"]
            assert response.content["metadata"]["total_count"] == 2

    @pytest.mark.anyio
    async def test_read_failure(self, resource):
        """Test workflows list retrieval failure."""
        mock_result = {"status": "error", "error": "Database error"}

        with patch("quilt_mcp.resources.workflow.workflow_list_all") as mock_tool:
            mock_tool.return_value = mock_result

            with pytest.raises(Exception, match="Failed to list workflows"):
                await resource.read("workflow://workflows")

    @pytest.mark.anyio
    async def test_read_sorts_by_recent_activity(self, resource):
        """Test that workflows are sorted by most recent activity."""
        mock_result = {
            "success": True,
            "workflows": [
                {"id": "wf-new", "name": "New Workflow", "status": "running", "updated_at": "2024-10-20T12:00:00Z"},
                {"id": "wf-old", "name": "Old Workflow", "status": "completed", "updated_at": "2024-10-19T12:00:00Z"},
            ],
            "count": 2,
        }

        with patch("quilt_mcp.resources.workflow.workflow_list_all") as mock_tool:
            mock_tool.return_value = mock_result

            response = await resource.read("workflow://workflows")

            # Verify workflows are in the correct order (newest first)
            workflow_ids = [wf["id"] for wf in response.content["items"]]
            assert workflow_ids[0] == "wf-new"
            assert workflow_ids[1] == "wf-old"


class TestWorkflowStatusResource:
    """Test WorkflowStatusResource (parameterized)."""

    @pytest.fixture
    def resource(self):
        return WorkflowStatusResource()

    @pytest.mark.anyio
    async def test_read_with_params(self, resource):
        """Test reading workflow status with parameters."""
        mock_result = {
            "success": True,  # Changed from "status" to "success"
            "workflow": {
                "id": "wf1",
                "name": "Workflow 1",
                "status": "running",
                "steps": [],
            },
        }

        with patch("quilt_mcp.resources.workflow.workflow_get_status") as mock_tool:
            mock_tool.return_value = mock_result

            params = {"id": "wf1"}
            response = await resource.read("workflow://workflows/wf1", params)

            assert response.uri == "workflow://workflows/wf1"
            assert response.content == mock_result
            mock_tool.assert_called_once_with(workflow_id="wf1")

    @pytest.mark.anyio
    async def test_read_missing_param(self, resource):
        """Test reading without required parameters raises error."""
        with pytest.raises(ValueError, match="Workflow ID required"):
            await resource.read("workflow://workflows/wf1", params=None)

    @pytest.mark.anyio
    async def test_read_failure(self, resource):
        """Test workflow status retrieval failure."""
        mock_result = {"status": "error", "error": "Workflow not found"}

        with patch("quilt_mcp.resources.workflow.workflow_get_status") as mock_tool:
            mock_tool.return_value = mock_result

            params = {"id": "nonexistent"}
            with pytest.raises(Exception, match="Failed to get workflow"):
                await resource.read("workflow://workflows/nonexistent", params)
