"""File-based workflow storage for local development."""

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
    """Persist workflows to local disk in a flat directory."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self._base_dir = base_dir or _default_base_dir()
        self._lock = threading.Lock()

    def save(self, workflow_id: str, workflow: Dict[str, Any]) -> None:
        path = self._workflow_path(workflow_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(workflow, indent=2, sort_keys=True)

        with self._lock:
            with tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent, encoding="utf-8") as tmp:
                tmp.write(payload)
                tmp_path = Path(tmp.name)
            tmp_path.replace(path)

    def load(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        path = self._workflow_path(workflow_id)
        if not path.exists():
            return None
        with self._lock:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)  # type: ignore[no-any-return]

    def list_all(self) -> List[Dict[str, Any]]:
        if not self._base_dir.exists():
            return []
        workflows: List[Dict[str, Any]] = []
        with self._lock:
            for path in self._base_dir.glob("*.json"):
                try:
                    with path.open("r", encoding="utf-8") as handle:
                        workflows.append(json.load(handle))
                except json.JSONDecodeError:
                    continue
        return workflows

    def delete(self, workflow_id: str) -> None:
        path = self._workflow_path(workflow_id)
        with self._lock:
            if path.exists():
                path.unlink()

    def _workflow_path(self, workflow_id: str) -> Path:
        if not workflow_id or not workflow_id.strip():
            raise ValueError("workflow_id is required")
        filename = f"{quote(workflow_id.strip(), safe='')}.json"
        candidate = self._base_dir / filename
        resolved_base = self._base_dir.resolve()
        resolved_candidate = candidate.resolve()
        if not resolved_candidate.is_relative_to(resolved_base):
            raise ValueError("Invalid workflow path")
        return candidate
