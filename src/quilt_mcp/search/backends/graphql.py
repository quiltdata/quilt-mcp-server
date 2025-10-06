"""Enterprise GraphQL backend for unified search.

This backend leverages the existing Enterprise GraphQL search infrastructure
including ObjectsSearchContext and PackagesSearchContext.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .base import (
    BackendResponse,
    BackendStatus,
    BackendType,
    SearchBackend,
    SearchResult,
)


OBJECT_EXTENSION_KEYWORDS = {
    "csv",
    "tsv",
    "json",
    "jsonl",
    "parquet",
    "txt",
    "md",
    "markdown",
    "yaml",
    "yml",
    "npy",
    "npz",
    "tiff",
    "tif",
    "png",
    "jpg",
    "jpeg",
    "log",
}


@dataclass
class ObjectSearchResponse:
    """Normalized payload for object search results."""

    results: List[SearchResult]
    total: Optional[int] = None
    stats: Dict[str, Any] = field(default_factory=dict)
    next_cursor: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None


@dataclass
class PackageSearchResponse:
    """Normalized payload for package search results."""

    results: List[SearchResult]
    total: Optional[int] = None
    stats: Dict[str, Any] = field(default_factory=dict)
    next_cursor: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None


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
        search_type: str = "auto",  # "auto", "packages", "objects", "both"
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
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

        object_payloads: List[ObjectSearchResponse] = []
        package_payloads: List[PackageSearchResponse] = []
        total_count: Optional[int] = None

        try:
            # Determine search strategy based on search_type
            if search_type == "packages":
                if scope == "bucket" and target:
                    results = await self._search_bucket_packages(target, query, filters, limit, offset)
                    total_count = len(results)
                elif scope == "package" and target:
                    results = await self._search_package_contents(query, target, filters, limit)
                    total_count = len(results)
                else:
                    package_payload = await self._search_packages_global(query, filters, limit, offset)
                    if isinstance(package_payload, PackageSearchResponse):
                        package_payloads.append(package_payload)
                        results = package_payload.results
                        total_count = package_payload.total if package_payload.total is not None else len(results)
                    else:
                        results = package_payload  # type: ignore[assignment]
                        total_count = len(results)
            elif search_type == "objects":
                obj_payload = await self._resolve_object_search(query, scope, target, filters, limit, offset)
                if isinstance(obj_payload, ObjectSearchResponse):
                    object_payloads.append(obj_payload)
                    results = obj_payload.results
                    total_count = obj_payload.total if obj_payload.total is not None else len(results)
                else:
                    results = obj_payload
                    total_count = len(results)
            elif search_type == "both":
                if scope == "bucket" and target:
                    package_results = await self._search_bucket_packages(
                        target, query, filters, limit // 2, offset // 2
                    )
                    object_payload = await self._search_objects_global(
                        query, filters, limit // 2, buckets=[target], offset=offset // 2
                    )
                elif scope == "package" and target:
                    package_results = await self._search_package_contents(query, target, filters, limit)
                    object_payload = ObjectSearchResponse(results=[])
                else:
                    package_payload = await self._search_packages_global(query, filters, limit // 2, offset // 2)
                    if isinstance(package_payload, PackageSearchResponse):
                        package_payloads.append(package_payload)
                        package_results = package_payload.results
                    else:
                        package_results = package_payload  # type: ignore[assignment]
                    object_payload = await self._search_objects_global(query, filters, limit // 2, offset=offset // 2)

                if isinstance(object_payload, ObjectSearchResponse):
                    object_payloads.append(object_payload)
                    object_results = object_payload.results
                else:
                    object_results = object_payload
                results = package_results + object_results
                total_count = len(results)
            else:  # search_type == "auto"
                is_file_query = self._is_file_or_object_query(query)
                if is_file_query:
                    obj_payload = await self._resolve_object_search(query, scope, target, filters, limit, offset)
                    if isinstance(obj_payload, ObjectSearchResponse):
                        object_payloads.append(obj_payload)
                        results = obj_payload.results
                        total_count = obj_payload.total if obj_payload.total is not None else len(results)
                    else:
                        results = obj_payload
                        total_count = len(results)
                else:
                    if scope == "bucket" and target:
                        results = await self._search_bucket_packages(target, query, filters, limit, offset)
                        total_count = len(results)
                    elif scope == "package" and target:
                        results = await self._search_package_contents(query, target, filters, limit)
                        total_count = len(results)
                    else:
                        package_payload = await self._search_packages_global(query, filters, limit, offset)
                        if isinstance(package_payload, PackageSearchResponse):
                            package_payloads.append(package_payload)
                            results = package_payload.results
                            total_count = package_payload.total if package_payload.total is not None else len(results)
                        else:
                            results = package_payload  # type: ignore[assignment]
                            total_count = len(results)

            if results is None:
                results = []

            if total_count is None:
                total_count = len(results)

            raw_metadata: Dict[str, Any] = {}
            if object_payloads:
                ext_counter: Dict[str, int] = {}
                totals: List[int] = []
                next_cursor: Optional[str] = None

                for payload in object_payloads:
                    stats_ext = (payload.stats or {}).get("ext") or []
                    for facet in stats_ext:
                        key = facet.get("key")
                        count = facet.get("count", 0)
                        if key:
                            ext_counter[key] = ext_counter.get(key, 0) + int(count or 0)
                    if payload.total is not None:
                        totals.append(payload.total)
                    if payload.next_cursor:
                        next_cursor = payload.next_cursor

                sorted_exts = sorted(ext_counter.items(), key=lambda item: item[1], reverse=True)
                raw_metadata["objects"] = {
                    "ext_stats": [{"key": key, "count": value} for key, value in sorted_exts],
                    "total": max(totals) if totals else None,
                    "next_cursor": next_cursor,
                }

            if package_payloads:
                totals: List[int] = []
                next_cursor: Optional[str] = None
                stats: Optional[Dict[str, Any]] = None

                for payload in package_payloads:
                    if payload.total is not None:
                        totals.append(payload.total)
                    if payload.next_cursor:
                        next_cursor = payload.next_cursor
                    if payload.raw and not stats:
                        stats = payload.raw.get("stats")

                raw_metadata["packages"] = {
                    "total": max(totals) if totals else None,
                    "next_cursor": next_cursor,
                    "stats": stats,
                }

            query_time = (time.time() - start_time) * 1000

            return BackendResponse(
                backend_type=self.backend_type,
                status=BackendStatus.AVAILABLE,
                results=results,
                total=total_count,
                query_time_ms=query_time,
                raw_response=raw_metadata or None,
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

    def _is_file_or_object_query(self, query: str) -> bool:
        """Detect if a query is likely for files/objects vs packages/collections."""
        query_lower = query.lower()

        # File extension patterns
        file_extensions = [
            '.csv',
            '.json',
            '.parquet',
            '.tsv',
            '.txt',
            '.md',
            '.py',
            '.r',
            '.ipynb',
            '.h5',
            '.hdf5',
            '.zarr',
            '.nc',
            '.tif',
            '.tiff',
            '.png',
            '.jpg',
            '.jpeg',
        ]

        # File-specific keywords
        file_keywords = ['file', 'files', 'object', 'objects', 'data file', 'dataset file', 'readme', 'config']

        # Package/collection keywords
        package_keywords = [
            'package',
            'packages',
            'dataset',
            'datasets',
            'collection',
            'collections',
            'project',
            'projects',
            'experiment',
            'experiments',
            'study',
            'studies',
        ]

        # Check for file extensions
        if any(ext in query_lower for ext in file_extensions):
            return True

        # Check for wildcard patterns (like *.csv)
        if '*' in query or 'wildcard' in query_lower:
            return True

        # Check for file-specific keywords
        if any(keyword in query_lower for keyword in file_keywords):
            return True

        # Check for package-specific keywords
        if any(keyword in query_lower for keyword in package_keywords):
            return False

        # Default to package-oriented search for ambiguous queries to surface datasets
        return False

    async def _search_bucket_packages(
        self, bucket: str, query: str, filters: Optional[Dict[str, Any]], limit: int, offset: int = 0
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

        # Calculate page number from offset
        page = (offset // limit) + 1

        variables = {
            "bucket": bucket.replace("s3://", ""),
            "filter": query if query else None,
            "page": page,
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

    async def _resolve_object_search(
        self,
        query: str,
        scope: str,
        target: str,
        filters: Optional[Dict[str, Any]],
        limit: int,
        offset: int,
    ) -> ObjectSearchResponse | List[SearchResult]:
        """Route object searches according to scope and target."""

        if scope == "bucket" and target:
            return await self._search_objects_global(query, filters, limit, buckets=[target], offset=offset)

        if scope == "package" and target:
            return await self._search_package_contents(query, target, filters, limit)

        return await self._search_objects_global(query, filters, limit, offset=offset)

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
        self, query: str, filters: Optional[Dict[str, Any]], limit: int, offset: int = 0
    ) -> PackageSearchResponse:
        """Search packages globally using GraphQL searchPackages with pagination support."""

        graphql_query = """
        query SearchPackages($searchString: String!, $order: SearchResultOrder!, $latestOnly: Boolean!) {
            searchPackages(buckets: [], searchString: $searchString, latestOnly: $latestOnly) {
                ... on PackagesSearchResultSet {
                    total
                    stats {
                        size { min max }
                        entries { min max }
                    }
                    firstPage(order: $order) {
                        cursor
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

        variables = {
            "searchString": query if query and query != "*" else "",
            "order": "BEST_MATCH",
            "latestOnly": False,
        }

        try:
            result = await self._execute_graphql_query(graphql_query, variables)

            if result.get("errors"):
                raise Exception(f"GraphQL errors: {result['errors']}")

            data = result.get("data", {})
            search_result = data.get("searchPackages", {})

            # Handle EmptySearchResultSet
            if isinstance(search_result, dict) and "_" in search_result:
                return PackageSearchResponse(results=[], total=0, stats={}, next_cursor=None, raw={"total": 0})

            total_packages = None
            stats = {}
            first_page: Dict[str, Any] = {}

            if isinstance(search_result, dict):
                total_packages = search_result.get("total")
                stats = search_result.get("stats") or {}
                first_page = search_result.get("firstPage", {}) or {}

            hits = list(first_page.get("hits", []) or [])
            cursor = first_page.get("cursor")

            if total_packages is None:
                total_packages = len(hits)

            # Determine how many hits we need to satisfy the requested window
            required = max(offset + limit, limit)
            target_count = min(total_packages, required)

            while cursor and len(hits) < target_count:
                remaining = min(max(target_count - len(hits), 0), 1000)
                if remaining <= 0:
                    break
                more_hits, cursor = await self._fetch_more_packages(cursor, remaining)
                if not more_hits:
                    break
                hits.extend(more_hits)

            if offset >= len(hits):
                paginated_hits = []
            else:
                paginated_hits = hits[offset : offset + limit]

            results: List[SearchResult] = []

            for hit in paginated_hits:
                bucket = hit.get("bucket", "")
                name = hit.get("name", "")
                pkg_hash = hit.get("hash", "")
                size = hit.get("size", 0)
                modified = hit.get("modified", "")
                entries_count = hit.get("totalEntriesCount", 0)
                comment = hit.get("comment", "")
                workflow = hit.get("workflow", {})

                description_parts = [f"{entries_count} files"]
                if isinstance(size, (int, float)) and size > 0:
                    size_mb = size / (1024**2)
                    if size_mb < 1024:
                        description_parts.append(f"{size_mb:.1f} MB")
                    else:
                        description_parts.append(f"{size / (1024**3):.1f} GB")
                if comment:
                    description_parts.append(comment[:100])

                # Generate catalog URL for the package
                catalog_url = self._generate_package_catalog_url(bucket, name)
                
                result_obj = SearchResult(
                    id=f"graphql-pkg-{bucket}-{name}-{pkg_hash}",
                    type="package",
                    title=f"{bucket}/{name}",
                    description=" | ".join(description_parts),
                    url=catalog_url,
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
                        "catalog_url": catalog_url,
                    },
                    score=hit.get("score", 1.0),
                    backend="graphql",
                )
                results.append(result_obj)

            raw_meta = {
                "total": total_packages,
                "next_cursor": cursor,
                "stats": stats,
            }

            return PackageSearchResponse(
                results=results,
                total=total_packages,
                stats=stats,
                next_cursor=cursor,
                raw=raw_meta,
            )

        except Exception:
            # Fallback: return empty payload if search fails
            return PackageSearchResponse(results=[], total=0, stats={}, next_cursor=None, raw={"total": 0})

    async def _search_objects_global(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        limit: int,
        buckets: Optional[List[str]] = None,
        offset: int = 0,
    ) -> ObjectSearchResponse:
        """Search objects globally using Enterprise GraphQL searchObjects.

        Args:
            query: Search query string
            filters: Search filters
            limit: Maximum number of results
            buckets: Optional list of buckets to search (if None, searches all buckets)
        """

        graphql_query = """
        query SearchObjects($searchString: String!, $filter: ObjectsSearchFilter, $order: SearchResultOrder!, $buckets: [String!], $size: Int!) {
            searchObjects(buckets: $buckets, searchString: $searchString, filter: $filter) {
                __typename
                ... on ObjectsSearchResultSet {
                    total
                    firstPage(size: $size, order: $order) {
                        hits {
                            id
                            score
                            bucket
                            key
                            version
                            size
                            modified
                            deleted
                            indexedContent
                        }
                        cursor
                    }
                }
                ... on EmptySearchResultSet {
                    _
                }
                ... on InvalidInput {
                    errors {
                        path
                        message
                        name
                        context
                    }
                }
                ... on OperationError {
                    name
                    message
                    context
                }
            }
        }
        """

        objects_filter, force_blank_search = self._build_objects_filter(query, filters)

        # Determine how many records we need from the API to satisfy the requested page
        requested_window = max(limit + offset, limit, 30)
        page_size = min(requested_window, 1000)

        search_string = query if (query and query != "*") else ""
        if force_blank_search:
            search_string = ""

        variables = {
            "searchString": search_string,
            "filter": objects_filter,
            "order": "BEST_MATCH",
            "buckets": buckets or [],  # Empty list means search all buckets
            "size": page_size,
        }

        try:
            result = await self._execute_graphql_query(graphql_query, variables)

            if result.get("errors"):
                raise Exception(f"GraphQL errors: {result['errors']}")

            data = result.get("data", {})
            search_result = data.get("searchObjects", {})

            # Check the response type
            typename = search_result.get("__typename")

            if typename == "EmptySearchResultSet":
                # No objects found - this is normal, not an error
                return ObjectSearchResponse(results=[], total=0, stats={})
            elif typename == "InvalidInput":
                errors = search_result.get("errors", [])
                error_msg = "; ".join([f"{e.get('message', 'Unknown error')}" for e in errors])
                raise Exception(f"Invalid search input: {error_msg}")
            elif typename == "OperationError":
                error_msg = search_result.get("message", "Unknown operation error")
                raise Exception(f"Search operation failed: {error_msg}")
            elif typename == "ObjectsSearchResultSet":
                first_page = search_result.get("firstPage", {})
                hits = list(first_page.get("hits", []) or [])
                cursor = first_page.get("cursor")
                total_hits = search_result.get("total", len(hits))
                stats = search_result.get("stats", {}) or {}

                # Fetch more pages if needed to satisfy offset/limit
                required = offset + limit
                while cursor and len(hits) < min(total_hits, required):
                    remaining = min(max(required - len(hits), 0), 1000)
                    more_hits, cursor = await self._fetch_more_objects(cursor, remaining)
                    if not more_hits:
                        break
                    hits.extend(more_hits)

                # Apply pagination window
                if offset >= len(hits):
                    paginated_hits = []
                else:
                    paginated_hits = hits[offset : offset + limit]

                results: List[SearchResult] = []
                for hit in paginated_hits:
                    bucket = hit.get("bucket", "")
                    key = hit.get("key", "")

                    # Build a more descriptive title and description
                    filename = key.split("/")[-1] if key else "(unknown)"
                    file_ext = filename.split(".")[-1].upper() if "." in filename else ""
                    size_info = ""
                    if hit.get("size"):
                        size_bytes = hit.get("size")
                        if size_bytes > 1024**3:
                            size_info = f" ({size_bytes / (1024**3):.1f} GB)"
                        elif size_bytes > 1024**2:
                            size_info = f" ({size_bytes / (1024**2):.1f} MB)"
                        elif size_bytes > 1024:
                            size_info = f" ({size_bytes / 1024:.1f} KB)"
                        else:
                            size_info = f" ({size_bytes} bytes)"

                    # Generate catalog URL for the object
                    catalog_url = self._generate_object_catalog_url(bucket, key)
                    
                    result_obj = SearchResult(
                        id=f"graphql-object-{bucket}-{key}",
                        type="file",
                        title=filename,
                        description=f"{file_ext} file in {bucket}{size_info}",
                        url=catalog_url,
                        s3_uri=f"s3://{bucket}/{key}" if bucket and key else None,
                        logical_key=key,
                        metadata={
                            "bucket": bucket,
                            "version": hit.get("version"),
                            "size": hit.get("size"),
                            "modified": hit.get("modified"),
                            "deleted": hit.get("deleted", False),
                            "score": hit.get("score"),
                            "indexed_content": hit.get("indexedContent"),
                            "file_extension": file_ext.lower() if file_ext else None,
                            "catalog_url": catalog_url,
                        },
                        score=hit.get("score", 1.0),
                        backend="graphql",
                    )
                    results.append(result_obj)

                return ObjectSearchResponse(
                    results=results,
                    total=total_hits,
                    stats=stats,
                    next_cursor=cursor,
                    raw=search_result,
                )
            else:
                # Unknown response type
                raise Exception(f"Unexpected response type: {typename}")

        except Exception as exc:  # pragma: no cover - defensive fallback
            # On failure, return an informative error result rather than crashing
            error_result = SearchResult(
                id="graphql-object-error",
                type="error",
                title="Object search failed",
                description=str(exc),
                metadata={"query": query, "filters": filters},
                score=0,
                backend="graphql",
            )
            return ObjectSearchResponse(results=[error_result], total=0, stats={})

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

    async def _fetch_more_objects(self, cursor: str, size: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Fetch additional object search results using searchMoreObjects."""
        graphql_query = """
        query SearchMoreObjects($after: String!, $size: Int!) {
            searchMoreObjects(after: $after, size: $size) {
                __typename
                ... on ObjectsSearchResultSetPage {
                    cursor
                    hits {
                        id
                        score
                        bucket
                        key
                        version
                        size
                        modified
                        deleted
                        indexedContent
                    }
                }
                ... on InvalidInput {
                    errors {
                        path
                        message
                        name
                        context
                    }
                }
            }
        }
        """

        variables = {
            "after": cursor,
            "size": max(min(size, 1000), 1),
        }

        result = await self._execute_graphql_query(graphql_query, variables)
        data = result.get("data", {})
        payload = data.get("searchMoreObjects", {})

        typename = payload.get("__typename")
        if typename == "ObjectsSearchResultSetPage":
            next_cursor = payload.get("cursor")
            hits = payload.get("hits", []) or []
            return list(hits), next_cursor
        if typename == "InvalidInput":
            errors = payload.get("errors", [])
            error_msg = "; ".join([err.get("message", "Invalid input") for err in errors])
            raise Exception(f"searchMoreObjects invalid input: {error_msg}")

        raise Exception(f"Unexpected searchMoreObjects response: {typename}")

    def _generate_package_catalog_url(self, bucket: str, package_name: str) -> str:
        """Generate a catalog URL for a package."""
        try:
            from ...tools.auth import catalog_url
            from ...utils import resolve_catalog_url
            
            catalog_base = resolve_catalog_url()
            if not catalog_base:
                return f"s3://{bucket}/.quilt/named_packages/{package_name}"
            
            # Extract bucket from registry if needed
            if catalog_base.startswith("s3://"):
                registry = catalog_base
            else:
                # Assume it's a catalog URL, extract bucket from it
                registry = f"s3://{bucket}"
            
            result = catalog_url(
                registry=registry,
                package_name=package_name,
                catalog_host=catalog_base
            )
            
            if result.get("status") == "success":
                return result.get("catalog_url", f"s3://{bucket}/.quilt/named_packages/{package_name}")
            else:
                return f"s3://{bucket}/.quilt/named_packages/{package_name}"
                
        except Exception:
            # Fallback to S3 URI if URL generation fails
            return f"s3://{bucket}/.quilt/named_packages/{package_name}"

    def _generate_object_catalog_url(self, bucket: str, key: str) -> str:
        """Generate a catalog URL for an object."""
        try:
            from ...tools.auth import catalog_url
            from ...utils import resolve_catalog_url
            
            catalog_base = resolve_catalog_url()
            if not catalog_base:
                return f"s3://{bucket}/{key}"
            
            # Extract bucket from registry if needed
            if catalog_base.startswith("s3://"):
                registry = catalog_base
            else:
                # Assume it's a catalog URL, extract bucket from it
                registry = f"s3://{bucket}"
            
            result = catalog_url(
                registry=registry,
                path=key,
                catalog_host=catalog_base
            )
            
            if result.get("status") == "success":
                return result.get("catalog_url", f"s3://{bucket}/{key}")
            else:
                return f"s3://{bucket}/{key}"
                
        except Exception:
            # Fallback to S3 URI if URL generation fails
            return f"s3://{bucket}/{key}"

    async def _fetch_more_packages(self, cursor: str, size: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Fetch additional package search results using searchMorePackages."""

        graphql_query = """
        query SearchMorePackagesMore($after: String!, $size: Int!) {
            searchMorePackages(after: $after, size: $size) {
                __typename
                ... on PackagesSearchResultSetPage {
                    cursor
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
                ... on InvalidInput {
                    errors {
                        message
                    }
                }
            }
        }
        """

        variables = {
            "after": cursor,
            "size": max(min(size, 1000), 1),
        }

        result = await self._execute_graphql_query(graphql_query, variables)
        data = result.get("data", {})
        payload = data.get("searchMorePackages", {})

        typename = payload.get("__typename")
        if typename == "PackagesSearchResultSetPage":
            next_cursor = payload.get("cursor")
            hits = payload.get("hits", []) or []
            return list(hits), next_cursor
        if typename == "InvalidInput":
            errors = payload.get("errors", [])
            error_msg = "; ".join([err.get("message", "Invalid input") for err in errors])
            raise Exception(f"searchMorePackages invalid input: {error_msg}")

        raise Exception(f"Unexpected searchMorePackages response: {typename}")

    def _build_objects_filter(
        self, query: str, filters: Optional[Dict[str, Any]]
    ) -> Tuple[Optional[Dict[str, Any]], bool]:
        """Translate unified search filters into ObjectsSearchFilter format.

        This matches the frontend's approach:
        - For extension filters, use ext.terms
        - For wildcard queries like *.csv, use key.wildcard
        - For general text, rely on searchString parameter
        """

        gql_filter: Dict[str, Any] = {}
        force_blank_search = False

        search_terms = (query or "").strip()

        if filters:
            extensions = filters.get("file_extensions") or []
            if extensions:
                # Normalize extensions (remove dots, lowercase)
                normalized = [ext.lower().lstrip(".") for ext in extensions]
                gql_filter["ext"] = {"terms": normalized}

                # If query is a wildcard pattern like *.csv, use key.wildcard
                if search_terms.startswith("*.") and len(normalized) == 1:
                    gql_filter["key"] = {"wildcard": search_terms}
                    force_blank_search = True
                elif not search_terms or search_terms == "*":
                    # If no specific query but extensions specified, create wildcard
                    gql_filter["key"] = {"wildcard": f"*.{normalized[0]}"}
                    force_blank_search = True

            size_min = filters.get("size_min")
            size_max = filters.get("size_max")
            if size_min or size_max:
                size_filter = {}
                if size_min:
                    size_filter["gte"] = size_min
                if size_max:
                    size_filter["lte"] = size_max
                gql_filter["size"] = size_filter

        # If we have a specific key pattern but no extension filter, use key.wildcard
        elif search_terms and search_terms != "*" and search_terms.startswith("*."):
            gql_filter["key"] = {"wildcard": search_terms}
            force_blank_search = True
        # Also handle extension-only queries like "csv" or "*.csv"
        else:
            lowered = search_terms.lower()
            if lowered in OBJECT_EXTENSION_KEYWORDS:
                gql_filter["key"] = {"wildcard": f"*.{lowered}"}
                force_blank_search = True
            elif lowered.startswith(".") and lowered[1:] in OBJECT_EXTENSION_KEYWORDS:
                gql_filter["key"] = {"wildcard": f"*.{lowered[1:]}"}
                force_blank_search = True
            elif lowered.endswith(tuple(f".{ext}" for ext in OBJECT_EXTENSION_KEYWORDS)):
                # Extract extension after last dot
                ext = lowered.rsplit(".", 1)[-1]
                gql_filter["key"] = {"wildcard": f"*.{ext}"}
                force_blank_search = True

        return (gql_filter or None, force_blank_search)

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
