"""Domain objects for the QuiltOps abstraction layer.

This module contains backend-agnostic data structures that represent Quilt concepts
without exposing implementation details from specific backends (quilt3 or Platform GraphQL).
"""

from .package_info import Package_Info
from .content_info import Content_Info
from .bucket_info import Bucket_Info

__all__ = ["Package_Info", "Content_Info", "Bucket_Info"]
