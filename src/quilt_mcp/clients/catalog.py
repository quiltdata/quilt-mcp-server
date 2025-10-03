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
    
    # Log response for debugging
    if response.status_code != 200:
        logger.error(f"GraphQL request failed with status {response.status_code}")
        logger.error(f"Response body: {response.text[:500]}")
    
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
    *, registry_url: str, bucket: str, package_name: str, auth_token: Optional[str], top: Optional[int] = None
) -> list[dict[str, Any]]:
    """Get package entries using the correct GraphQL schema.
    
    Uses PackageRevision.contentsFlatMap to get package contents.
    
    Args:
        registry_url: Quilt catalog URL
        bucket: S3 bucket name (without s3:// prefix)
        package_name: Package name (e.g., "team/package")
        auth_token: JWT authentication token
        top: Maximum number of entries to return (default: 1000)
    """
    query = """
    query PackageEntries($bucket: String!, $name: String!, $max: Int) {
      package(bucket: $bucket, name: $name) {
        revision(hashOrTag: "latest") {
          contentsFlatMap(max: $max)
        }
      }
    }
    """

    data = catalog_graphql_query(
        registry_url=registry_url,
        query=query,
        variables={"bucket": bucket, "name": package_name, "max": top or 1000},
        auth_token=auth_token,
    )

    # catalog_graphql_query already returns the 'data' field from the GraphQL response
    # and raises RuntimeError if there are errors, so we can directly access 'package'
    package = data.get("package")
    if not package:
        return []
    
    revision = package.get("revision")
    if not revision:
        return []
    
    contents_flat_map = revision.get("contentsFlatMap", {})
    if not contents_flat_map:
        return []
    
    # contentsFlatMap is a scalar that contains the flat map of package contents
    # We need to parse it and convert to our expected format
    entries = []
    for logical_key, entry_data in contents_flat_map.items():
        if isinstance(entry_data, dict):
            entries.append({
                "logicalKey": logical_key,
                "physicalKey": entry_data.get("physicalKey", ""),
                "size": entry_data.get("size", 0),
                "hash": entry_data.get("hash", ""),
            })
    
    return entries


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
    """
    Create a package using GraphQL packageConstruct mutation.
    
    This replaces the old REST endpoint approach which was causing 405 errors.
    """
    # Parse package name to get bucket and name
    if "/" not in package_name:
        return {
            "success": False,
            "error": f"Invalid package name format: {package_name}. Expected format: 'bucket/package-name'"
        }
    
    bucket, name = package_name.split("/", 1)
    
    # Convert S3 URIs to package entries
    entries = []
    for s3_uri in s3_uris:
        if not s3_uri.startswith("s3://"):
            return {
                "success": False,
                "error": f"Invalid S3 URI: {s3_uri}. Must start with 's3://'"
            }
        
        # Extract bucket and key from S3 URI
        uri_parts = s3_uri[5:].split("/", 1)  # Remove 's3://' prefix
        if len(uri_parts) != 2:
            return {
                "success": False,
                "error": f"Invalid S3 URI format: {s3_uri}. Expected format: 's3://bucket/key'"
            }
        
        s3_bucket, s3_key = uri_parts
        
        # Determine logical key (flattened or full path)
        if flatten:
            # Use just the filename as logical key
            logical_key = s3_key.split("/")[-1]
        else:
            # Use the full S3 key as logical key
            logical_key = s3_key
        
        entries.append({
            "logicalKey": logical_key,
            "physicalKey": s3_uri,
            "meta": metadata or {}
        })
    
    # GraphQL mutation
    mutation = """
    mutation PackageConstruct($params: PackagePushParams!, $src: PackageConstructSource!) {
        packageConstruct(params: $params, src: $src) {
            ... on PackagePushSuccess {
                package {
                    bucket
                    name
                }
                revision {
                    hash
                    modified
                    message
                    metadata
                    userMeta
                }
            }
            ... on InvalidInput {
                errors {
                    path
                    message
                    name
                }
            }
            ... on OperationError {
                message
                name
                context
            }
        }
    }
    """
    
    variables = {
        "params": {
            "bucket": bucket,
            "name": name,
            "message": message,
            "userMeta": metadata or {}
        },
        "src": {
            "entries": entries
        }
    }
    
    try:
        result = catalog_graphql_query(
            registry_url=registry_url,
            query=mutation,
            variables=variables,
            auth_token=auth_token,
        )
        
        if result.get("packageConstruct"):
            construct_result = result["packageConstruct"]
            
            # Check for success (PackagePushSuccess)
            if "package" in construct_result:
                return {
                    "success": True,
                    "package": construct_result["package"],
                    "revision": construct_result["revision"],
                    "message": f"Package {package_name} created successfully",
                    "top_hash": construct_result.get("revision", {}).get("hash"),
                    "entries_added": len(s3_uris),
                }
            
            # Check for InvalidInput errors
            if "errors" in construct_result:
                errors = construct_result.get("errors", [])
                error_messages = []
                for err in errors:
                    if isinstance(err, dict):
                        msg = err.get("message", "Unknown error")
                        path = err.get("path", "")
                        if path:
                            error_messages.append(f"{path}: {msg}")
                        else:
                            error_messages.append(msg)
                return {
                    "success": False,
                    "error": f"Invalid input: {'; '.join(error_messages) if error_messages else 'Package validation failed'}",
                    "error_type": "InvalidInput",
                }
            
            # Check for OperationError
            if "message" in construct_result:
                error_name = construct_result.get("name", "OperationError")
                error_message = construct_result.get("message", "Unknown operation error")
                error_context = construct_result.get("context", {})
                
                error_details = f"Operation failed: {error_message}"
                if error_context:
                    error_details += f" (context: {error_context})"
                
                return {
                    "success": False,
                    "error": error_details,
                    "error_type": error_name,
                }
            
            # Unexpected response format
            return {
                "success": False,
                "error": "Package creation failed - unexpected response format from backend"
            }
        else:
            return {
                "success": False,
                "error": "No result from packageConstruct mutation"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"GraphQL package creation failed: {str(e)}"
        }


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


def catalog_create_browsing_session(
    *,
    registry_url: str,
    bucket: str,
    package_name: str,
    package_hash: str,
    ttl: int = 180,
    auth_token: Optional[str],
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """Create a browsing session for accessing package files via REST.
    
    The browsing session allows downloading files from a package without
    direct AWS credentials. The backend assumes the necessary IAM role.
    
    Args:
        registry_url: Quilt catalog URL
        bucket: S3 bucket name
        package_name: Package name (e.g., "demo-team/visualization-showcase")
        package_hash: Package top hash
        ttl: Session time-to-live in seconds (default: 180)
        auth_token: JWT authentication token
        timeout: Request timeout
        
    Returns:
        Dict with 'id' (session ID) and 'expires' (expiration timestamp)
        
    Raises:
        ValueError: If session creation fails
    """
    token = _require_token(auth_token)
    
    # Format: quilt+s3://bucket#package=name@hash (or package=name:tag)
    # The fragment (#) contains package=name@hash
    scope = f"quilt+s3://{bucket}#package={package_name}@{package_hash}"
    
    query = """
    mutation BrowsingSessionCreate($scope: String!, $ttl: Int!) {
        browsingSessionCreate(scope: $scope, ttl: $ttl) {
            ... on BrowsingSession {
                id
                expires
            }
            ... on InvalidInput {
                errors {
                    name
                    message
                }
            }
            ... on OperationError {
                message
            }
        }
    }
    """
    
    result = catalog_graphql_query(
        registry_url=registry_url,
        query=query,
        variables={"scope": scope, "ttl": ttl},
        auth_token=token,
        timeout=timeout,
    )
    
    session_result = result.get("browsingSessionCreate", {})
    
    # Handle errors
    if "errors" in session_result:
        error_messages = [err.get("message", "Unknown error") for err in session_result["errors"]]
        raise ValueError(f"Failed to create browsing session: {'; '.join(error_messages)}")
    
    if "message" in session_result:  # OperationError
        raise ValueError(f"Failed to create browsing session: {session_result['message']}")
    
    if "id" not in session_result:
        raise ValueError("Browsing session creation returned unexpected response")
    
    return session_result


def catalog_browse_file(
    *,
    registry_url: str,
    session_id: str,
    path: str,
    auth_token: Optional[str],
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Get a presigned URL for a file in a package via browsing session.
    
    This uses the backend's /browse/ REST endpoint which assumes the
    necessary IAM role and generates presigned S3 URLs.
    
    Args:
        registry_url: Quilt catalog URL
        session_id: Browsing session ID from catalog_create_browsing_session
        path: File path within the package (logical key)
        auth_token: JWT authentication token
        timeout: Request timeout
        
    Returns:
        Presigned S3 URL as a string
        
    Raises:
        ValueError: If file not found or session invalid
    """
    token = _require_token(auth_token)
    
    browse_url = f"{registry_url.rstrip('/')}/browse/{session_id}/{path.lstrip('/')}"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Quilt-MCP-Server/Stateless",
    }
    
    # Make request - this will redirect to a presigned URL
    response = requests.get(
        browse_url,
        headers=headers,
        timeout=timeout,
        allow_redirects=False,  # We want the redirect URL, not to follow it
    )
    
    if response.status_code == 302 or response.status_code == 303:
        # Return the redirect location (presigned URL)
        return response.headers.get("Location", "")
    elif response.status_code == 404:
        raise ValueError(f"File not found: {path}")
    elif response.status_code == 403:
        raise ValueError("Session expired or invalid")
    else:
        response.raise_for_status()
        raise ValueError(f"Unexpected response: {response.status_code}")
