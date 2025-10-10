"""Backend factory for selecting appropriate Quilt backend implementation.

This module provides the factory function that returns backend instances based
on environment configuration. The factory enables backend switching without
code changes through the QUILT_BACKEND environment variable.
"""

import os
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quilt_mcp.backends.protocol import QuiltBackend

logger = logging.getLogger(__name__)


def get_backend() -> "QuiltBackend":
    """Get backend instance based on environment configuration.

    Configuration:
        QUILT_BACKEND: Backend type selection
            - "quilt3" (default): Use quilt3 SDK backend
            - "graphql": Use GraphQL-only backend (future)

    Returns:
        Backend instance implementing QuiltBackend protocol

    Raises:
        ValueError: Unknown backend type requested
        ImportError: Backend implementation not available

    Example:
        >>> backend = get_backend()  # Returns Quilt3Backend by default
        >>> packages = backend.list_packages(registry="s3://my-bucket")
    """
    backend_type = os.getenv("QUILT_BACKEND", "quilt3").lower()

    logger.info(f"Selecting Quilt backend: {backend_type}")

    if backend_type == "quilt3":
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        return Quilt3Backend()
    elif backend_type == "graphql":
        raise NotImplementedError(
            "GraphQL backend not yet implemented. Set QUILT_BACKEND=quilt3 or leave unset for default."
        )
    else:
        raise ValueError(f"Unknown backend type: {backend_type}. Valid options are: 'quilt3', 'graphql'")
