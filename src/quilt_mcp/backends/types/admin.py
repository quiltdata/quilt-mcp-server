"""Shared admin GraphQL response type aliases."""

from __future__ import annotations

from typing import Any, Dict, TypedDict


class GraphQLResult(TypedDict, total=False):
    data: Dict[str, Any]
    errors: list[Dict[str, Any]]
