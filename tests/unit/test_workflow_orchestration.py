"""Behavioral tests for the workflow orchestration toolset."""

from __future__ import annotations

import time

import pytest

from quilt_mcp.tools import workflow_orchestration as wo


@pytest.fixture(autouse=True)
def reset_workflows():
    """Ensure workflow registry is isolated between tests."""
    wo._workflows.clear()
    yield
    wo._workflows.clear()


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

    status = wo.workflow_get_status("wf-001")
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

    status = wo.workflow_get_status("wf-template")
    assert status["next_available_steps"] == ["discover-packages"]

    # Progress through the first step to unlock downstream dependencies
    wo.workflow_update_step("wf-template", "discover-packages", "completed")
    status_after_step = wo.workflow_get_status("wf-template")
    assert "analyze-structure" in status_after_step["next_available_steps"]


def test_workflow_list_all_sorts_by_recent_activity():
    """Workflows should be listed in descending order of their last update."""

    wo.workflow_create("wf-old", "Old workflow")
    time.sleep(0.01)
    wo.workflow_create("wf-new", "New workflow")

    listing = wo.workflow_list_all()

    assert listing["success"] is True
    workflow_ids = [wf["id"] for wf in listing["workflows"]]
    assert workflow_ids[0] == "wf-new"
