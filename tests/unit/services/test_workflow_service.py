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
