"""Authentication Service - Centralized authentication management for MCP server.

This service provides a unified authentication interface that works across different
deployment environments, following Quilt's authentication patterns:

- Local development: Uses quilt3 login (OAuth2 flow with refresh tokens)
- ECS deployment: Uses IAM role-based authentication (ECS task role)
- Hybrid: Graceful fallback between methods

Based on Quilt's authentication architecture:
1. Quilt uses OAuth2 with refresh tokens stored in ~/.quilt/auth.json
2. Quilt fetches temporary AWS credentials from the registry API
3. Quilt creates boto3 sessions with these temporary credentials
4. For ECS, we can use the task role directly without OAuth2
"""

from __future__ import annotations

import os
import json
import logging
import time
from typing import Any, Dict, Optional
from enum import Enum
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)


class AuthMethod(Enum):
    """Authentication methods supported by the service."""
    QUILT3 = "quilt3"
    IAM_ROLE = "iam_role"
    ENVIRONMENT = "environment"
    NONE = "none"


class AuthStatus(Enum):
    """Authentication status levels."""
    AUTHENTICATED = "authenticated"
    PARTIAL = "partial"
    UNAUTHENTICATED = "unauthenticated"


class AuthenticationService:
    """Centralized authentication service for MCP server.
    
    This service provides a unified interface for authentication across different
    deployment environments, with graceful fallback between methods.
    """
    
    def __init__(self) -> None:
        """Initialize the authentication service."""
        self._auth_method: Optional[AuthMethod] = None
        self._auth_status: AuthStatus = AuthStatus.UNAUTHENTICATED
        self._catalog_url: Optional[str] = None
        self._catalog_name: Optional[str] = None
        self._aws_credentials: Optional[Dict[str, str]] = None
        self._boto3_session: Optional[boto3.Session] = None
        
    def initialize(self) -> AuthStatus:
        """Initialize authentication and determine the best available method.
        
        Returns:
            AuthStatus indicating the authentication level achieved
        """
        logger.info("Initializing authentication service...")
        
        # Try different authentication methods in order of preference
        auth_methods = [
            self._try_quilt3_auth,
            self._try_quilt_registry_auth,
            self._try_iam_role_auth,
            self._try_environment_auth,
        ]
        
        for method in auth_methods:
            try:
                status = method()
                if status == AuthStatus.AUTHENTICATED:
                    logger.info("Successfully authenticated using %s", self._auth_method.value)
                    return status
                elif status == AuthStatus.PARTIAL and self._auth_status == AuthStatus.UNAUTHENTICATED:
                    self._auth_status = status
            except Exception as e:
                logger.debug("Authentication method %s failed: %s", method.__name__, e)
                continue
        
        logger.warning("No authentication method succeeded, using unauthenticated mode")
        self._auth_status = AuthStatus.UNAUTHENTICATED
        return self._auth_status
    
    def _try_quilt3_auth(self) -> AuthStatus:
        """Try to authenticate using quilt3 login.
        
        Returns:
            AuthStatus indicating success level
        """
        try:
            import quilt3
            
            # Check if quilt3 is available and user is logged in
            if hasattr(quilt3, "logged_in") and quilt3.logged_in():
                logged_in_url = quilt3.logged_in()
                if logged_in_url:
                    self._auth_method = AuthMethod.QUILT3
                    self._auth_status = AuthStatus.AUTHENTICATED
                    self._catalog_url = logged_in_url
                    self._catalog_name = self._extract_catalog_name(logged_in_url)
                    
                    # Get boto3 session from quilt3
                    if hasattr(quilt3, "get_boto3_session"):
                        self._boto3_session = quilt3.get_boto3_session()
                    
                    logger.info("Quilt3 authentication successful: %s", logged_in_url)
                    return AuthStatus.AUTHENTICATED
        except ImportError:
            logger.debug("Quilt3 not available")
        except Exception as e:
            logger.debug("Quilt3 authentication failed: %s", e)
        
        return AuthStatus.UNAUTHENTICATED
    
    def _try_quilt_registry_auth(self) -> AuthStatus:
        """Try to authenticate using Quilt registry credentials (like quilt3 does).
        
        This method mimics quilt3's authentication flow:
        1. Check for stored auth tokens in ~/.quilt/auth.json
        2. Check for stored credentials in ~/.quilt/credentials.json
        3. If credentials exist, use them to create a boto3 session
        
        Returns:
            AuthStatus indicating success level
        """
        try:
            # Get Quilt data directory (following quilt3's pattern)
            from platformdirs import user_data_dir
            APP_NAME = "Quilt"
            APP_AUTHOR = "QuiltData"
            BASE_DIR = user_data_dir(APP_NAME, APP_AUTHOR)
            BASE_PATH = Path(BASE_DIR)
            
            AUTH_PATH = BASE_PATH / 'auth.json'
            CREDENTIALS_PATH = BASE_PATH / 'credentials.json'
            
            # Check if we have stored credentials
            credentials = None
            if CREDENTIALS_PATH.exists():
                try:
                    with open(CREDENTIALS_PATH, 'r', encoding='utf-8') as f:
                        credentials = json.load(f)
                except Exception as e:
                    logger.debug("Failed to load credentials: %s", e)
            
            # Check if credentials are still valid (not expired)
            if credentials and credentials.get('expiry_time'):
                expiry_time = credentials['expiry_time']
                if time.time() < expiry_time:
                    # Create boto3 session with stored credentials
                    session = boto3.Session(
                        aws_access_key_id=credentials['access_key'],
                        aws_secret_access_key=credentials['secret_key'],
                        aws_session_token=credentials['token'],
                    )
                    
                    # Test the credentials
                    sts_client = session.client("sts")
                    identity = sts_client.get_caller_identity()
                    
                    self._auth_method = AuthMethod.QUILT3
                    self._auth_status = AuthStatus.AUTHENTICATED
                    self._boto3_session = session
                    self._aws_credentials = {
                        "account_id": identity.get("Account"),
                        "user_id": identity.get("UserId"),
                        "arn": identity.get("Arn"),
                    }
                    
                    # Try to get catalog URL from auth file
                    if AUTH_PATH.exists():
                        try:
                            with open(AUTH_PATH, 'r', encoding='utf-8') as f:
                                auth_data = json.load(f)
                                # Get the first catalog URL from auth data
                                if auth_data:
                                    self._catalog_url = list(auth_data.keys())[0]
                                    self._catalog_name = self._extract_catalog_name(self._catalog_url)
                        except Exception as e:
                            logger.debug("Failed to load auth data: %s", e)
                    
                    logger.info("Quilt registry authentication successful: %s", identity.get('Arn'))
                    return AuthStatus.AUTHENTICATED
                else:
                    logger.debug("Quilt credentials expired")
            else:
                logger.debug("No valid Quilt credentials found")
                
        except Exception as e:
            logger.debug("Quilt registry authentication failed: %s", e)
        
        return AuthStatus.UNAUTHENTICATED
    
    def _try_iam_role_auth(self) -> AuthStatus:
        """Try to authenticate using IAM role (ECS task role).
        
        Returns:
            AuthStatus indicating success level
        """
        try:
            # Create a boto3 session using default credentials (IAM role)
            session = boto3.Session()
            
            # Test the credentials by calling STS GetCallerIdentity
            sts_client = session.client("sts")
            identity = sts_client.get_caller_identity()
            
            self._auth_method = AuthMethod.IAM_ROLE
            self._auth_status = AuthStatus.AUTHENTICATED
            self._boto3_session = session
            self._aws_credentials = {
                "account_id": identity.get("Account"),
                "user_id": identity.get("UserId"),
                "arn": identity.get("Arn"),
            }
            
            # Try to determine catalog information from environment or configuration
            self._catalog_url = self._get_catalog_url_from_env()
            self._catalog_name = self._extract_catalog_name(self._catalog_url) if self._catalog_url else "ecs-deployment"
            
            logger.info("IAM role authentication successful: %s", identity.get('Arn'))
            return AuthStatus.AUTHENTICATED
            
        except (NoCredentialsError, ClientError) as e:
            logger.debug("IAM role authentication failed: %s", e)
        except Exception as e:
            logger.debug("IAM role authentication error: %s", e)
        
        return AuthStatus.UNAUTHENTICATED
    
    def _try_environment_auth(self) -> AuthStatus:
        """Try to authenticate using environment variables.
        
        Returns:
            AuthStatus indicating success level
        """
        try:
            # Check for AWS credentials in environment
            aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
            aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
            aws_session_token = os.environ.get("AWS_SESSION_TOKEN")
            
            if aws_access_key and aws_secret_key:
                # Create boto3 session with explicit credentials
                session = boto3.Session(
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                    aws_session_token=aws_session_token,
                    region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
                )
                
                # Test the credentials
                sts_client = session.client("sts")
                identity = sts_client.get_caller_identity()
                
                self._auth_method = AuthMethod.ENVIRONMENT
                self._auth_status = AuthStatus.AUTHENTICATED
                self._boto3_session = session
                self._aws_credentials = {
                    "account_id": identity.get("Account"),
                    "user_id": identity.get("UserId"),
                    "arn": identity.get("Arn"),
                }
                
                # Try to determine catalog information
                self._catalog_url = self._get_catalog_url_from_env()
                self._catalog_name = self._extract_catalog_name(self._catalog_url) if self._catalog_url else "env-deployment"
                
                logger.info("Environment authentication successful: %s", identity.get('Arn'))
                return AuthStatus.AUTHENTICATED
                
        except Exception as e:
            logger.debug("Environment authentication failed: %s", e)
        
        return AuthStatus.UNAUTHENTICATED
    
    def _get_catalog_url_from_env(self) -> Optional[str]:
        """Get catalog URL from environment variables.
        
        Returns:
            Catalog URL if found, None otherwise
        """
        return (
            os.environ.get("QUILT_CATALOG_URL") or
            os.environ.get("QUILT_CATALOG") or
            os.environ.get("QUILT_URL")
        )
    
    def _extract_catalog_name(self, catalog_url: Optional[str]) -> Optional[str]:
        """Extract catalog name from URL.
        
        Args:
            catalog_url: The catalog URL
            
        Returns:
            Catalog name if extractable, None otherwise
        """
        if not catalog_url:
            return None
        
        try:
            # Extract hostname from URL
            from urllib.parse import urlparse
            parsed = urlparse(catalog_url)
            hostname = parsed.hostname or parsed.netloc
            
            # Remove common prefixes/suffixes
            name = hostname.replace("quiltdata.com", "").replace("demo.", "").replace("app.", "")
            return name if name else "default"
        except Exception:
            return "unknown"
    
    def get_auth_status(self) -> Dict[str, Any]:
        """Get comprehensive authentication status.
        
        Returns:
            Dictionary with authentication status information
        """
        return {
            "status": self._auth_status.value,
            "method": self._auth_method.value if self._auth_method else "none",
            "catalog_url": self._catalog_url,
            "catalog_name": self._catalog_name,
            "aws_credentials": self._aws_credentials,
            "is_authenticated": self._auth_status == AuthStatus.AUTHENTICATED,
        }
    
    def get_boto3_session(self) -> Optional[boto3.Session]:
        """Get boto3 session for AWS operations.
        
        Returns:
            boto3 Session if available, None otherwise
        """
        return self._boto3_session
    
    def get_quilt_compatible_session(self) -> boto3.Session:
        """Get a boto3 session that's compatible with Quilt's expectations.
        
        This method creates a session that follows Quilt's authentication patterns,
        ensuring compatibility with quilt3 operations.
        
        Returns:
            boto3.Session: Quilt-compatible session
        """
        if self._boto3_session is not None:
            return self._boto3_session
        
        # Try to create a session using Quilt's credential provider
        try:
            # If we have quilt3 available, use its session creation
            import quilt3
            if hasattr(quilt3, "get_boto3_session"):
                return quilt3.get_boto3_session()
        except ImportError:
            pass
        
        # Fall back to default session
        return boto3.Session()
    
    def get_s3_client(self):
        """Get S3 client using current authentication.
        
        Returns:
            boto3 S3 client
        """
        if self._boto3_session:
            return self._boto3_session.client("s3")
        return boto3.client("s3")
    
    def get_sts_client(self):
        """Get STS client using current authentication.
        
        Returns:
            boto3 STS client
        """
        if self._boto3_session:
            return self._boto3_session.client("sts")
        return boto3.client("sts")
    
    def get_athena_client(self):
        """Get Athena client using current authentication.
        
        Returns:
            boto3 Athena client
        """
        if self._boto3_session:
            return self._boto3_session.client("athena")
        return boto3.client("athena")
    
    def is_authenticated(self) -> bool:
        """Check if currently authenticated.
        
        Returns:
            True if authenticated, False otherwise
        """
        return self._auth_status == AuthStatus.AUTHENTICATED
    
    def get_catalog_info(self) -> Dict[str, Any]:
        """Get catalog information.
        
        Returns:
            Dictionary with catalog information
        """
        return {
            "catalog_url": self._catalog_url,
            "catalog_name": self._catalog_name,
            "auth_method": self._auth_method.value if self._auth_method else "none",
        }


# Global authentication service instance
_auth_service: Optional[AuthenticationService] = None


def get_auth_service() -> AuthenticationService:
    """Get the global authentication service instance.
    
    Returns:
        AuthenticationService instance
    """
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthenticationService()
        _auth_service.initialize()
    return _auth_service


def initialize_auth() -> AuthStatus:
    """Initialize the global authentication service.
    
    Returns:
        AuthStatus indicating authentication level
    """
    return get_auth_service().initialize()


def get_auth_status() -> Dict[str, Any]:
    """Get authentication status.
    
    Returns:
        Dictionary with authentication status
    """
    return get_auth_service().get_auth_status()
