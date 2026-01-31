"""
Quilt3_Backend content operations mixin.

This module provides content/object-related operations including browsing,
URL generation, and transformation for the Quilt3_Backend implementation.
"""

import logging
from typing import List, Dict, Any, Optional

try:
    import quilt3
except ImportError:
    quilt3 = None

from quilt_mcp.ops.exceptions import BackendError, ValidationError, NotFoundError
from quilt_mcp.domain.content_info import Content_Info

logger = logging.getLogger(__name__)


class Quilt3_Backend_Content:
    """Mixin for content-related operations."""

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
            package = quilt3.Package.browse(package_name, registry=registry)

            # Browse the specific path if provided
            if path:
                package = package[path]

            result = [self._transform_content(entry) for entry in package]
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
            package = quilt3.Package.browse(package_name, registry=registry)
            url = package.get_url(path)
            logger.debug(f"Generated URL for: {package_name}/{path}")
            return url
        except Exception as e:
            raise BackendError(
                f"Quilt3 backend get_content_url failed: {str(e)}",
                context={'package_name': package_name, 'registry': registry, 'path': path},
            )

    def _transform_content(self, quilt3_entry) -> Content_Info:
        """Transform quilt3 content entry to domain Content_Info.

        Args:
            quilt3_entry: Quilt3 content entry object

        Returns:
            Content_Info domain object

        Raises:
            BackendError: If transformation fails
        """
        try:
            logger.debug(f"Transforming content entry: {getattr(quilt3_entry, 'name', 'unknown')}")

            # Validate required fields
            self._validate_content_fields(quilt3_entry)

            # Determine content type
            content_type = self._determine_content_type(quilt3_entry)

            # Handle optional fields with normalization
            size = self._normalize_size(getattr(quilt3_entry, 'size', None))
            modified_date = self._normalize_datetime(getattr(quilt3_entry, 'modified', None))

            content_info = Content_Info(
                path=quilt3_entry.name,
                size=size,
                type=content_type,
                modified_date=modified_date,
                download_url=None,  # URL not provided in transformation, use get_content_url
            )

            logger.debug(f"Successfully transformed content: {content_info.path} ({content_info.type})")
            return content_info

        except BackendError:
            raise
        except Exception as e:
            error_context = {
                'entry_name': getattr(quilt3_entry, 'name', 'unknown'),
                'entry_type': type(quilt3_entry).__name__,
                'available_attributes': [attr for attr in dir(quilt3_entry) if not attr.startswith('_')]
            }
            logger.error(f"Content transformation failed: {str(e)}", extra={'context': error_context})
            raise BackendError(
                f"Quilt3 backend content transformation failed: {str(e)}", 
                context=error_context
            )

    def _validate_content_fields(self, quilt3_entry) -> None:
        """Validate required fields for content transformation.

        Args:
            quilt3_entry: Content entry object to validate

        Raises:
            BackendError: If required fields are missing
        """
        if not hasattr(quilt3_entry, 'name') or quilt3_entry.name is None:
            raise BackendError("Quilt3 backend content transformation failed: invalid content entry: missing name")
        if quilt3_entry.name == "":
            raise BackendError("Quilt3 backend content transformation failed: invalid content entry: empty name")

    def _determine_content_type(self, quilt3_entry) -> str:
        """Determine content type (file or directory) from quilt3 entry.

        Args:
            quilt3_entry: Content entry object

        Returns:
            "file" or "directory"
        """
        try:
            return "directory" if getattr(quilt3_entry, 'is_dir', False) else "file"
        except (AttributeError, Exception):
            # If we can't access is_dir property, default to file
            return "file"

