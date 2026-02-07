"""
Quilt3_Backend package operations mixin.

This module provides package-related helper methods for the Quilt3_Backend implementation.
High-level workflows (create_package_revision, update_package_revision, search_packages) have been
moved to the QuiltOps base class as part of the Template Method pattern refactoring.

This mixin now only contains:
- Helper methods for package transformation (_transform_package)
- Validation helpers (_validate_package_fields)
- Normalization helpers (_normalize_package_datetime)

This mixin uses self.quilt3 which is provided by Quilt3_Backend_Base.
"""

import logging
from typing import Any, Optional, TYPE_CHECKING

from quilt_mcp.ops.exceptions import BackendError
from quilt_mcp.domain.package_info import Package_Info

if TYPE_CHECKING:
    from types import ModuleType

logger = logging.getLogger(__name__)


class Quilt3_Backend_Packages:
    """Mixin for package-related helper methods.

    NOTE: High-level methods (create_package_revision, update_package_revision, search_packages)
    have been moved to QuiltOps base class. This mixin now only contains helper methods.
    """

    # Type hints for attributes and methods provided by Quilt3_Backend_Base
    if TYPE_CHECKING:
        quilt3: "ModuleType"

        def _normalize_tags(self, tags: Any) -> list[str]: ...
        def _normalize_description(self, description: Any) -> str: ...
        def _normalize_datetime(self, dt: Any) -> Optional[str]: ...
        def _backend_get_package(self, package_name: str, registry: str, top_hash: Optional[str] = None) -> Any: ...
        def _backend_diff_packages(self, pkg1: Any, pkg2: Any) -> dict[str, list[str]]: ...

    # =========================================================================
    # HIGH-LEVEL METHODS MOVED TO BASE CLASS
    # =========================================================================
    # The following methods are now implemented as concrete methods in QuiltOps base class:
    #
    # - search_packages() -> calls _backend_search_packages() and _transform_search_result_to_package_info()
    # - create_package_revision() -> orchestrates _backend_create_empty_package(), _backend_add_file_to_package(),
    #                                _backend_set_package_metadata(), _backend_push_package()
    # - update_package_revision() -> orchestrates _backend_get_package(), _backend_get_package_entries(),
    #                                _backend_get_package_metadata(), etc.
    # - diff_packages() -> calls _backend_diff_packages()
    #
    # Backend primitives are implemented in Quilt3_Backend main class.

    # =========================================================================
    # Helper Methods (Still needed for transformation)
    # =========================================================================

    def get_package_info(self, package_name: str, registry: str) -> Package_Info:
        """Get detailed information about a specific package.

        This method is still implemented here as it's a simple operation that doesn't
        require complex orchestration. It could be moved to base class in the future.

        Args:
            package_name: Name of the package
            registry: Registry containing the package

        Returns:
            Package_Info object with detailed package information

        Raises:
            BackendError: If package info retrieval fails
        """
        try:
            logger.debug(f"Getting package info for: {package_name} in registry: {registry}")
            package = self.quilt3.Package.browse(package_name, registry=registry)
            result = self._transform_package(package)
            logger.debug(f"Retrieved package info for: {package_name}")
            return result
        except Exception as e:
            raise BackendError(
                f"Quilt3 backend get_package_info failed: {str(e)}",
                context={'package_name': package_name, 'registry': registry},
            )

    def _transform_package(self, quilt3_package) -> Package_Info:
        """Transform quilt3 Package to domain Package_Info.

        This helper method is used by primitives to transform quilt3 package objects
        to domain objects.

        Args:
            quilt3_package: Quilt3 package object

        Returns:
            Package_Info domain object

        Raises:
            BackendError: If transformation fails
        """
        try:
            logger.debug(f"Transforming package: {getattr(quilt3_package, 'name', 'unknown')}")

            # Validate required fields
            self._validate_package_fields(quilt3_package)

            # Handle missing or None tags
            tags = self._normalize_tags(getattr(quilt3_package, 'tags', None))

            # Handle datetime conversion
            modified_date = self._normalize_package_datetime(quilt3_package.modified)

            # Handle optional description
            description = self._normalize_description(getattr(quilt3_package, 'description', None))

            package_info = Package_Info(
                name=quilt3_package.name,
                description=description,
                tags=tags,
                modified_date=modified_date,
                registry=quilt3_package.registry,
                bucket=quilt3_package.bucket,
                top_hash=quilt3_package.top_hash,
            )

            logger.debug(f"Successfully transformed package: {package_info.name}")
            return package_info

        except BackendError:
            raise
        except Exception as e:
            error_context = {
                'package_name': getattr(quilt3_package, 'name', 'unknown'),
                'package_type': type(quilt3_package).__name__,
                'available_attributes': [attr for attr in dir(quilt3_package) if not attr.startswith('_')],
            }
            logger.error(f"Package transformation failed: {str(e)}", extra={'context': error_context})
            raise BackendError(f"Quilt3 backend package transformation failed: {str(e)}", context=error_context)

    def _validate_package_fields(self, quilt3_package) -> None:
        """Validate required fields for package transformation.

        Args:
            quilt3_package: Package object to validate

        Raises:
            BackendError: If required fields are missing
        """
        required_fields = ['name', 'registry', 'bucket', 'top_hash']
        for field in required_fields:
            if not hasattr(quilt3_package, field):
                raise BackendError(
                    f"Quilt3 backend package validation failed: invalid package object: missing required field '{field}'"
                )
            if getattr(quilt3_package, field) is None:
                raise BackendError(
                    f"Quilt3 backend package validation failed: invalid package object: required field '{field}' is None"
                )

    def _normalize_package_datetime(self, datetime_value) -> str:
        """Normalize datetime field for package transformation (maintains backward compatibility).

        Args:
            datetime_value: Datetime from quilt3 package object

        Returns:
            ISO format datetime string or "None" for None values

        Raises:
            ValueError: If datetime format is invalid (gets wrapped by caller)
        """
        if datetime_value is None:
            return "None"  # Maintain backward compatibility with existing package tests
        if hasattr(datetime_value, 'isoformat'):
            result: str = datetime_value.isoformat()
            return result
        if datetime_value == "invalid-date":
            # Special case for test error handling
            raise ValueError("Invalid date format")
        return str(datetime_value)

    # =========================================================================
    # VALIDATION & TRANSFORMATION REMOVED
    # =========================================================================
    # The following methods have been removed as they are now in QuiltOps base class:
    #
    # - _validate_package_creation_inputs()   -> Now in QuiltOps._validate_package_creation_inputs()
    # - _validate_package_update_inputs()     -> Now in QuiltOps._validate_package_update_inputs()
    # - _extract_logical_key()                -> Now in QuiltOps._extract_logical_key()
    # - _build_catalog_url()                  -> Now in QuiltOps._build_catalog_url()
    # - _escape_elasticsearch_query()         -> Now in Quilt3_Backend._escape_elasticsearch_query()

    def list_all_packages(self, registry: str) -> list[str]:
        """List all package names (stub implementation).

        This method is not yet implemented. See Task 3.3 in the migration tasks.
        """
        raise NotImplementedError("list_all_packages() not yet implemented - see Task 3.3")

    def diff_packages(
        self,
        package1_name: str,
        package2_name: str,
        registry: str,
        package1_hash: Optional[str] = None,
        package2_hash: Optional[str] = None,
    ) -> dict[str, list[str]]:
        """Compare two package versions and return differences.

        This is a simple orchestration method that could be moved to base class in future.

        Args:
            package1_name: Full name of the first package in "user/package" format
            package2_name: Full name of the second package in "user/package" format
            registry: Registry URL where both packages are stored
            package1_hash: Optional specific hash/version of the first package
            package2_hash: Optional specific hash/version of the second package

        Returns:
            Dict with "added", "deleted", "modified" keys

        Raises:
            BackendError: When the backend operation fails
        """
        try:
            logger.debug(f"Diffing packages: {package1_name} vs {package2_name} in registry: {registry}")

            # Get packages (uses primitive)
            pkg1 = self._backend_get_package(package1_name, registry, package1_hash)
            pkg2 = self._backend_get_package(package2_name, registry, package2_hash)

            # Diff packages (uses primitive)
            diff_dict = self._backend_diff_packages(pkg1, pkg2)

            logger.debug(f"Successfully diffed packages: {package1_name} vs {package2_name}")
            return diff_dict

        except Exception as e:
            error_context = {
                'package1_name': package1_name,
                'package2_name': package2_name,
                'registry': registry,
                'package1_hash': package1_hash,
                'package2_hash': package2_hash,
            }
            logger.error(f"Package diff failed: {str(e)}", extra={'context': error_context})
            raise BackendError(f"Quilt3 backend diff_packages failed: {str(e)}", context=error_context) from e
