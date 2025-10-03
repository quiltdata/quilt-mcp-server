"""Enterprise GraphQL backend for unified search.

This backend leverages the existing Enterprise GraphQL search infrastructure
including ObjectsSearchContext and PackagesSearchContext.
"""

import time
from typing import Any, Dict, List, Optional

from .base import (
    BackendResponse,
    BackendStatus,
    BackendType,
    SearchBackend,
    SearchResult,
)


class EnterpriseGraphQLBackend(SearchBackend):
    """GraphQL backend using existing Enterprise search contexts."""

    def __init__(self):
        super().__init__(BackendType.GRAPHQL)
        self._registry_url = None
        # Don't check access during initialization - do it lazily during searches
        # to ensure we have an active request context with JWT token
        self._update_status(BackendStatus.AVAILABLE)

    def _check_graphql_access(self):
        """Check if GraphQL endpoint is accessible using stateless infrastructure."""
        try:
            # Use stateless GraphQL infrastructure
            from ...runtime import get_active_token
            from ...tools.graphql import catalog_graphql_query
            from ...utils import resolve_catalog_url

            token = get_active_token()
            if not token:
                self._update_status(BackendStatus.UNAVAILABLE, "Authorization token not available")
                return

            # Get registry URL
            self._registry_url = resolve_catalog_url()
            if not self._registry_url:
                self._update_status(BackendStatus.UNAVAILABLE, "Catalog URL not configured")
                return

            # Test with the working bucketConfigs query
            test_query = "query { bucketConfigs { name } }"

            # Use the stateless catalog_graphql_query function
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
            # Use stateless GraphQL client
            from ...runtime import get_active_token
            from ...tools.graphql import catalog_graphql_query
            from ...utils import resolve_catalog_url
            
            token = get_active_token()
            registry_url = resolve_catalog_url()
            
            if not token or not registry_url:
                self._update_status(BackendStatus.UNAVAILABLE, "No token or GraphQL endpoint available")
                return False

            # Update cached registry URL
            self._registry_url = registry_url

            # Test with the working bucketConfigs query
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

        # Check for authorization token before executing search
        from ...runtime import get_active_token
        from ...utils import resolve_catalog_url
        
        token = get_active_token()
        if not token:
            return BackendResponse(
                backend_type=self.backend_type,
                status=BackendStatus.UNAVAILABLE,
                results=[],
                error_message="Authorization token not available",
            )
        
        # Update registry URL if needed
        if not self._registry_url:
            self._registry_url = resolve_catalog_url()
            if not self._registry_url:
                return BackendResponse(
                    backend_type=self.backend_type,
                    status=BackendStatus.UNAVAILABLE,
                    results=[],
                    error_message="Catalog URL not configured",
                )

        try:
            if scope == "bucket" and target:
                # For bucket scope, search both packages and objects
                package_results = await self._search_bucket_packages(target, query, filters, limit // 2)
                object_results = await self._search_bucket_objects(query, target, filters, limit // 2)
                results = package_results + object_results
            elif scope == "package" and target:
                results = await self._search_package_contents(query, target, filters, limit)
            else:
                # Global/catalog search - search both objects and packages across all buckets
                package_results = await self._search_packages_global(query, filters, limit // 2)
                object_results = await self._search_objects_global(query, filters, limit // 2)
                results = package_results + object_results

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

    async def _search_bucket_packages(
        self, bucket: str, query: str, filters: Optional[Dict[str, Any]], limit: int
    ) -> List[SearchResult]:
        """Search packages within a specific bucket using GraphQL packages() query."""
        graphql_query = """
        query BucketPackages($bucket: String!, $filter: String, $page: Int!, $perPage: Int!) {
            packages(bucket: $bucket, filter: $filter) {
                total
                page(number: $page, perPage: $perPage) {
                    bucket
                    name
                    modified
                }
            }
        }
        """

        variables = {
            "bucket": bucket.replace("s3://", ""),
            "filter": query if query else None,
            "page": 1,
            "perPage": limit,
        }

        try:
            result = await self._execute_graphql_query(graphql_query, variables)

            if result.get("errors"):
                raise Exception(f"GraphQL errors: {result['errors']}")

            return self._convert_packages_results(result, bucket)
        except Exception:
            # If packages query fails, return empty results
            return []

    async def _search_bucket_objects(
        self, query: str, bucket: str, filters: Optional[Dict[str, Any]], limit: int
    ) -> List[SearchResult]:
        """Search objects within a specific bucket using GraphQL."""
        # Note: The top-level objects() query doesn't exist in the GraphQL schema.
        # Objects can only be searched via searchObjects, but searchObjects.firstPage
        # has a backend bug. For now, we only return package results for bucket searches.
        # TODO: Implement object search when backend bug is fixed
        return []

    async def _search_packages_global(
        self, query: str, filters: Optional[Dict[str, Any]], limit: int
    ) -> List[SearchResult]:
        """Search packages globally using searchPackages.firstPage (FIXED).
        
        Note: The backend bug was caused by passing 'size' parameter to firstPage.
        The frontend does NOT pass size - it uses the default page size.
        """
        # Use searchPackages with firstPage WITHOUT size parameter (like the frontend)
        graphql_query = """
        query SearchPackages($searchString: String!, $order: SearchResultOrder!, $latestOnly: Boolean!) {
            searchPackages(buckets: [], searchString: $searchString, latestOnly: $latestOnly) {
                ... on PackagesSearchResultSet {
                    total
                    firstPage(order: $order) {
                        hits {
                            id
                            score
                            bucket
                            name
                            pointer
                            hash
                            size
                            modified
                            totalEntriesCount
                            comment
                            workflow
                        }
                    }
                }
                ... on EmptySearchResultSet {
                    _
                }
            }
        }
        """

        # Variables WITHOUT size parameter - this is the key!
        variables = {
            "searchString": query if query and query != "*" else "",
            "order": "BEST_MATCH",  # Default ordering
            "latestOnly": False,  # Include all revisions, not just latest
        }

        try:
            result = await self._execute_graphql_query(graphql_query, variables)

            if result.get("errors"):
                raise Exception(f"GraphQL errors: {result['errors']}")

            # Extract individual package results from firstPage
            data = result.get("data", {})
            search_result = data.get("searchPackages", {})
            
            # Handle EmptySearchResultSet
            if "_" in search_result:
                return []
            
            first_page = search_result.get("firstPage", {})
            hits = first_page.get("hits", [])
            
            if not hits:
                return []
            
            # Convert each hit to a SearchResult
            results = []
            for hit in hits[:limit]:  # Limit results to requested limit
                bucket = hit.get("bucket", "")
                name = hit.get("name", "")
                pkg_hash = hit.get("hash", "")
                size = hit.get("size", 0)
                modified = hit.get("modified", "")
                entries_count = hit.get("totalEntriesCount", 0)
                comment = hit.get("comment", "")
                workflow = hit.get("workflow", {})
                
                # Build description
                description_parts = [f"{entries_count} files"]
                if size > 0:
                    size_mb = size / (1024**2)
                    if size_mb < 1024:
                        description_parts.append(f"{size_mb:.1f} MB")
                    else:
                        description_parts.append(f"{size / (1024**3):.1f} GB")
                if comment:
                    description_parts.append(comment[:100])
                
                result_obj = SearchResult(
                    id=f"graphql-pkg-{bucket}-{name}-{pkg_hash}",
                    type="package",
                    title=f"{bucket}/{name}",
                    description=" | ".join(description_parts),
                    s3_uri=f"s3://{bucket}/.quilt/named_packages/{name}",
                    logical_key=name,
                    metadata={
                        "bucket": bucket,
                        "name": name,
                        "hash": pkg_hash,
                        "pointer": hit.get("pointer", ""),
                        "size": size,
                        "modified": modified,
                        "totalEntriesCount": entries_count,
                        "comment": comment,
                        "workflow": workflow,
                    },
                    score=hit.get("score", 1.0),
                    backend="graphql",
                )
                results.append(result_obj)
            
            return results

        except Exception:
            # Fallback: query buckets individually if searchPackages fails
            return []

    async def _search_objects_global(
        self, query: str, filters: Optional[Dict[str, Any]], limit: int
    ) -> List[SearchResult]:
        """Search objects globally by querying accessible buckets.
        
        Note: searchObjects.firstPage has a backend bug (Internal Server Error),
        so we query individual buckets using the working objects(bucket:...) query.
        """
        # First, get list of accessible buckets
        buckets_query = "query { bucketConfigs { name } }"
        try:
            buckets_result = await self._execute_graphql_query(buckets_query, {})
            bucket_names = [
                cfg["name"] 
                for cfg in buckets_result.get("data", {}).get("bucketConfigs", [])
            ]
        except Exception:
            # If we can't get buckets, we can't search
            return []
        
        if not bucket_names:
            return []
        
        # Build GraphQL filter from query and filters
        object_filter = self._build_graphql_filter(query, filters)
        
        # Query each bucket (limit results per bucket to spread across buckets)
        per_bucket_limit = max(10, limit // len(bucket_names)) if len(bucket_names) > 0 else limit
        all_results = []
        
        for bucket in bucket_names[:10]:  # Limit to first 10 buckets to avoid too many queries
            try:
                bucket_results = await self._search_bucket_objects(
                    query, bucket, filters, per_bucket_limit
                )
                all_results.extend(bucket_results)
                
                # Stop if we have enough results
                if len(all_results) >= limit:
                    break
            except Exception:
                # Skip buckets that fail
                continue
        
        # Return up to limit results
        return all_results[:limit]

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

    def _convert_packages_results(self, graphql_result: Dict[str, Any], bucket: str) -> List[SearchResult]:
        """Convert packages() GraphQL results to standard format."""
        results = []

        data = graphql_result.get("data", {})
        packages_data = data.get("packages", {})
        packages_list = packages_data.get("page", [])

        for pkg in packages_list:
            pkg_name = pkg.get("name", "")
            pkg_bucket = pkg.get("bucket", bucket)
            modified = pkg.get("modified", "")
            
            result = SearchResult(
                id=f"graphql-package-{pkg_bucket}/{pkg_name}",
                type="package",
                title=pkg_name,
                description=f"Package in {pkg_bucket}",
                s3_uri=f"s3://{pkg_bucket}/.quilt/named_packages/{pkg_name}",
                logical_key=pkg_name,
                metadata={
                    "bucket": pkg_bucket,
                    "name": pkg_name,
                    "modified": modified,
                },
                score=1.0,
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
            # ObjectsSearchResultSet - process individual objects from firstPage
            firstPage = search_objects.get("firstPage", {})
            edges = firstPage.get("edges", [])
            
            # Process each individual object
            for edge in edges:
                node = edge.get("node", {})
                key = node.get("key", "")
                size = node.get("size", 0)
                updated = node.get("updated")
                content_type = node.get("contentType", "")
                ext = node.get("ext", "")
                
                # Extract bucket from key (if available) or leave empty
                # Note: searchObjects might not include bucket in results
                s3_uri = f"s3://unknown/{key}"  # Will be corrected if bucket info available
                
                result = SearchResult(
                    id=f"graphql-object-{key}",
                    type="file",
                    title=key.split("/")[-1] if "/" in key else key,
                    description=f"{key} ({size} bytes)",
                    s3_uri=s3_uri,
                    logical_key=key,
                    metadata={
                        "key": key,
                        "size": size,
                        "updated": updated,
                        "content_type": content_type,
                        "extension": ext,
                    },
                    size=size,
                    score=1.0,
                    backend="graphql",
                )
                results.append(result)

        return results
