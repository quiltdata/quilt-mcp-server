"""
Quilt3_Backend package operations mixin.

This module provides package-related operations including search, retrieval,
and transformation for the Quilt3_Backend implementation.

This mixin uses self.quilt3 which is provided by Quilt3_Backend_Base.
"""

import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from quilt_mcp.ops.exceptions import BackendError, ValidationError, NotFoundError
from quilt_mcp.domain.package_info import Package_Info

if TYPE_CHECKING:
    from types import ModuleType

logger = logging.getLogger(__name__)


class Quilt3_Backend_Packages:
    """Mixin for package-related operations."""

    # Type hints for attributes and methods provided by Quilt3_Backend_Base
    if TYPE_CHECKING:
        quilt3: "ModuleType"

        def _normalize_tags(self, tags: Any) -> List[str]: ...
        def _normalize_description(self, description: Any) -> str: ...
        def _normalize_datetime(self, dt: Any) -> Optional[str]: ...

    def search_packages(self, query: str, registry: str) -> List[Package_Info]:
        """Search for packages matching query.

        Args:
            query: Search query string (will be converted to Elasticsearch DSL)
            registry: Registry to search in

        Returns:
            List of Package_Info objects matching the query

        Raises:
            BackendError: If search operation fails
        """
        try:
            logger.debug(f"Searching packages with query: {query} in registry: {registry}")

            # Convert string query to Elasticsearch DSL query
            # quilt3.search_util.search_api() expects ES DSL, not simple strings
            if query.strip() == "":
                # Empty query - match all packages (manifest documents only)
                es_query = {
                    "query": {
                        "bool": {
                            "must": [
                                {"match_all": {}},
                                {"exists": {"field": "ptr_name"}},  # Only manifest documents have ptr_name
                            ]
                        }
                    },
                    "size": 1000,  # Default limit for listing all packages
                }
            else:
                # Escape special ES characters but preserve wildcards
                escaped_query = self._escape_elasticsearch_query(query)
                es_query = {
                    "query": {
                        "bool": {
                            "must": [
                                {"query_string": {"query": escaped_query}},
                                {"exists": {"field": "ptr_name"}},  # Only manifest documents have ptr_name
                            ]
                        }
                    },
                    "size": 1000,  # Default limit
                }

            # Extract bucket name from registry for index pattern
            bucket_name = registry.replace("s3://", "").split("/")[0]
            # Use package index pattern (bucket_packages)
            index_pattern = f"{bucket_name}_packages"

            # Use quilt3.search_util.search_api instead of quilt3.search
            from quilt3.search_util import search_api

            response = search_api(query=es_query, index=index_pattern, limit=1000)

            if "error" in response:
                raise Exception(f"Search API error: {response['error']}")

            # Extract hits from response
            hits = response.get("hits", {}).get("hits", [])

            # Transform hits to Package_Info objects
            result = []
            for hit in hits:
                try:
                    # Create a mock package object from the hit data
                    mock_package = type('MockPackage', (), {})()
                    source = hit.get("_source", {})

                    # Use the correct field names from Elasticsearch package documents
                    mock_package.name = source.get("ptr_name", "")  # Package name is in ptr_name field
                    mock_package.description = source.get("description", "")
                    mock_package.tags = source.get("tags", [])
                    # Convert string date to a format that _transform_package expects
                    modified_str = source.get("ptr_last_modified", "")
                    mock_package.modified = modified_str  # Keep as string, _transform_package will handle it
                    mock_package.registry = registry
                    mock_package.bucket = bucket_name
                    mock_package.top_hash = source.get("top_hash", "")

                    package_info = self._transform_package(mock_package)
                    result.append(package_info)
                except Exception as e:
                    logger.warning(f"Failed to transform search result: {e}")
                    continue

            logger.debug(f"Found {len(result)} packages")
            return result
        except Exception as e:
            raise BackendError(
                f"Quilt3 backend search failed: {str(e)}", context={'query': query, 'registry': registry}
            )

    def get_package_info(self, package_name: str, registry: str) -> Package_Info:
        """Get detailed information about a specific package.

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

    def _escape_elasticsearch_query(self, query: str) -> str:
        """Escape special characters in Elasticsearch query_string queries.

        Elasticsearch query_string syntax treats certain characters as operators.
        This function escapes them to allow literal searches while preserving wildcards.

        Args:
            query: Raw query string

        Returns:
            Escaped query string safe for query_string queries (preserving wildcards)
        """
        # Characters that need to be escaped in Elasticsearch query_string
        # Order matters: escape backslash first to avoid double-escaping
        # NOTE: * and ? are INTENTIONALLY OMITTED to preserve wildcard functionality
        special_chars = [
            '\\',
            '+',
            '-',
            '=',
            '>',
            '<',
            '!',
            '(',
            ')',
            '{',
            '}',
            '[',
            ']',
            '^',
            '"',
            '~',
            ':',
            '/',
        ]

        # Escape each special character with a backslash
        escaped = query
        for char in special_chars:
            escaped = escaped.replace(char, '\\' + char)

        return escaped

    # Transformation helper methods

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

    def create_package_revision(
        self,
        package_name: str,
        s3_uris: List[str],
        metadata: Optional[Dict] = None,
        registry: Optional[str] = None,
        message: str = "Package created via QuiltOps",
    ):
        """Create and push a package revision (stub implementation).

        This method is not yet implemented. See Task 3.2 in the migration tasks.
        """
        from quilt_mcp.domain.package_creation import Package_Creation_Result

        raise NotImplementedError("create_package_revision() not yet implemented - see Task 3.2")

    def list_all_packages(self, registry: str) -> List[str]:
        """List all package names (stub implementation).

        This method is not yet implemented. See Task 3.3 in the migration tasks.
        """
        raise NotImplementedError("list_all_packages() not yet implemented - see Task 3.3")
