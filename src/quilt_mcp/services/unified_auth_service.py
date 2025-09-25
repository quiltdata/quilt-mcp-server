"""Unified Authentication Service for Quilt MCP Server.

This service provides a single authentication interface that works across both
web and desktop clients, using AWS credentials as the single source of truth.

Based on the unified authentication strategy:
1. Web clients: JWT tokens with AWS role information
2. Desktop clients: quilt3 credentials with AWS credentials
3. Unified: Both result in AWS credentials for tool execution
"""

from __future__ import annotations

import os
import json
import logging
import time
from typing import Any, Dict, Optional, List
from enum import Enum
from dataclasses import dataclass
from pathlib import Path

import boto3

from quilt_mcp.runtime_context import (
    get_runtime_access_token,
    get_runtime_environment,
)

logger = logging.getLogger(__name__)


class ClientType(Enum):
    """Client types supported by the unified authentication service."""
    WEB = "web"
    DESKTOP = "desktop"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


class AuthResult:
    """Result of authentication attempt."""
    
    def __init__(
        self,
        success: bool,
        client_type: ClientType,
        aws_credentials: Optional[Dict[str, Any]] = None,
        quilt_api_token: Optional[str] = None,
        user_info: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        auth_method: Optional[str] = None
    ):
        self.success = success
        self.client_type = client_type
        self.aws_credentials = aws_credentials or {}
        self.quilt_api_token = quilt_api_token
        self.user_info = user_info or {}
        self.error = error
        self.auth_method = auth_method


@dataclass
class AWSCredentials:
    """AWS credentials container."""
    access_key_id: str
    secret_access_key: str
    session_token: Optional[str] = None
    region: str = "us-east-1"
    expiration: Optional[str] = None


@dataclass
class Quilt3Credentials:
    """quilt3 credentials container."""
    access_token: str
    refresh_token: Optional[str] = None
    catalog_url: Optional[str] = None
    aws_credentials: Optional[AWSCredentials] = None


class UnifiedAuthService:
    """Unified authentication service for all MCP client types.
    
    This service detects client type and extracts AWS credentials from
    either JWT tokens (web clients) or quilt3 credentials (desktop clients).
    """
    
    def __init__(self):
        self._client_type: Optional[ClientType] = None
        self._aws_credentials: Optional[AWSCredentials] = None
        self._quilt_api_token: Optional[str] = None
        self._user_info: Optional[Dict[str, Any]] = None
        self._auth_method: Optional[str] = None
        self._credential_cache: Dict[str, Any] = {}
        self._cache_expiry: float = 0
        
    def authenticate_request(self, request_context: Optional[Dict[str, Any]] = None) -> AuthResult:
        """Authenticate request from any client type.
        
        Args:
            request_context: Optional request context for authentication
            
        Returns:
            AuthResult with authentication status and credentials
        """
        try:
            # Detect client type
            client_type = self._detect_client_type(request_context)
            
            if client_type == ClientType.WEB:
                return self._authenticate_web_client(request_context)
            elif client_type == ClientType.DESKTOP:
                return self._authenticate_desktop_client(request_context)
            elif client_type == ClientType.HYBRID:
                return self._authenticate_hybrid_client(request_context)
            else:
                return AuthResult(
                    success=False,
                    client_type=ClientType.UNKNOWN,
                    error="Unable to detect client type"
                )
                
        except Exception as e:
            logger.error("Authentication failed: %s", e)
            return AuthResult(
                success=False,
                client_type=ClientType.UNKNOWN,
                error=f"Authentication error: {str(e)}"
            )
    
    def _detect_client_type(self, request_context: Optional[Dict[str, Any]] = None) -> ClientType:
        """Detect client type from request context.
        
        Args:
            request_context: Optional request context
            
        Returns:
            ClientType detected from context
        """
        # Check runtime context first
        runtime_env = get_runtime_environment()
        if runtime_env:
            if "web" in runtime_env:
                return ClientType.WEB
            elif "desktop" in runtime_env:
                return ClientType.DESKTOP
        
        # Check request context
        if request_context:
            headers = request_context.get("headers", {})
            if headers.get("authorization", "").startswith("Bearer "):
                return ClientType.WEB
            elif headers.get("x-quilt-desktop-credentials"):
                return ClientType.DESKTOP
        
        # Check environment variables
        if os.environ.get("QUILT_ACCESS_TOKEN"):
            return ClientType.WEB
        elif os.environ.get("QUILT_USER_INFO"):
            return ClientType.DESKTOP
        
        # Check for quilt3 credentials file
        quilt_auth_path = Path.home() / ".quilt" / "auth.json"
        if quilt_auth_path.exists():
            return ClientType.DESKTOP
        
        # Default to hybrid for ECS deployment
        if os.environ.get("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI"):
            return ClientType.HYBRID
        
        return ClientType.UNKNOWN
    
    def _authenticate_web_client(self, request_context: Optional[Dict[str, Any]] = None) -> AuthResult:
        """Authenticate web client using JWT tokens.
        
        Args:
            request_context: Optional request context
            
        Returns:
            AuthResult for web client authentication
        """
        try:
            # Get JWT token from runtime context or request
            access_token = get_runtime_access_token()
            if not access_token and request_context:
                auth_header = request_context.get("headers", {}).get("authorization", "")
                if auth_header.startswith("Bearer "):
                    access_token = auth_header[7:]
            
            if not access_token:
                return AuthResult(
                    success=False,
                    client_type=ClientType.WEB,
                    error="No JWT token found"
                )
            
            # Parse JWT token
            jwt_processor = JWTProcessor()
            jwt_payload = jwt_processor.decode_jwt_token(access_token)
            
            if not jwt_payload:
                return AuthResult(
                    success=False,
                    client_type=ClientType.WEB,
                    error="Invalid JWT token"
                )
            
            # Extract AWS credentials from JWT
            aws_credentials = jwt_processor.extract_aws_credentials(jwt_payload)
            if not aws_credentials:
                # Try to extract AWS role and assume it
                aws_role_arn = jwt_processor.extract_aws_role_arn(jwt_payload)
                if aws_role_arn:
                    aws_credentials = self._assume_aws_role(aws_role_arn)
            
            if not aws_credentials:
                return AuthResult(
                    success=False,
                    client_type=ClientType.WEB,
                    error="No AWS credentials found in JWT token"
                )
            
            # Extract user info
            user_info = {
                "user_id": jwt_payload.get("sub", ""),
                "username": jwt_payload.get("username", ""),
                "permissions": jwt_payload.get("permissions", []),
                "buckets": jwt_payload.get("buckets", []),
                "roles": jwt_payload.get("roles", []),
                "client_type": "web"
            }
            
            return AuthResult(
                success=True,
                client_type=ClientType.WEB,
                aws_credentials=aws_credentials.__dict__,
                quilt_api_token=access_token,
                user_info=user_info,
                auth_method="jwt"
            )
            
        except Exception as e:
            logger.error("Web client authentication failed: %s", e)
            return AuthResult(
                success=False,
                client_type=ClientType.WEB,
                error=f"Web authentication failed: {str(e)}"
            )
    
    def _authenticate_desktop_client(self, request_context: Optional[Dict[str, Any]] = None) -> AuthResult:
        """Authenticate desktop client using quilt3 credentials.
        
        Args:
            request_context: Optional request context
            
        Returns:
            AuthResult for desktop client authentication
        """
        try:
            desktop_auth = DesktopAuthService()
            
            # Try to get credentials from request context first
            if request_context:
                credentials_data = request_context.get("quilt3_credentials")
                if credentials_data:
                    quilt3_creds = desktop_auth.parse_quilt3_credentials(credentials_data)
                else:
                    quilt3_creds = desktop_auth.load_quilt3_credentials()
            else:
                quilt3_creds = desktop_auth.load_quilt3_credentials()
            
            if not quilt3_creds:
                return AuthResult(
                    success=False,
                    client_type=ClientType.DESKTOP,
                    error="No quilt3 credentials found"
                )
            
            # Extract AWS credentials
            aws_credentials = desktop_auth.extract_aws_credentials(quilt3_creds)
            if not aws_credentials:
                return AuthResult(
                    success=False,
                    client_type=ClientType.DESKTOP,
                    error="No AWS credentials found in quilt3 session"
                )
            
            # Extract user info
            user_info = {
                "user_id": quilt3_creds.access_token[:8] + "...",  # Truncated for privacy
                "username": "desktop_user",
                "permissions": ["desktop:full_access"],
                "buckets": ["*"],  # Desktop clients typically have broader access
                "roles": ["desktop_user"],
                "client_type": "desktop"
            }
            
            return AuthResult(
                success=True,
                client_type=ClientType.DESKTOP,
                aws_credentials=aws_credentials.__dict__,
                quilt_api_token=quilt3_creds.access_token,
                user_info=user_info,
                auth_method="quilt3"
            )
            
        except Exception as e:
            logger.error("Desktop client authentication failed: %s", e)
            return AuthResult(
                success=False,
                client_type=ClientType.DESKTOP,
                error=f"Desktop authentication failed: {str(e)}"
            )
    
    def _authenticate_hybrid_client(self, request_context: Optional[Dict[str, Any]] = None) -> AuthResult:
        """Authenticate hybrid client (ECS deployment with headers).
        
        Args:
            request_context: Optional request context
            
        Returns:
            AuthResult for hybrid client authentication
        """
        try:
            # Check for role assumption headers
            if request_context:
                headers = request_context.get("headers", {})
                role_arn = headers.get("x-quilt-user-role")
                user_id = headers.get("x-quilt-user-id")
                
                if role_arn:
                    aws_credentials = self._assume_aws_role(role_arn)
                    if aws_credentials:
                        user_info = {
                            "user_id": user_id or "hybrid_user",
                            "username": "hybrid_user",
                            "permissions": ["hybrid:full_access"],
                            "buckets": ["*"],
                            "roles": [role_arn],
                            "client_type": "hybrid"
                        }
                        
                        return AuthResult(
                            success=True,
                            client_type=ClientType.HYBRID,
                            aws_credentials=aws_credentials.__dict__,
                            user_info=user_info,
                            auth_method="role_assumption"
                        )
            
            # Fall back to ECS task role
            try:
                # Use ECS task role
                session = boto3.Session()
                credentials = session.get_credentials()
                
                if credentials:
                    aws_credentials = AWSCredentials(
                        access_key_id=credentials.access_key,
                        secret_access_key=credentials.secret_key,
                        session_token=credentials.token,
                        region=session.region_name or "us-east-1"
                    )
                    
                    user_info = {
                        "user_id": "ecs_task",
                        "username": "ecs_task",
                        "permissions": ["ecs:full_access"],
                        "buckets": ["*"],
                        "roles": ["ecs_task_role"],
                        "client_type": "hybrid"
                    }
                    
                    return AuthResult(
                        success=True,
                        client_type=ClientType.HYBRID,
                        aws_credentials=aws_credentials.__dict__,
                        user_info=user_info,
                        auth_method="ecs_task_role"
                    )
                    
            except Exception as e:
                logger.debug("ECS task role authentication failed: %s", e)
            
            return AuthResult(
                success=False,
                client_type=ClientType.HYBRID,
                error="No valid authentication method found"
            )
            
        except Exception as e:
            logger.error("Hybrid client authentication failed: %s", e)
            return AuthResult(
                success=False,
                client_type=ClientType.HYBRID,
                error=f"Hybrid authentication failed: {str(e)}"
            )
    
    def _assume_aws_role(self, role_arn: str) -> Optional[AWSCredentials]:
        """Assume AWS role and return credentials.
        
        Args:
            role_arn: AWS role ARN to assume
            
        Returns:
            AWSCredentials if successful, None otherwise
        """
        try:
            sts_client = boto3.client("sts")
            response = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName=f"mcp-server-{int(time.time())}",
                DurationSeconds=3600,
                SourceIdentity="mcp-server"
            )
            
            credentials = response["Credentials"]
            return AWSCredentials(
                access_key_id=credentials["AccessKeyId"],
                secret_access_key=credentials["SecretAccessKey"],
                session_token=credentials["SessionToken"],
                region="us-east-1",
                expiration=credentials["Expiration"].isoformat()
            )
            
        except Exception as e:
            logger.error("Failed to assume AWS role %s: %s", role_arn, e)
            return None
    
    def get_aws_session(self, service: str) -> Optional[boto3.Session]:
        """Get boto3 session for AWS service.
        
        Args:
            service: AWS service name
            
        Returns:
            boto3.Session configured with credentials
        """
        try:
            if not self._aws_credentials:
                return None
            
            credentials = self._aws_credentials
            session = boto3.Session(
                aws_access_key_id=credentials.get("access_key_id"),
                aws_secret_access_key=credentials.get("secret_access_key"),
                aws_session_token=credentials.get("session_token"),
                region_name=credentials.get("region", "us-east-1")
            )
            
            return session
            
        except Exception as e:
            logger.error("Failed to create AWS session for %s: %s", service, e)
            return None
    
    def get_quilt_api_client(self) -> Optional[Any]:
        """Get Quilt API client with proper authentication.
        
        Returns:
            QuiltAPIClient configured with token
        """
        try:
            if not self._quilt_api_token:
                return None
            
            # Import here to avoid circular imports
            from .quilt_service import QuiltService
            return QuiltService(access_token=self._quilt_api_token)
            
        except Exception as e:
            logger.error("Failed to create Quilt API client: %s", e)
            return None
    
    def authorize_tool(self, tool_name: str, tool_args: Dict[str, Any], auth_result: AuthResult) -> bool:
        """Authorize tool access based on user permissions.
        
        Args:
            tool_name: Name of the tool
            tool_args: Tool arguments
            auth_result: Authentication result
            
        Returns:
            True if authorized, False otherwise
        """
        try:
            # Load permission mapping
            permission_mapper = PermissionMapper()
            
            # Get required permissions for tool
            required_permissions = permission_mapper.get_tool_permissions(tool_name)
            if not required_permissions:
                logger.warning("No permission mapping found for tool %s", tool_name)
                return True  # Allow if no mapping found
            
            # Check user permissions
            user_permissions = auth_result.user_info.get("permissions", [])
            user_buckets = auth_result.user_info.get("buckets", [])
            
            # Check permission requirements
            for permission in required_permissions.get("aws_permissions", []):
                if not self._check_aws_permission(permission, user_permissions):
                    return False
            
            # Check bucket access if required
            bucket_name = tool_args.get("bucket_name")
            if bucket_name and not self._check_bucket_access(bucket_name, user_buckets):
                return False
            
            return True
            
        except Exception as e:
            logger.error("Tool authorization failed for %s: %s", tool_name, e)
            return False
    
    def _check_aws_permission(self, permission: str, user_permissions: List[str]) -> bool:
        """Check if user has required AWS permission.
        
        Args:
            permission: Required permission
            user_permissions: User's permissions
            auth_result: Authentication result
            
        Returns:
            True if user has permission
        """
        # For now, use simple permission matching
        # In the future, this could be more sophisticated
        return permission in user_permissions or "*" in user_permissions
    
    def _check_bucket_access(self, bucket_name: str, user_buckets: List[str]) -> bool:
        """Check if user has access to bucket.
        
        Args:
            bucket_name: Bucket name to check
            user_buckets: User's accessible buckets
            
        Returns:
            True if user has access
        """
        return bucket_name in user_buckets or "*" in user_buckets
    
    def refresh_credentials(self) -> bool:
        """Refresh credentials if needed.
        
        Returns:
            True if refresh successful or not needed
        """
        try:
            # Check if credentials are expired
            if not self._aws_credentials:
                return False
            
            expiration_str = self._aws_credentials.get("expiration")
            if not expiration_str:
                return True  # No expiration, assume valid
            
            # Parse expiration and check if refresh needed
            from datetime import datetime
            expiration = datetime.fromisoformat(expiration_str.replace("Z", "+00:00"))
            now = datetime.now(expiration.tzinfo)
            
            # Refresh if expires within 5 minutes
            if (expiration - now).total_seconds() < 300:
                logger.info("Refreshing expired credentials")
                # For now, return False to trigger re-authentication
                # In the future, implement actual refresh logic
                return False
            
            return True
            
        except Exception as e:
            logger.error("Credential refresh failed: %s", e)
            return False


# Global instance
_unified_auth_service: Optional[UnifiedAuthService] = None


def get_unified_auth_service() -> UnifiedAuthService:
    """Get global unified authentication service instance.
    
    Returns:
        UnifiedAuthService instance
    """
    global _unified_auth_service
    if _unified_auth_service is None:
        _unified_auth_service = UnifiedAuthService()
    return _unified_auth_service


# Import supporting classes (will be implemented next)
class JWTProcessor:
    """JWT token processor for extracting AWS credentials."""
    
    def decode_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Decode JWT token without verification."""
        try:
            import jwt
            # Decode without verification for now
            # In production, should verify signature
            payload = jwt.decode(token, options={"verify_signature": False})
            return payload
        except Exception as e:
            logger.error("JWT decode failed: %s", e)
            return None
    
    def extract_aws_role_arn(self, payload: Dict[str, Any]) -> Optional[str]:
        """Extract AWS role ARN from JWT payload."""
        return payload.get("aws_role_arn")
    
    def extract_aws_credentials(self, payload: Dict[str, Any]) -> Optional[AWSCredentials]:
        """Extract AWS credentials from JWT payload."""
        aws_creds = payload.get("aws_credentials")
        if aws_creds:
            return AWSCredentials(
                access_key_id=aws_creds.get("access_key_id"),
                secret_access_key=aws_creds.get("secret_access_key"),
                session_token=aws_creds.get("session_token"),
                region=aws_creds.get("region", "us-east-1"),
                expiration=aws_creds.get("expiration")
            )
        return None


class DesktopAuthService:
    """Desktop authentication service for quilt3 credentials."""
    
    def load_quilt3_credentials(self) -> Optional[Quilt3Credentials]:
        """Load quilt3 credentials from file."""
        try:
            auth_path = Path.home() / ".quilt" / "auth.json"
            if not auth_path.exists():
                return None
            
            with open(auth_path, "r") as f:
                auth_data = json.load(f)
            
            return Quilt3Credentials(
                access_token=auth_data.get("access_token"),
                refresh_token=auth_data.get("refresh_token"),
                catalog_url=auth_data.get("catalog_url")
            )
        except Exception as e:
            logger.error("Failed to load quilt3 credentials: %s", e)
            return None
    
    def parse_quilt3_credentials(self, credentials_data: Dict[str, Any]) -> Quilt3Credentials:
        """Parse quilt3 credentials from data."""
        return Quilt3Credentials(
            access_token=credentials_data.get("access_token"),
            refresh_token=credentials_data.get("refresh_token"),
            catalog_url=credentials_data.get("catalog_url")
        )
    
    def extract_aws_credentials(self, quilt3_creds: Quilt3Credentials) -> Optional[AWSCredentials]:
        """Extract AWS credentials from quilt3 session."""
        # For now, use default AWS credentials
        # In the future, this would query Quilt API for AWS credentials
        try:
            session = boto3.Session()
            credentials = session.get_credentials()
            if credentials:
                return AWSCredentials(
                    access_key_id=credentials.access_key,
                    secret_access_key=credentials.secret_key,
                    session_token=credentials.token,
                    region=session.region_name or "us-east-1"
                )
        except Exception as e:
            logger.error("Failed to extract AWS credentials: %s", e)
        return None


class PermissionMapper:
    """Permission mapper for tool authorization."""
    
    def __init__(self):
        self._permission_mapping = self._load_permission_mapping()
    
    def _load_permission_mapping(self) -> Dict[str, Any]:
        """Load permission mapping from configuration."""
        # For now, return a basic mapping
        # In the future, this would load from config file
        return {
            "bucket_objects_list": {
                "aws_permissions": ["s3:ListBucket", "s3:GetBucketLocation"],
                "quilt_permissions": ["bucket:read"]
            },
            "package_create": {
                "aws_permissions": ["s3:PutObject", "s3:PutObjectAcl", "s3:ListBucket"],
                "quilt_permissions": ["package:write"]
            },
            "athena_query_execute": {
                "aws_permissions": ["athena:StartQueryExecution", "athena:GetQueryExecution"],
                "quilt_permissions": ["athena:execute"]
            }
        }
    
    def get_tool_permissions(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get permissions required for tool."""
        return self._permission_mapping.get(tool_name)
