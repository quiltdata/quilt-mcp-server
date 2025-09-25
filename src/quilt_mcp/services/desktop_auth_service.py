"""Desktop Authentication Service for Quilt MCP Server.

This service handles authentication for desktop clients (Claude Desktop, Cursor, VS Code)
using quilt3 credentials and AWS credential extraction.
"""

from __future__ import annotations

import os
import json
import logging
from typing import Any, Dict, Optional
from pathlib import Path
from dataclasses import dataclass

import boto3

logger = logging.getLogger(__name__)


@dataclass
class Quilt3Credentials:
    """quilt3 credentials container."""
    access_token: str
    refresh_token: Optional[str] = None
    catalog_url: Optional[str] = None
    user_info: Optional[Dict[str, Any]] = None
    aws_credentials: Optional[Dict[str, Any]] = None


@dataclass
class AWSCredentials:
    """AWS credentials container."""
    access_key_id: str
    secret_access_key: str
    session_token: Optional[str] = None
    region: str = "us-east-1"
    expiration: Optional[str] = None


class DesktopAuthService:
    """Desktop authentication service for quilt3 credentials."""
    
    def __init__(self):
        self._quilt_auth_path = Path.home() / ".quilt" / "auth.json"
        self._quilt_config_path = Path.home() / ".quilt" / "config.json"
    
    def load_quilt3_credentials(self) -> Optional[Quilt3Credentials]:
        """Load quilt3 credentials from file.
        
        Returns:
            Quilt3Credentials if found, None otherwise
        """
        try:
            if not self._quilt_auth_path.exists():
                logger.debug("Quilt auth file not found: %s", self._quilt_auth_path)
                return None
            
            with open(self._quilt_auth_path, "r") as f:
                auth_data = json.load(f)
            
            logger.debug("Loaded quilt3 credentials from %s", self._quilt_auth_path)
            
            return Quilt3Credentials(
                access_token=auth_data.get("access_token"),
                refresh_token=auth_data.get("refresh_token"),
                catalog_url=auth_data.get("catalog_url"),
                user_info=auth_data.get("user_info"),
                aws_credentials=auth_data.get("aws_credentials")
            )
            
        except Exception as e:
            logger.error("Failed to load quilt3 credentials from %s: %s", self._quilt_auth_path, e)
            return None
    
    def parse_quilt3_credentials(self, credentials_data: Dict[str, Any]) -> Quilt3Credentials:
        """Parse quilt3 credentials from data.
        
        Args:
            credentials_data: Credentials data dictionary
            
        Returns:
            Quilt3Credentials parsed from data
        """
        return Quilt3Credentials(
            access_token=credentials_data.get("access_token"),
            refresh_token=credentials_data.get("refresh_token"),
            catalog_url=credentials_data.get("catalog_url"),
            user_info=credentials_data.get("user_info"),
            aws_credentials=credentials_data.get("aws_credentials")
        )
    
    def extract_aws_credentials(self, quilt3_creds: Quilt3Credentials) -> Optional[AWSCredentials]:
        """Extract AWS credentials from quilt3 session.
        
        Args:
            quilt3_creds: Quilt3 credentials
            
        Returns:
            AWSCredentials if found, None otherwise
        """
        try:
            # First, try to get AWS credentials directly from quilt3 session
            if quilt3_creds.aws_credentials:
                aws_creds = quilt3_creds.aws_credentials
                return AWSCredentials(
                    access_key_id=aws_creds.get("access_key_id"),
                    secret_access_key=aws_creds.get("secret_access_key"),
                    session_token=aws_creds.get("session_token"),
                    region=aws_creds.get("region", "us-east-1"),
                    expiration=aws_creds.get("expiration")
                )
            
            # If no direct AWS credentials, try to fetch from Quilt API
            if quilt3_creds.access_token:
                aws_creds = self._fetch_aws_credentials_from_quilt_api(quilt3_creds)
                if aws_creds:
                    return aws_creds
            
            # Fall back to default AWS credentials (from environment or IAM role)
            return self._get_default_aws_credentials()
            
        except Exception as e:
            logger.error("Failed to extract AWS credentials: %s", e)
            return None
    
    def _fetch_aws_credentials_from_quilt_api(self, quilt3_creds: Quilt3Credentials) -> Optional[AWSCredentials]:
        """Fetch AWS credentials from Quilt API using quilt3 token.
        
        Args:
            quilt3_creds: Quilt3 credentials
            
        Returns:
            AWSCredentials if successful, None otherwise
        """
        try:
            import requests
            
            # Get catalog URL
            catalog_url = quilt3_creds.catalog_url or self._get_default_catalog_url()
            if not catalog_url:
                logger.warning("No catalog URL found for AWS credential fetch")
                return None
            
            # Make request to Quilt API for AWS credentials
            headers = {
                "Authorization": f"Bearer {quilt3_creds.access_token}",
                "Content-Type": "application/json"
            }
            
            # Try different endpoints for AWS credentials
            endpoints = [
                f"{catalog_url}/api/v1/aws/credentials",
                f"{catalog_url}/api/v1/user/aws/credentials",
                f"{catalog_url}/api/v1/credentials/aws"
            ]
            
            for endpoint in endpoints:
                try:
                    response = requests.get(endpoint, headers=headers, timeout=10)
                    if response.status_code == 200:
                        creds_data = response.json()
                        
                        return AWSCredentials(
                            access_key_id=creds_data.get("access_key_id"),
                            secret_access_key=creds_data.get("secret_access_key"),
                            session_token=creds_data.get("session_token"),
                            region=creds_data.get("region", "us-east-1"),
                            expiration=creds_data.get("expiration")
                        )
                        
                except requests.RequestException as e:
                    logger.debug("Failed to fetch AWS credentials from %s: %s", endpoint, e)
                    continue
            
            logger.debug("Could not fetch AWS credentials from Quilt API")
            return None
            
        except ImportError:
            logger.debug("Requests library not available for Quilt API calls")
            return None
        except Exception as e:
            logger.error("Error fetching AWS credentials from Quilt API: %s", e)
            return None
    
    def _get_default_aws_credentials(self) -> Optional[AWSCredentials]:
        """Get default AWS credentials from environment or IAM role.
        
        Returns:
            AWSCredentials if found, None otherwise
        """
        try:
            # Try to get credentials from boto3 session
            session = boto3.Session()
            credentials = session.get_credentials()
            
            if credentials:
                logger.debug("Using default AWS credentials from boto3 session")
                return AWSCredentials(
                    access_key_id=credentials.access_key,
                    secret_access_key=credentials.secret_key,
                    session_token=credentials.token,
                    region=session.region_name or "us-east-1"
                )
            
            # Try environment variables
            access_key = os.environ.get("AWS_ACCESS_KEY_ID")
            secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
            
            if access_key and secret_key:
                logger.debug("Using AWS credentials from environment variables")
                return AWSCredentials(
                    access_key_id=access_key,
                    secret_access_key=secret_key,
                    session_token=os.environ.get("AWS_SESSION_TOKEN"),
                    region=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
                )
            
            logger.debug("No default AWS credentials found")
            return None
            
        except Exception as e:
            logger.error("Failed to get default AWS credentials: %s", e)
            return None
    
    def _get_default_catalog_url(self) -> Optional[str]:
        """Get default catalog URL from configuration.
        
        Returns:
            Catalog URL if found
        """
        try:
            # Try config file first
            if self._quilt_config_path.exists():
                with open(self._quilt_config_path, "r") as f:
                    config = json.load(f)
                    catalog_url = config.get("catalog_url")
                    if catalog_url:
                        return catalog_url
            
            # Try environment variable
            catalog_url = os.environ.get("QUILT_CATALOG_URL")
            if catalog_url:
                return catalog_url
            
            # Default to demo catalog
            return "https://demo.quiltdata.com"
            
        except Exception as e:
            logger.error("Failed to get default catalog URL: %s", e)
            return "https://demo.quiltdata.com"
    
    def validate_credentials(self, credentials: Quilt3Credentials) -> bool:
        """Validate quilt3 credentials.
        
        Args:
            credentials: Quilt3 credentials to validate
            
        Returns:
            True if credentials are valid
        """
        try:
            if not credentials.access_token:
                logger.debug("No access token in credentials")
                return False
            
            # Try to make a test request to validate token
            import requests
            
            catalog_url = credentials.catalog_url or self._get_default_catalog_url()
            headers = {
                "Authorization": f"Bearer {credentials.access_token}",
                "Content-Type": "application/json"
            }
            
            # Try to get user info
            response = requests.get(
                f"{catalog_url}/api/v1/user/info",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.debug("Quilt3 credentials validated successfully")
                return True
            else:
                logger.debug("Quilt3 credentials validation failed: %s", response.status_code)
                return False
                
        except ImportError:
            logger.debug("Requests library not available for credential validation")
            return True  # Assume valid if we can't validate
        except Exception as e:
            logger.error("Error validating quilt3 credentials: %s", e)
            return False
    
    def refresh_quilt3_credentials(self, credentials: Quilt3Credentials) -> Optional[Quilt3Credentials]:
        """Refresh quilt3 credentials using refresh token.
        
        Args:
            credentials: Current credentials with refresh token
            
        Returns:
            Refreshed credentials if successful, None otherwise
        """
        try:
            if not credentials.refresh_token:
                logger.debug("No refresh token available")
                return None
            
            import requests
            
            catalog_url = credentials.catalog_url or self._get_default_catalog_url()
            
            # Make refresh request
            data = {
                "refresh_token": credentials.refresh_token
            }
            
            response = requests.post(
                f"{catalog_url}/api/v1/auth/refresh",
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                refresh_data = response.json()
                
                # Update credentials
                credentials.access_token = refresh_data.get("access_token", credentials.access_token)
                credentials.refresh_token = refresh_data.get("refresh_token", credentials.refresh_token)
                
                logger.info("Quilt3 credentials refreshed successfully")
                return credentials
            else:
                logger.warning("Failed to refresh quilt3 credentials: %s", response.status_code)
                return None
                
        except ImportError:
            logger.debug("Requests library not available for credential refresh")
            return None
        except Exception as e:
            logger.error("Error refreshing quilt3 credentials: %s", e)
            return None
    
    def save_quilt3_credentials(self, credentials: Quilt3Credentials) -> bool:
        """Save quilt3 credentials to file.
        
        Args:
            credentials: Credentials to save
            
        Returns:
            True if saved successfully
        """
        try:
            # Ensure directory exists
            self._quilt_auth_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Prepare data for saving
            auth_data = {
                "access_token": credentials.access_token,
                "refresh_token": credentials.refresh_token,
                "catalog_url": credentials.catalog_url,
                "user_info": credentials.user_info,
                "aws_credentials": credentials.aws_credentials
            }
            
            # Save to file
            with open(self._quilt_auth_path, "w") as f:
                json.dump(auth_data, f, indent=2)
            
            logger.debug("Quilt3 credentials saved to %s", self._quilt_auth_path)
            return True
            
        except Exception as e:
            logger.error("Failed to save quilt3 credentials: %s", e)
            return False


# Global instance
_desktop_auth_service: Optional[DesktopAuthService] = None


def get_desktop_auth_service() -> DesktopAuthService:
    """Get global desktop authentication service instance.
    
    Returns:
        DesktopAuthService instance
    """
    global _desktop_auth_service
    if _desktop_auth_service is None:
        _desktop_auth_service = DesktopAuthService()
    return _desktop_auth_service
