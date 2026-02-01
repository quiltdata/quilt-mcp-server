"""Behavioral tests for the workflow orchestration toolset."""

from __future__ import annotations

import pytest

from quilt_mcp.tools import workflow_orchestration as wo
from quilt_mcp.context.propagation import reset_current_context, set_current_context
from quilt_mcp.context.request_context import RequestContext
from quilt_mcp.services.workflow_service import WorkflowService
from quilt_mcp.storage.file_storage import FileBasedWorkflowStorage


@pytest.fixture(autouse=True)
def workflow_context(tmp_path):
    """Ensure workflow context uses isolated storage per test."""
    storage = FileBasedWorkflowStorage(base_dir=tmp_path)
    service = WorkflowService(tenant_id="tenant-a", storage=storage)
    context = RequestContext(
        request_id="req-1",
        tenant_id="tenant-a",
        user_id="user-1",
        auth_service=object(),
        permission_service=object(),
        workflow_service=service,
    )
    token = set_current_context(context)
    try:
        yield
    finally:
        reset_current_context(token)


def test_workflow_create_rejects_blank_identifier():
    """Creating a workflow should fail when the identifier is blank."""

    result = wo.workflow_create("   ", "Data pipeline")

    assert result["success"] is False
    assert "Workflow ID cannot be empty" in result["error"]


def test_workflow_progression_updates_status_and_next_steps():
    """Lifecycle updates should track progress and completion accurately."""

    create_result = wo.workflow_create("wf-001", "Test workflow")
    assert create_result["success"] is True

    wo.workflow_add_step("wf-001", "fetch", "Fetch data")
    wo.workflow_add_step("wf-001", "transform", "Transform data", dependencies=["fetch"])

    # Start the first step
    start_result = wo.workflow_update_step("wf-001", "fetch", "in_progress")
    assert start_result["workflow_status"] == "in_progress"

    # Complete both steps
    wo.workflow_update_step("wf-001", "fetch", "completed")
    final_update = wo.workflow_update_step("wf-001", "transform", "completed")

    assert final_update["workflow_status"] == "completed"
    assert final_update["progress"]["percentage"] == 100.0

    status = wo.workflow_get_status(id="wf-001")
    assert status["progress"]["completed_steps"] == 2
    assert status["next_available_steps"] == []


def test_workflow_template_apply_sets_dependencies_and_guidance():
    """Applying a template should create a workflow with sequenced steps."""

    params = {"source_packages": ["pkg/a", "pkg/b"], "target_package": "agg"}
    template_result = wo.workflow_template_apply("cross-package-aggregation", "wf-template", params)

    assert template_result["success"] is True
    workflow = template_result["workflow"]
    assert len(workflow["steps"]) == 5
    assert workflow["steps"][0]["id"] == "discover-packages"

    status = wo.workflow_get_status(id="wf-template")
    assert status["next_available_steps"] == ["discover-packages"]

    # Progress through the first step to unlock downstream dependencies
    wo.workflow_update_step("wf-template", "discover-packages", "completed")
    status_after_step = wo.workflow_get_status(id="wf-template")
    assert "analyze-structure" in status_after_step["next_available_steps"]
