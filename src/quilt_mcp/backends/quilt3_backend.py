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

# Import external dependencies for test patching compatibility
try:
    import quilt3
    import requests
    import boto3
except ImportError:
    quilt3 = None
    requests = None
    boto3 = None

from quilt_mcp.ops.quilt_ops import QuiltOps
from quilt_mcp.backends.quilt3_backend_base import Quilt3_Backend_Base
from quilt_mcp.backends.quilt3_backend_packages import Quilt3_Backend_Packages
from quilt_mcp.backends.quilt3_backend_content import Quilt3_Backend_Content
from quilt_mcp.backends.quilt3_backend_buckets import Quilt3_Backend_Buckets
from quilt_mcp.backends.quilt3_backend_session import Quilt3_Backend_Session

logger = logging.getLogger(__name__)


class Quilt3_Backend(
    Quilt3_Backend_Session,
    Quilt3_Backend_Buckets,
    Quilt3_Backend_Content,
    Quilt3_Backend_Packages,
    Quilt3_Backend_Base,
    QuiltOps,
):
    """Backend implementation using quilt3 library.

    This class composes multiple mixins to provide the complete QuiltOps interface:
    - Base: Core initialization and shared utilities
    - Packages: Package search, retrieval, and transformations
    - Content: Content browsing and URL generation
    - Buckets: Bucket listing and transformations
    - Session: Auth status, catalog config, GraphQL, and boto3 access

    The mixin order is important for proper method resolution order (MRO).
    """
    pass
