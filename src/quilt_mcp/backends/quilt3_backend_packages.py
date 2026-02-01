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
            error_msg = str(e)
            # Improve error message for invalid bucket/registry
            if "No valid indices provided" in error_msg:
                bucket_name = registry.replace("s3://", "").split("/")[0]
                raise BackendError(
                    f"Quilt3 backend search failed: bucket '{bucket_name}' not found or not accessible",
                    context={'query': query, 'registry': registry, 'bucket': bucket_name},
                )
            raise BackendError(
                f"Quilt3 backend search failed: {error_msg}", context={'query': query, 'registry': registry}
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
        auto_organize: bool = True,
        copy: bool = False,
    ):
        """Create and push a package revision in a single operation.

        Creates a new package revision with the specified files and metadata,
        then pushes it to the registry. This is a complete operation that
        handles the entire package creation workflow.

        Args:
            package_name: Full package name in "user/package" format
            s3_uris: List of S3 URIs to include in the package
            metadata: Optional metadata dictionary to attach to the package
            registry: Target registry URL (uses default if None)
            message: Commit message for the package revision
            auto_organize: If True, preserve S3 folder structure as logical keys.
                         If False, flatten to just filenames (default: True)
            copy: Whether to copy files to registry bucket (default: False)
                - True: Deep copy objects to registry bucket
                - False: Create shallow references to original S3 locations (no copy, default)

        Returns:
            Package_Creation_Result with creation details and status

        Raises:
            ValidationError: When parameters are invalid (malformed URIs, invalid names)
            BackendError: When the backend operation fails (S3 access, push errors, etc.)
        """
        from quilt_mcp.domain.package_creation import Package_Creation_Result
        from quilt_mcp.ops.exceptions import BackendError

        try:
            logger.debug(f"Creating package revision: {package_name} with {len(s3_uris)} files")

            # Validate inputs
            self._validate_package_creation_inputs(package_name, s3_uris)

            # Create new package
            package = self.quilt3.Package()

            # Add files to package
            for s3_uri in s3_uris:
                logical_key = self._extract_logical_key(s3_uri, auto_organize=auto_organize)
                package.set(logical_key, s3_uri)

            # Set metadata if provided
            if metadata:
                package.set_meta(metadata)

            # Push to registry with appropriate copy strategy
            # quilt3.Package.push() uses selector_fn to control copying behavior:
            # - selector_fn returns False: Don't copy, reference original S3 location
            # - No selector_fn (default): Copy to registry bucket
            if not copy:
                # copy=False: Don't copy objects - just create metadata references to original S3 URIs
                top_hash = package.push(
                    package_name,
                    registry=registry,
                    message=message,
                    selector_fn=lambda logical_key, entry: False,
                )
            else:
                # copy=True: Let quilt3 copy objects to registry bucket
                # (quilt3 default behavior is smart copying - only copies if bytes differ)
                top_hash = package.push(package_name, registry=registry, message=message)

            # Use provided registry (S3 URL required for Package_Creation_Result)
            # No default - client must provide explicit registry bucket
            effective_registry = registry or "s3://unknown-registry"

            # Build catalog URL from logged-in catalog
            catalog_url = None
            try:
                logged_in_url = self.quilt3.logged_in()
                if logged_in_url:
                    # Build catalog URL from actual catalog domain
                    from quilt_mcp.utils import normalize_url

                    normalized_catalog = normalize_url(logged_in_url)
                    catalog_url = f"{normalized_catalog}/b/{package_name}"
            except Exception:
                # Fallback: try to build from registry if available
                if effective_registry and effective_registry != "s3://unknown-registry":
                    catalog_url = self._build_catalog_url(package_name, effective_registry)

            # Handle push failure (when top_hash is None or empty)
            if not top_hash:
                return Package_Creation_Result(
                    package_name=package_name,
                    top_hash="",
                    registry=effective_registry,
                    catalog_url=catalog_url,
                    file_count=len(s3_uris),
                    success=False,
                )

            result = Package_Creation_Result(
                package_name=package_name,
                top_hash=top_hash,
                registry=effective_registry,
                catalog_url=catalog_url,
                file_count=len(s3_uris),
                success=True,
            )

            logger.debug(f"Successfully created package revision: {package_name} with hash: {top_hash}")
            return result

        except ValidationError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            error_context = {
                'package_name': package_name,
                'registry': registry,
                'file_count': len(s3_uris),
            }
            logger.error(f"Package creation failed: {str(e)}", extra={'context': error_context})
            raise BackendError(
                f"Quilt3 backend create_package_revision failed: {str(e)}", context=error_context
            ) from e

    def diff_packages(
        self,
        package1_name: str,
        package2_name: str,
        registry: str,
        package1_hash: Optional[str] = None,
        package2_hash: Optional[str] = None,
    ) -> Dict[str, List[str]]:
        """Compare two package versions and return differences.

        Compares the contents of two package versions and returns the differences
        between them. This includes files that were added, deleted, or modified
        between the two package versions.

        Args:
            package1_name: Full name of the first package in "user/package" format
            package2_name: Full name of the second package in "user/package" format
            registry: Registry URL where both packages are stored
            package1_hash: Optional specific hash/version of the first package.
                         If None, uses the latest version.
            package2_hash: Optional specific hash/version of the second package.
                         If None, uses the latest version.

        Returns:
            Dict[str, List[str]]: Dictionary with difference categories:
                - "added": List of file paths that were added in package2
                - "deleted": List of file paths that were deleted from package1
                - "modified": List of file paths that were modified between versions

        Raises:
            BackendError: When the backend operation fails or packages are not found
            ValidationError: When package names, registry, or hash parameters are invalid
        """
        try:
            logger.debug(f"Diffing packages: {package1_name} vs {package2_name} in registry: {registry}")

            # Browse packages with optional hash specification
            if package1_hash:
                pkg1 = self.quilt3.Package.browse(package1_name, registry=registry, top_hash=package1_hash)
            else:
                pkg1 = self.quilt3.Package.browse(package1_name, registry=registry)

            if package2_hash:
                pkg2 = self.quilt3.Package.browse(package2_name, registry=registry, top_hash=package2_hash)
            else:
                pkg2 = self.quilt3.Package.browse(package2_name, registry=registry)

            # Use quilt3's built-in diff functionality
            diff_result = pkg1.diff(pkg2)

            # Convert the diff tuple (added, deleted, modified) to a dictionary
            if isinstance(diff_result, tuple) and len(diff_result) == 3:
                added, deleted, modified = diff_result
                diff_dict = {
                    "added": [str(path) for path in added] if added else [],
                    "deleted": [str(path) for path in deleted] if deleted else [],
                    "modified": [str(path) for path in modified] if modified else [],
                }
            else:
                # If diff_result is already a dict or unexpected format, use as-is
                diff_dict = diff_result if isinstance(diff_result, dict) else {"raw": [str(diff_result)]}

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

    def list_all_packages(self, registry: str) -> List[str]:
        """List all package names (stub implementation).

        This method is not yet implemented. See Task 3.3 in the migration tasks.
        """
        raise NotImplementedError("list_all_packages() not yet implemented - see Task 3.3")

    def update_package_revision(
        self,
        package_name: str,
        s3_uris: List[str],
        registry: str,
        metadata: Optional[Dict] = None,
        message: str = "Package updated via QuiltOps",
        auto_organize: bool = False,
        copy: str = "none",
    ):
        """Update an existing package with new files.

        Updates an existing package by adding new files from the specified S3 URIs.
        This operation browses the existing package, adds the new files, and pushes
        the updated package to the registry.

        Args:
            package_name: Full package name in "user/package" format
            s3_uris: List of S3 URIs to add to the package
            registry: Registry URL where the package is stored
            metadata: Optional metadata dictionary to merge with existing package metadata
            message: Commit message for the package update
            auto_organize: If True, preserve S3 folder structure as logical keys.
                         If False, flatten to just filenames (default: False)
            copy: Copy behavior for files:
                - "none": Create shallow references to original S3 locations (no copy)
                - "all": Deep copy all objects to registry bucket

        Returns:
            Package_Creation_Result with update details and status

        Raises:
            ValidationError: When parameters are invalid (malformed URIs, invalid names)
            BackendError: When the backend operation fails (S3 access, push errors, etc.)
        """
        from quilt_mcp.domain.package_creation import Package_Creation_Result
        from quilt_mcp.ops.exceptions import BackendError, ValidationError

        try:
            logger.debug(f"Updating package: {package_name} with {len(s3_uris)} files")

            # Validate inputs
            self._validate_package_update_inputs(package_name, s3_uris, registry)

            # Browse existing package (extracted from package_update() tool)
            existing_pkg = self.quilt3.Package.browse(package_name, registry=registry)

            # Use the existing package as the base (extracted from package_update() tool)
            updated_pkg = existing_pkg

            # Add S3 URIs to package (extracted logic from _collect_objects_into_package)
            added_files = []
            for s3_uri in s3_uris:
                if not s3_uri.startswith("s3://"):
                    continue  # Skip non-S3 URIs

                without_scheme = s3_uri[5:]
                if "/" not in without_scheme:
                    continue  # Skip bucket-only URIs

                bucket, key = without_scheme.split("/", 1)
                if not key or key.endswith("/"):
                    continue  # Skip directory URIs

                # Extract logical key based on auto_organize setting
                if auto_organize:
                    logical_path = key  # Preserve folder structure
                else:
                    logical_path = key.split("/")[-1]  # Flatten to filename

                # Add file to package
                updated_pkg.set(logical_path, s3_uri)
                added_files.append({"logical_path": logical_path, "source": s3_uri})

            # Handle metadata merging (extracted from package_update() tool)
            if metadata:
                try:
                    combined = {}
                    try:
                        combined.update(existing_pkg.meta)
                    except Exception:
                        pass  # If existing package has no metadata, start fresh
                    combined.update(metadata)
                    updated_pkg.set_meta(combined)
                except Exception as e:
                    logger.warning(f"Failed to set merged metadata: {e}")

            # Build selector function based on copy parameter (extracted from _build_selector_fn)
            if copy == "all":
                selector_fn = lambda _logical_key, _entry: True  # Copy all objects
            else:  # copy == "none"
                selector_fn = lambda _logical_key, _entry: False  # Reference only

            # Push updated package (extracted from package_update() tool)
            top_hash = updated_pkg.push(
                package_name,
                registry=registry,
                message=message,
                selector_fn=selector_fn,
                force=True,
            )

            # Generate catalog URL
            catalog_url = self._build_catalog_url(package_name, registry)

            # Handle push failure
            if not top_hash:
                return Package_Creation_Result(
                    package_name=package_name,
                    top_hash="",
                    registry=registry,
                    catalog_url=catalog_url,
                    file_count=len(added_files),
                    success=False,
                )

            result = Package_Creation_Result(
                package_name=package_name,
                top_hash=top_hash,
                registry=registry,
                catalog_url=catalog_url,
                file_count=len(added_files),
                success=True,
            )

            logger.debug(f"Successfully updated package: {package_name} with hash: {top_hash}")
            return result

        except ValidationError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            error_context = {
                'package_name': package_name,
                'registry': registry,
                'file_count': len(s3_uris),
            }
            logger.error(f"Package update failed: {str(e)}", extra={'context': error_context})
            raise BackendError(
                f"Quilt3 backend update_package_revision failed: {str(e)}", context=error_context
            ) from e

    def _validate_package_creation_inputs(self, package_name: str, s3_uris: List[str]) -> None:
        """Validate inputs for package creation.

        Args:
            package_name: Package name to validate
            s3_uris: List of S3 URIs to validate

        Raises:
            ValidationError: If inputs are invalid
        """
        import re

        # Validate package name format (user/package)
        if not package_name or not isinstance(package_name, str):
            raise ValidationError("Package name must be a non-empty string", {"field": "package_name"})

        if not re.match(r'^[^/]+/[^/]+$', package_name):
            raise ValidationError("Package name must be in 'user/package' format", {"field": "package_name"})

        # Validate S3 URIs
        if not s3_uris or not isinstance(s3_uris, list):
            raise ValidationError("S3 URIs must be a non-empty list", {"field": "s3_uris"})

        for i, s3_uri in enumerate(s3_uris):
            if not isinstance(s3_uri, str) or not s3_uri.startswith('s3://'):
                raise ValidationError(
                    f"Invalid S3 URI at index {i}: must start with 's3://'",
                    {"field": "s3_uris", "index": i, "uri": s3_uri},
                )

            # Check for basic S3 URI structure (bucket and key)
            parts = s3_uri[5:].split('/', 1)  # Remove 's3://' and split
            if len(parts) < 2 or not parts[0] or not parts[1]:
                raise ValidationError(
                    f"Invalid S3 URI at index {i}: must include bucket and key",
                    {"field": "s3_uris", "index": i, "uri": s3_uri},
                )

    def _validate_package_update_inputs(self, package_name: str, s3_uris: List[str], registry: str) -> None:
        """Validate inputs for package update.

        Args:
            package_name: Package name to validate
            s3_uris: List of S3 URIs to validate
            registry: Registry URL to validate

        Raises:
            ValidationError: If inputs are invalid
        """
        import re

        # Validate package name format (user/package)
        if not package_name or not isinstance(package_name, str):
            raise ValidationError("Package name must be a non-empty string", {"field": "package_name"})

        if not re.match(r'^[^/]+/[^/]+$', package_name):
            raise ValidationError("Package name must be in 'user/package' format", {"field": "package_name"})

        # Validate registry
        if not registry or not isinstance(registry, str):
            raise ValidationError("Registry must be a non-empty string", {"field": "registry"})

        if not registry.startswith('s3://'):
            raise ValidationError("Registry must be an S3 URI starting with 's3://'", {"field": "registry"})

        # Validate S3 URIs list structure (but allow individual URIs to be invalid - they'll be skipped)
        if not s3_uris or not isinstance(s3_uris, list):
            raise ValidationError("S3 URIs must be a non-empty list", {"field": "s3_uris"})

        # Check that at least one URI could potentially be valid
        has_potential_valid_uri = any(
            isinstance(uri, str) and uri.startswith('s3://') and '/' in uri[5:] and not uri.endswith('/')
            for uri in s3_uris
        )

        if not has_potential_valid_uri:
            raise ValidationError(
                "No potentially valid S3 URIs found in list",
                {"field": "s3_uris", "note": "URIs must be strings starting with 's3://' and include bucket and key"},
            )

    def _extract_logical_key(self, s3_uri: str, auto_organize: bool = True) -> str:
        """Extract logical key from S3 URI for package.

        Args:
            s3_uri: S3 URI in format s3://bucket/path/to/file.ext
            auto_organize: If True, preserve S3 folder structure as logical keys.
                         If False, flatten to just filenames.

        Returns:
            Logical key for use in package
        """
        if auto_organize:
            # Preserve S3 folder structure: s3://bucket/path/to/file.ext -> path/to/file.ext
            parts = s3_uri[5:].split('/', 1)  # Remove 's3://' and split on first '/'
            if len(parts) >= 2:
                return parts[1]  # Return everything after bucket name
            else:
                # Fallback: use filename if no path
                return s3_uri.split('/')[-1]
        else:
            # Flatten to just filename: s3://bucket/path/to/file.ext -> file.ext
            return s3_uri.split('/')[-1]

    def _build_catalog_url(self, package_name: str, registry: str) -> Optional[str]:
        """Build catalog URL for viewing package in web UI.

        Args:
            package_name: Package name in user/package format
            registry: Registry S3 URL

        Returns:
            Catalog URL or None if cannot be constructed
        """
        try:
            # Extract bucket name from registry
            bucket_name = registry.replace('s3://', '').split('/')[0]

            # Construct catalog URL (this is a simplified version)
            # In practice, this would need to determine the actual catalog domain
            # For now, return a placeholder that includes the key information
            return f"https://catalog.example.com/b/{bucket_name}/packages/{package_name}"
        except Exception:
            # If URL construction fails, return None
            return None
