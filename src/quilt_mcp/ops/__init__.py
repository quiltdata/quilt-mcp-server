"""QuiltOps abstraction layer for backend-agnostic Quilt operations.

This module provides the core abstraction layer that allows MCP tools to work with
Quilt concepts without being tied to specific backend implementations (quilt3 or Platform GraphQL).
"""

from .exceptions import AuthenticationError, BackendError, ValidationError, NotFoundError, PermissionError
from .quilt_ops import QuiltOps

__all__ = ["AuthenticationError", "BackendError", "ValidationError", "NotFoundError", "PermissionError", "QuiltOps"]
