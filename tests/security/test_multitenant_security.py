"""Security tests for multitenant isolation."""

from __future__ import annotations

from quilt_mcp.services.workflow_service import WorkflowService
from quilt_mcp.storage.file_storage import FileBasedWorkflowStorage


def test_cross_tenant_workflow_access_is_denied(tmp_path):
    storage = FileBasedWorkflowStorage(base_dir=tmp_path)
    tenant_a = WorkflowService(tenant_id="tenant-a", storage=storage)
    tenant_b = WorkflowService(tenant_id="tenant-b", storage=storage)

    tenant_a.create_workflow("wf-secure", "Tenant A")

    response = tenant_b.get_status("wf-secure")
    assert response.error == "Workflow 'wf-secure' not found"


def test_tenant_id_spoofing_does_not_leak_data(tmp_path):
    storage = FileBasedWorkflowStorage(base_dir=tmp_path)
    tenant_a = WorkflowService(tenant_id="tenant-a", storage=storage)
    tenant_a.create_workflow("wf-1", "Tenant A")

    spoofed = WorkflowService(tenant_id="tenant-a/../tenant-a", storage=storage)
    response = spoofed.get_status("wf-1")
    assert response.error == "Workflow 'wf-1' not found"
