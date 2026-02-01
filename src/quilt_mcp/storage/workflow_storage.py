"""Workflow storage interface for tenant-isolated persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class WorkflowStorage(ABC):
    """Abstract storage backend for workflow persistence."""

    @abstractmethod
    def save(self, tenant_id: str, workflow_id: str, workflow: Dict[str, Any]) -> None:
        """Persist a workflow for the given tenant."""

    @abstractmethod
    def load(self, tenant_id: str, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Load a workflow for the given tenant, returning None if missing."""

    @abstractmethod
    def list_all(self, tenant_id: str) -> List[Dict[str, Any]]:
        """List all workflows for a tenant."""

    @abstractmethod
    def delete(self, tenant_id: str, workflow_id: str) -> None:
        """Delete a workflow for a tenant."""
