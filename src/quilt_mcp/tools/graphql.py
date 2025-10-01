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
    """Search for objects within a bucket via Quilt GraphQL.

    Note: The exact schema may vary by Quilt deployment. This targets a common
    Enterprise pattern with `objects(bucket:, filter:, first:, after:)` and
    nodes containing object attributes and an optional `package` linkage.
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

    result = catalog_graphql_query(gql, variables)
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
