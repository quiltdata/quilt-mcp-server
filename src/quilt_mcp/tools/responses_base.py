"""Shared base response models used across tool response modules."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel


class DictAccessibleModel(BaseModel):
    """Base model that supports dict-like access for backward compatibility."""

    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            return default

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)


class SuccessResponse(DictAccessibleModel):
    """Base model for successful operations."""

    success: Literal[True] = True


class ErrorResponse(DictAccessibleModel):
    """Base model for error responses."""

    success: Literal[False] = False
    error: str
    cause: Optional[str] = None
    possible_fixes: Optional[list[str]] = None
    suggested_actions: Optional[list[str]] = None
