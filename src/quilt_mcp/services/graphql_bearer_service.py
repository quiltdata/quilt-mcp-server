"""GraphQL Bearer Token Service for Quilt MCP Server.

This service provides GraphQL query execution using bearer token authentication,
replacing the old quilt3 session-based approach.
"""

import os
import logging
import requests
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

from quilt_mcp.runtime_context import get_runtime_access_token


class GraphQLBearerService:
    """GraphQL service using bearer token authentication."""
    
    def __init__(self, catalog_url: str = "https://demo.quiltdata.com"):
        """Initialize the GraphQL bearer service.
        
        Args:
            catalog_url: Quilt catalog URL for GraphQL endpoints
        """
        self.catalog_url = catalog_url.rstrip('/')
    
    def get_graphql_endpoint(self) -> Tuple[Optional[requests.Session], Optional[str]]:
        """Get authenticated session and GraphQL endpoint URL.
        
        Returns:
            Tuple of (authenticated_session, graphql_url) or (None, None)
        """
        try:
            # Get access token from runtime context or environment (middleware)
            access_token = get_runtime_access_token()
            if not access_token:
                access_token = os.environ.get("QUILT_ACCESS_TOKEN")
            if not access_token:
                logger.debug("No QUILT_ACCESS_TOKEN environment variable set")
                return None, None
            
            # Get bearer auth service to create authenticated session
            from quilt_mcp.services.bearer_auth_service import get_bearer_auth_service
            bearer_auth_service = get_bearer_auth_service()
            
            # Create authenticated session
            session = bearer_auth_service.get_authenticated_session(access_token)
            if not session:
                logger.warning("Failed to create authenticated session for GraphQL")
                return None, None
            
            # Construct GraphQL endpoint URL
            graphql_url = urljoin(self.catalog_url + "/", "graphql")
            
            logger.debug("GraphQL endpoint ready: %s", graphql_url)
            return session, graphql_url
            
        except Exception as e:
            logger.error("Error getting GraphQL endpoint: %s", e)
            return None, None
    
    def execute_query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GraphQL query using bearer token authentication.
        
        Args:
            query: GraphQL query string
            variables: Variables dictionary to bind
            
        Returns:
            Dict with raw `data`, optional `errors`, and `success` flag
        """
        session, graphql_url = self.get_graphql_endpoint()
        if not session or not graphql_url:
            return {
                "success": False,
                "error": "GraphQL endpoint or authentication unavailable. Ensure bearer token is provided.",
            }
        
        try:
            # Execute GraphQL query
            payload = {"query": query, "variables": variables or {}}
            resp = session.post(graphql_url, json=payload)
            
            if resp.status_code != 200:
                logger.warning("GraphQL HTTP %d: %s", resp.status_code, resp.text)
                return {
                    "success": False,
                    "error": f"GraphQL HTTP {resp.status_code}: {resp.text}",
                }
            
            # Parse response
            response_data = resp.json()
            
            # Check for GraphQL errors
            if "errors" in response_data and response_data["errors"]:
                logger.warning("GraphQL errors: %s", response_data["errors"])
                return {
                    "success": False,
                    "data": response_data.get("data"),
                    "errors": response_data["errors"],
                    "error": f"GraphQL errors: {response_data['errors']}",
                }
            
            logger.debug("GraphQL query executed successfully")
            return {
                "success": True,
                "data": response_data.get("data"),
                "errors": response_data.get("errors", []),
            }
            
        except Exception as e:
            logger.error("GraphQL request failed: %s", e)
            return {"success": False, "error": f"GraphQL request failed: {e}"}
    
    def search_objects(
        self, 
        bucket: str, 
        object_filter: Optional[Dict[str, Any]] = None, 
        first: int = 100, 
        after: str = ""
    ) -> Dict[str, Any]:
        """Search bucket objects via GraphQL.
        
        Args:
            bucket: S3 bucket name or s3:// URI
            object_filter: Dictionary of filter fields compatible with the catalog schema
            first: Page size (default 100)
            after: Cursor for pagination
            
        Returns:
            Dict with objects, pagination info, and the effective filter used
        """
        # Normalize bucket name
        bkt = bucket.replace("s3://", "").rstrip("/")
        
        # GraphQL query for object search
        query = """
        query($bucket: String!, $filter: ObjectFilterInput, $first: Int, $after: String) {
            objects(bucket: $bucket, filter: $filter, first: $first, after: $after) {
                edges {
                    node {
                        key
                        size
                        updated
                        contentType
                        extension
                        package {
                            name
                            topHash
                            tag
                        }
                    }
                    cursor
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
        """
        
        variables = {
            "bucket": bkt,
            "filter": object_filter or {},
            "first": first,
            "after": after
        }
        
        result = self.execute_query(query, variables)
        
        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "GraphQL search failed"),
                "bucket": bkt,
                "objects": [],
            }
        
        # Process the GraphQL response
        data = result.get("data", {})
        objects_data = data.get("objects", {})
        edges = objects_data.get("edges", [])
        page_info = objects_data.get("pageInfo", {})
        
        # Convert to expected format
        objects = []
        for edge in edges:
            node = edge["node"]
            obj_info = {
                "key": node["key"],
                "size": node.get("size"),
                "updated": node.get("updated"),
                "contentType": node.get("contentType"),
                "extension": node.get("extension"),
            }
            
            # Add package info if available
            if node.get("package"):
                obj_info["package"] = node["package"]
            
            objects.append(obj_info)
        
        return {
            "success": True,
            "bucket": bkt,
            "objects": objects,
            "pagination": {
                "endCursor": page_info.get("endCursor"),
                "hasNextPage": page_info.get("hasNextPage", False),
                "total": len(objects)
            },
            "filter": object_filter or {},
        }
    
    def search_packages(
        self, 
        query: str, 
        registry: str = "s3://quilt-sandbox-bucket",  # pylint: disable=unused-argument
        limit: int = 10,
        from_: int = 0
    ) -> Dict[str, Any]:
        """Search packages via GraphQL.
        
        Args:
            query: Search query string
            registry: Registry URL
            limit: Maximum results to return
            from_: Starting offset
            
        Returns:
            Dict with search results
        """
        # GraphQL query for package search
        gql_query = """
        query($query: String!, $limit: Int, $offset: Int) {
            packages(query: $query, first: $limit, after: $offset) {
                edges {
                    node {
                        name
                        topHash
                        tag
                        updated
                        description
                        owner
                    }
                    cursor
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
        """
        
        variables = {
            "query": query,
            "limit": limit,
            "offset": from_
        }
        
        result = self.execute_query(gql_query, variables)
        
        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "GraphQL package search failed"),
                "packages": [],
            }
        
        # Process the GraphQL response
        data = result.get("data", {})
        packages_data = data.get("packages", {})
        edges = packages_data.get("edges", [])
        page_info = packages_data.get("pageInfo", {})
        
        # Convert to expected format
        packages = []
        for edge in edges:
            node = edge["node"]
            package_info = {
                "name": node["name"],
                "topHash": node.get("topHash"),
                "tag": node.get("tag"),
                "updated": node.get("updated"),
                "description": node.get("description"),
                "owner": node.get("owner"),
            }
            packages.append(package_info)
        
        return {
            "success": True,
            "packages": packages,
            "pagination": {
                "endCursor": page_info.get("endCursor"),
                "hasNextPage": page_info.get("hasNextPage", False),
                "total": len(packages)
            },
            "query": query,
        }


# Global instance
_graphql_bearer_service = None


def get_graphql_bearer_service(catalog_url: str = "https://demo.quiltdata.com") -> GraphQLBearerService:
    """Get the global GraphQL bearer service instance.
    
    Args:
        catalog_url: Quilt catalog URL for GraphQL endpoints
        
    Returns:
        GraphQLBearerService instance
    """
    global _graphql_bearer_service
    if _graphql_bearer_service is None:
        _graphql_bearer_service = GraphQLBearerService(catalog_url)
    return _graphql_bearer_service
