"""Integration tests for tenant-isolated workflow storage."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from quilt_mcp.services.workflow_service import WorkflowService
from quilt_mcp.storage.file_storage import FileBasedWorkflowStorage


@pytest.mark.integration
def test_workflow_tenant_isolation(tmp_path):
    storage = FileBasedWorkflowStorage(base_dir=tmp_path)
    tenant_a = WorkflowService(tenant_id="tenant-a", storage=storage)
    tenant_b = WorkflowService(tenant_id="tenant-b", storage=storage)

    tenant_a.create_workflow("wf-1", "Tenant A")
    tenant_b.create_workflow("wf-2", "Tenant B")

    assert tenant_a.get_status("wf-1").success is True
    assert tenant_b.get_status("wf-2").success is True
    assert tenant_b.get_status("wf-1").error == "Workflow 'wf-1' not found"


@pytest.mark.integration
def test_workflow_names_dont_collide_across_tenants(tmp_path):
    storage = FileBasedWorkflowStorage(base_dir=tmp_path)
    tenant_a = WorkflowService(tenant_id="tenant-a", storage=storage)
    tenant_b = WorkflowService(tenant_id="tenant-b", storage=storage)

    assert tenant_a.create_workflow("shared", "Tenant A")["success"] is True
    assert tenant_b.create_workflow("shared", "Tenant B")["success"] is True

    assert tenant_a.get_status("shared").workflow["name"] == "Tenant A"
    assert tenant_b.get_status("shared").workflow["name"] == "Tenant B"


@pytest.mark.integration
def test_workflow_deletion_is_tenant_scoped(tmp_path):
    storage = FileBasedWorkflowStorage(base_dir=tmp_path)
    tenant_a = WorkflowService(tenant_id="tenant-a", storage=storage)
    tenant_b = WorkflowService(tenant_id="tenant-b", storage=storage)

    tenant_a.create_workflow("wf-a", "Tenant A")
    tenant_b.create_workflow("wf-b", "Tenant B")

    storage.delete("tenant-a", "wf-a")

    assert tenant_a.get_status("wf-a").error == "Workflow 'wf-a' not found"
    assert tenant_b.get_status("wf-b").success is True


@pytest.mark.integration
def test_workflow_persistence_across_restarts(tmp_path):
    storage = FileBasedWorkflowStorage(base_dir=tmp_path)
    tenant_a = WorkflowService(tenant_id="tenant-a", storage=storage)

    tenant_a.create_workflow("wf-1", "Persistent")

    new_storage = FileBasedWorkflowStorage(base_dir=tmp_path)
    tenant_a_reloaded = WorkflowService(tenant_id="tenant-a", storage=new_storage)

    status = tenant_a_reloaded.get_status("wf-1")
    assert status.success is True
    assert status.workflow["name"] == "Persistent"


@pytest.mark.integration
def test_workflow_concurrent_access(tmp_path):
    storage = FileBasedWorkflowStorage(base_dir=tmp_path)

    def _create_workflow(index: int) -> None:
        service = WorkflowService(tenant_id=f"tenant-{index % 3}", storage=storage)
        service.create_workflow(f"wf-{index}", f"Workflow {index}")

    with ThreadPoolExecutor(max_workers=6) as executor:
        list(executor.map(_create_workflow, range(12)))

    service_a = WorkflowService(tenant_id="tenant-0", storage=storage)
    service_b = WorkflowService(tenant_id="tenant-1", storage=storage)

    assert service_a.list_all().total_workflows > 0
    assert service_b.list_all().total_workflows > 0
