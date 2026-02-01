"""File-based workflow storage with tenant isolation."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from quilt_mcp.storage.workflow_storage import WorkflowStorage


def _default_base_dir() -> Path:
    base_dir = os.getenv("QUILT_WORKFLOW_DIR") or "~/.quilt/workflows"
    return Path(base_dir).expanduser()


class FileBasedWorkflowStorage(WorkflowStorage):
    """Persist workflows to tenant-specific directories on disk."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self._base_dir = base_dir or _default_base_dir()
        self._lock = threading.Lock()

    def save(self, tenant_id: str, workflow_id: str, workflow: Dict[str, Any]) -> None:
        path = self._workflow_path(tenant_id, workflow_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(workflow, indent=2, sort_keys=True)

        with self._lock:
            with tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent, encoding="utf-8") as tmp:
                tmp.write(payload)
                tmp_path = Path(tmp.name)
            tmp_path.replace(path)

    def load(self, tenant_id: str, workflow_id: str) -> Optional[Dict[str, Any]]:
        path = self._workflow_path(tenant_id, workflow_id)
        if not path.exists():
            return None
        with self._lock:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)  # type: ignore[no-any-return]

    def list_all(self, tenant_id: str) -> List[Dict[str, Any]]:
        tenant_dir = self._tenant_dir(tenant_id)
        if not tenant_dir.exists():
            return []
        workflows: List[Dict[str, Any]] = []
        with self._lock:
            for path in tenant_dir.glob("*.json"):
                try:
                    with path.open("r", encoding="utf-8") as handle:
                        workflows.append(json.load(handle))
                except json.JSONDecodeError:
                    continue
        return workflows

    def delete(self, tenant_id: str, workflow_id: str) -> None:
        path = self._workflow_path(tenant_id, workflow_id)
        with self._lock:
            if path.exists():
                path.unlink()

    def _tenant_dir(self, tenant_id: str) -> Path:
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")
        tenant_segment = quote(tenant_id.strip(), safe="")
        return self._base_dir / tenant_segment

    def _workflow_path(self, tenant_id: str, workflow_id: str) -> Path:
        if not workflow_id or not workflow_id.strip():
            raise ValueError("workflow_id is required")
        tenant_dir = self._tenant_dir(tenant_id)
        filename = f"{quote(workflow_id.strip(), safe='')}.json"
        candidate = tenant_dir / filename
        resolved_base = tenant_dir.resolve()
        resolved_candidate = candidate.resolve()
        if not resolved_candidate.is_relative_to(resolved_base):
            raise ValueError("Invalid workflow path")
        return candidate
