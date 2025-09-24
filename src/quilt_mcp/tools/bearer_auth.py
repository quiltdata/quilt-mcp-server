"""Bearer Token Authentication Tools for Quilt MCP Server.

This module provides tools for bearer token authentication, allowing the MCP server
to authenticate with Quilt's APIs using OAuth2 access tokens.
"""

import logging
import os
from typing import Dict, Any, Optional

from quilt_mcp.runtime_context import get_runtime_access_token, get_runtime_auth, get_runtime_environment

logger = logging.getLogger(__name__)


def auth_status() -> Dict[str, Any]:
    """Get the current authentication status.
    
    Returns:
        Dictionary containing authentication status and user information
    """
    try:
        from quilt_mcp.services.auth_service import get_auth_service
        
        auth_service = get_auth_service()
        
        # Get authentication status
        auth_method = getattr(auth_service, '_auth_method', None)
        current_auth_status = getattr(auth_service, '_auth_status', None)
        
        result = {
            "authenticated": current_auth_status.value == "authenticated" if current_auth_status else False,
            "method": auth_method.value if auth_method else "none",
            "status": current_auth_status.value if current_auth_status else "unauthenticated",
            "debug_info": {
                "runtime_environment": get_runtime_environment(),
                "runtime_token_available": get_runtime_access_token() is not None,
                "env_token_available": os.environ.get("QUILT_ACCESS_TOKEN") is not None,
                "auth_service_initialized": auth_service is not None
            }
        }
        
        # Add user info if available
        user_info = getattr(auth_service, '_user_info', None)
        if user_info:
            result["user_info"] = user_info
        
        # Add bearer token specific info
        if auth_method and auth_method.value == "bearer_token":
            result["bearer_token_authenticated"] = True
            result["token_source"] = "Authorization header"
            
            # Check if we have an authenticated session
            session = auth_service.get_authenticated_session()
            if session:
                result["authenticated_session_available"] = True
            else:
                result["authenticated_session_available"] = False
        
        return result
        
    except Exception as e:  # pragma: no cover
        logger.error("Error getting auth status: %s", e)
        return {
            "authenticated": False,
            "method": "none",
            "status": "error",
            "error": str(e)
        }


def validate_bearer_token(access_token: str) -> Dict[str, Any]:
    """Validate a bearer token with Quilt's authentication system.
    
    Args:
        access_token: The bearer token to validate
        
    Returns:
        Dictionary containing validation results
    """
    try:
        from quilt_mcp.services.bearer_auth_service import get_bearer_auth_service
        
        bearer_auth_service = get_bearer_auth_service()
        
        # Validate the token
        status, user_info = bearer_auth_service.validate_bearer_token(access_token)
        
        result = {
            "valid": status.value == "authenticated",
            "status": status.value,
        }
        
        if user_info:
            result["user_info"] = user_info
            result["username"] = user_info.get("username", "unknown")
        
        return result
        
    except Exception as e:  # pragma: no cover
        logger.error("Error validating bearer token: %s", e)
        return {
            "valid": False,
            "status": "error",
            "error": str(e)
        }


def get_user_info() -> Dict[str, Any]:
    """Get current user information from authentication.
    
    Returns:
        Dictionary containing user information
    """
    try:
        from quilt_mcp.services.auth_service import get_auth_service
        
        auth_service = get_auth_service()
        auth_method = getattr(auth_service, '_auth_method', None)
        runtime_auth = get_runtime_auth()
        
        if auth_method and auth_method.value == "bearer_token":
            user_info = getattr(auth_service, '_user_info', None)
            if user_info:
                return {
                    "authenticated": True,
                    "method": "bearer_token",
                    "user_info": user_info
                }
            else:
                return {
                    "authenticated": False,
                    "method": "bearer_token",
                    "error": "No user info available"
                }
        if runtime_auth and runtime_auth.extras.get("user_info"):
            return {
                "authenticated": True,
                "method": runtime_auth.scheme,
                "user_info": runtime_auth.extras.get("user_info")
            }
        else:
            return {
                "authenticated": False,
                "method": auth_method.value if auth_method else "none",
                "error": "Not using bearer token authentication"
            }
            
    except Exception as e:  # pragma: no cover
        logger.error("Error getting user info: %s", e)
        return {
            "authenticated": False,
            "error": str(e)
        }


def validate_bucket_access(bucket_name: str, operation: str = "read") -> Dict[str, Any]:
    """Validate if the current user has access to a specific bucket and operation.
    
    Args:
        bucket_name: Name of the bucket to check access for
        operation: Operation type ("read", "write", "delete", "list")
        
    Returns:
        Dictionary containing validation results
    """
    try:
        from quilt_mcp.services.bearer_auth_service import get_bearer_auth_service
        
        bearer_auth_service = get_bearer_auth_service()
        
        access_token = get_runtime_access_token()
        if not access_token:
            access_token = os.environ.get("QUILT_ACCESS_TOKEN")
        if not access_token:
            return {
                "success": False,
                "error": "No bearer token available"
            }
        
        # Validate bucket access
        allowed, reason = bearer_auth_service.validate_bucket_access_with_token(access_token, bucket_name, operation)
        
        return {
            "success": True,
            "allowed": allowed,
            "bucket": bucket_name,
            "operation": operation,
            "reason": reason if not allowed else None
        }
        
    except Exception as e:  # pragma: no cover
        logger.error("Error validating bucket access: %s", e)
        return {
            "success": False,
            "error": str(e)
        }


def get_user_permissions() -> Dict[str, Any]:
    """Get the current user's permissions and authorization level.
    
    Returns:
        Dictionary containing user permissions
    """
    try:
        from quilt_mcp.services.bearer_auth_service import get_bearer_auth_service
        
        bearer_auth_service = get_bearer_auth_service()
        
        access_token = get_runtime_access_token()
        if not access_token:
            access_token = os.environ.get("QUILT_ACCESS_TOKEN")
        if not access_token:
            return {
                "success": False,
                "error": "No bearer token available. The frontend needs to send an 'Authorization: Bearer <token>' header with the JWT token.",
                "debug_info": {
                    "runtime_token_available": get_runtime_access_token() is not None,
                    "env_token_available": os.environ.get("QUILT_ACCESS_TOKEN") is not None,
                    "runtime_environment": get_runtime_environment()
                }
            }
        
        # Get user permissions
        permissions = bearer_auth_service.get_user_permissions(access_token)
        
        if permissions:
            return {
                "success": True,
                "permissions": permissions
            }
        else:
            return {
                "success": False,
                "error": "Could not retrieve user permissions"
            }
        
    except Exception as e:  # pragma: no cover
        logger.error("Error getting user permissions: %s", e)
        return {
            "success": False,
            "error": str(e)
        }


def make_authenticated_request(method: str, url: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Make an authenticated request to Quilt's API.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        url: URL to request
        data: Optional data to send with the request
        
    Returns:
        Dictionary containing response data or error information
    """
    try:
        from quilt_mcp.services.auth_service import get_auth_service
        
        auth_service = get_auth_service()
        session = auth_service.get_authenticated_session()
        
        if not session:
            return {
                "success": False,
                "error": "No authenticated session available"
            }
        
        # Make the request
        response = session.request(method, url, json=data)
        
        return {
            "success": True,
            "status_code": response.status_code,
            "data": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text,
            "headers": dict(response.headers)
        }
        
    except Exception as e:  # pragma: no cover
        logger.error("Error making authenticated request: %s", e)
        return {
            "success": False,
            "error": str(e)
        }


def validate_tool_access(tool_name: str, bucket_name: str = None) -> Dict[str, Any]:
    """Validate if the current user has permission to use a specific tool.
    
    Args:
        tool_name: Name of the tool/operation to validate (e.g., "bucket_objects_list")
        bucket_name: Optional bucket name for bucket-specific validation
        
    Returns:
        Dictionary containing validation results
    """
    try:
        from quilt_mcp.services.bearer_auth_service import get_bearer_auth_service
        
        bearer_auth_service = get_bearer_auth_service()
        
        access_token = get_runtime_access_token()
        if not access_token:
            access_token = os.environ.get("QUILT_ACCESS_TOKEN")
        if not access_token:
            return {
                "success": False,
                "error": "No bearer token available"
            }
        
        # Validate tool access
        allowed, reason = bearer_auth_service.validate_tool_permissions(access_token, tool_name, bucket_name)
        
        return {
            "success": True,
            "allowed": allowed,
            "tool": tool_name,
            "bucket": bucket_name,
            "reason": reason if not allowed else None,
            "message": f"Tool '{tool_name}' {'allowed' if allowed else 'denied'}"
        }
        
    except Exception as e:  # pragma: no cover
        logger.error("Error validating tool access: %s", e)
        return {
            "success": False,
            "error": str(e)
        }


def list_available_tools() -> Dict[str, Any]:
    """List all available tools and their permission requirements.
    
    Returns:
        Dictionary containing tool categories and their permission mappings
    """
    try:
        from quilt_mcp.services.bearer_auth_service import get_bearer_auth_service
        
        bearer_auth_service = get_bearer_auth_service()
        
        access_token = get_runtime_access_token()
        if not access_token:
            access_token = os.environ.get("QUILT_ACCESS_TOKEN")
        if not access_token:
            return {
                "success": False,
                "error": "No bearer token available"
            }
        
        # Get user permissions
        permissions = bearer_auth_service.get_user_permissions(access_token)
        if not permissions:
            return {
                "success": False,
                "error": "Could not retrieve user permissions"
            }
        
        allowed_tools = permissions.get("tools", [])
        allowed_buckets = permissions.get("buckets", [])
        
        # Get tool permission mappings
        tool_permissions = getattr(bearer_auth_service, 'tool_permissions', {})
        
        # Categorize tools
        tool_categories = {
            "s3_bucket_operations": {
                "description": "S3 bucket and object operations",
                "tools": ["bucket_objects_list", "bucket_object_info", "bucket_object_text", 
                         "bucket_object_fetch", "bucket_objects_put", "bucket_object_link"]
            },
            "package_operations": {
                "description": "Quilt package creation and management",
                "tools": ["package_create", "package_update", "package_delete", "package_browse",
                         "package_contents_search", "package_diff", "create_package_enhanced", 
                         "create_package_from_s3", "package_create_from_s3"]
            },
            "athena_glue_operations": {
                "description": "AWS Athena queries and Glue Data Catalog discovery",
                "tools": ["athena_query_execute", "athena_databases_list", "athena_tables_list",
                         "athena_table_schema", "athena_workgroups_list", "athena_query_history"]
            },
            "tabulator_operations": {
                "description": "Quilt tabulator table management",
                "tools": ["tabulator_tables_list", "tabulator_table_create"]
            },
            "search_operations": {
                "description": "Search and discovery tools",
                "tools": ["unified_search", "packages_search"]
            },
            "permission_operations": {
                "description": "Permission discovery and validation",
                "tools": ["aws_permissions_discover", "bucket_access_check", "bucket_recommendations_get"]
            }
        }
        
        # Build response with permission details
        result = {
            "success": True,
            "user_permissions": {
                "level": permissions.get("level", "unknown"),
                "buckets": allowed_buckets,
                "tools": allowed_tools
            },
            "tool_categories": {}
        }
        
        # Process each category
        for category_name, category_info in tool_categories.items():
            category_result = {
                "description": category_info["description"],
                "tools": {}
            }
            
            for tool_name in category_info["tools"]:
                # Check if user has access to this tool
                if allowed_tools == ["*"] or tool_name in allowed_tools:
                    tool_result = {
                        "allowed": True,
                        "permissions": tool_permissions.get(tool_name, []),
                        "description": f"User has access to {tool_name}"
                    }
                else:
                    tool_result = {
                        "allowed": False,
                        "permissions": tool_permissions.get(tool_name, []),
                        "description": f"User does not have access to {tool_name}"
                    }
                
                category_result["tools"][tool_name] = tool_result
            
            result["tool_categories"][category_name] = category_result
        
        return result
        
    except Exception as e:  # pragma: no cover
        logger.error("Error listing available tools: %s", e)
        return {
            "success": False,
            "error": str(e)
        }
