"""Tests for file-based workflow storage."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from quilt_mcp.storage.file_storage import FileBasedWorkflowStorage


def test_file_storage_flat_structure(tmp_path, monkeypatch):
    monkeypatch.setenv("QUILT_WORKFLOW_DIR", str(tmp_path))
    storage = FileBasedWorkflowStorage()

    storage.save("wf-1", {"id": "wf-1"})
    storage.save("wf-2", {"id": "wf-2"})

    assert len(list(tmp_path.glob("*.json"))) == 2

    workflows = storage.list_all()
    assert {wf["id"] for wf in workflows} == {"wf-1", "wf-2"}


def test_file_storage_crud_operations(tmp_path, monkeypatch):
    monkeypatch.setenv("QUILT_WORKFLOW_DIR", str(tmp_path))
    storage = FileBasedWorkflowStorage()

    workflow = {"id": "wf-1", "status": "created"}
    storage.save("wf-1", workflow)

    loaded = storage.load("wf-1")
    assert loaded == workflow

    storage.delete("wf-1")
    assert storage.load("wf-1") is None


def test_file_storage_persists_across_instances(tmp_path, monkeypatch):
    monkeypatch.setenv("QUILT_WORKFLOW_DIR", str(tmp_path))
    storage = FileBasedWorkflowStorage()
    storage.save("wf-1", {"id": "wf-1", "status": "created"})

    new_storage = FileBasedWorkflowStorage()
    loaded = new_storage.load("wf-1")
    assert loaded is not None
    assert loaded["id"] == "wf-1"


def test_file_storage_handles_concurrent_saves(tmp_path, monkeypatch):
    monkeypatch.setenv("QUILT_WORKFLOW_DIR", str(tmp_path))
    storage = FileBasedWorkflowStorage()

    def _save(index: int) -> None:
        storage.save(f"wf-{index}", {"id": f"wf-{index}"})

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(_save, range(8)))

    workflows = storage.list_all()
    assert {wf["id"] for wf in workflows} == {f"wf-{i}" for i in range(8)}


def test_file_storage_sanitizes_workflow_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("QUILT_WORKFLOW_DIR", str(tmp_path))
    storage = FileBasedWorkflowStorage()

    storage.save("../workflow", {"id": "wf-unsafe"})

    # Ensure all files remain within the base directory
    for path in tmp_path.rglob("*"):
        assert path.resolve().is_relative_to(tmp_path.resolve())
