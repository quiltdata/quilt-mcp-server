"""Bearer Token Authentication Service for Quilt MCP Server.

This service implements bearer token authentication using Quilt's OAuth2 system,
providing a simpler alternative to IAM role assumption.

Based on Quilt's authentication architecture:
1. Frontend sends Authorization: Bearer <access_token> header
2. MCP server validates token with Quilt's API
3. MCP server extracts JWT claims for authorization (scopes, permissions, roles)
4. MCP server maps Quilt roles to AWS permissions for S3 access
5. Quilt's backend handles S3 access with proper permissions
"""

import os
import logging
import time
import requests
import base64
import json
import jwt
from typing import Any, Dict, Optional, Tuple, List
from enum import Enum
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class BearerAuthStatus(Enum):
    """Bearer token authentication status levels."""
    AUTHENTICATED = "authenticated"
    EXPIRED = "expired"
    INVALID = "invalid"
    UNAUTHENTICATED = "unauthenticated"


class AuthorizationLevel(Enum):
    """Authorization levels for bucket access."""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    NONE = "none"


class QuiltRole(Enum):
    """Quilt roles that can be mapped to AWS permissions."""
    READ_WRITE_QUILT_V2_SALES_PROD = "ReadWriteQuiltV2-sales-prod"
    READ_ONLY_QUILT = "ReadOnlyQuilt"
    ADMIN_QUILT = "AdminQuilt"
    # Add more roles as needed


class BearerAuthService:
    """Bearer token authentication service for Quilt MCP server.
    
    This service validates bearer tokens and provides authenticated sessions
    for making requests to Quilt's APIs.
    """
    
    def __init__(self, catalog_url: str = "https://demo.quiltdata.com"):
        """Initialize the bearer auth service.
        
        Args:
            catalog_url: Quilt catalog URL for token validation
        """
        self.catalog_url = catalog_url.rstrip('/')
        self.token_cache: Dict[str, Dict[str, Any]] = {}
        self.session_cache: Dict[str, requests.Session] = {}
        
        # JWT configuration
        self.jwt_secret = os.getenv('MCP_ENHANCED_JWT_SECRET', 'development-enhanced-jwt-secret')
        self.jwt_kid = os.getenv('MCP_ENHANCED_JWT_KID', 'frontend-enhanced')
        
        # Comprehensive tool-based permission mapping
        self.tool_permissions = {
            # S3 Bucket Operations
            "bucket_objects_list": ["s3:ListBucket", "s3:GetBucketLocation"],
            "bucket_object_info": ["s3:GetObject", "s3:GetObjectVersion"],
            "bucket_object_text": ["s3:GetObject"],
            "bucket_object_fetch": ["s3:GetObject", "s3:GetObjectVersion"],
            "bucket_objects_put": ["s3:PutObject", "s3:PutObjectAcl"],
            "bucket_object_link": ["s3:GetObject"],  # For signed URLs
            
            # Package Operations
            "package_create": ["s3:PutObject", "s3:PutObjectAcl", "s3:ListBucket", "s3:GetObject"],
            "package_update": ["s3:GetObject", "s3:PutObject", "s3:ListBucket", "s3:DeleteObject"],
            "package_delete": ["s3:DeleteObject", "s3:ListBucket"],
            "package_browse": ["s3:ListBucket", "s3:GetObject"],
            "package_contents_search": ["s3:ListBucket"],
            "package_diff": ["s3:ListBucket", "s3:GetObject"],
            
            # Unified Package Operations
            "create_package_enhanced": ["s3:PutObject", "s3:PutObjectAcl", "s3:ListBucket", "s3:GetObject"],
            "create_package_from_s3": ["s3:ListBucket", "s3:GetObject", "s3:PutObject", "s3:PutObjectAcl"],
            
            # S3-to-Package Operations
            "package_create_from_s3": ["s3:ListBucket", "s3:GetObject", "s3:PutObject", "s3:PutObjectAcl"],
            
            # Athena/Glue Operations
            "athena_query_execute": ["athena:StartQueryExecution", "athena:GetQueryExecution", "athena:GetQueryResults", "athena:StopQueryExecution"],
            "athena_databases_list": ["glue:GetDatabases"],
            "athena_tables_list": ["glue:GetTables", "glue:GetDatabase"],
            "athena_table_schema": ["glue:GetTable", "glue:GetDatabase"],
            "athena_workgroups_list": ["athena:ListWorkGroups"],
            "athena_query_history": ["athena:ListQueryExecutions", "athena:BatchGetQueryExecution"],
            
            # Tabulator Operations (read-only)
            "tabulator_tables_list": ["glue:GetDatabases", "glue:GetTables"],
            "tabulator_table_create": ["glue:CreateTable", "glue:GetTable", "s3:ListBucket"],
            
            # Search Operations (read-only)
            "unified_search": ["s3:ListBucket", "glue:GetTables", "glue:GetDatabases"],
            "packages_search": ["s3:ListBucket"],
            
            # Permission Discovery (read-only)
            "aws_permissions_discover": ["iam:ListAttachedUserPolicies", "iam:ListUserPolicies", "iam:GetPolicy", "iam:GetPolicyVersion"],
            "bucket_access_check": ["s3:ListBucket", "s3:GetBucketLocation"],
            "bucket_recommendations_get": ["s3:ListAllMyBuckets"]
        }
        
        # Role to permission mapping with tool-based approach
        self.role_permissions: Dict[str, Dict[str, Any]] = {
            "ReadWriteQuiltV2-sales-prod": {
                "level": AuthorizationLevel.WRITE,
                "buckets": ["quilt-sandbox-bucket", "quilt-sales-prod"],
                "tools": [
                    # Full S3 access
                    "bucket_objects_list", "bucket_object_info", "bucket_object_text", 
                    "bucket_object_fetch", "bucket_objects_put", "bucket_object_link",
                    # Full package operations
                    "package_create", "package_update", "package_delete", "package_browse",
                    "package_contents_search", "package_diff",
                    "create_package_enhanced", "create_package_from_s3", "package_create_from_s3",
                    # Read-only operations
                    "athena_query_execute", "athena_databases_list", "athena_tables_list",
                    "athena_table_schema", "athena_workgroups_list", "athena_query_history",
                    "tabulator_tables_list", "unified_search", "packages_search",
                    "aws_permissions_discover", "bucket_access_check", "bucket_recommendations_get"
                ],
                "description": "Full read/write access to sales production buckets with all tool capabilities"
            },
            "ReadOnlyQuilt": {
                "level": AuthorizationLevel.READ,
                "buckets": ["quilt-sandbox-bucket"],
                "tools": [
                    # Read-only S3 access
                    "bucket_objects_list", "bucket_object_info", "bucket_object_text", 
                    "bucket_object_fetch", "bucket_object_link",
                    # Read-only package operations
                    "package_browse", "package_contents_search", "package_diff",
                    # Read-only operations
                    "athena_query_execute", "athena_databases_list", "athena_tables_list",
                    "athena_table_schema", "athena_workgroups_list", "athena_query_history",
                    "tabulator_tables_list", "unified_search", "packages_search",
                    "aws_permissions_discover", "bucket_access_check", "bucket_recommendations_get"
                ],
                "description": "Read-only access to sandbox bucket with query capabilities"
            },
            "AdminQuilt": {
                "level": AuthorizationLevel.ADMIN,
                "buckets": ["*"],  # All buckets
                "tools": ["*"],  # All tools
                "description": "Administrative access to all buckets and operations"
            }
        }
    
    def decode_jwt_token(self, auth_header: str) -> Optional[Dict[str, Any]]:
        """Decode and validate the JWT token from Authorization header.
        
        Args:
            auth_header: "Bearer <token>" format
            
        Returns:
            Decoded token payload or None if invalid
        """
        try:
            # Extract token from "Bearer <token>" format
            if not auth_header.startswith('Bearer '):
                logger.warning("Authorization header does not start with 'Bearer '")
                return None
            
            token = auth_header[7:]  # Remove "Bearer " prefix
            
            # Decode and verify the token
            payload = jwt.decode(
                token, 
                self.jwt_secret, 
                algorithms=['HS256'],
                options={"verify_exp": True, "verify_aud": False}  # Disable audience verification for flexibility
            )
            
            logger.debug("JWT token decoded successfully for user: %s", payload.get('id', 'unknown'))
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid JWT token: %s", e)
            return None
        except Exception as e:
            logger.error("Error decoding JWT token: %s", e)
            return None

    def _parse_jwt_claims(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Parse JWT claims from bearer token without verification.
        
        Args:
            access_token: The JWT token to parse
            
        Returns:
            Dictionary containing JWT claims or None if parsing fails
        """
        try:
            # Split JWT into header, payload, signature
            parts = access_token.split('.')
            if len(parts) != 3:
                logger.warning("Invalid JWT format: expected 3 parts, got %d", len(parts))
                return None
            
            # Decode payload (base64url)
            payload = parts[1]
            
            # Add padding if needed for base64 decoding
            missing_padding = len(payload) % 4
            if missing_padding:
                payload += '=' * (4 - missing_padding)
            
            # Decode and parse JSON
            decoded_bytes = base64.urlsafe_b64decode(payload)
            claims = json.loads(decoded_bytes.decode('utf-8'))
            
            logger.debug("Parsed JWT claims: %s", list(claims.keys()))
            return claims
            
        except Exception as e:
            logger.warning("Failed to parse JWT claims: %s", e)
            return None

    def extract_auth_claims(self, token_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extract authorization claims from JWT token payload.
        
        Args:
            token_payload: Decoded JWT token payload
        
        Returns:
            Dictionary with extracted authorization claims
        """
        return {
            'permissions': token_payload.get('permissions', []),
            'roles': token_payload.get('roles', []),
            'groups': token_payload.get('groups', []),
            'scope': token_payload.get('scope', ''),
            'buckets': token_payload.get('buckets', []),
            'user_id': token_payload.get('id', ''),
            'expires_at': token_payload.get('exp', 0)
        }

    def validate_permission(self, required_permission: str, user_permissions: List[str]) -> bool:
        """Check if user has required permission.
        
        Args:
            required_permission: Permission needed (e.g., 's3:ListBucket')
            user_permissions: List of user's permissions
        
        Returns:
            True if user has permission, False otherwise
        """
        return required_permission in user_permissions

    def validate_bucket_access(self, bucket_name: str, user_buckets: List[str]) -> bool:
        """Check if user has access to specific bucket.
        
        Args:
            bucket_name: Name of bucket to check
            user_buckets: List of buckets user can access
        
        Returns:
            True if user has access, False otherwise
        """
        return bucket_name in user_buckets

    def validate_role_access(self, required_roles: List[str], user_roles: List[str]) -> bool:
        """Check if user has any of the required roles.
        
        Args:
            required_roles: List of roles that can perform action
            user_roles: List of user's roles
        
        Returns:
            True if user has any required role, False otherwise
        """
        return any(role in user_roles for role in required_roles)

    def authorize_mcp_tool(self, tool_name: str, tool_args: Dict[str, Any], auth_claims: Dict[str, Any]) -> bool:
        """Authorize access to specific MCP tool based on user's permissions.
        
        Args:
            tool_name: Name of MCP tool being called
            tool_args: Arguments passed to the tool
            auth_claims: User's authorization claims
        
        Returns:
            True if authorized, False otherwise
        """
        permissions = auth_claims.get('permissions', [])
        buckets = auth_claims.get('buckets', [])
        
        # Define tool-specific authorization rules
        tool_auth_rules = {
            'list_available_resources': {
                'required_permissions': ['s3:ListAllMyBuckets'],
                'description': 'List available S3 resources'
            },
            'bucket_objects_list': {
                'required_permissions': ['s3:ListBucket'],
                'required_bucket_access': True,
                'description': 'List objects in specific bucket'
            },
            'bucket_objects_put': {
                'required_permissions': ['s3:PutObject'],
                'required_bucket_access': True,
                'description': 'Upload objects to bucket'
            },
            'bucket_object_info': {
                'required_permissions': ['s3:GetObject'],
                'required_bucket_access': True,
                'description': 'Get object metadata'
            },
            'bucket_object_text': {
                'required_permissions': ['s3:GetObject'],
                'required_bucket_access': True,
                'description': 'Read object content as text'
            },
            'bucket_object_fetch': {
                'required_permissions': ['s3:GetObject'],
                'required_bucket_access': True,
                'description': 'Fetch object data'
            },
            'bucket_object_link': {
                'required_permissions': ['s3:GetObject'],
                'required_bucket_access': True,
                'description': 'Generate presigned download URL'
            },
            'package_create': {
                'required_permissions': ['s3:PutObject', 's3:ListBucket'],
                'required_bucket_access': True,
                'description': 'Create Quilt packages'
            },
            'package_update': {
                'required_permissions': ['s3:GetObject', 's3:PutObject', 's3:ListBucket'],
                'required_bucket_access': True,
                'description': 'Update Quilt packages'
            },
            'package_delete': {
                'required_permissions': ['s3:DeleteObject', 's3:ListBucket'],
                'required_bucket_access': True,
                'description': 'Delete Quilt packages'
            },
            'package_browse': {
                'required_permissions': ['s3:ListBucket', 's3:GetObject'],
                'required_bucket_access': True,
                'description': 'Browse package contents'
            },
            'athena_query_execute': {
                'required_permissions': ['athena:StartQueryExecution', 'athena:GetQueryResults'],
                'description': 'Execute Athena queries'
            },
            'athena_databases_list': {
                'required_permissions': ['glue:GetDatabases'],
                'description': 'List Athena databases'
            },
            'athena_tables_list': {
                'required_permissions': ['glue:GetTables', 'glue:GetDatabase'],
                'description': 'List Athena tables'
            },
            'unified_search': {
                'required_permissions': ['s3:ListBucket'],
                'description': 'Search across packages and objects'
            },
            'packages_search': {
                'required_permissions': ['s3:ListBucket'],
                'description': 'Search for packages'
            },
            'aws_permissions_discover': {
                'required_permissions': ['iam:ListAttachedUserPolicies', 'iam:GetPolicy'],
                'description': 'Discover AWS permissions'
            },
            'bucket_access_check': {
                'required_permissions': ['s3:ListBucket'],
                'description': 'Check bucket access permissions'
            }
        }
        
        # Handle tool name variations (remove mcp_quilt-mcp-server_ prefix if present)
        clean_tool_name = tool_name
        if tool_name.startswith('mcp_quilt-mcp-server_'):
            clean_tool_name = tool_name.replace('mcp_quilt-mcp-server_', '')
        
        if clean_tool_name not in tool_auth_rules:
            logger.warning("Unknown tool: %s", clean_tool_name)
            return False
        
        rules = tool_auth_rules[clean_tool_name]
        
        # Check required permissions
        required_perms = rules.get('required_permissions', [])
        for perm in required_perms:
            if not self.validate_permission(perm, permissions):
                logger.warning("Missing permission for tool %s: %s", clean_tool_name, perm)
                return False
        
        # Check bucket access if required
        if rules.get('required_bucket_access', False):
            bucket_name = tool_args.get('bucket', '')
            if bucket_name and not self.validate_bucket_access(bucket_name, buckets):
                logger.warning("No access to bucket for tool %s: %s", clean_tool_name, bucket_name)
                return False
        
        logger.debug("Authorized for tool: %s", clean_tool_name)
        return True
    
    def _extract_authorization_claims(self, claims: Dict[str, Any]) -> Dict[str, Any]:
        """Extract authorization-related claims from JWT.
        
        Args:
            claims: JWT claims dictionary
            
        Returns:
            Dictionary containing authorization information
        """
        auth_info = {
            "scopes": claims.get("scope", "").split() if claims.get("scope") else [],
            "permissions": claims.get("permissions", []),
            "roles": claims.get("roles", []),
            "groups": claims.get("groups", []),
            "user_id": claims.get("sub") or claims.get("user_id"),
            "username": claims.get("preferred_username") or claims.get("username"),
            "email": claims.get("email"),
            "exp": claims.get("exp"),
            "iat": claims.get("iat"),
            "iss": claims.get("iss")
        }
        
        # Extract Quilt-specific claims
        if "quilt" in claims:
            quilt_claims = claims["quilt"]
            auth_info.update({
                "quilt_roles": quilt_claims.get("roles", []),
                "quilt_permissions": quilt_claims.get("permissions", []),
                "quilt_buckets": quilt_claims.get("buckets", [])
            })
        
        return auth_info
    
    def _map_roles_to_permissions(self, roles: List[str]) -> Dict[str, Any]:
        """Map Quilt roles to AWS permissions and bucket access.
        
        Args:
            roles: List of user roles
            
        Returns:
            Dictionary containing permission information
        """
        permissions = {
            "level": AuthorizationLevel.NONE,
            "buckets": [],
            "aws_permissions": [],
            "matched_roles": []
        }
        
        for role in roles:
            if role in self.role_permissions:
                role_info = self.role_permissions[role]
                permissions["matched_roles"].append(role)
                
                # Merge permissions (take highest level)
                if role_info["level"].value in ["admin", "write", "read"]:
                    if permissions["level"] == AuthorizationLevel.NONE:
                        permissions["level"] = role_info["level"]
                    elif role_info["level"] == AuthorizationLevel.ADMIN:
                        permissions["level"] = role_info["level"]
                    elif role_info["level"] == AuthorizationLevel.WRITE and permissions["level"] == AuthorizationLevel.READ:
                        permissions["level"] = role_info["level"]
                
                # Merge buckets and permissions
                if role_info["buckets"] == ["*"]:
                    permissions["buckets"] = ["*"]
                else:
                    permissions["buckets"].extend(role_info["buckets"])
                
                permissions["aws_permissions"].extend(role_info["aws_permissions"])
        
        # Remove duplicates
        permissions["buckets"] = list(set(permissions["buckets"]))
        permissions["aws_permissions"] = list(set(permissions["aws_permissions"]))
        
        return permissions
    
    def _create_authorization_from_jwt_claims(self, roles: List[str], permissions: List[str], scopes: List[str]) -> Dict[str, Any]:
        """Create authorization object from JWT claims (enhanced JWT from frontend).
        
        Args:
            roles: List of user roles from JWT
            permissions: List of AWS permissions from JWT
            scopes: List of scopes from JWT
            
        Returns:
            Authorization dictionary with level, buckets, and permissions
        """
        # Determine authorization level from scopes
        auth_level = AuthorizationLevel.NONE
        if "admin" in scopes:
            auth_level = AuthorizationLevel.ADMIN
        elif "write" in scopes:
            auth_level = AuthorizationLevel.WRITE
        elif "read" in scopes:
            auth_level = AuthorizationLevel.READ
        
        # Extract buckets from permissions or use default based on roles
        buckets = []
        if permissions:
            # Look for bucket-specific permissions
            for perm in permissions:
                if "s3:" in perm and "bucket" in perm.lower():
                    # Extract bucket name from permission if possible
                    pass  # For now, we'll use role-based bucket mapping
        
        # If no buckets found, use role-based mapping
        if not buckets:
            for role in roles:
                if role in self.role_permissions:
                    role_info = self.role_permissions[role]
                    buckets.extend(role_info["buckets"])
        
        # Remove duplicates
        buckets = list(set(buckets))
        
        return {
            "level": auth_level,
            "buckets": buckets,
            "aws_permissions": permissions,
            "matched_roles": roles,
            "scopes": scopes,
            "source": "jwt_claims"
        }
        
    def validate_bearer_token(self, access_token: str) -> Tuple[BearerAuthStatus, Optional[Dict[str, Any]]]:
        """Validate a bearer token by parsing JWT claims (enhanced JWT from frontend).
        
        The frontend now provides all necessary authorization information in the JWT token,
        so we can validate the token by parsing the JWT claims directly.
        
        Args:
            access_token: The bearer token to validate
            
        Returns:
            Tuple of (status, user_info_with_authorization)
        """
        try:
            # Parse JWT claims to extract authorization information
            jwt_claims = self._parse_jwt_claims(access_token)
            if not jwt_claims:
                logger.warning("Could not parse JWT claims from token")
                return BearerAuthStatus.INVALID, None
            
            # Extract authorization claims from JWT
            auth_claims = self._extract_authorization_claims(jwt_claims)
            logger.debug("Extracted authorization claims: %s", auth_claims)
            
            # Check if token is expired
            exp = auth_claims.get("exp")
            if exp and exp < time.time():
                logger.warning("Bearer token has expired")
                return BearerAuthStatus.EXPIRED, None
            
            # Build user info from JWT claims
            user_info = {
                "id": auth_claims.get("user_id"),
                "username": auth_claims.get("username"),
                "email": auth_claims.get("email"),
                "user_id": auth_claims.get("user_id"),
                "scope": auth_claims.get("scopes", []),
                "permissions": auth_claims.get("permissions", []),
                "roles": auth_claims.get("roles", []),
                "groups": auth_claims.get("groups", [])
            }
            
            # Extract authorization information from JWT
            roles = auth_claims.get("roles", [])
            permissions = auth_claims.get("permissions", [])
            scopes = auth_claims.get("scopes", [])
            
            # Create authorization object from JWT claims
            if roles or permissions or scopes:
                # Use the authorization information directly from JWT
                authorization = self._create_authorization_from_jwt_claims(roles, permissions, scopes)
                user_info["authorization"] = authorization
                
                logger.info("Bearer token validation successful for user: %s with auth level: %s", 
                           user_info.get('username', 'unknown'),
                           authorization.get("level", "none"))
            else:
                logger.warning("No authorization claims found in JWT for user: %s", user_info.get('username', 'unknown'))
                user_info["authorization"] = {
                    "level": AuthorizationLevel.NONE,
                    "buckets": [],
                    "aws_permissions": [],
                    "matched_roles": [],
                    "source": "jwt_claims"
                }
            
            return BearerAuthStatus.AUTHENTICATED, user_info
                
        except Exception as e:
            logger.error("Unexpected error during bearer token validation: %s", e)
            return BearerAuthStatus.UNAUTHENTICATED, None
    
    def validate_bucket_access_with_token(self, access_token: str, bucket_name: str, operation: str = "read") -> Tuple[bool, Optional[str]]:
        """Validate if the bearer token allows access to a specific bucket and operation.
        
        Args:
            access_token: The bearer token
            bucket_name: Name of the bucket to access
            operation: Operation type ("read", "write", "delete", "list")
            
        Returns:
            Tuple of (allowed, reason)
        """
        try:
            # Get user info with authorization
            status, user_info = self.validate_bearer_token(access_token)
            if status != BearerAuthStatus.AUTHENTICATED or not user_info:
                return False, "Authentication failed"
            
            authorization = user_info.get("authorization", {})
            if not authorization:
                return False, "No authorization information found"
            
            auth_level = authorization.get("level", AuthorizationLevel.NONE)
            allowed_buckets = authorization.get("buckets", [])
            
            # Check if user has access to this bucket
            if "*" not in allowed_buckets and bucket_name not in allowed_buckets:
                return False, f"User does not have access to bucket '{bucket_name}'"
            
            # Check operation permissions
            if operation == "read" and auth_level in [AuthorizationLevel.READ, AuthorizationLevel.WRITE, AuthorizationLevel.ADMIN]:
                return True, None
            elif operation in ["write", "delete"] and auth_level in [AuthorizationLevel.WRITE, AuthorizationLevel.ADMIN]:
                return True, None
            elif operation == "list" and auth_level in [AuthorizationLevel.READ, AuthorizationLevel.WRITE, AuthorizationLevel.ADMIN]:
                return True, None
            else:
                return False, f"Insufficient permissions for '{operation}' operation (level: {auth_level.value})"
                
        except Exception as e:
            logger.error("Error validating bucket access: %s", e)
            return False, f"Validation error: {str(e)}"
    
    def get_user_permissions(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Get user permissions from bearer token.
        
        Args:
            access_token: The bearer token
            
        Returns:
            Dictionary containing user permissions or None if invalid
        """
        try:
            status, user_info = self.validate_bearer_token(access_token)
            if status != BearerAuthStatus.AUTHENTICATED or not user_info:
                return None
            
            return user_info.get("authorization")
            
        except Exception as e:
            logger.error("Error getting user permissions: %s", e)
            return None

    def validate_tool_permissions(self, access_token: str, tool_name: str, bucket_name: str = None) -> Tuple[bool, str]:
        """Validate if user has permission to use a specific tool.
        
        Args:
            access_token: The bearer token to validate
            tool_name: Name of the tool/operation being requested
            bucket_name: Optional bucket name for bucket-specific validation
            
        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        try:
            # Get user permissions
            permissions = self.get_user_permissions(access_token)
            if not permissions:
                return False, "Could not retrieve user permissions"
            
            # Check if user has access to all tools (admin)
            allowed_tools = permissions.get("tools", [])
            if allowed_tools == ["*"]:
                return True, "Admin access granted"
            
            # Check if tool is in user's allowed tools
            if tool_name not in allowed_tools:
                return False, f"Tool '{tool_name}' not in allowed tools: {allowed_tools}"
            
            # Check bucket access if bucket is specified
            if bucket_name:
                allowed_buckets = permissions.get("buckets", [])
                if "*" not in allowed_buckets and bucket_name not in allowed_buckets:
                    return False, f"Bucket '{bucket_name}' not in allowed buckets: {allowed_buckets}"
            
            # Get required AWS permissions for this tool
            required_permissions = self.tool_permissions.get(tool_name, [])
            if not required_permissions:
                logger.warning("No permission mapping found for tool: %s", tool_name)
                return True, "No specific permissions required for this tool"
            
            # For now, assume the role-based mapping covers the required permissions
            # In a full implementation, you might want to check individual AWS permissions
            return True, f"Tool '{tool_name}' authorized with permissions: {required_permissions}"
            
        except Exception as e:
            logger.error("Error validating tool permissions: %s", e)
            return False, f"Permission validation error: {e}"
    
    def get_authenticated_session(self, access_token: str) -> Optional[requests.Session]:
        """Get an authenticated requests session with the bearer token.
        
        Args:
            access_token: The bearer token to use for authentication
            
        Returns:
            Authenticated requests session or None if token is invalid
        """
        # Check cache first
        if access_token in self.session_cache:
            return self.session_cache[access_token]
        
        # Validate token
        status, user_info = self.validate_bearer_token(access_token)
        if status != BearerAuthStatus.AUTHENTICATED:
            return None
        
        # Create authenticated session
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "quilt-mcp-server/1.0.0"
        })
        
        # Cache the session
        self.session_cache[access_token] = session
        
        # Store user info in cache
        self.token_cache[access_token] = {
            "user_info": user_info,
            "validated_at": time.time(),
            "status": status
        }
        
        return session
    
    def make_authenticated_request(self, access_token: str, method: str, url: str, **kwargs) -> Optional[requests.Response]:
        """Make an authenticated request to Quilt's API.
        
        Args:
            access_token: The bearer token to use
            method: HTTP method (GET, POST, etc.)
            url: URL to request (can be relative to catalog_url)
            **kwargs: Additional arguments for requests
            
        Returns:
            Response object or None if authentication fails
        """
        session = self.get_authenticated_session(access_token)
        if not session:
            return None
        
        # Make URL absolute if it's relative
        if not url.startswith('http'):
            url = urljoin(self.catalog_url, url)
        
        try:
            response = session.request(method, url, **kwargs)
            return response
        except Exception as e:
            logger.error("Authenticated request failed: %s", e)
            return None
    
    def get_user_info(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Get user information from the bearer token.
        
        Args:
            access_token: The bearer token
            
        Returns:
            User information dictionary or None if invalid
        """
        if access_token in self.token_cache:
            return self.token_cache[access_token].get("user_info")
        
        status, user_info = self.validate_bearer_token(access_token)
        if status == BearerAuthStatus.AUTHENTICATED:
            return user_info
        
        return None
    
    def clear_cache(self, access_token: Optional[str] = None):
        """Clear token and session cache.
        
        Args:
            access_token: Specific token to clear, or None to clear all
        """
        if access_token:
            self.token_cache.pop(access_token, None)
            self.session_cache.pop(access_token, None)
        else:
            self.token_cache.clear()
            self.session_cache.clear()
    
    def refresh_token_if_needed(self, refresh_token: str) -> Optional[str]:
        """Refresh an access token using a refresh token.
        
        Args:
            refresh_token: The refresh token
            
        Returns:
            New access token or None if refresh fails
        """
        try:
            response = requests.post(
                f"{self.catalog_url}/api/token",
                data={"refresh_token": refresh_token},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("access_token")
            else:
                logger.warning("Token refresh failed with status: %s", response.status_code)
                return None
                
        except Exception as e:
            logger.error("Token refresh error: %s", e)
            return None


# Global instance
_bearer_auth_service: Optional[BearerAuthService] = None


def get_bearer_auth_service() -> BearerAuthService:
    """Get the global bearer auth service instance."""
    global _bearer_auth_service
    if _bearer_auth_service is None:
        catalog_url = os.environ.get("QUILT_CATALOG_URL", "https://demo.quiltdata.com")
        _bearer_auth_service = BearerAuthService(catalog_url)
    return _bearer_auth_service
