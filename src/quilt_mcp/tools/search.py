"""Search tools for Quilt MCP Server.

This module exposes the unified search functionality as MCP tools.
"""

import asyncio
from typing import Annotated, Any, Dict, List, Literal, Optional

from pydantic import Field

from ..models.responses import (
    SearchCatalogError,
    SearchCatalogSuccess,
    SearchExplainError,
    SearchExplainSuccess,
    SearchGraphQLError,
    SearchGraphQLSuccess,
    SearchResult,
)
from ..search.tools.search_explain import search_explain as _search_explain
from ..search.tools.search_suggest import search_suggest as _search_suggest
from ..search.tools.unified_search import UnifiedSearchEngine


def search_catalog(
    query: Annotated[
        str,
        Field(
            description='Natural language search query (e.g., "CSV files", "genomics data", "files larger than 100MB")',
        ),
    ],
    scope: Annotated[
        Literal["global", "packageEntry", "package", "file"],
        Field(
            default="file",
            description='Search scope - "file" (file-level search, default), "packageEntry" (package-level search), "package" (package-centric with collapsed results), "global" (all)',
        ),
    ] = "file",
    bucket: Annotated[
        str,
        Field(
            default="",
            description='S3 bucket to search in (e.g., "my-bucket" or "s3://my-bucket"). Empty string searches all accessible buckets.',
        ),
    ] = "",
    backend: Annotated[
        Literal["elasticsearch"],
        Field(
            default="elasticsearch",
            description='Backend to use - "elasticsearch" (only valid option, graphql is currently broken)',
        ),
    ] = "elasticsearch",
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
) -> Dict[str, Any]:  # Returns dict on success, raises exception on failure
    """Intelligent unified search across Quilt catalog using Elasticsearch - Catalog and package search experiences

    This tool automatically:
    - Parses natural language queries to extract filters (file types, sizes, dates)
    - Aggregates and ranks results
    - Provides context and explanations

    Natural Language Query Capabilities:
    - File types: "CSV files", "JSON data", "Parquet files"
    - Sizes: "files larger than 100MB", "smaller than 1GB"
    - Dates: "created after 2023-01-01", "in the last 30 days", "modified this week"
    - Combined: "CSV files larger than 100MB created after 2024-01-01"

    Args:
        query: Natural language search query (e.g., "CSV files", "genomics data", "files larger than 100MB")
        scope: Search scope - "file" (file-level search, default), "packageEntry" (package-level search), "package" (package-centric with collapsed results), "global" (all)
        bucket: S3 bucket to search in (e.g., "my-bucket" or "s3://my-bucket"). Empty string searches all accessible buckets.
        backend: Backend to use - "elasticsearch" (only valid option, graphql is currently broken)
        limit: Maximum number of results to return (default: 50)
        include_metadata: Include rich metadata in results (default: True)
        explain_query: Include query execution explanation and backend selection reasoning (default: False)
        count_only: Return aggregated counts only (skips fetching full result payloads) when True.

    Returns:
        Unified search results with metadata, explanations, and suggestions

    Examples:
        search_catalog("CSV files")  # File-level search across all buckets
        search_catalog("files larger than 100MB created after 2024-01-01", bucket="my-bucket")  # Specific bucket
        search_catalog("packages created last month", scope="packageEntry")  # Package-level search
        search_catalog("genomics/data", scope="package")  # Package-centric search with collapsed results
        search_catalog("README files", scope="global")  # Global search (files and packages)
        search_catalog("Parquet files", bucket="s3://other-bucket")  # Specific bucket with s3:// URI

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
            backend = "elasticsearch"

        # Normalize bucket (extract from s3:// URI if provided)
        if bucket and bucket.startswith("s3://"):
            bucket = bucket[5:].split("/")[0]

        # Handle count-only mode by running search and extracting count
        if count_only:
            engine = UnifiedSearchEngine()

            async def _get_count():
                results = await engine.search(
                    query=query,
                    scope=scope,
                    bucket=bucket,
                    backend=backend,
                    limit=0,  # Don't need results
                    include_metadata=False,
                    explain_query=False,
                )
                return {
                    "success": True,
                    "total_count": results.get("total_results", 0),
                    "query": query,
                    "scope": scope,
                    "bucket": bucket,
                    "count_only": True,
                }

            return asyncio.run(_get_count())

        # Get search engine and execute search
        engine = UnifiedSearchEngine()

        # Handle async execution properly for MCP tools
        async def _execute_search():
            return await engine.search(
                query=query,
                scope=scope,
                bucket=bucket,
                backend=backend,
                limit=limit,
                include_metadata=include_metadata,
                explain_query=explain_query,
            )

        try:
            # Try to get the current event loop
            asyncio.get_running_loop()
            # We're in an async context, need to handle this carefully
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _execute_search())
                result = future.result(timeout=30)
        except RuntimeError:
            # No event loop running, we can use asyncio.run directly
            result = asyncio.run(_execute_search())

        # Convert result dict to proper response model, then serialize to dict
        if result.get("success", False):
            return SearchCatalogSuccess(
                query=result["query"],
                scope=result["scope"],
                bucket=result.get("bucket", ""),
                results=[SearchResult(**r) for r in result.get("results", [])],
                total_results=result.get("total_results", 0),
                query_time_ms=result.get("query_time_ms", 0.0),
                backend_used=result.get("backend_used"),
                analysis=result.get("analysis"),
                backend_status=result.get("backend_status"),
                backend_info=result.get("backend_info"),
                explanation=result.get("explanation"),
            ).model_dump()
        else:
            # Return error as dict (not raise) so tools can handle errors gracefully
            error_model = SearchCatalogError(
                error=result.get("error", "Search failed"),
                query=result["query"],
                scope=result.get("scope", scope),
                bucket=result.get("bucket", bucket),
                backend_used=result.get("backend_used"),
                backend_status=result.get("backend_status"),
            )
            # Return error dict instead of raising
            return error_model.model_dump()
    except asyncio.TimeoutError as e:
        raise RuntimeError(f"Search timeout: {e}")
    except OSError as e:
        raise RuntimeError(f"Search I/O error: {e}")


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
        Literal["global", "packageEntry", "package", "file"],
        Field(
            default="global",
            description="Search scope",
        ),
    ] = "global",
    bucket: Annotated[
        str,
        Field(
            default="",
            description="S3 bucket for scoped searches",
        ),
    ] = "",
) -> SearchExplainSuccess | SearchExplainError:
    """Explain how a search query would be processed and executed - Catalog and package search experiences

    Args:
        query: Search query to explain
        scope: Search scope
        bucket: S3 bucket for scoped searches

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


def _get_quilt_ops():
    """Return QuiltOps instance or None if unavailable.

    Uses QuiltOpsFactory to create a QuiltOps instance for GraphQL operations.
    This replaces the old GraphQL endpoint helper with QuiltOps abstraction.
    """
    try:
        from ..ops.factory import QuiltOpsFactory

        quilt_ops = QuiltOpsFactory.create()
        return quilt_ops
    except Exception:
        return None


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
    quilt_ops = _get_quilt_ops()
    if not quilt_ops:
        return SearchGraphQLError(error="QuiltOps unavailable. Ensure quilt3 is configured and authenticated.")

    try:
        # Use QuiltOps.execute_graphql_query() which handles session and endpoint internally
        result = quilt_ops.execute_graphql_query(query=query, variables=variables)

        # Check for GraphQL errors in the response
        if "errors" in result:
            return SearchGraphQLError(error=f"GraphQL errors: {result.get('errors')}")

        return SearchGraphQLSuccess(
            data=result.get("data"),
            errors=result.get("errors"),
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
            "packageEntry": edge.get("node", {}).get("packageEntry"),
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
