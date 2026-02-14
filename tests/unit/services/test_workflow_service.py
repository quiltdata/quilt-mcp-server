"""Unit tests for workflow service."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from quilt_mcp.services.workflow_service import WorkflowService
from quilt_mcp.storage.file_storage import FileBasedWorkflowStorage
import quilt_mcp.services.workflow_service as workflow_service_module


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


def test_workflow_create_empty_id_returns_error(tmp_path):
    service = WorkflowService(storage=FileBasedWorkflowStorage(base_dir=tmp_path))
    result = service.create_workflow("", "Name")
    assert result["success"] is False


def test_workflow_add_step_errors_for_missing_workflow_and_invalid_deps(tmp_path):
    service = WorkflowService(storage=FileBasedWorkflowStorage(base_dir=tmp_path))
    missing = service.add_step("wf-missing", "step-1", "desc")
    assert missing.success is False

    service.create_workflow("wf-1", "Workflow")
    invalid = service.add_step("wf-1", "step-2", "desc", dependencies=["nope"])
    assert invalid.success is False
    assert "Invalid dependencies" in invalid.error


def test_workflow_update_step_invalid_status_and_step_not_found(tmp_path):
    service = WorkflowService(storage=FileBasedWorkflowStorage(base_dir=tmp_path))
    service.create_workflow("wf-1", "Workflow")
    service.add_step("wf-1", "step-1", "desc")

    invalid_status = service.update_step("wf-1", "step-1", "bad-status")
    assert invalid_status["success"] is False
    assert "Invalid status" in invalid_status["error"]

    missing_step = service.update_step("wf-1", "step-missing", "completed")
    assert missing_step["success"] is False
    assert "not found" in missing_step["error"]


def test_workflow_status_and_delete_paths(tmp_path):
    service = WorkflowService(storage=FileBasedWorkflowStorage(base_dir=tmp_path))
    service.create_workflow("wf-1", "Workflow")
    service.add_step("wf-1", "s1", "first")
    service.add_step("wf-1", "s2", "second", dependencies=["s1"])

    status_created = service.get_status("wf-1")
    assert status_created.success is True
    assert status_created.next_available_steps == ["s1"]

    service.update_step("wf-1", "s1", "in_progress")
    service.update_step("wf-1", "s1", "completed")
    status_after = service.get_status("wf-1")
    assert "s2" in status_after.next_available_steps

    not_found = service.get_status("wf-missing")
    assert not_found.success is False

    delete_missing = service.delete_workflow("wf-missing")
    assert delete_missing["success"] is False
    delete_ok = service.delete_workflow("wf-1")
    assert delete_ok["success"] is True


def test_workflow_wrappers_dispatch_to_context_service(tmp_path):
    service = WorkflowService(storage=FileBasedWorkflowStorage(base_dir=tmp_path))
    context = SimpleNamespace(workflow_service=service)

    created = workflow_service_module.workflow_create("wf-w", "Name", context=context)
    assert created["success"] is True

    added = workflow_service_module.workflow_add_step("wf-w", "step-1", "desc", context=context)
    assert added.success is True

    updated = workflow_service_module.workflow_update_step("wf-w", "step-1", "completed", context=context)
    assert updated["success"] is True

    status = workflow_service_module.workflow_get_status("wf-w", context=context)
    assert status.success is True
    listing = workflow_service_module.workflow_list_all(context=context)
    assert listing.success is True

    templated = workflow_service_module.workflow_template_apply(
        "data-validation",
        "wf-template-via-wrapper",
        {"packages": ["p1"], "validation_rules": ["r1"]},
        context=context,
    )
    assert templated.success is True

    deleted = workflow_service_module.workflow_delete("wf-w", context=context)
    assert deleted["success"] is True


def test_current_workflow_service_raises_when_unavailable(monkeypatch):
    context = SimpleNamespace(workflow_service=None)

    class _Mode:
        is_multiuser = True

    monkeypatch.setattr(workflow_service_module, "get_mode_config", lambda: _Mode())
    with pytest.raises(Exception, match="Workflows are not available"):
        workflow_service_module._current_workflow_service(context)


def test_template_apply_error_paths(tmp_path, monkeypatch):
    service = WorkflowService(storage=FileBasedWorkflowStorage(base_dir=tmp_path))

    unknown = service.template_apply("unknown-template", "wf-err", {})
    assert unknown.success is False

    monkeypatch.setattr(service, "create_workflow", lambda **kwargs: {"success": False, "error": "boom"})
    create_failed = service.template_apply("cross-package-aggregation", "wf-err2", {})
    assert create_failed.success is False

    service2 = WorkflowService(storage=FileBasedWorkflowStorage(base_dir=tmp_path))
    monkeypatch.setattr(service2, "add_step", lambda **kwargs: {"success": False, "error": "step boom"})
    step_failed = service2.template_apply("cross-package-aggregation", "wf-err3", {})
    assert step_failed.success is False


def test_template_helpers_and_recommendations():
    promo = workflow_service_module._create_promotion_template({})
    assert "staging" in promo["name"]

    analysis = workflow_service_module._create_analysis_template({})
    assert "Longitudinal Analysis" in analysis["name"]

    validation = workflow_service_module._create_validation_template({})
    assert "Data Validation Workflow" == validation["name"]

    rec_created = workflow_service_module._get_workflow_recommendations({"status": "created", "failed_steps": 0})
    rec_in_progress_failed = workflow_service_module._get_workflow_recommendations(
        {"status": "in_progress", "failed_steps": 1}
    )
    rec_completed = workflow_service_module._get_workflow_recommendations({"status": "completed", "failed_steps": 0})
    rec_failed = workflow_service_module._get_workflow_recommendations({"status": "failed", "failed_steps": 2})
    assert rec_created
    assert rec_in_progress_failed
    assert rec_completed
    assert rec_failed
