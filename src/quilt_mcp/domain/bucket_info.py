"""Bucket_Info domain object for backend-agnostic bucket representation.

This module defines the Bucket_Info dataclass that represents Quilt bucket metadata
in a way that's independent of the underlying backend (quilt3 library or Platform GraphQL).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Bucket_Info:
    """Backend-agnostic bucket information.

    This dataclass represents bucket metadata consistently across different backends,
    allowing MCP tools to work with Quilt concepts rather than backend-specific types.

    Attributes:
        name: S3 bucket name
        region: AWS region where the bucket is located
        access_level: Access level or permissions for the bucket
        created_date: ISO 8601 formatted creation date (optional)
    """

    name: str
    region: str
    access_level: str
    created_date: Optional[str]

    def __post_init__(self) -> None:
        """Validate required fields after initialization."""
        # All validation is handled by dataclass field requirements
        # Optional validation logic could be added here if needed
        pass

    def __hash__(self) -> int:
        """Custom hash implementation for hashable dataclass."""
        return hash((
            self.name,
            self.region,
            self.access_level,
            self.created_date
        ))
