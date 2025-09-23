"""
OAuth 2.1 Authorization Service for MCP Server.

This service implements OAuth 2.1 authorization according to the MCP specification:
https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization

It provides a hybrid approach using IAM role authentication as the authorization server.
"""

import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin, urlparse

import jwt
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class OAuthService:
    """OAuth 2.1 authorization service for MCP server."""
    
    def __init__(self, server_base_url: str = "https://demo.quiltdata.com"):
        self.server_base_url = server_base_url.rstrip("/")
        self.mcp_endpoint = f"{self.server_base_url}/mcp"
        self.auth_endpoint = f"{self.server_base_url}/oauth"
        self.jwt_secret = "mcp-oauth-secret"  # In production, use proper secret management
        self.token_lifetime = 3600  # 1 hour
        
    def get_protected_resource_metadata(self) -> Dict[str, Any]:
        """
        Return OAuth 2.0 Protected Resource Metadata (RFC9728).
        
        This is required by the MCP specification for authorization server discovery.
        """
        return {
            "resource": self.mcp_endpoint,
            "authorization_servers": [f"{self.auth_endpoint}/authorize"],
            "scopes_supported": [
                "mcp:read",
                "mcp:write", 
                "mcp:admin",
                "quilt:packages:read",
                "quilt:packages:write",
                "quilt:buckets:read",
                "quilt:buckets:write"
            ],
            "bearer_methods_supported": ["header"],
            "resource_documentation": f"{self.server_base_url}/docs",
            "resource_policy_uri": f"{self.server_base_url}/policy",
            "resource_tos_uri": f"{self.server_base_url}/terms"
        }
    
    def get_authorization_server_metadata(self) -> Dict[str, Any]:
        """
        Return OAuth 2.0 Authorization Server Metadata (RFC8414).
        
        This provides the authorization server configuration.
        """
        return {
            "issuer": self.auth_endpoint,
            "authorization_endpoint": f"{self.auth_endpoint}/authorize",
            "token_endpoint": f"{self.auth_endpoint}/token",
            "registration_endpoint": f"{self.auth_endpoint}/register",
            "jwks_uri": f"{self.auth_endpoint}/jwks",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],  # PKCE support
            "scopes_supported": [
                "mcp:read",
                "mcp:write", 
                "mcp:admin",
                "quilt:packages:read",
                "quilt:packages:write",
                "quilt:buckets:read",
                "quilt:buckets:write"
            ],
            "token_endpoint_auth_methods_supported": ["none"],  # Public client
            "claims_supported": [
                "sub",
                "aud",
                "exp",
                "iat",
                "iss",
                "scope"
            ]
        }
    
    def generate_access_token(self, client_id: str, scopes: List[str] = None) -> Dict[str, Any]:
        """
        Generate an OAuth 2.1 access token for the given client and scopes.
        
        This uses our existing IAM role authentication to issue tokens.
        """
        if scopes is None:
            scopes = ["mcp:read", "mcp:write"]
            
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=self.token_lifetime)
        
        # Create JWT payload
        payload = {
            "iss": self.auth_endpoint,  # Issuer
            "sub": client_id,  # Subject (client ID)
            "aud": self.mcp_endpoint,  # Audience (our MCP server)
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "scope": " ".join(scopes),
            "jti": str(uuid.uuid4())  # JWT ID for uniqueness
        }
        
        # Generate JWT token
        token = jwt.encode(payload, self.jwt_secret, algorithm="HS256")
        
        return {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": self.token_lifetime,
            "scope": " ".join(scopes)
        }
    
    def validate_access_token(self, token: str) -> Dict[str, Any]:
        """
        Validate an OAuth 2.1 access token according to the MCP specification.
        
        Returns the token payload if valid, raises HTTPException if invalid.
        """
        try:
            # Decode and validate JWT
            payload = jwt.decode(
                token, 
                self.jwt_secret, 
                algorithms=["HS256"],
                audience=self.mcp_endpoint,  # Validate audience
                issuer=self.auth_endpoint   # Validate issuer
            )
            
            # Check if token is expired
            if payload.get("exp", 0) < time.time():
                raise HTTPException(status_code=401, detail="Token expired")
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    
    def require_authorization(self, request: Request) -> Dict[str, Any]:
        """
        Middleware to require OAuth 2.1 authorization for MCP requests.
        
        This implements the MCP authorization requirements.
        """
        # Check for Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            # Return 401 with WWW-Authenticate header as per RFC9728
            raise HTTPException(
                status_code=401,
                detail="Authorization required",
                headers={
                    "WWW-Authenticate": f'Bearer realm="{self.mcp_endpoint}", authorization_uri="{self.auth_endpoint}/.well-known/oauth-protected-resource"'
                }
            )
        
        # Parse Bearer token
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header format")
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        
        # Validate token
        return self.validate_access_token(token)
    
    def get_authorization_scopes(self, token_payload: Dict[str, Any]) -> List[str]:
        """Extract scopes from validated token payload."""
        scope_str = token_payload.get("scope", "")
        return scope_str.split() if scope_str else []
    
    def has_scope(self, token_payload: Dict[str, Any], required_scope: str) -> bool:
        """Check if token has the required scope."""
        scopes = self.get_authorization_scopes(token_payload)
        return required_scope in scopes or "mcp:admin" in scopes


# Global OAuth service instance
_oauth_service: Optional[OAuthService] = None


def get_oauth_service() -> OAuthService:
    """Get the global OAuth service instance."""
    global _oauth_service
    if _oauth_service is None:
        server_url = "https://demo.quiltdata.com"  # Default to demo catalog
        _oauth_service = OAuthService(server_url)
    return _oauth_service


def initialize_oauth_service(server_base_url: str) -> None:
    """Initialize the OAuth service with the given server URL."""
    global _oauth_service
    _oauth_service = OAuthService(server_base_url)
