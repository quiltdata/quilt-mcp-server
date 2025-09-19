"""Generic Quilt Catalog GraphQL tools.

Provides a general-purpose GraphQL executor for the Quilt Catalog and a
convenience wrapper for object search within a bucket using GraphQL. This
module relies on the authenticated quilt3 session to inherit auth and
catalog configuration, similar to how bucket discovery uses GraphQL in
`aws/permission_discovery.py`.
"""

from __future__ import annotations

from typing import Any

from ..services.quilt_service import QuiltService


def _get_graphql_endpoint():
    """Return (session, graphql_url) from QuiltService context or (None, None).

    Uses QuiltService to acquire the authenticated requests session and
    the active registry URL, then constructs the GraphQL endpoint.
    """
    try:
        from urllib.parse import urljoin

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


def catalog_graphql_query(query: str, variables: dict | None = None) -> dict[str, Any]:
    """Execute an arbitrary GraphQL query against the configured Quilt Catalog.

    Args:
        query: GraphQL query string
        variables: Variables dictionary to bind

    Returns:
        Dict with raw `data`, optional `errors`, and `success` flag.
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
