"""JWT Authentication tools for Quilt MCP Server.

This module provides tools for testing and validating JWT token authentication.
"""

import os
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def validate_jwt_token(auth_header: str = None) -> Dict[str, Any]:
    """Validate JWT token from Authorization header.
    
    Args:
        auth_header: Authorization header (optional, will use from request if not provided)
        
    Returns:
        Dictionary containing validation results
    """
    try:
        from quilt_mcp.services.bearer_auth_service import get_bearer_auth_service
        
        bearer_auth_service = get_bearer_auth_service()
        
        # Get auth header from environment if not provided
        if not auth_header:
            auth_header = os.environ.get("HTTP_AUTHORIZATION", "")
        
        if not auth_header:
            return {
                "success": False,
                "error": "No Authorization header found"
            }
        
        # Decode JWT token
        token_payload = bearer_auth_service.decode_jwt_token(auth_header)
        if not token_payload:
            return {
                "success": False,
                "error": "Failed to decode JWT token"
            }
        
        # Extract authorization claims
        auth_claims = bearer_auth_service.extract_auth_claims(token_payload)
        
        return {
            "success": True,
            "token_payload": {
                "id": token_payload.get("id"),
                "exp": token_payload.get("exp"),
                "iss": token_payload.get("iss"),
                "aud": token_payload.get("aud")
            },
            "authorization_claims": auth_claims,
            "validation_summary": {
                "has_permissions": len(auth_claims.get("permissions", [])) > 0,
                "has_roles": len(auth_claims.get("roles", [])) > 0,
                "has_buckets": len(auth_claims.get("buckets", [])) > 0,
                "permission_count": len(auth_claims.get("permissions", [])),
                "bucket_count": len(auth_claims.get("buckets", [])),
                "role_count": len(auth_claims.get("roles", []))
            }
        }
        
    except Exception as e:  # pragma: no cover
        logger.error("Error validating JWT token: %s", e)
        return {
            "success": False,
            "error": str(e)
        }


def test_tool_authorization(tool_name: str, tool_args: Dict[str, Any] = None) -> Dict[str, Any]:
    """Test authorization for a specific MCP tool.
    
    Args:
        tool_name: Name of the MCP tool to test
        tool_args: Arguments that would be passed to the tool
        
    Returns:
        Dictionary containing authorization test results
    """
    try:
        from quilt_mcp.services.bearer_auth_service import get_bearer_auth_service
        
        bearer_auth_service = get_bearer_auth_service()
        
        # Get auth header from environment
        auth_header = os.environ.get("HTTP_AUTHORIZATION", "")
        if not auth_header:
            return {
                "success": False,
                "error": "No Authorization header found"
            }
        
        # Decode JWT token
        token_payload = bearer_auth_service.decode_jwt_token(auth_header)
        if not token_payload:
            return {
                "success": False,
                "error": "Failed to decode JWT token"
            }
        
        # Extract authorization claims
        auth_claims = bearer_auth_service.extract_auth_claims(token_payload)
        
        # Test tool authorization
        is_authorized = bearer_auth_service.authorize_mcp_tool(
            tool_name, 
            tool_args or {}, 
            auth_claims
        )
        
        return {
            "success": True,
            "tool_name": tool_name,
            "tool_args": tool_args or {},
            "authorized": is_authorized,
            "user_permissions": auth_claims.get("permissions", []),
            "user_buckets": auth_claims.get("buckets", []),
            "user_roles": auth_claims.get("roles", [])
        }
        
    except Exception as e:  # pragma: no cover
        logger.error("Error testing tool authorization: %s", e)
        return {
            "success": False,
            "error": str(e)
        }


def get_user_permissions_summary() -> Dict[str, Any]:
    """Get a summary of user permissions from JWT token.
    
    Returns:
        Dictionary containing user permissions summary
    """
    try:
        from quilt_mcp.services.bearer_auth_service import get_bearer_auth_service
        
        bearer_auth_service = get_bearer_auth_service()
        
        # Get auth header from environment
        auth_header = os.environ.get("HTTP_AUTHORIZATION", "")
        if not auth_header:
            return {
                "success": False,
                "error": "No Authorization header found"
            }
        
        # Decode JWT token
        token_payload = bearer_auth_service.decode_jwt_token(auth_header)
        if not token_payload:
            return {
                "success": False,
                "error": "Failed to decode JWT token"
            }
        
        # Extract authorization claims
        auth_claims = bearer_auth_service.extract_auth_claims(token_payload)
        
        # Categorize permissions
        permissions = auth_claims.get("permissions", [])
        s3_permissions = [p for p in permissions if p.startswith("s3:")]
        athena_permissions = [p for p in permissions if p.startswith("athena:")]
        glue_permissions = [p for p in permissions if p.startswith("glue:")]
        iam_permissions = [p for p in permissions if p.startswith("iam:")]
        other_permissions = [p for p in permissions if not any(p.startswith(prefix) for prefix in ["s3:", "athena:", "glue:", "iam:"])]
        
        return {
            "success": True,
            "user_id": auth_claims.get("user_id", ""),
            "roles": auth_claims.get("roles", []),
            "groups": auth_claims.get("groups", []),
            "scope": auth_claims.get("scope", ""),
            "buckets": auth_claims.get("buckets", []),
            "permissions": {
                "total": len(permissions),
                "s3": s3_permissions,
                "athena": athena_permissions,
                "glue": glue_permissions,
                "iam": iam_permissions,
                "other": other_permissions
            },
            "permission_summary": {
                "s3_count": len(s3_permissions),
                "athena_count": len(athena_permissions),
                "glue_count": len(glue_permissions),
                "iam_count": len(iam_permissions),
                "other_count": len(other_permissions)
            }
        }
        
    except Exception as e:  # pragma: no cover
        logger.error("Error getting user permissions summary: %s", e)
        return {
            "success": False,
            "error": str(e)
        }


def test_all_tools_authorization() -> Dict[str, Any]:
    """Test authorization for all available MCP tools.
    
    Returns:
        Dictionary containing authorization test results for all tools
    """
    try:
        from quilt_mcp.services.bearer_auth_service import get_bearer_auth_service
        
        bearer_auth_service = get_bearer_auth_service()
        
        # Get auth header from environment
        auth_header = os.environ.get("HTTP_AUTHORIZATION", "")
        if not auth_header:
            return {
                "success": False,
                "error": "No Authorization header found"
            }
        
        # Decode JWT token
        token_payload = bearer_auth_service.decode_jwt_token(auth_header)
        if not token_payload:
            return {
                "success": False,
                "error": "Failed to decode JWT token"
            }
        
        # Extract authorization claims
        auth_claims = bearer_auth_service.extract_auth_claims(token_payload)
        
        # Test all tools
        tools_to_test = [
            "list_available_resources",
            "bucket_objects_list",
            "bucket_objects_put",
            "bucket_object_info",
            "bucket_object_text",
            "bucket_object_fetch",
            "bucket_object_link",
            "package_create",
            "package_update",
            "package_delete",
            "package_browse",
            "athena_query_execute",
            "athena_databases_list",
            "athena_tables_list",
            "unified_search",
            "packages_search",
            "aws_permissions_discover",
            "bucket_access_check"
        ]
        
        results = {}
        authorized_count = 0
        
        for tool_name in tools_to_test:
            is_authorized = bearer_auth_service.authorize_mcp_tool(
                tool_name, 
                {"bucket": "quilt-sandbox-bucket"},  # Test with a common bucket
                auth_claims
            )
            results[tool_name] = is_authorized
            if is_authorized:
                authorized_count += 1
        
        return {
            "success": True,
            "total_tools": len(tools_to_test),
            "authorized_tools": authorized_count,
            "unauthorized_tools": len(tools_to_test) - authorized_count,
            "tool_results": results,
            "user_permissions": auth_claims.get("permissions", []),
            "user_buckets": auth_claims.get("buckets", []),
            "user_roles": auth_claims.get("roles", [])
        }
        
    except Exception as e:  # pragma: no cover
        logger.error("Error testing all tools authorization: %s", e)
        return {
            "success": False,
            "error": str(e)
        }
