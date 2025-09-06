"""Enterprise GraphQL backend for unified search.

This backend leverages the existing Enterprise GraphQL search infrastructure
including ObjectsSearchContext and PackagesSearchContext.
"""

import json
import time
from typing import Dict, List, Any, Optional, Union
from urllib.parse import urljoin

import requests
import quilt3
from ..core.query_parser import QueryAnalysis, QueryType
from .base import (
    SearchBackend,
    BackendType,
    BackendStatus,
    SearchResult,
    BackendResponse,
)


class EnterpriseGraphQLBackend(SearchBackend):
    """GraphQL backend using existing Enterprise search contexts."""

    def __init__(self):
        super().__init__(BackendType.GRAPHQL)
        self._registry_url = None
        self._session = None
        self._check_graphql_access()

    def _check_graphql_access(self):
        """Check if GraphQL endpoint is accessible using proven infrastructure."""
        try:
            # Use the existing working GraphQL infrastructure
            from ...tools.graphql import _get_graphql_endpoint, catalog_graphql_query

            session, graphql_url = _get_graphql_endpoint()

            if not session or not graphql_url:
                self._update_status(BackendStatus.UNAVAILABLE, "GraphQL endpoint or session unavailable")
                return

            self._session = session
            self._registry_url = quilt3.session.get_registry_url()

            # Test with the working bucketConfigs query first
            test_query = "query { bucketConfigs { name } }"

            # Use the proven catalog_graphql_query function
            result = catalog_graphql_query(test_query, {})

            if result.get("success"):
                self._update_status(BackendStatus.AVAILABLE)
            else:
                error_msg = result.get("error", "Unknown GraphQL error")
                if "404" in str(error_msg):
                    self._update_status(
                        BackendStatus.UNAVAILABLE,
                        "GraphQL endpoint not available (likely not Enterprise catalog)",
                    )
                else:
                    self._update_status(BackendStatus.ERROR, f"GraphQL test failed: {error_msg}")

        except Exception as e:
            self._update_status(BackendStatus.ERROR, f"GraphQL access check failed: {e}")

    async def health_check(self) -> bool:
        """Check if GraphQL backend is healthy."""
        try:
            if not self._registry_url or not self._session:
                self._registry_url = quilt3.session.get_registry_url()
                self._session = quilt3.session.get_session()

            if not self._registry_url or not self._session:
                self._update_status(BackendStatus.UNAVAILABLE, "No GraphQL endpoint available")
                return False

            # Test with the working bucketConfigs query
            from ...tools.graphql import catalog_graphql_query

            test_query = "query { bucketConfigs { name } }"
            result = catalog_graphql_query(test_query, {})

            if result.get("success"):
                self._update_status(BackendStatus.AVAILABLE)
                return True
            else:
                error_msg = result.get("error", "Unknown GraphQL error")
                self._update_status(BackendStatus.ERROR, f"GraphQL health check failed: {error_msg}")
                return False

        except Exception as e:
            self._update_status(BackendStatus.ERROR, f"GraphQL health check error: {e}")
            return False

    async def search(
        self,
        query: str,
        scope: str = "global",
        target: str = "",
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
    ) -> BackendResponse:
        """Execute search using Enterprise GraphQL."""
        start_time = time.time()

        if self.status != BackendStatus.AVAILABLE:
            return BackendResponse(
                backend_type=self.backend_type,
                status=self.status,
                results=[],
                error_message=self.last_error,
            )

        try:
            if scope == "bucket" and target:
                results = await self._search_bucket_objects(query, target, filters, limit)
            elif scope == "package" and target:
                results = await self._search_package_contents(query, target, filters, limit)
            else:
                # Global/catalog search - search both objects and packages
                object_results = await self._search_objects_global(query, filters, limit // 2)
                package_results = await self._search_packages_global(query, filters, limit // 2)
                results = object_results + package_results

            query_time = (time.time() - start_time) * 1000

            return BackendResponse(
                backend_type=self.backend_type,
                status=BackendStatus.AVAILABLE,
                results=results,
                total=len(results),
                query_time_ms=query_time,
            )

        except Exception as e:
            query_time = (time.time() - start_time) * 1000

            return BackendResponse(
                backend_type=self.backend_type,
                status=BackendStatus.ERROR,
                results=[],
                query_time_ms=query_time,
                error_message=str(e),
            )

    async def _search_bucket_objects(
        self, query: str, bucket: str, filters: Optional[Dict[str, Any]], limit: int
    ) -> List[SearchResult]:
        """Search objects within a specific bucket using GraphQL."""
        # Use the same GraphQL query pattern as the working bucket_objects_search_graphql
        graphql_query = """
        query SearchBucketObjects($bucket: String!, $filter: ObjectFilterInput, $first: Int!) {
            objects(bucket: $bucket, filter: $filter, first: $first) {
                edges {
                    node {
                        key
                        size
                        updated
                        contentType
                        extension
                        package {
                            name
                            topHash
                            tag
                        }
                    }
                    cursor
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
        """

        # Build filter from query and filters
        object_filter = self._build_graphql_filter(query, filters)

        variables = {
            "bucket": bucket.replace("s3://", ""),
            "filter": object_filter,
            "first": limit,
        }

        result = await self._execute_graphql_query(graphql_query, variables)

        if result.get("errors"):
            raise Exception(f"GraphQL errors: {result['errors']}")

        return self._convert_bucket_objects_results(result, bucket)

    async def _search_packages_global(
        self, query: str, filters: Optional[Dict[str, Any]], limit: int
    ) -> List[SearchResult]:
        """Search packages globally using Enterprise GraphQL searchPackages."""
        # Use working searchPackages query (total only - firstPage has server errors)
        # Based on Enterprise schema: PackagesSearchResult union type
        graphql_query = """
        query SearchPackages($searchString: String!) {
            searchPackages(buckets: [], searchString: $searchString) {
                ... on PackagesSearchResultSet {
                    total
                    stats {
                        modified {
                            min
                            max
                        }
                        size {
                            min
                            max
                            sum
                        }
                    }
                }
                ... on EmptySearchResultSet {
                    _
                }
            }
        }
        """

        # Simplified variables
        variables = {"searchString": query}

        try:
            result = await self._execute_graphql_query(graphql_query, variables)

            if result.get("errors"):
                raise Exception(f"GraphQL errors: {result['errors']}")

            # Extract rich metadata from working searchPackages query
            data = result.get("data", {})
            search_result = data.get("searchPackages", {})
            total = search_result.get("total", 0)
            stats = search_result.get("stats", {})

            if total > 0:
                # Create meaningful result with statistics from GraphQL
                size_stats = stats.get("size", {})
                modified_stats = stats.get("modified", {})

                description_parts = [f"Found {total} packages"]
                if size_stats.get("sum"):
                    total_gb = size_stats["sum"] / (1024**3)
                    description_parts.append(f"Total size: {total_gb:.1f} GB")
                if modified_stats.get("min") and modified_stats.get("max"):
                    description_parts.append(
                        f"Date range: {modified_stats['min'][:10]} to {modified_stats['max'][:10]}"
                    )

                return [
                    SearchResult(
                        id=f"graphql-packages-{query}",
                        type="package_summary",
                        title=f"{total} packages matching '{query}'",
                        description=" | ".join(description_parts),
                        metadata={
                            "total_packages": total,
                            "search_query": query,
                            "stats": stats,
                            "size_sum_bytes": size_stats.get("sum"),
                            "size_min_bytes": size_stats.get("min"),
                            "size_max_bytes": size_stats.get("max"),
                            "modified_min": modified_stats.get("min"),
                            "modified_max": modified_stats.get("max"),
                        },
                        score=1.0,
                        backend="graphql",
                    )
                ]
            else:
                return []

        except Exception as e:
            # Fallback: try simple bucketConfigs if searchPackages fails
            try:
                bucketconfigs_query = "query { bucketConfigs { name } }"
                fallback_result = await self._execute_graphql_query(bucketconfigs_query, {})
                return self._convert_bucketconfigs_to_packages(fallback_result, query, limit)
            except Exception:
                return []

    async def _search_objects_global(
        self, query: str, filters: Optional[Dict[str, Any]], limit: int
    ) -> List[SearchResult]:
        """Search objects globally using Enterprise GraphQL searchObjects (expensive but valuable)."""
        # Use the proper Enterprise searchObjects query with rich filtering
        graphql_query = """
        query SearchObjects($buckets: [String!], $searchString: String, $filter: ObjectsSearchFilter) {
            searchObjects(buckets: $buckets, searchString: $searchString, filter: $filter) {
                ... on ObjectsSearchResultSet {
                    total
                    stats {
                        modified {
                            min
                            max
                        }
                        size {
                            min
                            max
                            sum
                        }
                        ext {
                            buckets {
                                key
                                docCount
                            }
                        }
                    }
                }
                ... on EmptySearchResultSet {
                    _
                }
            }
        }
        """

        # Build comprehensive filter from our parsed filters
        object_filter = {}
        if filters:
            if filters.get("file_extensions"):
                object_filter["ext"] = {"terms": filters["file_extensions"]}
            if filters.get("size_min") or filters.get("size_max"):
                size_filter = {}
                if filters.get("size_min"):
                    size_filter["gte"] = filters["size_min"]
                if filters.get("size_max"):
                    size_filter["lte"] = filters["size_max"]
                object_filter["size"] = size_filter

        variables = {
            "buckets": [],  # Search all accessible buckets
            "searchString": query,
            "filter": object_filter,
        }

        try:
            result = await self._execute_graphql_query(graphql_query, variables)

            if result.get("errors"):
                raise Exception(f"GraphQL errors: {result['errors']}")

            return self._convert_objects_search_results(result, query)

        except Exception as e:
            # For expensive object queries, we expect some may timeout or fail
            # Log the attempt but don't fail the entire search
            return []

    async def _search_package_contents(
        self,
        query: str,
        package_name: str,
        filters: Optional[Dict[str, Any]],
        limit: int,
    ) -> List[SearchResult]:
        """Search within a specific package using GraphQL."""
        # This would require package-specific GraphQL queries
        # For now, return empty results as this is complex to implement without full schema
        return []

    def _build_graphql_filter(self, query: str, filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Build GraphQL filter object from query and filters."""
        graphql_filter = {}

        # Add key-based search if query contains terms
        if query and query.strip():
            # For simple text queries, use key_contains
            graphql_filter["key_contains"] = query

        # Add file extension filters
        if filters and filters.get("file_extensions"):
            # Use extension filter if available
            if len(filters["file_extensions"]) == 1:
                graphql_filter["extension"] = filters["file_extensions"][0]
            else:
                # For multiple extensions, use key pattern matching
                ext_patterns = [f"*.{ext}" for ext in filters["file_extensions"]]
                graphql_filter["key_contains"] = " OR ".join(ext_patterns)

        # Add size filters
        if filters:
            if filters.get("size_min"):
                graphql_filter["size_gte"] = filters["size_min"]
            if filters.get("size_max"):
                graphql_filter["size_lte"] = filters["size_max"]

        return graphql_filter

    async def _execute_graphql_query(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a GraphQL query using the proven catalog_graphql_query approach."""
        # Use the existing working GraphQL infrastructure (synchronous)
        from ...tools.graphql import catalog_graphql_query

        # catalog_graphql_query is synchronous, so we can call it directly
        result = catalog_graphql_query(query, variables)

        if not result.get("success"):
            # Unpack detailed error information for better troubleshooting
            error_details = []

            if result.get("error"):
                error_details.append(f"Error: {result['error']}")

            if result.get("errors"):
                for error in result["errors"]:
                    error_msg = error.get("message", "Unknown error")
                    error_path = " -> ".join(error.get("path", []))
                    error_location = error.get("locations", [{}])[0]
                    location_str = f"line {error_location.get('line', '?')}, col {error_location.get('column', '?')}"

                    error_details.append(f"GraphQL Error: {error_msg} (path: {error_path}, location: {location_str})")

            detailed_error = "; ".join(error_details) if error_details else "Unknown GraphQL error"
            raise Exception(f"GraphQL query failed: {detailed_error}")

        # Return in the expected format for our async interface
        return {"data": result.get("data"), "errors": result.get("errors")}

    def _convert_bucket_objects_results(self, graphql_result: Dict[str, Any], bucket: str) -> List[SearchResult]:
        """Convert GraphQL bucket objects results to standard format."""
        results = []

        # Use the same result structure as bucket_objects_search_graphql
        data = graphql_result.get("data", {})
        objects = data.get("objects", {})
        edges = objects.get("edges", [])

        for edge in edges:
            if not isinstance(edge, dict):
                continue

            node = edge.get("node", {})

            # Extract package information if available
            package_info = node.get("package", {})
            package_name = package_info.get("name") if package_info else None

            result = SearchResult(
                id=f"graphql-object-{node.get('key', '')}",
                type="file",
                title=(node.get("key", "").split("/")[-1] if node.get("key") else "Unknown"),
                description=f"Object in {bucket}" + (f" (package: {package_name})" if package_name else ""),
                s3_uri=f"s3://{bucket.replace('s3://', '')}/{node.get('key', '')}",
                package_name=package_name,
                logical_key=node.get("key"),
                size=node.get("size"),
                last_modified=node.get("updated"),  # GraphQL uses 'updated' not 'lastModified'
                metadata={
                    "bucket": bucket,
                    "content_type": node.get("contentType"),
                    "extension": node.get("extension"),
                    "package": package_info,
                },
                score=1.0,  # GraphQL doesn't provide relevance scores
                backend="graphql",
            )

            results.append(result)

        return results

    def _convert_packages_results(self, graphql_result: Dict[str, Any]) -> List[SearchResult]:
        """Convert GraphQL packages results to standard format."""
        results = []

        data = graphql_result.get("data", {})
        packages = data.get("packages", {})
        edges = packages.get("edges", [])

        for edge in edges:
            node = edge.get("node", {})

            result = SearchResult(
                id=f"graphql-package-{node.get('name', '')}",
                type="package",
                title=node.get("name", ""),
                description=f"Quilt package: {node.get('name', '')}",
                package_name=node.get("name"),
                size=node.get("totalBytes"),
                last_modified=node.get("lastModified"),
                metadata={
                    "total_entries": node.get("totalEntries"),
                    "total_bytes": node.get("totalBytes"),
                    "package_metadata": node.get("metadata", {}),
                },
                score=1.0,  # GraphQL doesn't provide relevance scores
                backend="graphql",
            )

            results.append(result)

        return results

    def _convert_objects_results(self, graphql_result: Dict[str, Any]) -> List[SearchResult]:
        """Convert GraphQL objects results to standard format."""
        results = []

        data = graphql_result.get("data", {})
        objects = data.get("objects", {})
        edges = objects.get("edges", [])

        for edge in edges:
            node = edge.get("node", {})

            result = SearchResult(
                id=f"graphql-object-{node.get('key', '')}",
                type="file",
                title=(node.get("key", "").split("/")[-1] if node.get("key") else "Unknown"),
                description=f"Object in {node.get('bucket', 'unknown bucket')}",
                s3_uri=f"s3://{node.get('bucket', '')}/{node.get('key', '')}",
                package_name=node.get("packageName"),
                logical_key=node.get("logicalKey") or node.get("key"),
                size=node.get("size"),
                last_modified=node.get("lastModified"),
                metadata={
                    "bucket": node.get("bucket"),
                    "package_name": node.get("packageName"),
                    "logical_key": node.get("logicalKey"),
                },
                score=1.0,
                backend="graphql",
            )

            results.append(result)

        return results

    def _convert_bucketconfigs_to_packages(
        self, graphql_result: Dict[str, Any], query: str, limit: int
    ) -> List[SearchResult]:
        """Convert bucketConfigs results to package-like results for compatibility."""
        results = []

        data = graphql_result.get("data", {})
        bucket_configs = data.get("bucketConfigs", [])

        # Filter bucket configs based on query
        query_lower = query.lower()
        matching_buckets = []

        for bucket_config in bucket_configs:
            bucket_name = bucket_config.get("name", "")
            if not query_lower or query_lower in bucket_name.lower():
                matching_buckets.append(bucket_config)

        # Convert to SearchResult format
        for i, bucket_config in enumerate(matching_buckets[:limit]):
            bucket_name = bucket_config.get("name", "")

            result = SearchResult(
                id=f"graphql-bucket-{bucket_name}",
                type="bucket",
                title=bucket_name,
                description=f"Quilt bucket: {bucket_name}",
                s3_uri=f"s3://{bucket_name}",
                metadata={"bucket_name": bucket_name, "source": "bucketConfigs"},
                score=1.0 - (i * 0.1),  # Simple relevance scoring
                backend="graphql",
            )

            results.append(result)

        return results

    def _build_packages_filter(self, filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Build PackagesSearchFilter from parsed filters."""
        if not filters:
            return {}

        packages_filter = {}

        # Date filters
        if filters.get("created_after") or filters.get("created_before"):
            modified_filter = {}
            if filters.get("created_after"):
                modified_filter["gte"] = filters["created_after"]
            if filters.get("created_before"):
                modified_filter["lte"] = filters["created_before"]
            packages_filter["modified"] = modified_filter

        # Size filters
        if filters.get("size_min") or filters.get("size_max"):
            size_filter = {}
            if filters.get("size_min"):
                size_filter["gte"] = filters["size_min"]
            if filters.get("size_max"):
                size_filter["lte"] = filters["size_max"]
            packages_filter["size"] = size_filter

        return packages_filter

    def _build_user_meta_filters(self, filters: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build user metadata filters for package search."""
        if not filters:
            return []

        user_meta_filters = []

        # Example: quality_score > 0.8
        if filters.get("quality_score_min"):
            user_meta_filters.append(
                {
                    "path": "quality_score",
                    "number": {"gte": filters["quality_score_min"]},
                }
            )

        return user_meta_filters

    def _convert_packages_search_results(self, graphql_result: Dict[str, Any]) -> List[SearchResult]:
        """Convert searchPackages GraphQL results to standard format."""
        results = []

        data = graphql_result.get("data", {})
        search_packages = data.get("searchPackages", {})

        # Handle union type response
        if search_packages.get("total") is not None:
            # PackagesSearchResultSet
            first_page = search_packages.get("firstPage", {})
            hits = first_page.get("hits", [])

            for hit in hits:
                # Extract rich package metadata from SearchHitPackage
                result = SearchResult(
                    id=hit.get("id", ""),
                    type="package",
                    title=hit.get("name", ""),
                    description=hit.get("comment", f"Package: {hit.get('name', 'Unknown')}"),
                    package_name=hit.get("name"),
                    size=hit.get("size"),
                    last_modified=hit.get("modified"),
                    metadata={
                        "bucket": hit.get("bucket"),
                        "hash": hit.get("hash"),
                        "pointer": hit.get("pointer"),
                        "total_entries": hit.get("totalEntriesCount"),
                        "comment": hit.get("comment"),
                        "workflow": hit.get("workflow"),
                        "meta": hit.get("meta"),  # Full metadata JSON
                    },
                    score=hit.get("score", 0.0),
                    backend="graphql",
                )

                results.append(result)

        return results

    def _convert_objects_search_results(self, graphql_result: Dict[str, Any], query: str) -> List[SearchResult]:
        """Convert searchObjects GraphQL results to standard format."""
        results = []

        data = graphql_result.get("data", {})
        search_objects = data.get("searchObjects", {})

        # Handle union type response
        if search_objects.get("total") is not None:
            # ObjectsSearchResultSet
            total = search_objects["total"]
            stats = search_objects.get("stats", {})

            # Create a summary result with rich statistics
            size_stats = stats.get("size", {})
            modified_stats = stats.get("modified", {})
            ext_stats = stats.get("ext", {})

            description_parts = [f"Found {total} objects"]
            if size_stats.get("sum"):
                total_gb = size_stats["sum"] / (1024**3)
                description_parts.append(f"Total size: {total_gb:.1f} GB")

            # Add file extension breakdown
            if ext_stats.get("buckets"):
                ext_breakdown = ext_stats["buckets"][:3]  # Top 3 extensions
                ext_summary = ", ".join([f"{ext['key']}: {ext['docCount']}" for ext in ext_breakdown])
                description_parts.append(f"Top types: {ext_summary}")

            result = SearchResult(
                id=f"graphql-objects-{query}",
                type="object_summary",
                title=f"{total} objects matching '{query}'",
                description=" | ".join(description_parts),
                metadata={
                    "total_objects": total,
                    "search_query": query,
                    "stats": stats,
                    "size_sum_bytes": size_stats.get("sum"),
                    "size_min_bytes": size_stats.get("min"),
                    "size_max_bytes": size_stats.get("max"),
                    "modified_min": modified_stats.get("min"),
                    "modified_max": modified_stats.get("max"),
                    "extension_breakdown": ext_stats.get("buckets", []),
                },
                score=1.0,
                backend="graphql",
            )

            results.append(result)

        return results
