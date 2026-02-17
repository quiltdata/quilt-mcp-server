"""Protocol contracts for backend dependencies used by admin ops."""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol


class AdminBackendProtocol(Protocol):
    """Minimal backend surface required by Platform_Admin_Ops."""

    def execute_graphql_query(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        registry: Optional[str] = None,
    ) -> Dict[str, Any]: ...
