"""Enhanced JWT Token Processor for Quilt MCP Server.

This module provides enhanced JWT token processing capabilities for extracting
AWS role information and credentials from JWT tokens issued by Quilt frontend.
"""

from __future__ import annotations

import json
import logging
import base64
from typing import Any, Dict, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class JWTPayload:
    """JWT payload container with extracted information."""
    user_id: str
    username: Optional[str]
    permissions: List[str]
    buckets: List[str]
    roles: List[str]
    aws_role_arn: Optional[str]
    aws_credentials: Optional[Dict[str, Any]]
    client_type: str
    expiration: Optional[str]
    scope: Optional[str]


class JWTProcessor:
    """Enhanced JWT token processor for AWS credential extraction."""
    
    def __init__(self):
        self._compression_enabled = True
    
    def decode_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Decode JWT token and return payload.
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded JWT payload or None if failed
        """
        try:
            # Split JWT into parts
            parts = token.split('.')
            if len(parts) != 3:
                logger.warning("Invalid JWT format: expected 3 parts, got %d", len(parts))
                return None
            
            # Decode payload (base64url)
            payload_part = parts[1]
            
            # Add padding if needed
            missing_padding = len(payload_part) % 4
            if missing_padding:
                payload_part += '=' * (4 - missing_padding)
            
            # Decode base64url
            decoded_bytes = base64.urlsafe_b64decode(payload_part)
            payload = json.loads(decoded_bytes.decode('utf-8'))
            
            # Check for compression
            if self._compression_enabled and self._is_compressed_jwt(payload):
                logger.info("Detected compressed JWT token, decompressing...")
                payload = self._decompress_jwt(payload)
                logger.info("JWT token decompressed successfully: %d permissions, %d buckets", 
                           len(payload.get('permissions', [])), 
                           len(payload.get('buckets', [])))
            
            return payload
            
        except Exception as e:
            logger.error("Failed to decode JWT token: %s", e)
            return None
    
    def extract_jwt_payload(self, token: str) -> Optional[JWTPayload]:
        """Extract structured JWT payload.
        
        Args:
            token: JWT token string
            
        Returns:
            JWTPayload with extracted information
        """
        payload = self.decode_jwt_token(token)
        if not payload:
            return None
        
        try:
            return JWTPayload(
                user_id=payload.get("sub", ""),
                username=payload.get("username", ""),
                permissions=self._extract_permissions(payload),
                buckets=self._extract_buckets(payload),
                roles=self._extract_roles(payload),
                aws_role_arn=self.extract_aws_role_arn(payload),
                aws_credentials=self._extract_aws_credentials_dict(payload),
                client_type=payload.get("client_type", "web"),
                expiration=payload.get("exp"),
                scope=payload.get("scope", "")
            )
        except Exception as e:
            logger.error("Failed to extract JWT payload: %s", e)
            return None
    
    def extract_aws_role_arn(self, payload: Dict[str, Any]) -> Optional[str]:
        """Extract AWS role ARN from JWT payload.
        
        Args:
            payload: Decoded JWT payload
            
        Returns:
            AWS role ARN if found
        """
        # Try multiple possible fields
        role_arn = (
            payload.get("aws_role_arn") or
            payload.get("awsRoleArn") or
            payload.get("role_arn") or
            payload.get("roleArn")
        )
        
        if role_arn:
            logger.debug("Extracted AWS role ARN: %s", role_arn)
            return role_arn
        
        # Try to construct from roles array
        roles = payload.get("roles", [])
        if roles:
            # Look for AWS role pattern
            for role in roles:
                if role.startswith("arn:aws:iam::"):
                    logger.debug("Found AWS role in roles array: %s", role)
                    return role
        
        logger.debug("No AWS role ARN found in JWT payload")
        return None
    
    def extract_aws_credentials(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract AWS credentials from JWT payload.
        
        Args:
            payload: Decoded JWT payload
            
        Returns:
            AWS credentials dictionary if found
        """
        aws_creds = self._extract_aws_credentials_dict(payload)
        if aws_creds:
            logger.debug("Extracted AWS credentials from JWT")
            return aws_creds
        
        logger.debug("No AWS credentials found in JWT payload")
        return None
    
    def _extract_aws_credentials_dict(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract AWS credentials dictionary from payload.
        
        Args:
            payload: Decoded JWT payload
            
        Returns:
            AWS credentials dictionary
        """
        # Try multiple possible fields
        aws_creds = (
            payload.get("aws_credentials") or
            payload.get("awsCredentials") or
            payload.get("credentials") or
            payload.get("temp_credentials") or
            payload.get("tempCredentials")
        )
        
        if aws_creds and isinstance(aws_creds, dict):
            # Validate required fields
            required_fields = ["access_key_id", "secret_access_key"]
            if all(field in aws_creds for field in required_fields):
                return {
                    "access_key_id": aws_creds.get("access_key_id"),
                    "secret_access_key": aws_creds.get("secret_access_key"),
                    "session_token": aws_creds.get("session_token"),
                    "region": aws_creds.get("region", "us-east-1"),
                    "expiration": aws_creds.get("expiration")
                }
        
        return None
    
    def _extract_permissions(self, payload: Dict[str, Any]) -> List[str]:
        """Extract permissions from JWT payload.
        
        Args:
            payload: Decoded JWT payload
            
        Returns:
            List of permissions
        """
        permissions = payload.get("permissions", [])
        if isinstance(permissions, list):
            return permissions
        
        # Try alternative field names
        alt_permissions = (
            payload.get("scopes") or
            payload.get("authorities") or
            payload.get("claims", {}).get("permissions", [])
        )
        
        if isinstance(alt_permissions, list):
            return alt_permissions
        
        return []
    
    def _extract_buckets(self, payload: Dict[str, Any]) -> List[str]:
        """Extract buckets from JWT payload.
        
        Args:
            payload: Decoded JWT payload
            
        Returns:
            List of bucket names
        """
        buckets = payload.get("buckets", [])
        if isinstance(buckets, list):
            return buckets
        
        # Try alternative field names
        alt_buckets = (
            payload.get("s3_buckets") or
            payload.get("accessible_buckets") or
            payload.get("claims", {}).get("buckets", [])
        )
        
        if isinstance(alt_buckets, list):
            return alt_buckets
        
        return []
    
    def _extract_roles(self, payload: Dict[str, Any]) -> List[str]:
        """Extract roles from JWT payload.
        
        Args:
            payload: Decoded JWT payload
            
        Returns:
            List of role names
        """
        roles = payload.get("roles", [])
        if isinstance(roles, list):
            return roles
        
        # Try alternative field names
        alt_roles = (
            payload.get("authorities") or
            payload.get("groups") or
            payload.get("claims", {}).get("roles", [])
        )
        
        if isinstance(alt_roles, list):
            return alt_roles
        
        return []
    
    def _is_compressed_jwt(self, payload: Dict[str, Any]) -> bool:
        """Check if JWT payload is compressed.
        
        Args:
            payload: Decoded JWT payload
            
        Returns:
            True if payload appears to be compressed
        """
        # Check for compression indicators
        compression_indicators = [
            "compressed" in payload,
            "b" in payload,  # Compressed buckets
            "p" in payload,  # Compressed permissions
            "r" in payload,  # Compressed roles
        ]
        
        return any(compression_indicators)
    
    def _decompress_jwt(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Decompress JWT payload if compressed.
        
        Args:
            payload: Compressed JWT payload
            
        Returns:
            Decompressed JWT payload
        """
        try:
            # Import compression utilities
            from quilt_mcp.jwt_utils.jwt_decompression import safe_decompress_jwt
            
            decompressed = safe_decompress_jwt(payload)
            if decompressed:
                logger.debug("Successfully decompressed JWT payload")
                return decompressed
            
        except ImportError:
            logger.debug("JWT decompression utilities not available")
        except Exception as e:
            logger.warning("JWT decompression failed: %s", e)
        
        # Return original payload if decompression fails
        return payload
    
    def validate_token_expiration(self, payload: Dict[str, Any]) -> bool:
        """Validate JWT token expiration.
        
        Args:
            payload: Decoded JWT payload
            
        Returns:
            True if token is not expired
        """
        try:
            exp = payload.get("exp")
            if not exp:
                logger.warning("JWT token missing expiration claim")
                return True  # Allow if no expiration
            
            import time
            current_time = time.time()
            
            if exp < current_time:
                logger.warning("JWT token has expired (exp: %s, now: %s)", exp, current_time)
                return False
            
            # Check if token expires soon (within 5 minutes)
            if exp - current_time < 300:
                logger.info("JWT token expires soon (within 5 minutes)")
            
            return True
            
        except Exception as e:
            logger.error("Failed to validate JWT expiration: %s", e)
            return False
    
    def map_permissions_to_aws(self, jwt_permissions: List[str]) -> List[str]:
        """Map JWT permissions to AWS permissions.
        
        Args:
            jwt_permissions: List of JWT permissions
            
        Returns:
            List of AWS permissions
        """
        # Permission mapping dictionary
        permission_mapping = {
            "bucket:read": ["s3:ListBucket", "s3:GetBucketLocation"],
            "bucket:write": ["s3:PutObject", "s3:PutObjectAcl", "s3:DeleteObject"],
            "bucket:admin": ["s3:*"],
            "package:read": ["s3:GetObject", "s3:ListBucket"],
            "package:write": ["s3:PutObject", "s3:PutObjectAcl", "s3:ListBucket"],
            "package:admin": ["s3:*"],
            "athena:execute": ["athena:StartQueryExecution", "athena:GetQueryExecution", "athena:GetQueryResults"],
            "athena:admin": ["athena:*"],
            "glue:read": ["glue:GetTable", "glue:GetDatabase", "glue:GetPartitions"],
            "glue:write": ["glue:CreateTable", "glue:UpdateTable", "glue:DeleteTable"],
            "glue:admin": ["glue:*"],
            "iam:read": ["iam:GetRole", "iam:ListRoles", "iam:GetUser"],
            "iam:admin": ["iam:*"],
            "admin": ["*"]  # Full access
        }
        
        aws_permissions = set()
        
        for jwt_perm in jwt_permissions:
            if jwt_perm in permission_mapping:
                aws_permissions.update(permission_mapping[jwt_perm])
            elif jwt_perm.startswith("s3:"):
                # Already an AWS permission
                aws_permissions.add(jwt_perm)
            elif jwt_perm == "*":
                # Full access
                aws_permissions.add("*")
        
        return list(aws_permissions)
    
    def extract_user_info(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extract user information from JWT payload.
        
        Args:
            payload: Decoded JWT payload
            
        Returns:
            Dictionary with user information
        """
        return {
            "user_id": payload.get("sub", ""),
            "username": payload.get("username", ""),
            "email": payload.get("email", ""),
            "name": payload.get("name", ""),
            "permissions": self._extract_permissions(payload),
            "buckets": self._extract_buckets(payload),
            "roles": self._extract_roles(payload),
            "scope": payload.get("scope", ""),
            "client_type": payload.get("client_type", "web"),
            "expires_at": payload.get("exp"),
            "issued_at": payload.get("iat")
        }


# Global instance
_jwt_processor: Optional[JWTProcessor] = None


def get_jwt_processor() -> JWTProcessor:
    """Get global JWT processor instance.
    
    Returns:
        JWTProcessor instance
    """
    global _jwt_processor
    if _jwt_processor is None:
        _jwt_processor = JWTProcessor()
    return _jwt_processor
