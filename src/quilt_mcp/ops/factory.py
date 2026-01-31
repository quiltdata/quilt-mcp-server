"""
QuiltOpsFactory implementation.

This module provides the factory for creating QuiltOps instances with appropriate backend selection
based on ModeConfig. The factory uses centralized mode configuration to determine which backend
to create, eliminating scattered credential detection logic.
"""

import logging
from typing import Optional

try:
    import quilt3
except ImportError:
    quilt3 = None

from quilt_mcp.ops.quilt_ops import QuiltOps
from quilt_mcp.ops.exceptions import AuthenticationError
from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
from quilt_mcp.backends.platform_backend import Platform_Backend
from quilt_mcp.config import get_mode_config

logger = logging.getLogger(__name__)


class QuiltOpsFactory:
    """Factory for creating appropriate QuiltOps backend instances.

    This factory uses ModeConfig to determine which backend to create based on
    deployment mode configuration. It eliminates scattered credential detection
    logic by centralizing mode decisions.

    - Local mode (QUILT_MULTITENANT_MODE=false): Creates Quilt3_Backend
    - Multitenant mode (QUILT_MULTITENANT_MODE=true): Creates Platform_Backend
    """

    @staticmethod
    def create() -> QuiltOps:
        """Create QuiltOps instance based on mode configuration.

        Uses ModeConfig to determine the appropriate backend type and creates
        the corresponding backend instance. This eliminates the need for
        scattered credential detection logic.

        Returns:
            QuiltOps instance with appropriate backend

        Raises:
            AuthenticationError: If no valid authentication is found for the backend type
        """
        mode_config = get_mode_config()
        logger.debug(f"Creating QuiltOps instance for backend type: {mode_config.backend_type}")

        if mode_config.backend_type == "quilt3":
            # Local development mode - use quilt3 library
            logger.info("Creating Quilt3_Backend for local development mode")
            return Quilt3_Backend()

        elif mode_config.backend_type == "graphql":
            # Multitenant production mode - use Platform GraphQL backend
            logger.info("Creating Platform_Backend for multitenant mode")
            return Platform_Backend()

        else:
            # This should never happen with proper ModeConfig implementation
            raise AuthenticationError(f"Unknown backend type: {mode_config.backend_type}")
