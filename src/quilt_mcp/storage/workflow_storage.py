"""Workflow storage interface for local persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class WorkflowStorage(ABC):
    """Abstract storage backend for workflow persistence."""

    @abstractmethod
    def save(self, workflow_id: str, workflow: Dict[str, Any]) -> None:
        """Persist a workflow."""

    @abstractmethod
    def load(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Load a workflow, returning None if missing."""

    @abstractmethod
    def list_all(self) -> List[Dict[str, Any]]:
        """List all workflows."""

    @abstractmethod
    def delete(self, workflow_id: str) -> None:
        """Delete a workflow."""
