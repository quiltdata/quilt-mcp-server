"""Unit tests for workflow service."""

from __future__ import annotations

from quilt_mcp.services.workflow_service import WorkflowService
from quilt_mcp.storage.file_storage import FileBasedWorkflowStorage


def test_workflow_service_crud_and_status(tmp_path):
    storage = FileBasedWorkflowStorage(base_dir=tmp_path)
    service = WorkflowService(storage=storage)

    create_result = service.create_workflow("wf-1", "Test Workflow")
    assert create_result["success"] is True

    add_result = service.add_step("wf-1", "step-1", "First step")
    assert add_result.success is True

    update_result = service.update_step("wf-1", "step-1", "completed")
    assert update_result["success"] is True

    status = service.get_status("wf-1")
    assert status.success is True
    assert status.progress.completed_steps == 1

    listing = service.list_all()
    assert listing.total_workflows == 1


def test_workflow_service_shares_storage(tmp_path):
    storage = FileBasedWorkflowStorage(base_dir=tmp_path)
    service_a = WorkflowService(storage=storage)
    service_b = WorkflowService(storage=storage)

    service_a.create_workflow("wf-1", "Workflow A")

    status_b = service_b.get_status("wf-1")
    assert status_b.success is True

    listing_a = service_a.list_all()
    listing_b = service_b.list_all()

    assert listing_a.total_workflows == 1
    assert listing_b.total_workflows == 1


def test_workflow_service_template_apply(tmp_path):
    storage = FileBasedWorkflowStorage(base_dir=tmp_path)
    service = WorkflowService(storage=storage)

    params = {"source_packages": ["pkg/a", "pkg/b"], "target_package": "agg"}
    result = service.template_apply("cross-package-aggregation", "wf-template", params)

    assert result.success is True
    assert result.workflow["id"] == "wf-template"
    assert len(result.workflow["steps"]) == 5


def test_workflow_create_idempotent(tmp_path):
    """Test that creating the same workflow twice is idempotent."""
    storage = FileBasedWorkflowStorage(base_dir=tmp_path)
    service = WorkflowService(storage=storage)

    # First create
    result1 = service.create_workflow("wf-1", "Test Workflow", description="First")
    assert result1["success"] is True
    assert result1["workflow"]["name"] == "Test Workflow"
    assert "idempotent" not in result1["message"]

    # Second create with same ID - should return existing workflow
    result2 = service.create_workflow("wf-1", "Different Name", description="Second")
    assert result2["success"] is True
    assert result2["workflow"]["name"] == "Test Workflow"  # Original name preserved
    assert "idempotent" in result2["message"]
    assert result2["workflow"]["id"] == result1["workflow"]["id"]


def test_workflow_add_step_idempotent(tmp_path):
    """Test that adding the same step twice is idempotent."""
    storage = FileBasedWorkflowStorage(base_dir=tmp_path)
    service = WorkflowService(storage=storage)

    service.create_workflow("wf-1", "Test Workflow")

    # First add
    result1 = service.add_step("wf-1", "step-1", "First description")
    assert result1.success is True
    assert "idempotent" not in result1.message

    # Second add with same step_id - should return existing step
    result2 = service.add_step("wf-1", "step-1", "Different description")
    assert result2.success is True
    assert "idempotent" in result2.message
    assert result2.step.description == "First description"  # Original description preserved


def test_workflow_template_apply_idempotent(tmp_path):
    """Test that applying the same template twice is idempotent."""
    storage = FileBasedWorkflowStorage(base_dir=tmp_path)
    service = WorkflowService(storage=storage)

    params = {"source_packages": ["pkg/a"], "target_package": "agg"}

    # First template apply
    result1 = service.template_apply("cross-package-aggregation", "wf-1", params)
    assert result1.success is True
    assert len(result1.workflow["steps"]) == 5
    assert "idempotent" not in result1.message

    # Second template apply - should detect existing workflow with steps
    result2 = service.template_apply("cross-package-aggregation", "wf-1", params)
    assert result2.success is True
    assert len(result2.workflow["steps"]) == 5
    assert "idempotent" in result2.message
    assert "already exists with 5 steps" in result2.message


def test_workflow_update_step_not_found_helpful_error(tmp_path):
    """Test that update_step provides helpful error when workflow not found."""
    storage = FileBasedWorkflowStorage(base_dir=tmp_path)
    service = WorkflowService(storage=storage)

    # Create a different workflow so we have suggestions
    service.create_workflow("wf-actual", "Actual Workflow")

    # Try to update step in non-existent workflow
    result = service.update_step("wf-nonexistent", "step-1", "completed")
    assert result["success"] is False
    assert "wf-nonexistent" in result["error"]
    assert "not found" in result["error"]
    # Should suggest available workflows
    assert "wf-actual" in result["error"] or "Available workflows" in result["error"]
