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
    BEARER_TOKEN = "bearer_token"
    IAM_ROLE = "iam_role"
    ASSUMED_ROLE = "assumed_role"
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
        self._assumed_role_arn: Optional[str] = None
        self._assumed_session: Optional[boto3.Session] = None
        self._auto_role_assumption_enabled: bool = True
        
    def initialize(self) -> AuthStatus:
        """Initialize authentication and determine the best available method.
        
        Returns:
            AuthStatus indicating the authentication level achieved
        """
        logger.info("Initializing authentication service...")
        
        # Try different authentication methods in order of preference
        auth_methods = [
            self._try_bearer_token_auth,
            self._try_quilt3_auth,
            self._try_quilt_registry_auth,
            self._try_assume_role_auth,
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
                    # Check if we have a specific catalog URL from environment variables
                    env_catalog_url = self._get_catalog_url_from_env()
                    
                    # If environment variable is set, use it instead of quilt3's logged-in URL
                    if env_catalog_url:
                        logger.info("Using catalog URL from environment: %s (overriding quilt3 login: %s)", 
                                   env_catalog_url, logged_in_url)
                        self._catalog_url = env_catalog_url
                    else:
                        self._catalog_url = logged_in_url
                    
                    self._auth_method = AuthMethod.QUILT3
                    self._auth_status = AuthStatus.AUTHENTICATED
                    self._catalog_name = self._extract_catalog_name(self._catalog_url)
                    
                    # Get boto3 session from quilt3
                    if hasattr(quilt3, "get_boto3_session"):
                        self._boto3_session = quilt3.get_boto3_session()
                    
                    logger.info("Quilt3 authentication successful: %s", self._catalog_url)
                    return AuthStatus.AUTHENTICATED
        except ImportError:
            logger.debug("Quilt3 not available")
        except Exception as e:
            logger.debug("Quilt3 authentication failed: %s", e)
        
        return AuthStatus.UNAUTHENTICATED
    
    def _try_bearer_token_auth(self) -> AuthStatus:
        """Try to authenticate using a bearer token from environment variables.
        
        This method looks for a bearer token set by the MCP server middleware
        and validates it with Quilt's authentication system.
        
        Returns:
            AuthStatus indicating success level
        """
        try:
            # Get the access token from environment variables (set from Authorization header)
            access_token = os.environ.get("QUILT_ACCESS_TOKEN")
            if not access_token:
                logger.debug("No QUILT_ACCESS_TOKEN environment variable set from Authorization header")
                return AuthStatus.UNAUTHENTICATED
            
            # Import and use the bearer auth service
            from quilt_mcp.services.bearer_auth_service import get_bearer_auth_service
            bearer_auth_service = get_bearer_auth_service()
            
            # Validate the bearer token
            status, user_info = bearer_auth_service.validate_bearer_token(access_token)
            
            if status.value == "authenticated":
                logger.info("Bearer token authentication successful for user: %s", 
                           user_info.get('username', 'unknown') if user_info else 'unknown')
                
                # Store the authenticated session
                self._auth_method = AuthMethod.BEARER_TOKEN
                self._auth_status = AuthStatus.AUTHENTICATED
                
                # Create a requests session for authenticated API calls
                self._authenticated_session = bearer_auth_service.get_authenticated_session(access_token)
                
                # Store user info
                if user_info:
                    self._user_info = user_info
                
                return AuthStatus.AUTHENTICATED
            else:
                logger.debug("Bearer token authentication failed: %s", status.value)
                return AuthStatus.UNAUTHENTICATED
                
        except Exception as e:
            logger.debug("Bearer token authentication error: %s", e)
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
    
    def _try_assume_role_auth(self) -> AuthStatus:
        """Try to authenticate by assuming the Quilt user role from headers.
        
        This method looks for Quilt role information in environment variables
        (which would be set from HTTP headers by the MCP server middleware)
        and assumes that role for MCP operations.
        
        Returns:
            AuthStatus indicating success level
        """
        try:
            # Get the role ARN from environment variables (set from Quilt headers)
            role_arn = os.environ.get("QUILT_USER_ROLE_ARN")
            if not role_arn:
                logger.debug("No QUILT_USER_ROLE_ARN environment variable set from Quilt headers")
                return AuthStatus.UNAUTHENTICATED
            
            # Create a session with the current IAM role (ECS task role)
            base_session = boto3.Session()
            sts_client = base_session.client("sts")
            
            # Assume the Quilt user's role
            response = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName=f"mcp-server-{int(time.time())}",
                DurationSeconds=3600,  # 1 hour
                SourceIdentity="mcp-server"  # For audit trail
            )
            
            # Create a new session with the assumed role credentials
            assumed_credentials = response["Credentials"]
            assumed_session = boto3.Session(
                aws_access_key_id=assumed_credentials["AccessKeyId"],
                aws_secret_access_key=assumed_credentials["SecretAccessKey"],
                aws_session_token=assumed_credentials["SessionToken"]
            )
            
            # Test the assumed role by calling GetCallerIdentity
            assumed_sts_client = assumed_session.client("sts")
            identity = assumed_sts_client.get_caller_identity()
            
            self._auth_method = AuthMethod.ASSUMED_ROLE
            self._auth_status = AuthStatus.AUTHENTICATED
            self._boto3_session = assumed_session
            self._assumed_role_arn = role_arn
            self._assumed_session = assumed_session
            self._aws_credentials = {
                "account_id": identity.get("Account"),
                "user_id": identity.get("UserId"),
                "arn": identity.get("Arn"),
                "assumed_role_arn": role_arn,
                "expiration": assumed_credentials["Expiration"].isoformat(),
            }
            
            # Try to determine catalog information from environment or configuration
            self._catalog_url = self._get_catalog_url_from_env()
            self._catalog_name = self._extract_catalog_name(self._catalog_url) if self._catalog_url else "assumed-role-deployment"
            
            logger.info("Quilt role assumption successful: %s -> %s", 
                       base_session.client("sts").get_caller_identity().get("Arn"),
                       identity.get('Arn'))
            return AuthStatus.AUTHENTICATED
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "AccessDenied":
                logger.debug("Access denied when assuming Quilt user role: %s", e)
            else:
                logger.debug("STS assume role failed: %s", e)
        except Exception as e:
            logger.debug("Role assumption authentication error: %s", e)
        
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
            Catalog URL if found, defaults to demo.quiltdata.com otherwise
        """
        return (
            os.environ.get("QUILT_CATALOG_URL") or
            os.environ.get("QUILT_CATALOG") or
            os.environ.get("QUILT_URL") or
            "https://demo.quiltdata.com"  # Default fallback for deployed containers
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
    
    def update_catalog_url(self, catalog_url: str) -> None:
        """Update the catalog URL and reinitialize authentication.
        
        Args:
            catalog_url: New catalog URL to use
        """
        self._catalog_url = catalog_url
        self._catalog_name = self._extract_catalog_name(catalog_url)
        
        # Reinitialize authentication with new catalog URL
        self.initialize()
    
    def _get_quilt_user_role_arn(self) -> Optional[str]:
        """Get the Quilt user's role ARN from their current session.
        
        This method attempts to determine what role the Quilt user is currently using
        by examining their Quilt credentials and session information.
        
        Returns:
            Role ARN if found, None otherwise
        """
        try:
            # Method 1: Try to get role from Quilt credentials file
            from platformdirs import user_data_dir
            APP_NAME = "Quilt"
            APP_AUTHOR = "QuiltData"
            BASE_DIR = user_data_dir(APP_NAME, APP_AUTHOR)
            BASE_PATH = Path(BASE_DIR)
            
            CREDENTIALS_PATH = BASE_PATH / 'credentials.json'
            
            if CREDENTIALS_PATH.exists():
                try:
                    with open(CREDENTIALS_PATH, 'r', encoding='utf-8') as f:
                        credentials = json.load(f)
                    
                    # Check if credentials are still valid
                    if credentials and credentials.get('expiry_time'):
                        expiry_time = credentials['expiry_time']
                        if time.time() < expiry_time:
                            # Get the role ARN from the credentials
                            # Quilt stores the role ARN in the credentials
                            role_arn = credentials.get('role_arn') or credentials.get('assumed_role_arn')
                            if role_arn:
                                logger.debug("Found Quilt user role ARN: %s", role_arn)
                                return role_arn
                except Exception as e:
                    logger.debug("Failed to read Quilt credentials: %s", e)
            
            # Method 2: Try to get role from current Quilt session
            try:
                import quilt3
                if hasattr(quilt3, 'session') and hasattr(quilt3.session, 'get_session'):
                    session = quilt3.session.get_session()
                    # Check if session has credentials with role information
                    if hasattr(session, 'credentials'):
                        credentials = session.credentials
                        # Try different possible attribute names for role ARN
                        role_arn = (getattr(credentials, 'assumed_role_arn', None) or 
                                  getattr(credentials, 'role_arn', None))
                        if role_arn:
                            logger.debug("Found Quilt session role ARN: %s", role_arn)
                            return role_arn
            except Exception as e:
                logger.debug("Failed to get role from Quilt session: %s", e)
            
            # Method 3: Try to get role from environment variable (fallback)
            role_arn = os.environ.get("QUILT_USER_ROLE_ARN") or os.environ.get("MCP_ASSUME_ROLE_ARN")
            if role_arn:
                logger.debug("Found role ARN from environment: %s", role_arn)
                return role_arn
                
        except Exception as e:
            logger.debug("Error determining Quilt user role ARN: %s", e)
        
        return None
    
    def assume_quilt_user_role(self, role_arn: str) -> bool:
        """Manually assume a specific Quilt user role.
        
        This method allows the MCP server to assume a specific role that the
        Quilt user is using, providing per-user AWS isolation.
        
        Args:
            role_arn: The ARN of the role to assume
            
        Returns:
            True if role assumption was successful, False otherwise
        """
        try:
            # Create a session with the current IAM role (ECS task role)
            base_session = boto3.Session()
            sts_client = base_session.client("sts")
            
            # Assume the specified role
            response = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName=f"mcp-server-{int(time.time())}",
                DurationSeconds=3600  # 1 hour
            )
            
            # Create a new session with the assumed role credentials
            assumed_credentials = response["Credentials"]
            assumed_session = boto3.Session(
                aws_access_key_id=assumed_credentials["AccessKeyId"],
                aws_secret_access_key=assumed_credentials["SecretAccessKey"],
                aws_session_token=assumed_credentials["SessionToken"]
            )
            
            # Test the assumed role
            assumed_sts_client = assumed_session.client("sts")
            identity = assumed_sts_client.get_caller_identity()
            
            # Update the authentication service state
            self._auth_method = AuthMethod.ASSUMED_ROLE
            self._auth_status = AuthStatus.AUTHENTICATED
            self._boto3_session = assumed_session
            self._assumed_role_arn = role_arn
            self._assumed_session = assumed_session
            self._aws_credentials = {
                "account_id": identity.get("Account"),
                "user_id": identity.get("UserId"),
                "arn": identity.get("Arn"),
                "assumed_role_arn": role_arn,
                "expiration": assumed_credentials["Expiration"].isoformat(),
            }
            
            logger.info("Successfully assumed Quilt user role: %s -> %s", 
                       base_session.client("sts").get_caller_identity().get("Arn"),
                       identity.get('Arn'))
            return True
            
        except Exception as e:
            logger.error("Failed to assume Quilt user role %s: %s", role_arn, e)
            return False
    
    def auto_attempt_role_assumption(self) -> bool:
        """Automatically attempt to assume Quilt user role if headers are present.
        
        This method checks for Quilt role information in environment variables
        (set by the middleware from HTTP headers) and automatically assumes
        the role if available and different from the current role.
        
        Returns:
            True if role assumption was successful or already using correct role,
            False if no role assumption was attempted or failed
        """
        if not self._auto_role_assumption_enabled:
            return False
        
        try:
            # Check for role information from Quilt headers
            header_role_arn = os.environ.get("QUILT_USER_ROLE_ARN")
            if not header_role_arn:
                logger.debug("No QUILT_USER_ROLE_ARN environment variable set")
                return False
            
            # If we're already using the same role, no need to assume again
            if (self._auth_method == AuthMethod.ASSUMED_ROLE and 
                self._assumed_role_arn == header_role_arn):
                logger.debug("Already using the requested Quilt user role: %s", header_role_arn)
                return True
            
            # Attempt to assume the role
            logger.info("Automatically attempting to assume Quilt user role: %s", header_role_arn)
            success = self.assume_quilt_user_role(header_role_arn)
            
            if success:
                logger.info("Automatic role assumption successful: %s", header_role_arn)
                return True
            else:
                logger.warning("Automatic role assumption failed: %s", header_role_arn)
                return False
                
        except Exception as e:
            logger.error("Error during automatic role assumption: %s", e)
            return False
    
    def get_boto3_session(self) -> Optional[boto3.Session]:
        """Get the current boto3 session, attempting automatic role assumption if needed.
        
        This method ensures that if Quilt role headers are present, the service
        automatically attempts to assume that role before returning the session.
        
        Returns:
            Current boto3 session, or None if no authentication is available
        """
        # Attempt automatic role assumption if headers are present
        self.auto_attempt_role_assumption()
        
        return self._boto3_session
    
    def disable_auto_role_assumption(self) -> None:
        """Disable automatic role assumption."""
        self._auto_role_assumption_enabled = False
        logger.info("Automatic role assumption disabled")
    
    def enable_auto_role_assumption(self) -> None:
        """Enable automatic role assumption."""
        self._auto_role_assumption_enabled = True
        logger.info("Automatic role assumption enabled")
    
    def get_authenticated_session(self):
        """Get an authenticated requests session for API calls.
        
        Returns:
            requests.Session: The authenticated session or None
        """
        if self._auth_method == AuthMethod.BEARER_TOKEN and self._authenticated_session:
            return self._authenticated_session
        elif self._boto3_session:
            # For IAM-based auth, we can create a session with AWS credentials
            # This would be used for direct AWS API calls
            return None
        return None


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
