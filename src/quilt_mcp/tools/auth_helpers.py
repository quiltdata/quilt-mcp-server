"""Unified Authentication Helpers for Quilt MCP Tools.

This module provides unified authentication helpers that replace the existing
tool-specific authentication functions with a consistent interface.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Callable

from quilt_mcp.services.unified_auth_service import get_unified_auth_service, AuthResult

logger = logging.getLogger(__name__)


def check_unified_authorization(tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    """Unified authorization check for all tools.
    
    Args:
        tool_name: Name of the MCP tool being called
        tool_args: Arguments passed to the tool
        
    Returns:
        Dictionary with authorization result and user info
    """
    try:
        # Get unified auth service
        auth_service = get_unified_auth_service()
        
        # Authenticate request
        auth_result = auth_service.authenticate_request()
        
        if not auth_result.success:
            return {
                "authorized": False, 
                "error": auth_result.error,
                "client_type": auth_result.client_type.value if auth_result.client_type else "unknown"
            }
        
        # Check tool-specific authorization
        if not auth_service.authorize_tool(tool_name, tool_args, auth_result):
            return {
                "authorized": False,
                "error": f"Tool {tool_name} not authorized for user",
                "client_type": auth_result.client_type.value,
                "user_info": auth_result.user_info
            }
        
        # Return success with all necessary information
        return {
            "authorized": True,
            "client_type": auth_result.client_type.value,
            "user_info": auth_result.user_info,
            "aws_credentials": auth_result.aws_credentials,
            "quilt_api_token": auth_result.quilt_api_token,
            "auth_method": auth_result.auth_method
        }
        
    except Exception as e:
        logger.error("Unified authorization failed for tool %s: %s", tool_name, e)
        return {
            "authorized": False,
            "error": f"Authorization failed: {str(e)}",
            "client_type": "unknown"
        }


def get_aws_session_for_tool(tool_name: str, service: str) -> Optional[Any]:
    """Get AWS session for specific service and tool.
    
    Args:
        tool_name: Name of the tool
        service: AWS service name (e.g., 's3', 'athena', 'glue')
        
    Returns:
        boto3 client for the service, or None if not available
    """
    try:
        auth_service = get_unified_auth_service()
        session = auth_service.get_aws_session(service)
        
        if session:
            return session.client(service)
        
        logger.warning("No AWS session available for tool %s, service %s", tool_name, service)
        return None
        
    except Exception as e:
        logger.error("Failed to get AWS session for tool %s, service %s: %s", tool_name, service, e)
        return None


def get_quilt_api_for_tool(tool_name: str) -> Optional[Any]:
    """Get Quilt API client for specific tool.
    
    Args:
        tool_name: Name of the tool
        
    Returns:
        Quilt API client, or None if not available
    """
    try:
        auth_service = get_unified_auth_service()
        return auth_service.get_quilt_api_client()
        
    except Exception as e:
        logger.error("Failed to get Quilt API client for tool %s: %s", tool_name, e)
        return None


def validate_tool_permissions(tool_name: str, user_permissions: Dict[str, Any]) -> bool:
    """Validate tool permissions for user.
    
    Args:
        tool_name: Name of the tool
        user_permissions: User's permission information
        
    Returns:
        True if user has required permissions
    """
    try:
        from ..services.permission_mapper import get_permission_mapper
        
        permission_mapper = get_permission_mapper()
        required_permissions = permission_mapper.get_tool_permissions(tool_name)
        
        if not required_permissions:
            logger.debug("No permission requirements found for tool %s", tool_name)
            return True  # Allow if no requirements
        
        # Check AWS permissions
        aws_permissions = required_permissions.get("aws_permissions", [])
        user_aws_permissions = user_permissions.get("permissions", [])
        
        for required_perm in aws_permissions:
            if required_perm not in user_aws_permissions and "*" not in user_aws_permissions:
                logger.debug("User missing required AWS permission %s for tool %s", required_perm, tool_name)
                return False
        
        # Check Quilt permissions
        quilt_permissions = required_permissions.get("quilt_permissions", [])
        user_quilt_permissions = user_permissions.get("quilt_permissions", [])
        
        for required_perm in quilt_permissions:
            if required_perm not in user_quilt_permissions and "*" not in user_quilt_permissions:
                logger.debug("User missing required Quilt permission %s for tool %s", required_perm, tool_name)
                return False
        
        return True
        
    except Exception as e:
        logger.error("Permission validation failed for tool %s: %s", tool_name, e)
        return False


def check_bucket_access(bucket_name: str, user_buckets: list) -> bool:
    """Check if user has access to specific bucket.
    
    Args:
        bucket_name: Name of the bucket
        user_buckets: List of buckets user can access
        
    Returns:
        True if user has access
    """
    if not bucket_name:
        return False
    
    # Check for wildcard access
    if "*" in user_buckets:
        return True
    
    # Check for exact match
    if bucket_name in user_buckets:
        return True
    
    # Check for pattern matching (e.g., "quilt-*")
    for pattern in user_buckets:
        if "*" in pattern:
            import fnmatch
            if fnmatch.fnmatch(bucket_name, pattern):
                return True
    
    return False


def get_authorization_context(tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    """Get complete authorization context for tool execution.
    
    Args:
        tool_name: Name of the tool
        tool_args: Tool arguments
        
    Returns:
        Dictionary with complete authorization context
    """
    try:
        # Get unified authorization
        auth_result = check_unified_authorization(tool_name, tool_args)
        
        if not auth_result["authorized"]:
            return auth_result
        
        # Add tool-specific context
        context = {
            **auth_result,
            "aws_sessions": {},
            "quilt_api": None
        }
        
        # Get AWS sessions for required services
        from ..services.permission_mapper import get_permission_mapper
        permission_mapper = get_permission_mapper()
        required_permissions = permission_mapper.get_tool_permissions(tool_name)
        
        if required_permissions:
            required_services = required_permissions.get("required_services", [])
            for service in required_services:
                session = get_aws_session_for_tool(tool_name, service)
                if session:
                    context["aws_sessions"][service] = session
        
        # Get Quilt API if needed
        if required_permissions and "quilt_api" in required_permissions.get("required_services", []):
            context["quilt_api"] = get_quilt_api_for_tool(tool_name)
        
        return context
        
    except Exception as e:
        logger.error("Failed to get authorization context for tool %s: %s", tool_name, e)
        return {
            "authorized": False,
            "error": f"Failed to get authorization context: {str(e)}",
            "client_type": "unknown"
        }


def with_unified_auth(tool_name: str):
    """Decorator to add unified authentication to tool functions.
    
    Args:
        tool_name: Name of the tool
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            # Get authorization context
            context = get_authorization_context(tool_name, kwargs)
            
            if not context["authorized"]:
                return {
                    "success": False,
                    "error": context["error"],
                    "client_type": context.get("client_type", "unknown")
                }
            
            # Add context to function arguments
            kwargs["_auth_context"] = context
            
            # Call original function
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


# Tool-specific authentication helpers

def check_s3_authorization(tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    """S3-specific authorization check.
    
    Args:
        tool_name: Name of the S3 tool
        tool_args: Tool arguments
        
    Returns:
        Authorization result with S3 client
    """
    auth_result = check_unified_authorization(tool_name, tool_args)
    
    if not auth_result["authorized"]:
        return auth_result
    
    # Get S3 client
    s3_client = get_aws_session_for_tool(tool_name, "s3")
    if not s3_client:
        return {
            "authorized": False,
            "error": "S3 client not available",
            "client_type": auth_result["client_type"]
        }
    
    # Check bucket access if specified
    bucket_name = tool_args.get("bucket_name")
    if bucket_name:
        user_buckets = auth_result["user_info"].get("buckets", [])
        if not check_bucket_access(bucket_name, user_buckets):
            return {
                "authorized": False,
                "error": f"Access denied to bucket {bucket_name}",
                "client_type": auth_result["client_type"]
            }
    
    return {
        **auth_result,
        "s3_client": s3_client
    }


def check_package_authorization(tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    """Package-specific authorization check.
    
    Args:
        tool_name: Name of the package tool
        tool_args: Tool arguments
        
    Returns:
        Authorization result with S3 and Quilt API clients
    """
    auth_result = check_unified_authorization(tool_name, tool_args)
    
    if not auth_result["authorized"]:
        return auth_result
    
    # Get S3 client
    s3_client = get_aws_session_for_tool(tool_name, "s3")
    if not s3_client:
        return {
            "authorized": False,
            "error": "S3 client not available",
            "client_type": auth_result["client_type"]
        }
    
    # Get Quilt API client
    quilt_api = get_quilt_api_for_tool(tool_name)
    if not quilt_api:
        return {
            "authorized": False,
            "error": "Quilt API client not available",
            "client_type": auth_result["client_type"]
        }
    
    return {
        **auth_result,
        "s3_client": s3_client,
        "quilt_api": quilt_api
    }


def check_athena_authorization(tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    """Athena/Glue-specific authorization check.
    
    Args:
        tool_name: Name of the Athena/Glue tool
        tool_args: Tool arguments
        
    Returns:
        Authorization result with Athena and Glue clients
    """
    auth_result = check_unified_authorization(tool_name, tool_args)
    
    if not auth_result["authorized"]:
        return auth_result
    
    # Get Athena client
    athena_client = get_aws_session_for_tool(tool_name, "athena")
    if not athena_client:
        return {
            "authorized": False,
            "error": "Athena client not available",
            "client_type": auth_result["client_type"]
        }
    
    # Get Glue client
    glue_client = get_aws_session_for_tool(tool_name, "glue")
    if not glue_client:
        return {
            "authorized": False,
            "error": "Glue client not available",
            "client_type": auth_result["client_type"]
        }
    
    return {
        **auth_result,
        "athena_client": athena_client,
        "glue_client": glue_client
    }


def check_search_authorization(tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    """Search-specific authorization check.
    
    Args:
        tool_name: Name of the search tool
        tool_args: Tool arguments
        
    Returns:
        Authorization result with Quilt API client
    """
    auth_result = check_unified_authorization(tool_name, tool_args)
    
    if not auth_result["authorized"]:
        return auth_result
    
    # Get Quilt API client
    quilt_api = get_quilt_api_for_tool(tool_name)
    if not quilt_api:
        return {
            "authorized": False,
            "error": "Quilt API client not available",
            "client_type": auth_result["client_type"]
        }
    
    return {
        **auth_result,
        "quilt_api": quilt_api
    }


def check_permission_authorization(tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    """Permission-specific authorization check.
    
    Args:
        tool_name: Name of the permission tool
        tool_args: Tool arguments
        
    Returns:
        Authorization result with IAM client
    """
    auth_result = check_unified_authorization(tool_name, tool_args)
    
    if not auth_result["authorized"]:
        return auth_result
    
    # Get IAM client
    iam_client = get_aws_session_for_tool(tool_name, "iam")
    if not iam_client:
        return {
            "authorized": False,
            "error": "IAM client not available",
            "client_type": auth_result["client_type"]
        }
    
    return {
        **auth_result,
        "iam_client": iam_client
    }
