"""Platform GraphQL backend implementation.

This module provides a concrete implementation of QuiltOps backed by the
Platform GraphQL API and JWT authentication claims.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from typing import List, Optional, Dict, Any, cast

from quilt_mcp.ops.quilt_ops import QuiltOps
from quilt_mcp.ops.tabulator_mixin import TabulatorMixin
from quilt_mcp.ops.admin_ops import AdminOps
from quilt_mcp.ops.exceptions import AuthenticationError, BackendError, ValidationError, NotFoundError
from quilt_mcp.domain import (
    Package_Info,
    Content_Info,
    Bucket_Info,
    Auth_Status,
    Catalog_Config,
    Package_Creation_Result,
)
from quilt_mcp.context.runtime_context import (
    get_runtime_auth,
)
from quilt_mcp.services.browsing_session_client import BrowsingSessionClient
from quilt_mcp.utils.common import graphql_endpoint, normalize_url, get_dns_name_from_url

logger = logging.getLogger(__name__)


class Platform_Backend(TabulatorMixin, QuiltOps):
    """Platform GraphQL backend implementation."""

    def __init__(self) -> None:
        self._access_token = self._load_access_token()

        # Admin operations (lazy loaded)
        self._admin_ops: Optional[AdminOps] = None

        self._catalog_url = os.getenv("QUILT_CATALOG_URL")
        self._registry_url = os.getenv("QUILT_REGISTRY_URL")
        if not self._catalog_url or not self._registry_url:
            raise AuthenticationError(
                "Platform backend requires QUILT_CATALOG_URL and QUILT_REGISTRY_URL environment variables."
            )

        self._graphql_endpoint = os.getenv("QUILT_GRAPHQL_ENDPOINT")
        if not self._graphql_endpoint and self._registry_url:
            self._graphql_endpoint = graphql_endpoint(self._registry_url)

        if not self._graphql_endpoint:
            raise AuthenticationError(
                "GraphQL endpoint not configured. Set QUILT_GRAPHQL_ENDPOINT or QUILT_REGISTRY_URL."
            )

        import requests

        self._requests = requests
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

        ttl_seconds = int(os.getenv("QUILT_BROWSING_SESSION_TTL", "180"))
        self._browse_client = BrowsingSessionClient(
            catalog_url=self._catalog_url,
            graphql_endpoint=self._graphql_endpoint,
            access_token=self._access_token,
            session=self._session,
            ttl_seconds=ttl_seconds,
        )

        logger.info("Platform_Backend initialized")

    # ---------------------------------------------------------------------
    # GraphQL auth + endpoint helpers
    # ---------------------------------------------------------------------

    def get_graphql_endpoint(self) -> str:
        if not self._graphql_endpoint:
            raise AuthenticationError("GraphQL endpoint not configured")
        return self._graphql_endpoint

    def get_graphql_auth_headers(self) -> Dict[str, str]:
        if not self._access_token:
            raise AuthenticationError("Missing JWT access token for GraphQL authentication")
        return {"Authorization": f"Bearer {self._access_token}"}

    def execute_graphql_query(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        registry: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            endpoint = self.get_graphql_endpoint()
            headers = self.get_graphql_auth_headers()
            payload: Dict[str, Any] = {"query": query}
            if variables:
                payload["variables"] = variables

            response = self._session.post(endpoint, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise BackendError("GraphQL response was not a JSON object")

            if "errors" in result:
                error_messages = [err.get("message", str(err)) for err in result.get("errors", [])]
                raise BackendError(f"GraphQL query failed: {'; '.join(error_messages)}")

            return result
        except self._requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in {401, 403}:
                raise AuthenticationError("GraphQL query not authorized") from exc
            error_text = exc.response.text if exc.response is not None else str(exc)
            raise BackendError(f"GraphQL query failed: {error_text}") from exc
        except BackendError:
            raise
        except Exception as exc:
            raise BackendError(f"GraphQL query failed: {exc}") from exc

    # ---------------------------------------------------------------------
    # Auth + catalog
    # ---------------------------------------------------------------------

    def get_auth_status(self) -> Auth_Status:
        try:
            query = """
            query AuthStatus {
              me {
                name
                email
                isAdmin
              }
            }
            """
            result = self.execute_graphql_query(query)
            me = result.get("data", {}).get("me")
            is_authenticated = bool(me)

            catalog_url = self._catalog_url
            catalog_name = get_dns_name_from_url(catalog_url) if catalog_url else None

            return Auth_Status(
                is_authenticated=is_authenticated,
                logged_in_url=catalog_url,
                catalog_name=catalog_name,
                registry_url=self._registry_url,
            )
        except AuthenticationError:
            raise
        except Exception as exc:
            raise BackendError(f"Failed to get authentication status: {exc}") from exc

    # HIGH-LEVEL METHOD REMOVED - Now implemented in QuiltOps base class
    # get_catalog_config() is now a concrete method in QuiltOps that calls:
    # - _backend_get_catalog_config() primitive
    # - _transform_catalog_config() transformation (in QuiltOps base)

    def configure_catalog(self, catalog_url: str) -> None:
        raise ValidationError(
            "Platform backend uses static configuration. "
            "Set QUILT_CATALOG_URL and QUILT_REGISTRY_URL environment variables instead."
        )

    def get_registry_url(self) -> Optional[str]:
        return self._registry_url

    # ---------------------------------------------------------------------
    # Read operations
    # ---------------------------------------------------------------------

    # HIGH-LEVEL METHOD REMOVED - Now implemented in QuiltOps base class
    # list_buckets() is now a concrete method in QuiltOps that calls:
    # - _backend_list_buckets() primitive
    # - _transform_bucket_to_bucket_info() primitive

    # HIGH-LEVEL METHOD REMOVED - Now implemented in QuiltOps base class
    # search_packages() is now a concrete method in QuiltOps that calls:
    # - _backend_search_packages() primitive
    # - _transform_search_result_to_package_info() primitive

    def get_package_info(self, package_name: str, registry: str) -> Package_Info:
        try:
            bucket = self._extract_bucket_from_registry(registry)
            gql = """
            query PackageInfo($bucket: String!, $name: String!) {
              package(bucket: $bucket, name: $name) {
                bucket
                name
                modified
                revision(hashOrTag: "latest") {
                  hash
                  message
                  userMeta
                }
              }
            }
            """
            result = self.execute_graphql_query(gql, variables={"bucket": bucket, "name": package_name})
            package_data = result.get("data", {}).get("package")
            if not package_data:
                raise NotFoundError(f"Package not found: {package_name}")

            return self._transform_package_details(package_data, registry)
        except NotFoundError:
            raise
        except Exception as exc:
            raise BackendError(
                f"Platform backend get_package_info failed: {exc}",
                context={"package_name": package_name, "registry": registry},
            ) from exc

    def browse_content(self, package_name: str, registry: str, path: str = "") -> List[Content_Info]:
        try:
            bucket = self._extract_bucket_from_registry(registry)
            gql = """
            query BrowseContent($bucket: String!, $name: String!, $path: String!) {
              package(bucket: $bucket, name: $name) {
                revision(hashOrTag: "latest") {
                  dir(path: $path) {
                    path
                    size
                    children {
                      __typename
                      ... on PackageFile { path size physicalKey }
                      ... on PackageDir { path size }
                    }
                  }
                  file(path: $path) {
                    path
                    size
                    physicalKey
                  }
                }
              }
            }
            """
            result = self.execute_graphql_query(
                gql,
                variables={"bucket": bucket, "name": package_name, "path": path or ""},
            )
            revision = result.get("data", {}).get("package", {}).get("revision")
            if not revision:
                raise NotFoundError(f"Package not found: {package_name}")

            dir_info = revision.get("dir")
            file_info = revision.get("file")

            if dir_info:
                children = dir_info.get("children", [])
                return [self._transform_content_entry(entry) for entry in children]

            if file_info:
                return [self._transform_content_entry({"__typename": "PackageFile", **file_info})]

            raise NotFoundError(f"Path not found in package: {path}")
        except NotFoundError:
            raise
        except Exception as exc:
            raise BackendError(
                f"Platform backend browse_content failed: {exc}",
                context={"package_name": package_name, "registry": registry, "path": path},
            ) from exc

    # HIGH-LEVEL METHOD REMOVED - Now implemented in QuiltOps base class
    # diff_packages() is now a concrete method in QuiltOps that calls:
    # - _backend_get_package() primitive (twice)
    # - _backend_diff_packages() primitive

    # ---------------------------------------------------------------------
    # Content URLs
    # ---------------------------------------------------------------------

    # HIGH-LEVEL METHOD REMOVED - Now implemented in QuiltOps base class
    # get_content_url() is now a concrete method in QuiltOps that calls:
    # - _backend_get_file_url() primitive

    # ---------------------------------------------------------------------
    # Write operations (quilt3 Package)
    # ---------------------------------------------------------------------

    def get_boto3_client(self, service_name: str, region: Optional[str] = None) -> Any:
        raise AuthenticationError("AWS client access is not available in Platform backend.")

    # HIGH-LEVEL METHODS REMOVED - Now implemented in QuiltOps base class
    # create_package_revision() is now a concrete method in QuiltOps that calls:
    # - _backend_create_empty_package() primitive
    # - _backend_add_file_to_package() primitive
    # - _backend_set_package_metadata() primitive
    # - _backend_push_package() primitive

    def update_package_revision(
        self,
        package_name: str,
        s3_uris: List[str],
        registry: str,
        metadata: Optional[Dict] = None,
        message: str = "Package updated via QuiltOps",
        auto_organize: bool = False,
        copy: str = "none",
    ) -> Package_Creation_Result:
        try:
            self._validate_package_update_inputs(package_name, s3_uris, registry)

            # Extract bucket from registry
            bucket = self._extract_bucket_from_registry(registry)

            # Query existing package
            query = """
            query GetPackageForUpdate($bucket: String!, $name: String!) {
              package(bucket: $bucket, name: $name) {
                revision(hashOrTag: "latest") {
                  hash
                  userMeta
                  contentsFlatMap(max: 10000)
                }
              }
            }
            """
            query_result = self.execute_graphql_query(query, variables={"bucket": bucket, "name": package_name})

            package_data = query_result.get("data", {}).get("package")
            if not package_data:
                raise NotFoundError(f"Package not found: {package_name}")

            revision = package_data.get("revision", {})
            existing_entries_map = revision.get("contentsFlatMap") or {}
            existing_meta = revision.get("userMeta") or {}

            # Build entries array from existing entries
            entries = []
            for logical_key, entry_data in existing_entries_map.items():
                if isinstance(entry_data, dict):
                    entries.append(
                        {
                            "logicalKey": logical_key,
                            "physicalKey": entry_data.get("physicalKey", ""),
                            "size": entry_data.get("size"),
                            "hash": entry_data.get("hash"),
                            "meta": None,
                        }
                    )

            # Add new files (overwrites if same logicalKey)
            added_count = 0
            for s3_uri in s3_uris:
                if not s3_uri.startswith("s3://"):
                    continue
                without_scheme = s3_uri[5:]
                if "/" not in without_scheme:
                    continue
                bucket_part, key = without_scheme.split("/", 1)
                if not key or key.endswith("/"):
                    continue

                logical_key = self._extract_logical_key(s3_uri, auto_organize)
                # Remove existing entry with same logical_key
                entries = [e for e in entries if e["logicalKey"] != logical_key]
                # Add new entry
                entries.append(
                    {
                        "logicalKey": logical_key,
                        "physicalKey": s3_uri,
                        "hash": None,
                        "size": None,
                        "meta": None,
                    }
                )
                added_count += 1

            # Merge metadata (new overrides existing)
            merged_meta = {**existing_meta, **(metadata or {})}

            # Build GraphQL packageConstruct mutation
            mutation = """
            mutation PackageConstruct($params: PackagePushParams!, $src: PackageConstructSource!) {
              packageConstruct(params: $params, src: $src) {
                __typename
                ... on PackagePushSuccess {
                  package { name }
                  revision { hash }
                }
                ... on PackagePushInvalidInputFailure {
                  errors { path message }
                }
                ... on PackagePushComputeFailure {
                  message
                }
              }
            }
            """

            # Build variables
            variables = {
                "params": {
                    "bucket": bucket,
                    "name": package_name,
                    "message": message,
                    "userMeta": merged_meta,
                    "workflow": None,
                },
                "src": {"entries": entries},
            }

            # Execute mutation
            result = self.execute_graphql_query(mutation, variables=variables)

            # Parse response
            package_construct = result.get("data", {}).get("packageConstruct", {})
            typename = package_construct.get("__typename")

            catalog_url = self._build_catalog_url(package_name, registry)

            if typename == "PackagePushSuccess":
                revision_data = package_construct.get("revision", {})
                top_hash = revision_data.get("hash", "")

                # If copy mode enabled, promote the package to copy objects to registry
                if copy != "none":
                    top_hash = self._promote_package(bucket, package_name, top_hash, message, merged_meta)

                return Package_Creation_Result(
                    package_name=package_name,
                    top_hash=top_hash,
                    registry=registry,
                    catalog_url=catalog_url,
                    file_count=added_count,
                    success=True,
                )
            elif typename == "PackagePushInvalidInputFailure":
                errors = package_construct.get("errors", [])
                error_messages = [
                    f"{err.get('path', 'unknown')}: {err.get('message', 'invalid input')}" for err in errors
                ]
                raise ValidationError(f"Invalid package input: {'; '.join(error_messages)}")
            elif typename == "PackagePushComputeFailure":
                message_text = package_construct.get("message", "Package update failed")
                raise BackendError(f"Package update compute failure: {message_text}")
            else:
                raise BackendError(f"Unexpected response type: {typename}")

        except (ValidationError, NotImplementedError, NotFoundError):
            raise
        except Exception as exc:
            raise BackendError(
                f"Platform backend update_package_revision failed: {exc}",
                context={"package_name": package_name, "registry": registry},
            ) from exc

    # ---------------------------------------------------------------------
    # Admin operations
    # ---------------------------------------------------------------------

    @property
    def admin(self) -> AdminOps:
        """Get admin operations interface.

        Returns:
            AdminOps instance for performing admin operations
        """
        if self._admin_ops is None:
            # Import here to avoid circular dependency
            from quilt_mcp.backends.platform_admin_ops import Platform_Admin_Ops

            self._admin_ops = Platform_Admin_Ops(self)
        return self._admin_ops

    # =========================================================================
    # Backend Primitives (Template Method Pattern)
    # =========================================================================
    # These methods implement the abstract backend primitives defined in QuiltOps.
    # They wrap GraphQL operations without adding validation or transformation logic.

    def _backend_create_empty_package(self) -> Any:
        """Create a new empty package representation (backend primitive).

        Returns:
            Internal package representation (entries list)
        """
        return {"entries": []}

    def _backend_add_file_to_package(self, package: Any, logical_key: str, s3_uri: str) -> None:
        """Add a file reference to package representation (backend primitive).

        Args:
            package: Internal package representation
            logical_key: Logical path within package
            s3_uri: S3 URI of file to add
        """
        package["entries"].append(
            {
                "logicalKey": logical_key,
                "physicalKey": s3_uri,
                "hash": None,
                "size": None,
                "meta": None,
            }
        )

    def _backend_set_package_metadata(self, package: Any, metadata: Dict[str, Any]) -> None:
        """Set metadata on package representation (backend primitive).

        Args:
            package: Internal package representation
            metadata: Metadata dictionary
        """
        package["metadata"] = metadata

    def _backend_push_package(self, package: Any, package_name: str, registry: str, message: str, copy: bool) -> str:
        """Push package via GraphQL packageConstruct mutation (backend primitive).

        Args:
            package: Internal package representation
            package_name: Full package name
            registry: Registry S3 URL
            message: Commit message
            copy: If True, promote package to copy objects

        Returns:
            Top hash of pushed package (empty string if push fails)
        """
        bucket = self._extract_bucket_from_registry(registry)

        mutation = """
        mutation PackageConstruct($params: PackagePushParams!, $src: PackageConstructSource!) {
          packageConstruct(params: $params, src: $src) {
            __typename
            ... on PackagePushSuccess {
              package { name }
              revision { hash }
            }
            ... on PackagePushInvalidInputFailure {
              errors { path message }
            }
            ... on PackagePushComputeFailure {
              message
            }
          }
        }
        """

        variables = {
            "params": {
                "bucket": bucket,
                "name": package_name,
                "message": message,
                "userMeta": package.get("metadata", {}),
                "workflow": None,
            },
            "src": {"entries": package["entries"]},
        }

        result = self.execute_graphql_query(mutation, variables=variables)
        package_construct = result.get("data", {}).get("packageConstruct", {})
        typename = package_construct.get("__typename")

        if typename == "PackagePushSuccess":
            revision = package_construct.get("revision", {})
            top_hash: str = str(revision.get("hash", ""))

            # If copy=True, promote the package to copy objects to registry
            if copy:
                promoted_hash = self._promote_package(
                    bucket, package_name, top_hash, message, package.get("metadata", {})
                )
                return str(promoted_hash)

            return top_hash
        elif typename == "PackagePushInvalidInputFailure":
            errors = package_construct.get("errors", [])
            error_messages = [f"{err.get('path', 'unknown')}: {err.get('message', 'invalid input')}" for err in errors]
            raise ValidationError(f"Invalid package input: {'; '.join(error_messages)}")
        elif typename == "PackagePushComputeFailure":
            message_text = package_construct.get("message", "Package creation failed")
            raise Exception(f"Package creation compute failure: {message_text}")
        else:
            raise Exception(f"Unexpected response type: {typename}")

    def _backend_get_package(self, package_name: str, registry: str, top_hash: Optional[str] = None) -> Any:
        """Retrieve package via GraphQL query (backend primitive).

        Args:
            package_name: Full package name
            registry: Registry S3 URL
            top_hash: Optional specific version hash

        Returns:
            Package data structure with contentsFlatMap

        Raises:
            NotFoundError: If package not found
        """
        bucket = self._extract_bucket_from_registry(registry)

        query = """
        query GetPackage($bucket: String!, $name: String!, $hash: String!) {
          package(bucket: $bucket, name: $name) {
            revision(hashOrTag: $hash) {
              hash
              userMeta
              contentsFlatMap(max: 10000)
            }
          }
        }
        """

        variables = {
            "bucket": bucket,
            "name": package_name,
            "hash": top_hash or "latest",
        }

        result = self.execute_graphql_query(query, variables=variables)
        package_data = result.get("data", {}).get("package")

        if not package_data:
            raise NotFoundError(f"Package not found: {package_name}")

        return package_data

    def _backend_get_package_entries(self, package: Any) -> Dict[str, Dict[str, Any]]:
        """Get all entries from package data (backend primitive).

        Args:
            package: Package data structure from GraphQL

        Returns:
            Dict mapping logical_key to entry metadata
        """
        result: Dict[str, Dict[str, Any]] = package.get("revision", {}).get("contentsFlatMap", {})
        return result

    def _backend_get_package_metadata(self, package: Any) -> Dict[str, Any]:
        """Get metadata from package data (backend primitive).

        Args:
            package: Package data structure from GraphQL

        Returns:
            Package metadata dictionary (empty dict if no metadata)
        """
        result: Dict[str, Any] = package.get("revision", {}).get("userMeta", {})
        return result

    def _backend_search_packages(self, query: str, registry: str) -> List[Dict[str, Any]]:
        """Execute GraphQL package search (backend primitive).

        Args:
            query: Search query string
            registry: Registry S3 URL

        Returns:
            List of package data dictionaries (not domain objects)
        """
        bucket = self._extract_bucket_from_registry(registry)

        gql = """
        query SearchPackages($buckets: [String!], $searchString: String) {
          searchPackages(buckets: $buckets, searchString: $searchString) {
            __typename
            ... on PackagesSearchResultSet {
              firstPage(size: 1000, order: NEWEST) {
                hits {
                  name
                  bucket
                  hash
                  modified
                  comment
                  meta
                }
              }
            }
            ... on EmptySearchResultSet {
              _
            }
            ... on InvalidInput {
              errors { path message name context }
            }
            ... on OperationError {
              message
              name
              context
            }
          }
        }
        """

        result = self.execute_graphql_query(gql, variables={"buckets": [bucket], "searchString": query})
        search_result = result.get("data", {}).get("searchPackages", {})
        typename = search_result.get("__typename")

        # Handle both old and new API response types
        if typename == "PackageSearchResults":
            # New API format
            hits = search_result.get("hits", [])
        elif typename == "PackagesSearchResultSet":
            # Old API format (with pagination)
            hits = search_result.get("firstPage", {}).get("hits", [])
        elif typename == "EmptySearchResultSet":
            # Empty results
            return []
        elif typename == "InvalidInput":
            errors = search_result.get("errors", [])
            raise ValidationError(f"Search invalid input: {errors}")
        elif typename == "OperationError":
            message = search_result.get("message", "Search failed")
            raise Exception(f"Search operation error: {message}")
        else:
            raise Exception(f"Unexpected search response type: {typename}")

        # Return raw hits (not transformed to domain objects)
        return [
            {
                "name": hit.get("name", ""),
                "bucket": hit.get("bucket", bucket),
                "top_hash": hit.get("hash", ""),
                "modified": hit.get("modified"),
                "comment": hit.get("comment"),
                "meta": hit.get("meta"),
                "registry": registry,
            }
            for hit in hits
        ]

    def _backend_diff_packages(self, pkg1: Any, pkg2: Any) -> Dict[str, List[str]]:
        """Compute diff between two package data structures (backend primitive).

        Args:
            pkg1: First package data structure from GraphQL
            pkg2: Second package data structure from GraphQL

        Returns:
            Dict with keys "added", "deleted", "modified"
        """
        map1 = self._backend_get_package_entries(pkg1)
        map2 = self._backend_get_package_entries(pkg2)

        keys1 = set(map1.keys())
        keys2 = set(map2.keys())

        added = sorted(keys2 - keys1)
        deleted = sorted(keys1 - keys2)

        modified: List[str] = []
        for key in sorted(keys1 & keys2):
            if not self._entries_equal(map1.get(key), map2.get(key)):
                modified.append(key)

        return {"added": added, "deleted": deleted, "modified": modified}

    def _backend_browse_package_content(self, package: Any, path: str) -> List[Dict[str, Any]]:
        """List contents of package at path via GraphQL (backend primitive).

        Args:
            package: Package data structure from GraphQL (must include name and bucket)
            path: Path within package to browse

        Returns:
            List of content entry dictionaries (not domain objects)
        """
        # Extract package info from package data
        package_name = package.get("name", "")
        bucket = package.get("bucket", "")

        gql = """
        query BrowseContent($bucket: String!, $name: String!, $path: String!) {
          package(bucket: $bucket, name: $name) {
            revision(hashOrTag: "latest") {
              dir(path: $path) {
                path
                size
                children {
                  __typename
                  ... on PackageFile { path size physicalKey }
                  ... on PackageDir { path size }
                }
              }
              file(path: $path) {
                path
                size
                physicalKey
              }
            }
          }
        }
        """

        result = self.execute_graphql_query(
            gql, variables={"bucket": bucket, "name": package_name, "path": path or ""}
        )
        revision = result.get("data", {}).get("package", {}).get("revision")

        if not revision:
            raise NotFoundError(f"Package not found: {package_name}")

        dir_info = revision.get("dir")
        file_info = revision.get("file")

        if dir_info:
            children = dir_info.get("children", [])
            return [
                {
                    "path": entry.get("path", ""),
                    "size": entry.get("size"),
                    "type": "directory" if entry.get("__typename") == "PackageDir" else "file",
                }
                for entry in children
            ]

        if file_info:
            return [
                {
                    "path": file_info.get("path", ""),
                    "size": file_info.get("size"),
                    "type": "file",
                }
            ]

        raise NotFoundError(f"Path not found in package: {path}")

    def _backend_get_file_url(
        self, package_name: str, registry: str, path: str, top_hash: Optional[str] = None
    ) -> str:
        """Generate download URL via browsing session (backend primitive).

        Args:
            package_name: Full package name
            registry: Registry S3 URL
            path: Path to file within package
            top_hash: Optional specific version hash

        Returns:
            Presigned URL for file download
        """
        bucket = self._extract_bucket_from_registry(registry)

        # Get revision hash if not provided
        if not top_hash:
            gql = """
            query GetRevisionHash($bucket: String!, $name: String!) {
              package(bucket: $bucket, name: $name) {
                revision(hashOrTag: "latest") {
                  hash
                }
              }
            }
            """
            result = self.execute_graphql_query(gql, variables={"bucket": bucket, "name": package_name})
            top_hash = result.get("data", {}).get("package", {}).get("revision", {}).get("hash")

        if not top_hash:
            raise Exception("Missing revision hash for browsing session")

        scope = f"s3://{bucket}#package={package_name}&hash={top_hash}"
        return self._browse_client.get_presigned_url(scope=scope, path=path)

    def _backend_get_session_info(self) -> Dict[str, Any]:
        """Get Platform session information (backend primitive).

        Returns:
            Dict with session info
        """
        return {
            "is_authenticated": bool(self._access_token),
            "catalog_url": self._catalog_url,
            "registry_url": self._registry_url,
        }

    def _backend_get_catalog_config(self, catalog_url: str) -> Dict[str, Any]:
        """Fetch catalog config.json via requests (backend primitive).

        Args:
            catalog_url: Catalog URL

        Returns:
            Raw config dictionary

        Raises:
            Exception: If config fetch fails
        """
        normalized_url = normalize_url(catalog_url)
        config_url = f"{normalized_url}/config.json"

        response = self._requests.get(config_url, timeout=10)
        response.raise_for_status()

        result: Dict[str, Any] = response.json()
        return result

    def _backend_list_buckets(self) -> List[Dict[str, Any]]:
        """List S3 buckets via GraphQL (backend primitive).

        Returns:
            List of bucket information dictionaries
        """
        gql = """
        query ListBuckets {
          bucketConfigs {
            name
          }
        }
        """

        result = self.execute_graphql_query(gql)
        buckets = result.get("data", {}).get("bucketConfigs", [])

        return [{"name": bucket["name"]} for bucket in buckets if bucket.get("name")]

    def _backend_get_boto3_session(self) -> Any:
        """Get boto3 session (backend primitive).

        Raises:
            AuthenticationError: Platform backend doesn't support boto3 access
        """
        raise AuthenticationError("AWS client access is not available in Platform backend.")

    def _transform_search_result_to_package_info(self, result: Dict[str, Any], registry: str) -> Package_Info:
        """Transform GraphQL search result to Package_Info (backend primitive).

        Args:
            result: Backend-specific search result dictionary
            registry: Registry URL for context

        Returns:
            Package_Info domain object
        """
        return self._transform_search_hit(result, registry)

    def _transform_content_entry_to_content_info(self, entry: Dict[str, Any]) -> Content_Info:
        """Transform GraphQL content entry to Content_Info (backend primitive).

        Args:
            entry: Backend-specific content entry dictionary

        Returns:
            Content_Info domain object
        """
        return self._transform_content_entry(entry)

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------

    def _load_access_token(self) -> str:
        runtime_auth = get_runtime_auth()
        if runtime_auth and runtime_auth.access_token:
            return runtime_auth.access_token
        raise AuthenticationError("JWT access token is required for Platform backend.")

    # TRANSFORMATION METHOD REMOVED - Now in QuiltOps base class
    # _transform_catalog_config() is now a concrete method in QuiltOps base class

    def _transform_search_hit(self, hit: Dict[str, Any], registry: str) -> Package_Info:
        name = hit.get("name") or ""
        bucket = hit.get("bucket") or self._extract_bucket_from_registry(registry)
        # Handle both GraphQL response format ("hash") and primitive format ("top_hash")
        top_hash = hit.get("top_hash") or hit.get("hash") or ""
        modified = self._normalize_package_datetime(hit.get("modified"))

        meta = self._parse_meta(hit.get("meta"))
        description = self._extract_description(meta, hit.get("comment"))
        tags = self._extract_tags_from_meta(meta)

        return Package_Info(
            name=name,
            description=description,
            tags=tags,
            modified_date=modified,
            registry=registry,
            bucket=bucket,
            top_hash=top_hash,
        )

    def _transform_package_details(self, package_data: Dict[str, Any], registry: str) -> Package_Info:
        revision = package_data.get("revision") or {}
        meta = self._parse_meta(revision.get("userMeta"))
        description = self._extract_description(meta, revision.get("message"))
        tags = self._extract_tags_from_meta(meta)
        modified = self._normalize_package_datetime(package_data.get("modified"))

        return Package_Info(
            name=package_data.get("name", ""),
            description=description,
            tags=tags,
            modified_date=modified,
            registry=registry,
            bucket=package_data.get("bucket", self._extract_bucket_from_registry(registry)),
            top_hash=revision.get("hash", ""),
        )

    def _transform_content_entry(self, entry: Dict[str, Any]) -> Content_Info:
        typename = entry.get("__typename") or "PackageFile"
        path = entry.get("path") or ""
        size = self._normalize_size(entry.get("size"))
        if typename == "PackageDir":
            content_type = "directory"
        else:
            content_type = "file"

        return Content_Info(
            path=path,
            size=size,
            type=content_type,
            modified_date=None,
            download_url=None,
        )

    def _entries_equal(self, entry1: Any, entry2: Any) -> bool:
        if entry1 is None or entry2 is None:
            return False
        if not isinstance(entry1, dict) or not isinstance(entry2, dict):
            return bool(entry1 == entry2)
        return (
            entry1.get("hash") == entry2.get("hash")
            and entry1.get("size") == entry2.get("size")
            and entry1.get("physicalKey") == entry2.get("physicalKey")
        )

    def _normalize_package_datetime(self, datetime_value: Any) -> str:
        if datetime_value is None:
            return "None"
        if hasattr(datetime_value, "isoformat"):
            return str(datetime_value.isoformat())
        return str(datetime_value)

    def _normalize_size(self, size: Any) -> Optional[int]:
        if size is None:
            return None
        try:
            return int(size)
        except (ValueError, TypeError):
            return None

    def _extract_description(self, meta: Optional[Dict[str, Any]], fallback: Optional[str]) -> Optional[str]:
        if isinstance(meta, dict):
            desc = meta.get("description")
            if desc is not None:
                return str(desc)
        return str(fallback) if fallback else None

    def _extract_tags_from_meta(self, meta: Optional[Dict[str, Any]]) -> List[str]:
        if not isinstance(meta, dict):
            return []
        tags = meta.get("tags") or meta.get("keywords") or []
        if isinstance(tags, list):
            return [str(tag) for tag in tags if tag is not None]
        if isinstance(tags, str):
            return [tags]
        return []

    def _parse_meta(self, meta: Any) -> Optional[Dict[str, Any]]:
        if meta is None:
            return None
        if isinstance(meta, dict):
            return meta
        if isinstance(meta, str):
            try:
                parsed = json.loads(meta)
                return parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                return None
        return None

    def _extract_bucket_from_registry(self, registry: str) -> str:
        if not registry:
            return ""
        if registry.startswith("s3://"):
            return registry.replace("s3://", "").split("/")[0]
        if registry.startswith("http://") or registry.startswith("https://"):
            return registry.split("//", 1)[-1].split("/")[0]
        return registry.split("/")[0]

    def _promote_package(self, bucket: str, name: str, hash: str, message: str, user_meta: Dict) -> str:
        """
        Promote (copy) a package to the registry bucket using packagePromote mutation.
        Returns the new package hash after promotion.
        """
        mutation = """
        mutation PackagePromote($params: PackagePushParams!, $src: PackagePromoteSource!) {
          packagePromote(params: $params, src: $src) {
            __typename
            ... on PackagePushSuccess {
              revision { hash }
            }
            ... on InvalidInput {
              errors { path message name }
            }
            ... on OperationError {
              message
              name
            }
          }
        }
        """

        variables = {
            "params": {
                "bucket": bucket,
                "name": name,
                "message": message,
                "userMeta": user_meta,
                "workflow": None,
            },
            "src": {
                "bucket": bucket,
                "name": name,
                "hash": hash,
            },
        }

        result = self.execute_graphql_query(mutation, variables=variables)
        package_promote = result.get("data", {}).get("packagePromote", {})
        typename = package_promote.get("__typename")

        if typename == "PackagePushSuccess":
            revision = package_promote.get("revision", {})
            promoted_hash = cast(str, revision.get("hash", ""))
            return promoted_hash
        elif typename == "InvalidInput":
            errors = package_promote.get("errors", [])
            error_messages = [f"{err.get('path', 'unknown')}: {err.get('message', 'invalid input')}" for err in errors]
            raise ValidationError(f"Package promotion invalid input: {'; '.join(error_messages)}")
        elif typename == "OperationError":
            message_text = package_promote.get("message", "Package promotion failed")
            raise BackendError(f"Package promotion error: {message_text}")
        else:
            raise BackendError(f"Unexpected packagePromote response type: {typename}")

    # =========================================================================
    # VALIDATION METHODS REMOVED - Now in QuiltOps base class
    # =========================================================================
    # The following methods have been removed as they are now in QuiltOps base class:
    #
    # - _validate_package_creation_inputs()   -> Now in QuiltOps._validate_package_creation_inputs()
    # - _validate_package_update_inputs()     -> Now in QuiltOps._validate_package_update_inputs()

    def _validate_package_creation_inputs_REMOVED(self, package_name: str, s3_uris: List[str]) -> None:
        import re

        if not package_name or not isinstance(package_name, str):
            raise ValidationError("Package name must be a non-empty string", {"field": "package_name"})

        if not re.match(r"^[^/]+/[^/]+$", package_name):
            raise ValidationError("Package name must be in 'user/package' format", {"field": "package_name"})

        if not s3_uris or not isinstance(s3_uris, list):
            raise ValidationError("S3 URIs must be a non-empty list", {"field": "s3_uris"})

        for i, s3_uri in enumerate(s3_uris):
            if not isinstance(s3_uri, str) or not s3_uri.startswith("s3://"):
                raise ValidationError(
                    f"Invalid S3 URI at index {i}: must start with 's3://'",
                    {"field": "s3_uris", "index": i, "uri": s3_uri},
                )
            parts = s3_uri[5:].split("/", 1)
            if len(parts) < 2 or not parts[0] or not parts[1]:
                raise ValidationError(
                    f"Invalid S3 URI at index {i}: must include bucket and key",
                    {"field": "s3_uris", "index": i, "uri": s3_uri},
                )

    def _validate_package_update_inputs(self, package_name: str, s3_uris: List[str], registry: str) -> None:
        import re

        if not package_name or not isinstance(package_name, str):
            raise ValidationError("Package name must be a non-empty string", {"field": "package_name"})

        if not re.match(r"^[^/]+/[^/]+$", package_name):
            raise ValidationError("Package name must be in 'user/package' format", {"field": "package_name"})

        if not registry or not isinstance(registry, str):
            raise ValidationError("Registry must be a non-empty string", {"field": "registry"})

        if not registry.startswith("s3://"):
            raise ValidationError("Registry must be an S3 URI starting with 's3://'", {"field": "registry"})

        if not s3_uris or not isinstance(s3_uris, list):
            raise ValidationError("S3 URIs must be a non-empty list", {"field": "s3_uris"})

        has_valid_uri = any(
            isinstance(uri, str) and uri.startswith("s3://") and "/" in uri[5:] and not uri.endswith("/")
            for uri in s3_uris
        )
        if not has_valid_uri:
            raise ValidationError(
                "No potentially valid S3 URIs found in list",
                {
                    "field": "s3_uris",
                    "note": "URIs must be strings starting with 's3://' and include bucket and key",
                },
            )

    # =========================================================================
    # TRANSFORMATION METHODS REMOVED - Now in QuiltOps base class
    # =========================================================================
    # The following methods have been removed as they are now in QuiltOps base class:
    #
    # - _extract_logical_key()    -> Now in QuiltOps._extract_logical_key()
    # - _build_catalog_url()      -> Now in QuiltOps._build_catalog_url()
