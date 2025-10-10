"""Backend abstraction layer for Quilt catalog operations.

This module provides a protocol-based abstraction layer that enables multiple
backend implementations (quilt3 SDK, GraphQL) without requiring tool refactoring.
Tools use the factory function `get_backend()` to obtain a backend instance that
implements the `QuiltBackend` protocol.

Example:
    from quilt_mcp.backends import get_backend

    backend = get_backend()  # Returns Quilt3Backend by default
    packages = backend.list_packages(registry="s3://my-bucket")
"""

from quilt_mcp.backends.protocol import QuiltBackend
from quilt_mcp.backends.factory import get_backend
from quilt_mcp.backends.quilt3_backend import Quilt3Backend

__all__ = ["QuiltBackend", "get_backend", "Quilt3Backend"]
