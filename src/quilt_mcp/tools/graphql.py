"""Generic Quilt Catalog GraphQL tools using stateless catalog clients."""

from __future__ import annotations

from typing import Any, Optional

from ..clients import catalog as catalog_client
from ..runtime import get_active_token
from ..utils import resolve_catalog_url


def catalog_graphql_query(
    query: str,
    variables: Optional[dict] = None,
    registry_url: Optional[str] = None,
) -> dict[str, Any]:
    """Execute a GraphQL query against the Quilt catalog using a bearer token."""

    token = get_active_token()
    catalog_url = resolve_catalog_url(registry_url)

    if not token or not catalog_url:
        return {
            "success": False,
            "error": "Authorization token or catalog URL unavailable",
        }

    try:
        data = catalog_client.catalog_graphql_query(
            registry_url=catalog_url,
            query=query,
            variables=variables,
            auth_token=token,
        )
        return {
            "success": True,
            "data": data,
        }
    except Exception as exc:
        return {
            "success": False,
            "error": f"GraphQL request failed: {exc}",
        }


def objects_search_graphql(
    bucket: str,
    object_filter: dict | None = None,
    first: int = 100,
    after: str = "",
) -> dict[str, Any]:
    """DEPRECATED: Use search.unified_search instead.
    
    This function is deprecated and will be removed in a future version.
    Use search.unified_search with scope="bucket" and target=bucket for better results.
    
    Args:
        bucket: S3 bucket name or s3:// URI
        object_filter: Object filter criteria (deprecated parameter)
        first: Maximum number of results (deprecated parameter)
        after: Pagination cursor (deprecated parameter)

    Returns:
        Dict with deprecation warning and redirect to unified search.
    """
    from .search import unified_search
    
    # Normalize bucket input: allow s3://bucket
    bkt = bucket[5:].split("/", 1)[0] if bucket.startswith("s3://") else bucket
    
    # Redirect to unified search
    try:
        search_result = unified_search(
            query="*",  # Search for all objects in bucket
            scope="bucket",
            target=bkt,
            limit=first,
            include_metadata=True
        )
        
        return {
            "success": True,
            "deprecated": True,
            "message": "objects_search_graphql is deprecated. Use search.unified_search instead.",
            "bucket": bkt,
            "redirected_to": "search.unified_search",
            "search_results": search_result
        }
    except Exception as e:
        return {
            "success": False,
            "deprecated": True,
            "error": f"Deprecated function failed to redirect to unified search: {e}",
            "message": "objects_search_graphql is deprecated. Use search.unified_search instead.",
            "bucket": bkt,
        }
