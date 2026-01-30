"""
QuiltOpsFactory implementation.

This module provides the factory for creating QuiltOps instances with appropriate backend selection.
For Phase 1, this focuses only on quilt3 session detection (no JWT support yet).

Phase 1 Implementation Scope:
- Only supports quilt3 session-based authentication
- Creates Quilt3_Backend instances only
- JWT token support will be added in Phase 2
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

logger = logging.getLogger(__name__)


class QuiltOpsFactory:
    """Factory for creating appropriate QuiltOps backend instances.

    Phase 1 Implementation:
    This factory currently only supports quilt3 session-based authentication.
    JWT token support and Platform_Backend will be added in Phase 2.

    The factory detects available authentication methods and creates the appropriate
    backend instance. In Phase 1, only Quilt3_Backend is supported.
    """

    @staticmethod
    def create() -> QuiltOps:
        """Create QuiltOps instance with appropriate backend.

        Phase 1 Implementation:
        - Only checks for quilt3 sessions
        - Creates Quilt3_Backend instances only
        - JWT token support will be added in Phase 2

        Returns:
            QuiltOps instance with appropriate backend

        Raises:
            AuthenticationError: If no valid authentication is found
        """
        logger.debug("Creating QuiltOps instance - Phase 1 (quilt3 only)")

        # Phase 1: Only check for quilt3 sessions
        # JWT token support will be added in Phase 2

        # Check for quilt3 session
        session_info = QuiltOpsFactory._detect_quilt3_session()
        if session_info is not None:
            logger.info("Found valid quilt3 session, creating Quilt3_Backend")
            return Quilt3_Backend(session_info)

        # No valid authentication found
        logger.warning("No valid authentication found")
        raise AuthenticationError(
            "No valid authentication found. Please provide valid quilt3 session.\n"
            "To authenticate with quilt3, run: quilt3 login\n"
            "For more information, see: https://docs.quiltdata.com/installation-and-setup"
        )

    @staticmethod
    def _detect_quilt3_session() -> Optional[dict]:
        """Detect and validate quilt3 session.

        Returns:
            Session configuration dict if valid, None otherwise
        """
        if quilt3 is None:
            logger.debug("quilt3 library not available")
            return None

        try:
            logger.debug("Checking for quilt3 session")

            # Check if user is logged in
            if not quilt3.logged_in():
                logger.debug("User not logged in to quilt3")
                return None

            # Get session information
            session = quilt3.session.get_session()
            if session:
                logger.debug("Found quilt3 session")
                # Return a dict with session info for the backend
                return {
                    'session': session,
                    'logged_in': True,
                    'registry_url': quilt3.session.get_registry_url() if hasattr(quilt3.session, 'get_registry_url') else None
                }
            else:
                logger.debug("No quilt3 session found")
                return None

        except Exception as e:
            logger.debug(f"Error checking quilt3 session: {e}")
            return None
