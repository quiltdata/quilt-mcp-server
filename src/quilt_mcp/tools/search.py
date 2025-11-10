"""Search tools for Quilt MCP Server.

This module exposes the unified search functionality as MCP tools.
"""

import asyncio
from typing import Annotated, Any, Dict, List, Optional

from pydantic import Field

from ..models.responses import (
    SearchExplainError,
    SearchExplainSuccess,
    SearchGraphQLError,
    SearchGraphQLSuccess,
)
from ..search.tools.search_explain import search_explain as _search_explain
from ..search.tools.search_suggest import search_suggest as _search_suggest
from ..search.tools.unified_search import unified_search as _unified_search


def search_catalog(
    query: Annotated[
        str,
        Field(
            description='Natural language search query (e.g., "CSV files", "genomics data", "files larger than 100MB")',
        ),
    ],
    scope: Annotated[
        str,
        Field(
            default="global",
            description='Search scope - "global" (all), "catalog" (current catalog), "package" (specific package), "bucket" (specific bucket)',
        ),
    ] = "global",
    target: Annotated[
        str,
        Field(
            default="",
            description='Specific target when scope is narrow (package name like "user/dataset" or bucket like "s3://my-bucket")',
        ),
    ] = "",
    backend: Annotated[
        str,
        Field(
            default="auto",
            description='Preferred backend - "auto" (intelligent selection), "elasticsearch", "graphql", or "s3"',
        ),
    ] = "auto",
    limit: Annotated[
        int,
        Field(
            default=50,
            description="Maximum number of results to return (default: 50)",
        ),
    ] = 50,
    include_metadata: Annotated[
        bool,
        Field(
            default=True,
            description="Include rich metadata in results (default: True)",
        ),
    ] = True,
    include_content_preview: Annotated[
        bool,
        Field(
            default=False,
            description="Include content previews for files (default: False)",
        ),
    ] = False,
    explain_query: Annotated[
        bool,
        Field(
            default=False,
            description="Include query execution explanation and backend selection reasoning (default: False)",
        ),
    ] = False,
    count_only: Annotated[
        bool,
        Field(
            default=False,
            description="Return aggregated counts only (skips fetching full result payloads) when True.",
        ),
    ] = False,
) -> Dict[str, Any]:
    """Intelligent unified search across Quilt catalogs, packages, and S3 buckets - Catalog and package search experiences

    This tool automatically:
    - Parses natural language queries to extract filters (file types, sizes, dates)
    - Selects optimal search backends
    - Aggregates and ranks results
    - Provides context and explanations

    Natural Language Query Capabilities:
    - File types: "CSV files", "JSON data", "Parquet files"
    - Sizes: "files larger than 100MB", "smaller than 1GB"
    - Dates: "created after 2023-01-01", "in the last 30 days", "modified this week"
    - Combined: "CSV files larger than 100MB created after 2024-01-01"

    Args:
        query: Natural language search query (e.g., "CSV files", "genomics data", "files larger than 100MB")
        scope: Search scope - "global" (all), "catalog" (current catalog), "package" (specific package), "bucket" (specific bucket)
        target: Specific target when scope is narrow (package name like "user/dataset" or bucket like "s3://my-bucket")
        backend: Preferred backend - "auto" (intelligent selection), "elasticsearch", "graphql", or "s3"
        limit: Maximum number of results to return (default: 50)
        include_metadata: Include rich metadata in results (default: True)
        include_content_preview: Include content previews for files (default: False)
        explain_query: Include query execution explanation and backend selection reasoning (default: False)
        count_only: Return aggregated counts only (skips fetching full result payloads) when True.

    Returns:
        Unified search results with metadata, explanations, and suggestions

    Examples:
        search_catalog("CSV files in genomics packages")
        search_catalog("files larger than 100MB created after 2024-01-01")
        search_catalog("packages created last month", scope="catalog")
        search_catalog("README files", scope="package", target="user/dataset")
        search_catalog("Parquet files smaller than 500MB", scope="bucket", target="s3://quilt-example")

    Next step:
        Summarize the search insight or refine the query with another search helper.

    Example:
        ```python
        from quilt_mcp.tools import search

        result = search.search_catalog(
            query="status:READY",
        )
        # Next step: Summarize the search insight or refine the query with another search helper.
        ```
    """
    try:
        # Set default backend if None or empty
        if not backend:
            backend = "auto"

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
                        backend=backend,
                        limit=limit,
                        include_metadata=include_metadata,
                        include_content_preview=include_content_preview,
                        explain_query=explain_query,
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
                    backend=backend,
                    limit=limit,
                    include_metadata=include_metadata,
                    include_content_preview=include_content_preview,
                    explain_query=explain_query,
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
                "backend": ["auto", "elasticsearch", "graphql", "s3"],
            },
        }


def search_suggest(
    partial_query: Annotated[
        str,
        Field(
            description="Partial or incomplete search query",
        ),
    ],
    context: Annotated[
        str,
        Field(
            default="",
            description="Additional context to improve suggestions",
        ),
    ] = "",
    suggestion_types: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description='Types of suggestions to generate - ["auto"], ["query"], ["filter"], ["scope"]',
        ),
    ] = None,
    limit: Annotated[
        int,
        Field(
            default=10,
            description="Maximum number of suggestions to return",
        ),
    ] = 10,
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


def search_explain(
    query: Annotated[
        str,
        Field(
            description="Search query to explain",
        ),
    ],
    scope: Annotated[
        str,
        Field(
            default="global",
            description="Search scope",
        ),
    ] = "global",
    target: Annotated[
        str,
        Field(
            default="",
            description="Target for scoped searches",
        ),
    ] = "",
) -> SearchExplainSuccess | SearchExplainError:
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
        explanation = _search_explain(query=query)
        backend_selection = explanation.get("backend_selection", {})
        backends_selected = backend_selection.get("selected_backends", [])
        query_analysis = explanation.get("query_analysis", {})

        return SearchExplainSuccess(
            query=query,
            explanation=explanation,
            backends_selected=backends_selected,
            query_complexity=query_analysis.get("detected_type", "unknown"),
        )
    except (RuntimeError, ValueError) as e:
        return SearchExplainError(
            error=f"Search explanation failed: {e}",
            query=query,
        )


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


def search_graphql(
    query: Annotated[
        str,
        Field(
            description="GraphQL query string",
        ),
    ],
    variables: Annotated[
        Optional[Dict],
        Field(
            default=None,
            description="Variables dictionary to bind",
        ),
    ] = None,
) -> SearchGraphQLSuccess | SearchGraphQLError:
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
        return SearchGraphQLError(
            error="GraphQL endpoint or session unavailable. Ensure quilt3 is configured and authenticated."
        )

    try:
        resp = session.post(graphql_url, json={"query": query, "variables": variables or {}})
        if resp.status_code != 200:
            return SearchGraphQLError(error=f"GraphQL HTTP {resp.status_code}: {resp.text}")

        payload = resp.json()
        if "errors" in payload:
            return SearchGraphQLError(error=f"GraphQL errors: {payload.get('errors')}")
        return SearchGraphQLSuccess(
            data=payload.get("data"),
            errors=payload.get("errors"),
        )
    except Exception as e:
        return SearchGraphQLError(error=f"GraphQL request failed: {e}")


def search_objects_graphql(
    bucket: Annotated[
        str,
        Field(
            description="S3 bucket name or s3:// URI",
            examples=["my-bucket", "s3://my-bucket"],
        ),
    ],
    object_filter: Annotated[
        Optional[Dict],
        Field(
            default=None,
            description="Dictionary of filter fields compatible with the catalog schema",
            examples=[{"extension": "csv"}, {"size_gt": 1000000}],
        ),
    ] = None,
    first: Annotated[
        int,
        Field(
            default=100,
            ge=1,
            le=1000,
            description="Page size (default 100)",
        ),
    ] = 100,
    after: Annotated[
        str,
        Field(
            default="",
            description="Cursor for pagination",
        ),
    ] = "",
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
