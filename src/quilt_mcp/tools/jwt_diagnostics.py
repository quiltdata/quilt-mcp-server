"""JWT authentication diagnostics and troubleshooting tools."""

from __future__ import annotations

import logging
from typing import Any, Dict

import jwt

from quilt_mcp.runtime_context import get_runtime_auth, get_runtime_environment, get_runtime_metadata
from quilt_mcp.services.bearer_auth_service import get_bearer_auth_service
from quilt_mcp.services.session_auth import get_session_auth_manager

logger = logging.getLogger(__name__)


def jwt_diagnostics() -> Dict[str, Any]:
    """Comprehensive JWT authentication diagnostics.
    
    This tool provides detailed information about the current JWT authentication state,
    helping diagnose authentication and authorization issues.
    
    Returns:
        Dict with comprehensive JWT diagnostic information
    """
    try:
        # Get runtime auth state
        auth_state = get_runtime_auth()
        runtime_env = get_runtime_environment()
        metadata = get_runtime_metadata()
        
        # Get session manager stats
        session_manager = get_session_auth_manager()
        session_stats = session_manager.get_stats()
        
        # Get bearer auth service config
        bearer_service = get_bearer_auth_service()
        
        diagnostics = {
            "runtime_environment": runtime_env,
            "has_auth_state": bool(auth_state),
            "auth_scheme": auth_state.scheme if auth_state else None,
            "session_stats": session_stats,
            "bearer_service": {
                "jwt_kid": bearer_service.jwt_kid,
                "secret_configured": bool(bearer_service.jwt_secret),
                "secret_length": len(bearer_service.jwt_secret) if bearer_service.jwt_secret else 0,
                "tool_permissions_defined": len(bearer_service.tool_permissions),
            },
        }
        
        # If we have auth state, add detailed info
        if auth_state:
            diagnostics["auth_details"] = {
                "has_access_token": bool(auth_state.access_token),
                "token_length": len(auth_state.access_token) if auth_state.access_token else 0,
                "has_claims": bool(auth_state.claims),
                "claim_keys": list(auth_state.claims.keys()) if auth_state.claims else [],
            }
            
            # If we have a JWT auth result in extras
            if auth_state.extras and "jwt_auth_result" in auth_state.extras:
                jwt_result = auth_state.extras["jwt_auth_result"]
                diagnostics["jwt_details"] = {
                    "user_id": jwt_result.user_id,
                    "username": jwt_result.username,
                    "buckets_count": len(jwt_result.buckets),
                    "permissions_count": len(jwt_result.permissions),
                    "roles_count": len(jwt_result.roles),
                    "buckets": jwt_result.buckets,
                    "permissions": jwt_result.permissions,
                    "roles": jwt_result.roles,
                    "has_aws_credentials": bool(jwt_result.aws_credentials),
                    "has_aws_role_arn": bool(jwt_result.aws_role_arn),
                }
        
        # Check metadata
        if metadata:
            diagnostics["metadata"] = metadata
        
        return {
            "success": True,
            "diagnostics": diagnostics,
            "summary": _generate_diagnostic_summary(diagnostics),
            "recommendations": _generate_recommendations(diagnostics),
        }
        
    except Exception as e:
        logger.error("Error running JWT diagnostics: %s", e)
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to run JWT diagnostics"
        }


def validate_jwt_token(token: str = None) -> Dict[str, Any]:
    """Validate a JWT token and show detailed information.
    
    Args:
        token: JWT token to validate (optional - uses current session token if not provided)
    
    Returns:
        Dict with token validation results and detailed information
    """
    try:
        # If no token provided, try to get from runtime context
        if not token:
            auth_state = get_runtime_auth()
            if auth_state and auth_state.access_token:
                token = auth_state.access_token
            else:
                return {
                    "success": False,
                    "error": "No token provided and no token in current session",
                    "hint": "Pass a JWT token as the 'token' parameter"
                }
        
        # Decode without verification first to see contents
        try:
            header = jwt.get_unverified_header(token)
            payload = jwt.decode(token, options={"verify_signature": False})
            
            unverified_info = {
                "header": header,
                "algorithm": header.get("alg"),
                "key_id": header.get("kid"),
                "payload_keys": list(payload.keys()),
                "issuer": payload.get("iss"),
                "audience": payload.get("aud"),
                "subject": payload.get("sub"),
                "issued_at": payload.get("iat"),
                "expires_at": payload.get("exp"),
                "buckets_count": len(payload.get("buckets", payload.get("b", []))),
                "permissions_count": len(payload.get("permissions", payload.get("p", []))),
                "roles": payload.get("roles", payload.get("r", [])),
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to decode token: {str(e)}",
                "hint": "Token appears to be malformed or corrupted"
            }
        
        # Now try to validate with secret
        bearer_service = get_bearer_auth_service()
        try:
            auth_header = f"Bearer {token}"
            jwt_result = bearer_service.authenticate_header(auth_header)
            
            return {
                "success": True,
                "validation": "passed",
                "unverified_info": unverified_info,
                "validated_claims": {
                    "user_id": jwt_result.user_id,
                    "username": jwt_result.username,
                    "buckets": jwt_result.buckets,
                    "permissions": jwt_result.permissions,
                    "roles": jwt_result.roles,
                    "has_aws_credentials": bool(jwt_result.aws_credentials),
                    "has_aws_role_arn": bool(jwt_result.aws_role_arn),
                },
                "message": "JWT token is valid and can be used for authentication"
            }
            
        except Exception as e:
            return {
                "success": False,
                "validation": "failed",
                "unverified_info": unverified_info,
                "error": str(e),
                "bearer_service_config": {
                    "secret_configured": bool(bearer_service.jwt_secret),
                    "secret_length": len(bearer_service.jwt_secret),
                    "expected_kid": bearer_service.jwt_kid,
                    "token_kid": header.get("kid"),
                    "kid_matches": header.get("kid") == bearer_service.jwt_kid,
                },
                "recommendations": [
                    "Verify JWT secret matches between frontend and backend",
                    "Check that token hasn't expired",
                    "Ensure token was signed with HS256 algorithm",
                    "Verify kid (key ID) matches between frontend and backend"
                ]
            }
        
    except Exception as e:
        logger.error("Error validating JWT token: %s", e)
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to validate JWT token"
        }


def session_diagnostics(session_id: str = None) -> Dict[str, Any]:
    """Get diagnostics for a specific session or all sessions.
    
    Args:
        session_id: Optional session ID to get diagnostics for
        
    Returns:
        Dict with session diagnostic information
    """
    try:
        session_manager = get_session_auth_manager()
        
        if session_id:
            # Get specific session
            session = session_manager.get_session(session_id)
            
            if not session:
                return {
                    "success": False,
                    "session_id": session_id,
                    "found": False,
                    "message": "Session not found or expired"
                }
            
            return {
                "success": True,
                "session_id": session_id,
                "found": True,
                "details": {
                    "created_at": session.created_at,
                    "last_used": session.last_used,
                    "age_seconds": time.time() - session.created_at,
                    "idle_seconds": time.time() - session.last_used,
                    "is_expired": session.is_expired(),
                    "user_id": session.jwt_result.user_id,
                    "username": session.jwt_result.username,
                    "buckets_count": len(session.jwt_result.buckets),
                    "permissions_count": len(session.jwt_result.permissions),
                    "roles": session.jwt_result.roles,
                }
            }
        else:
            # Get all sessions
            stats = session_manager.get_stats()
            return {
                "success": True,
                "all_sessions": True,
                "stats": stats,
                "message": f"Currently tracking {stats['total_sessions']} active sessions"
            }
        
    except Exception as e:
        logger.error("Error getting session diagnostics: %s", e)
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to get session diagnostics"
        }


def _generate_diagnostic_summary(diagnostics: Dict[str, Any]) -> str:
    """Generate a human-readable summary of diagnostics."""
    lines = []
    
    env = diagnostics.get("runtime_environment", "unknown")
    has_auth = diagnostics.get("has_auth_state")
    scheme = diagnostics.get("auth_scheme")
    
    lines.append(f"Environment: {env}")
    lines.append(f"Authentication: {'Active' if has_auth else 'None'}")
    
    if scheme:
        lines.append(f"Auth Scheme: {scheme}")
    
    jwt_details = diagnostics.get("jwt_details", {})
    if jwt_details:
        lines.append(f"User: {jwt_details.get('username') or jwt_details.get('user_id')}")
        lines.append(f"Buckets: {jwt_details.get('buckets_count')}")
        lines.append(f"Permissions: {jwt_details.get('permissions_count')}")
        lines.append(f"Roles: {', '.join(jwt_details.get('roles', []))}")
    
    session_stats = diagnostics.get("session_stats", {})
    if session_stats:
        lines.append(f"Active Sessions: {session_stats.get('total_sessions')}")
    
    return " | ".join(lines)


def _generate_recommendations(diagnostics: Dict[str, Any]) -> list[str]:
    """Generate recommendations based on diagnostic results."""
    recommendations = []
    
    if not diagnostics.get("has_auth_state"):
        recommendations.append("No authentication state found - ensure JWT is being sent in Authorization header")
    
    jwt_details = diagnostics.get("jwt_details", {})
    if jwt_details:
        if jwt_details.get("buckets_count", 0) == 0:
            recommendations.append("No buckets in JWT - user may not have access to any S3 buckets")
        
        if jwt_details.get("permissions_count", 0) == 0:
            recommendations.append("No permissions in JWT - user may have read-only or no access")
    
    bearer_config = diagnostics.get("bearer_service", {})
    if bearer_config:
        if not bearer_config.get("secret_configured"):
            recommendations.append("JWT secret not configured - authentication will fail")
        
        if bearer_config.get("secret_length", 0) < 32:
            recommendations.append("JWT secret is too short - should be at least 32 characters")
    
    if not recommendations:
        recommendations.append("All checks passed - JWT authentication is properly configured")
    
    return recommendations
