"""
Quilt3_Backend implementation.

This module provides the concrete implementation of QuiltOps using the quilt3 library.
All quilt3 operations are wrapped with proper error handling and transformation to domain objects.

The implementation is organized into modular components:
- quilt3_backend_base: Core initialization and shared utilities
- quilt3_backend_packages: Package operations
- quilt3_backend_content: Content operations
- quilt3_backend_buckets: Bucket operations
- quilt3_backend_session: Session, config, and AWS operations
"""

import logging
from typing import List, Dict, Any, Optional

from quilt_mcp.ops.quilt_ops import QuiltOps
from quilt_mcp.ops.exceptions import NotFoundError
from quilt_mcp.domain.package_info import Package_Info
from quilt_mcp.domain.content_info import Content_Info
from quilt_mcp.domain.bucket_info import Bucket_Info
from quilt_mcp.backends.quilt3_backend_base import Quilt3_Backend_Base, quilt3, requests, boto3
from quilt_mcp.backends.quilt3_backend_packages import Quilt3_Backend_Packages
from quilt_mcp.backends.quilt3_backend_content import Quilt3_Backend_Content
from quilt_mcp.backends.quilt3_backend_buckets import Quilt3_Backend_Buckets
from quilt_mcp.backends.quilt3_backend_session import Quilt3_Backend_Session
from quilt_mcp.backends.quilt3_backend_admin import Quilt3_Backend_Admin
from quilt_mcp.ops.tabulator_mixin import TabulatorMixin

logger = logging.getLogger(__name__)


class Quilt3_Backend(
    Quilt3_Backend_Session,
    TabulatorMixin,
    Quilt3_Backend_Buckets,
    Quilt3_Backend_Content,
    Quilt3_Backend_Packages,
    Quilt3_Backend_Admin,
    Quilt3_Backend_Base,
    QuiltOps,
):
    """Backend implementation using quilt3 library.

    This class composes multiple mixins to provide the complete QuiltOps interface:
    - Session: Auth status, catalog config, GraphQL, and boto3 access
    - TabulatorMixin: Tabulator table management operations
    - Base: Core initialization and shared utilities
    - Packages: Package search, retrieval, and transformations
    - Content: Content browsing and URL generation
    - Buckets: Bucket listing and transformations
    - Admin: User management, role management, and SSO configuration

    The mixin order is important for proper method resolution order (MRO).
    Session is first to ensure execute_graphql_query() is found before TabulatorMixin's stub.
    """

    @property
    def admin(self):
        """Access to admin operations.

        Provides access to administrative operations including user management,
        role management, and SSO configuration through the AdminOps interface.

        Returns:
            AdminOps interface (self, since this class inherits from Quilt3_Backend_Admin)

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When admin functionality is not available or fails to initialize
            PermissionError: When user lacks admin privileges
        """
        return self

    pass
