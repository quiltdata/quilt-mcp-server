"""Stateless Quilt Catalog client helpers."""

from __future__ import annotations

import logging
from typing import Any, Dict, Mapping, Optional

import requests


logger = logging.getLogger(__name__)


DEFAULT_TIMEOUT = 30


def _require_token(auth_token: Optional[str]) -> str:
    if not auth_token:
        raise ValueError("Authorization token is required for catalog requests")
    token = auth_token.strip()
    if not token:
        raise ValueError("Authorization token is required for catalog requests")
    return token


def _auth_headers(auth_token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
        "User-Agent": "Quilt-MCP-Server/Stateless",
    }


def execute_catalog_query(
    graphql_url: str,
    *,
    query: str,
    variables: Optional[Mapping[str, Any]] = None,
    auth_token: Optional[str],
    timeout: int = DEFAULT_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> Dict[str, Any]:
    """Execute a GraphQL query against the Quilt catalog using a bearer token."""

    # Debug logging
    logger.info(f"execute_catalog_query called with auth_token: {auth_token[:20] if auth_token else 'None'}...")
    logger.info(f"GraphQL URL: {graphql_url}")

    token = _require_token(auth_token)
    logger.info(f"Token after _require_token: {token[:20] if token else 'None'}...")
    payload = {"query": query, "variables": variables or {}}

    client = session or requests
    response = client.post(
        graphql_url,
        json=payload,
        headers=_auth_headers(token),
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()

    if "errors" in data:
        logger.warning("GraphQL errors returned: %s", data["errors"])
        raise RuntimeError(f"GraphQL query failed: {data['errors']}")

    return data.get("data", {})


def _graphql_url(registry_url: str) -> str:
    """
    Convert catalog URL to GraphQL endpoint URL.
    
    The catalog URL (demo.quiltdata.com) needs to be converted to the
    registry URL (demo-registry.quiltdata.com) for GraphQL queries.
    """
    # Handle demo.quiltdata.com -> demo-registry.quiltdata.com
    if "demo.quiltdata.com" in registry_url:
        registry_url = registry_url.replace("demo.quiltdata.com", "demo-registry.quiltdata.com")
    
    return registry_url.rstrip("/") + "/graphql"


def catalog_graphql_query(
    *,
    registry_url: str,
    query: str,
    variables: Optional[Mapping[str, Any]] = None,
    auth_token: Optional[str],
    timeout: int = DEFAULT_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> Dict[str, Any]:
    graphql_url = _graphql_url(registry_url)
    return execute_catalog_query(
        graphql_url,
        query=query,
        variables=variables,
        auth_token=auth_token,
        timeout=timeout,
        session=session,
    )


def catalog_rest_request(
    *,
    method: str,
    url: str,
    auth_token: Optional[str],
    json_body: Optional[Mapping[str, Any]] = None,
    timeout: int = DEFAULT_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> Dict[str, Any]:
    token = _require_token(auth_token)
    client = session or requests
    response = client.request(
        method.upper(),
        url,
        json=json_body,
        headers=_auth_headers(token),
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def catalog_tabulator_tables_list(
    *, registry_url: str, bucket_name: str, auth_token: Optional[str], session: Optional[requests.Session] = None
) -> Dict[str, Any]:
    query = (
        "query ($bucketName: String!) {\n"
        "  bucketConfig(name: $bucketName) {\n"
        "    name\n"
        "    tabulatorTables { name config }\n"
        "  }\n"
        "}\n"
    )

    data = catalog_graphql_query(
        registry_url=registry_url,
        query=query,
        variables={"bucketName": bucket_name},
        auth_token=auth_token,
        session=session,
    )

    bucket_config = data.get("bucketConfig") if isinstance(data, dict) else None
    if not bucket_config:
        raise RuntimeError(f"Bucket '{bucket_name}' not found or tabulator data unavailable")
    return bucket_config


def _handle_tabulator_mutation_result(result: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(result, dict):
        raise RuntimeError("Unexpected tabulator mutation response")

    typename = result.get("__typename")
    if typename == "BucketConfig" or (typename is None and "tabulatorTables" in result):
        result.pop("__typename", None)
        return result

    if typename == "InvalidInput":
        errors = result.get("errors", [])
        raise ValueError(f"Invalid tabulator input: {errors}")

    if typename == "OperationError":
        message = result.get("message", "Unknown error")
        raise RuntimeError(f"Tabulator operation failed: {message}")

    raise RuntimeError("Unknown tabulator mutation response type")


def catalog_tabulator_table_set(
    *,
    registry_url: str,
    bucket_name: str,
    table_name: str,
    config_yaml: Optional[str],
    auth_token: Optional[str],
    session: Optional[requests.Session] = None,
) -> Dict[str, Any]:
    mutation = (
        "mutation ($bucketName: String!, $tableName: String!, $config: String) {\n"
        "  admin {\n"
        "    bucketSetTabulatorTable(bucketName: $bucketName, tableName: $tableName, config: $config) {\n"
        "      __typename\n"
        "      ... on BucketConfig {\n"
        "        name\n"
        "        tabulatorTables { name config }\n"
        "      }\n"
        "      ... on InvalidInput { errors { message path } }\n"
        "      ... on OperationError { message name }\n"
        "    }\n"
        "  }\n"
        "}\n"
    )

    graphql_url = _graphql_url(registry_url)
    data = execute_catalog_query(
        graphql_url,
        query=mutation,
        variables={
            "bucketName": bucket_name,
            "tableName": table_name,
            "config": config_yaml,
        },
        auth_token=auth_token,
        session=session,
    )

    result = (data.get("admin") or {}).get("bucketSetTabulatorTable") if isinstance(data, dict) else None
    if not result:
        raise RuntimeError("Missing tabulator mutation result")

    return _handle_tabulator_mutation_result(result)


def catalog_tabulator_table_rename(
    *,
    registry_url: str,
    bucket_name: str,
    table_name: str,
    new_table_name: str,
    auth_token: Optional[str],
    session: Optional[requests.Session] = None,
) -> Dict[str, Any]:
    mutation = (
        "mutation ($bucketName: String!, $tableName: String!, $newTableName: String!) {\n"
        "  admin {\n"
        "    bucketRenameTabulatorTable(\n"
        "      bucketName: $bucketName\n"
        "      tableName: $tableName\n"
        "      newTableName: $newTableName\n"
        "    ) {\n"
        "      __typename\n"
        "      ... on BucketConfig {\n"
        "        name\n"
        "        tabulatorTables { name config }\n"
        "      }\n"
        "      ... on InvalidInput { errors { message path } }\n"
        "      ... on OperationError { message name }\n"
        "    }\n"
        "  }\n"
        "}\n"
    )

    graphql_url = _graphql_url(registry_url)
    data = execute_catalog_query(
        graphql_url,
        query=mutation,
        variables={
            "bucketName": bucket_name,
            "tableName": table_name,
            "newTableName": new_table_name,
        },
        auth_token=auth_token,
        session=session,
    )

    result = (data.get("admin") or {}).get("bucketRenameTabulatorTable") if isinstance(data, dict) else None
    if not result:
        raise RuntimeError("Missing tabulator rename result")

    return _handle_tabulator_mutation_result(result)


def catalog_tabulator_open_query_status(
    *, registry_url: str, auth_token: Optional[str], session: Optional[requests.Session] = None
) -> bool:
    query = "query { admin { tabulatorOpenQuery } }"

    data = catalog_graphql_query(
        registry_url=registry_url,
        query=query,
        variables=None,
        auth_token=auth_token,
        session=session,
    )

    admin = data.get("admin") if isinstance(data, dict) else None
    if admin is None or "tabulatorOpenQuery" not in admin:
        raise RuntimeError("Tabulator open query status unavailable")
    return bool(admin.get("tabulatorOpenQuery"))


def catalog_tabulator_open_query_set(
    *, registry_url: str, enabled: bool, auth_token: Optional[str], session: Optional[requests.Session] = None
) -> bool:
    mutation = (
        "mutation ($enabled: Boolean!) {\n"
        "  admin {\n"
        "    setTabulatorOpenQuery(enabled: $enabled) { tabulatorOpenQuery }\n"
        "  }\n"
        "}\n"
    )

    graphql_url = _graphql_url(registry_url)
    data = execute_catalog_query(
        graphql_url,
        query=mutation,
        variables={"enabled": enabled},
        auth_token=auth_token,
        session=session,
    )

    admin = data.get("admin") if isinstance(data, dict) else None
    if not admin or "setTabulatorOpenQuery" not in admin:
        raise RuntimeError("Failed to set tabulator open query")

    result = admin.get("setTabulatorOpenQuery")
    if not isinstance(result, dict) or "tabulatorOpenQuery" not in result:
        raise RuntimeError("Invalid tabulator open query response")

    return bool(result.get("tabulatorOpenQuery"))


def catalog_packages_list(
    *, registry_url: str, auth_token: Optional[str], limit: Optional[int] = None, prefix: str | None = None
) -> list[str]:
    query = """
    query PackagesList($prefix: String, $limit: Int) {
      packages(prefix: $prefix, first: $limit) {
        edges { node { name } }
      }
    }
    """

    data = catalog_graphql_query(
        registry_url=registry_url,
        query=query,
        variables={"prefix": prefix, "limit": limit},
        auth_token=auth_token,
    )

    edges = (data.get("packages", {}) or {}).get("edges", []) if isinstance(data, dict) else []
    return [edge.get("node", {}).get("name") for edge in edges if isinstance(edge, dict)]


def catalog_package_entries(
    *, registry_url: str, package_name: str, auth_token: Optional[str], top: Optional[int] = None
) -> list[dict[str, Any]]:
    query = """
    query PackageEntries($name: String!, $first: Int) {
      package(name: $name) {
        entries(first: $first) {
          edges { node { logicalKey physicalKey size hash } }
        }
      }
    }
    """

    data = catalog_graphql_query(
        registry_url=registry_url,
        query=query,
        variables={"name": package_name, "first": top},
        auth_token=auth_token,
    )

    package = data.get("package") if isinstance(data, dict) else None
    edges = package.get("entries", {}).get("edges", []) if isinstance(package, dict) else []
    return [edge.get("node", {}) for edge in edges if isinstance(edge, dict)]


def _registry_endpoint(registry_url: str, path: str) -> str:
    return registry_url.rstrip("/") + path


def catalog_package_create(
    *,
    registry_url: str,
    package_name: str,
    auth_token: Optional[str],
    s3_uris: list[str],
    metadata: Mapping[str, Any] | None,
    message: str,
    flatten: bool,
    copy_mode: str,
) -> Dict[str, Any]:
    payload = {
        "package": package_name,
        "s3_uris": list(s3_uris),
        "metadata": metadata or {},
        "message": message,
        "flatten": flatten,
        "copy_mode": copy_mode,
    }

    url = _registry_endpoint(registry_url, "/api/package_revisions")
    return catalog_rest_request(
        method="POST",
        url=url,
        auth_token=auth_token,
        json_body=payload,
    )


def catalog_package_update(
    *,
    registry_url: str,
    package_name: str,
    auth_token: Optional[str],
    s3_uris: list[str],
    metadata: Mapping[str, Any] | None,
    message: str,
    copy_mode: str,
    flatten: bool,
) -> Dict[str, Any]:
    payload = {
        "package": package_name,
        "s3_uris": list(s3_uris),
        "metadata": metadata or {},
        "message": message,
        "copy_mode": copy_mode,
        "flatten": flatten,
    }

    url = _registry_endpoint(registry_url, "/api/package_revisions/update")
    return catalog_rest_request(
        method="POST",
        url=url,
        auth_token=auth_token,
        json_body=payload,
    )


def catalog_package_delete(
    *,
    registry_url: str,
    package_name: str,
    auth_token: Optional[str],
) -> Dict[str, Any]:
    url = _registry_endpoint(registry_url, f"/api/packages/{package_name}")
    return catalog_rest_request(
        method="DELETE",
        url=url,
        auth_token=auth_token,
        json_body=None,
    )


def catalog_bucket_search(
    *,
    registry_url: str,
    bucket: str,
    query: Any,
    limit: int,
    auth_token: Optional[str],
) -> Dict[str, Any]:
    payload = {
        "bucket": bucket,
        "query": query,
        "limit": max(0, limit),
    }

    url = _registry_endpoint(registry_url, "/api/search/bucket")
    return catalog_rest_request(
        method="POST",
        url=url,
        auth_token=auth_token,
        json_body=payload,
    )


def catalog_bucket_search_graphql(
    *,
    registry_url: str,
    bucket: str,
    object_filter: Optional[Mapping[str, Any]],
    first: int,
    after: Optional[str],
    auth_token: Optional[str],
) -> Dict[str, Any]:
    gql = (
        "query($bucket: String!, $filter: ObjectFilterInput, $first: Int, $after: String) {\n"
        "  objects(bucket: $bucket, filter: $filter, first: $first, after: $after) {\n"
        "    edges {\n"
        "      node { key size updated contentType extension package { name topHash tag } }\n"
        "      cursor\n"
        "    }\n"
        "    pageInfo { endCursor hasNextPage }\n"
        "  }\n"
        "}\n"
    )

    variables = {
        "bucket": bucket,
        "filter": object_filter or {},
        "first": max(1, min(first, 1000)),
        "after": after,
    }

    data = catalog_graphql_query(
        registry_url=registry_url,
        query=gql,
        variables=variables,
        auth_token=auth_token,
    )

    return data
