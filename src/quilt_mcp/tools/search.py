"""Search tools for Quilt MCP Server.

This module exposes the unified search functionality as MCP tools.
"""

import asyncio
from typing import Dict, List, Any, Optional

from ..search.tools.unified_search import unified_search as _unified_search
from ..search.tools.search_suggest import search_suggest as _search_suggest
from ..search.tools.search_explain import search_explain as _search_explain


def unified_search(
    query: str,
    scope: str = "global",
    target: str = "",
    backends: Optional[List[str]] = None,
    limit: int = 50,
    include_metadata: bool = True,
    include_content_preview: bool = False,
    explain_query: bool = False,
    filters: Optional[Dict[str, Any]] = None,
    count_only: bool = False,
) -> Dict[str, Any]:
    """Intelligent unified search across Quilt catalogs, packages, and S3 buckets - Catalog and package search experiences

    This tool automatically:
    - Parses natural language queries
    - Selects optimal search backends
    - Aggregates and ranks results
    - Provides context and explanations

    Args:
        query: Natural language search query (e.g., "CSV files", "genomics data", "files larger than 100MB")
        scope: Search scope - "global" (all), "catalog" (current catalog), "package" (specific package), "bucket" (specific bucket)
        target: Specific target when scope is narrow (package name like "user/dataset" or bucket like "s3://my-bucket")
        backends: Preferred backends - ["auto"] (intelligent selection), ["elasticsearch"], ["graphql"], ["s3"], or combinations
        limit: Maximum number of results to return (default: 50)
        include_metadata: Include rich metadata in results (default: True)
        include_content_preview: Include content previews for files (default: False)
        explain_query: Include query execution explanation and backend selection reasoning (default: False)
        filters: Additional filters as dict - e.g., {"file_extensions": ["csv"], "size_gt": "100MB", "date_after": "2023-01-01"}
        count_only: Return aggregated counts only (skips fetching full result payloads) when True.

    Returns:
        Unified search results with metadata, explanations, and suggestions

    Examples:
        unified_search("CSV files in genomics packages")
        unified_search("packages created last month", scope="catalog")
        unified_search("README files", scope="package", target="user/dataset")
        unified_search("files larger than 100MB", filters={"size_gt": "100MB"})
        unified_search("*.csv", scope="bucket", target="s3://quilt-example")

    Next step:
        Summarize the search insight or refine the query with another search helper.

    Example:
        ```python
        from quilt_mcp.tools import search

        result = search.unified_search(
            query="status:READY",
        )
        # Next step: Summarize the search insight or refine the query with another search helper.
        ```
    """
    try:
        # Set default backends if None
        if backends is None:
            backends = ["auto"]

        # Handle async execution properly for MCP tools
        try:
            # Try to get the current event loop
            asyncio.get_running_loop()
            # We're in an async context, need to handle this carefully
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    _unified_search(
                        query=query,
                        scope=scope,
                        target=target,
                        backends=backends,
                        limit=limit,
                        include_metadata=include_metadata,
                        include_content_preview=include_content_preview,
                        explain_query=explain_query,
                        filters=filters,
                        count_only=count_only,
                    ),
                )
                return future.result(timeout=30)
        except RuntimeError:
            # No event loop running, we can use asyncio.run directly
            return asyncio.run(
                _unified_search(
                    query=query,
                    scope=scope,
                    target=target,
                    backends=backends,
                    limit=limit,
                    include_metadata=include_metadata,
                    include_content_preview=include_content_preview,
                    explain_query=explain_query,
                    filters=filters,
                    count_only=count_only,
                )
            )
    except (RuntimeError, asyncio.TimeoutError, OSError) as e:
        return {
            "success": False,
            "error": f"Unified search failed: {e}",
            "query": query,
            "scope": scope,
            "target": target,
            "help": {
                "common_queries": [
                    "CSV files",
                    "genomics data",
                    "files larger than 100MB",
                    "packages created this month",
                ],
                "scopes": ["global", "catalog", "package", "bucket"],
                "backends": ["auto", "elasticsearch", "graphql", "s3"],
            },
        }


def search_suggest(
    partial_query: str,
    context: str = "",
    suggestion_types: Optional[List[str]] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """Get intelligent search suggestions based on partial queries and context - Catalog and package search experiences

    Args:
        partial_query: Partial or incomplete search query
        context: Additional context to improve suggestions
        suggestion_types: Types of suggestions to generate - ["auto"], ["query"], ["filter"], ["scope"]
        limit: Maximum number of suggestions to return

    Returns:
        Search suggestions with explanations and examples

    Next step:
        Summarize the search insight or refine the query with another search helper.

    Example:
        ```python
        from quilt_mcp.tools import search

        result = search.search_suggest(
            partial_query="SELECT * FROM table",
        )
        # Next step: Summarize the search insight or refine the query with another search helper.
        ```
    """
    try:
        if suggestion_types is None:
            suggestion_types = ["auto"]

        return _search_suggest(
            partial_query=partial_query,
            context=context,
            suggestion_types=suggestion_types,
            limit=limit,
        )
    except (RuntimeError, ValueError) as e:
        return {
            "success": False,
            "error": f"Search suggestions failed: {e}",
            "partial_query": partial_query,
        }


def search_explain(query: str, scope: str = "global", target: str = "") -> Dict[str, Any]:
    """Explain how a search query would be processed and executed - Catalog and package search experiences

    Args:
        query: Search query to explain
        scope: Search scope
        target: Target for scoped searches

    Returns:
        Detailed explanation of query processing and backend selection

    Next step:
        Summarize the search insight or refine the query with another search helper.

    Example:
        ```python
        from quilt_mcp.tools import search

        result = search.search_explain(
            query="status:READY",
        )
        # Next step: Summarize the search insight or refine the query with another search helper.
        ```
    """
    try:
        return _search_explain(query=query)
    except (RuntimeError, ValueError) as e:
        return {
            "success": False,
            "error": f"Search explanation failed: {e}",
            "query": query,
        }


# Renamed from unified_search for simpler interface
search = unified_search


# GraphQL search functions (previously in separate graphql module)


def _get_graphql_endpoint():
    """Return (session, graphql_url) from QuiltService context or (None, None).

    Uses QuiltService to acquire the authenticated requests session and
    the active registry URL, then constructs the GraphQL endpoint.
    """
    try:
        from urllib.parse import urljoin

        from ..services.quilt_service import QuiltService

        quilt_service = QuiltService()

        if not quilt_service.has_session_support():
            return None, None
        session = quilt_service.get_session()
        registry_url = quilt_service.get_registry_url()
        if not registry_url:
            return None, None
        graphql_url = urljoin(registry_url.rstrip("/") + "/", "graphql")
        return session, graphql_url
    except Exception:
        return None, None


def search_graphql(query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
    """Execute an arbitrary GraphQL query against the configured Quilt Catalog - Catalog and package search experiences

    Args:
        query: GraphQL query string
        variables: Variables dictionary to bind

    Returns:
        Dict with raw `data`, optional `errors`, and `success` flag.

    Next step:
        Summarize the search insight or refine the query with another search helper.

    Example:
        ```python
        from quilt_mcp.tools import search

        result = search.search_graphql(
            query="query { bucketConfigs { name } }",
        )
        # Next step: Summarize the search insight or refine the query with another search helper.
        ```
    """
    session, graphql_url = _get_graphql_endpoint()
    if not session or not graphql_url:
        return {
            "success": False,
            "error": "GraphQL endpoint or session unavailable. Ensure quilt3 is configured and authenticated.",
        }

    try:
        resp = session.post(graphql_url, json={"query": query, "variables": variables or {}})
        if resp.status_code != 200:
            return {
                "success": False,
                "error": f"GraphQL HTTP {resp.status_code}: {resp.text}",
            }
        payload = resp.json()
        return {
            "success": "errors" not in payload,
            "data": payload.get("data"),
            "errors": payload.get("errors"),
        }
    except Exception as e:
        return {"success": False, "error": f"GraphQL request failed: {e}"}


def search_objects_graphql(
    bucket: str,
    object_filter: Optional[Dict] = None,
    first: int = 100,
    after: str = "",
) -> Dict[str, Any]:
    """Search for objects within a bucket via Quilt GraphQL - Catalog and package search experiences

    Note: The exact schema may vary by Quilt deployment. This targets a common
    Enterprise pattern with `objects(bucket:, filter:, first:, after:)` and
    nodes containing object attributes and an optional `package` linkage.

    Args:
        bucket: S3 bucket name or s3:// URI
        object_filter: Dictionary of filter fields compatible with the catalog schema
        first: Page size (default 100)
        after: Cursor for pagination

    Returns:
        Dict with objects, pagination info, and the effective filter used.

    Next step:
        Summarize the search insight or refine the query with another search helper.

    Example:
        ```python
        from quilt_mcp.tools import search

        result = search.search_objects_graphql(
            bucket="my-bucket",
            object_filter={"extension": "csv"},
            first=50,
        )
        # Next step: Summarize the search insight or refine the query with another search helper.
        ```
    """
    # Normalize bucket input: allow s3://bucket
    bkt = bucket[5:].split("/", 1)[0] if bucket.startswith("s3://") else bucket

    gql = (
        "query($bucket: String!, $filter: ObjectFilterInput, $first: Int, $after: String) {\n"
        "  objects(bucket: $bucket, filter: $filter, first: $first, after: $after) {\n"
        "    edges {\n"
        "      node { key size updated contentType extension package { name topHash tag } }\n"
        "      cursor\n"
        "    }\n"
        "    pageInfo { endCursor hasNextPage }\n"
        "  }\n"
        "}"
    )
    variables = {
        "bucket": bkt,
        "filter": object_filter or {},
        "first": max(1, min(first, 1000)),
        "after": after or None,
    }

    result = search_graphql(gql, variables)
    if not result.get("success"):
        return {
            "success": False,
            "bucket": bkt,
            "objects": [],
            "error": result.get("error") or result.get("errors"),
        }
    data = result.get("data", {}) or {}
    conn = data.get("objects", {}) or {}
    edges = conn.get("edges", []) or []
    objects = [
        {
            "key": edge.get("node", {}).get("key"),
            "size": edge.get("node", {}).get("size"),
            "updated": edge.get("node", {}).get("updated"),
            "content_type": edge.get("node", {}).get("contentType"),
            "extension": edge.get("node", {}).get("extension"),
            "package": edge.get("node", {}).get("package"),
        }
        for edge in edges
        if isinstance(edge, dict)
    ]
    page_info = conn.get("pageInfo") or {}
    return {
        "success": True,
        "bucket": bkt,
        "objects": objects,
        "page_info": {
            "end_cursor": page_info.get("endCursor"),
            "has_next_page": page_info.get("hasNextPage", False),
        },
        "filter": variables["filter"],
    }
