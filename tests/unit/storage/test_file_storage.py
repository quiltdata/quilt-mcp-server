"""Tests for file-based workflow storage."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from quilt_mcp.storage.file_storage import FileBasedWorkflowStorage


def test_file_storage_tenant_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("QUILT_WORKFLOW_DIR", str(tmp_path))
    storage = FileBasedWorkflowStorage()

    storage.save("tenant-a", "wf-1", {"id": "wf-1", "tenant": "tenant-a"})
    storage.save("tenant-b", "wf-2", {"id": "wf-2", "tenant": "tenant-b"})

    tenant_a_dir = tmp_path / "tenant-a"
    tenant_b_dir = tmp_path / "tenant-b"

    assert tenant_a_dir.exists()
    assert tenant_b_dir.exists()
    assert len(list(tenant_a_dir.glob("*.json"))) == 1
    assert len(list(tenant_b_dir.glob("*.json"))) == 1

    tenant_a_workflows = storage.list_all("tenant-a")
    tenant_b_workflows = storage.list_all("tenant-b")

    assert {wf["id"] for wf in tenant_a_workflows} == {"wf-1"}
    assert {wf["id"] for wf in tenant_b_workflows} == {"wf-2"}


def test_file_storage_crud_operations(tmp_path, monkeypatch):
    monkeypatch.setenv("QUILT_WORKFLOW_DIR", str(tmp_path))
    storage = FileBasedWorkflowStorage()

    workflow = {"id": "wf-1", "status": "created"}
    storage.save("tenant-a", "wf-1", workflow)

    loaded = storage.load("tenant-a", "wf-1")
    assert loaded == workflow

    storage.delete("tenant-a", "wf-1")
    assert storage.load("tenant-a", "wf-1") is None


def test_file_storage_persists_across_instances(tmp_path, monkeypatch):
    monkeypatch.setenv("QUILT_WORKFLOW_DIR", str(tmp_path))
    storage = FileBasedWorkflowStorage()
    storage.save("tenant-a", "wf-1", {"id": "wf-1", "status": "created"})

    new_storage = FileBasedWorkflowStorage()
    loaded = new_storage.load("tenant-a", "wf-1")
    assert loaded is not None
    assert loaded["id"] == "wf-1"


def test_file_storage_handles_concurrent_saves(tmp_path, monkeypatch):
    monkeypatch.setenv("QUILT_WORKFLOW_DIR", str(tmp_path))
    storage = FileBasedWorkflowStorage()

    def _save(index: int) -> None:
        storage.save("tenant-a", f"wf-{index}", {"id": f"wf-{index}"})

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(_save, range(8)))

    workflows = storage.list_all("tenant-a")
    assert {wf["id"] for wf in workflows} == {f"wf-{i}" for i in range(8)}


def test_file_storage_sanitizes_tenant_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("QUILT_WORKFLOW_DIR", str(tmp_path))
    storage = FileBasedWorkflowStorage()

    storage.save("../tenant", "../workflow", {"id": "wf-unsafe"})

    # Ensure all files remain within the base directory
    for path in tmp_path.rglob("*"):
        assert path.resolve().is_relative_to(tmp_path.resolve())
