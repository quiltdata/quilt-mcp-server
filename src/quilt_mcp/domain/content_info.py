"""Content_Info domain object for backend-agnostic content representation.

This module defines the Content_Info dataclass that represents Quilt content/file metadata
in a way that's independent of the underlying backend (quilt3 library or Platform GraphQL).
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass(frozen=True)
class Content_Info:
    """Backend-agnostic content information.

    This dataclass represents content metadata consistently across different backends,
    allowing MCP tools to work with Quilt concepts rather than backend-specific types.

    Attributes:
        path: File or directory path within the package
        size: File size in bytes (None for directories or unknown)
        type: Content type ('file' or 'directory')
        modified_date: ISO 8601 formatted modification date (optional)
        download_url: URL for downloading the content (optional)
        meta: Entry-level metadata dictionary (optional)
    """

    path: str
    size: Optional[int]
    type: str
    modified_date: Optional[str]
    download_url: Optional[str]
    meta: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        """Validate required fields after initialization."""
        # Validate path field
        if self.path is None:
            raise TypeError("path field is required and cannot be None")
        if not isinstance(self.path, str):
            raise TypeError("path field must be a string")
        if self.path == "":
            raise ValueError("path field cannot be empty")

        # Validate type field
        if self.type is None:
            raise TypeError("type field is required and cannot be None")
        if not isinstance(self.type, str):
            raise TypeError("type field must be a string")
        if self.type == "":
            raise ValueError("type field cannot be empty")

        # Validate size field (when not None)
        if self.size is not None:
            if not isinstance(self.size, int):
                raise TypeError("size field must be an integer when provided")
            if self.size < 0:
                raise ValueError("size field cannot be negative")

    def __hash__(self) -> int:
        """Custom hash implementation for hashable dataclass."""
        # meta is a dict and not hashable, so we exclude it from hash
        return hash((self.path, self.size, self.type, self.modified_date, self.download_url))
