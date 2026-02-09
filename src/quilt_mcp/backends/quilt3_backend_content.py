"""
Quilt3_Backend content operations mixin.

This module provides content/object-related operations including browsing,
URL generation, and transformation for the Quilt3_Backend implementation.

This mixin uses self.quilt3 which is provided by Quilt3_Backend_Base.
"""

import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from quilt_mcp.ops.exceptions import BackendError, ValidationError, NotFoundError
from quilt_mcp.domain.content_info import Content_Info

if TYPE_CHECKING:
    from types import ModuleType

logger = logging.getLogger(__name__)


class Quilt3_Backend_Content:
    """Mixin for content-related operations."""

    # Type hints for attributes and methods provided by Quilt3_Backend_Base
    if TYPE_CHECKING:
        quilt3: "ModuleType"

        def _normalize_size(self, size: Any) -> Optional[int]: ...
        def _normalize_datetime(self, dt: Any) -> Optional[str]: ...

    def browse_content(self, package_name: str, registry: str, path: str = "") -> List[Content_Info]:
        """Browse contents of a package at the specified path.

        Args:
            package_name: Name of the package
            registry: Registry containing the package
            path: Path within the package to browse (default: root)

        Returns:
            List of Content_Info objects representing the contents

        Raises:
            BackendError: If content browsing fails
        """
        try:
            logger.debug(f"Browsing content for: {package_name} at path: {path}")
            package = self.quilt3.Package.browse(package_name, registry=registry)

            # Browse the specific path if provided
            if path:
                package = package[path]

            result = [self._transform_content(key, entry) for key, entry in package.walk()]
            logger.debug(f"Found {len(result)} content items")
            return result
        except Exception as e:
            raise BackendError(
                f"Quilt3 backend browse_content failed: {str(e)}",
                context={'package_name': package_name, 'registry': registry, 'path': path},
            )

    def get_content_url(self, package_name: str, registry: str, path: str) -> str:
        """Get download URL for specific content.

        Args:
            package_name: Name of the package
            registry: Registry containing the package
            path: Path to the content within the package

        Returns:
            Download URL for the content

        Raises:
            BackendError: If URL generation fails
        """
        try:
            logger.debug(f"Getting content URL for: {package_name}/{path}")
            package = self.quilt3.Package.browse(package_name, registry=registry)
            url = package.get_url(path)
            logger.debug(f"Generated URL for: {package_name}/{path}")
            return str(url)
        except Exception as e:
            raise BackendError(
                f"Quilt3 backend get_content_url failed: {str(e)}",
                context={'package_name': package_name, 'registry': registry, 'path': path},
            )

    def _transform_content(self, key: str, quilt3_entry) -> Content_Info:
        """Transform quilt3 content entry to domain Content_Info.

        Args:
            key: The path/key for this content entry
            quilt3_entry: Quilt3 content entry object

        Returns:
            Content_Info domain object

        Raises:
            BackendError: If transformation fails
        """
        try:
            logger.debug(f"Transforming content entry: {key}")

            # Validate required fields
            self._validate_content_fields(key, quilt3_entry)

            # Determine content type
            content_type = self._determine_content_type(quilt3_entry)

            # Handle optional fields with normalization
            size = self._normalize_size(getattr(quilt3_entry, 'size', None))
            modified_date = self._normalize_datetime(getattr(quilt3_entry, 'modified', None))
            meta = getattr(quilt3_entry, 'meta', None)

            content_info = Content_Info(
                path=key,
                size=size,
                type=content_type,
                modified_date=modified_date,
                download_url=None,  # URL not provided in transformation, use get_content_url
                meta=meta,  # Entry-level metadata
            )

            logger.debug(f"Successfully transformed content: {content_info.path} ({content_info.type})")
            return content_info

        except BackendError:
            raise
        except Exception as e:
            error_context = {
                'entry_key': key,
                'entry_type': type(quilt3_entry).__name__,
                'available_attributes': [attr for attr in dir(quilt3_entry) if not attr.startswith('_')],
            }
            logger.error(f"Content transformation failed: {str(e)}", extra={'context': error_context})
            raise BackendError(f"Quilt3 backend content transformation failed: {str(e)}", context=error_context)

    def _validate_content_fields(self, key: str, quilt3_entry) -> None:
        """Validate required fields for content transformation.

        Args:
            key: The path/key for this content entry
            quilt3_entry: Content entry object to validate

        Raises:
            BackendError: If required fields are missing
        """
        if not key or key == "":
            raise BackendError("Quilt3 backend content transformation failed: invalid content entry: empty key")

    def _determine_content_type(self, quilt3_entry) -> str:
        """Determine content type from quilt3 entry.

        Args:
            quilt3_entry: Content entry object (PackageEntry)

        Returns:
            Always "file" - packages only contain files, not directories
        """
        # Packages only contain files (PackageEntry objects), never directories
        return "file"
