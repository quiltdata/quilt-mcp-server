"""Shared GraphQL HTTP client for Platform backend operations."""

from __future__ import annotations

from typing import Any, Dict, Optional


class PlatformGraphQLClient:
    """Thin HTTP client wrapper for GraphQL execution."""

    def __init__(self, session: Any, endpoint: str, auth_header: str) -> None:
        self._session = session
        self._endpoint = endpoint
        self._auth_header = auth_header

    def execute(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        response = self._session.post(
            self._endpoint,
            json=payload,
            headers={
                "Authorization": self._auth_header,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("GraphQL response was not a JSON object")
        return result
