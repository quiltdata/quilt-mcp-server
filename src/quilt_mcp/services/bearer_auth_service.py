"""JWT authentication and authorization service for the Quilt MCP server."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import boto3
import jwt

from quilt_mcp.services.jwt_decoder import safe_decompress_jwt

logger = logging.getLogger(__name__)


class JwtAuthError(Exception):
    """Raised when JWT authentication fails."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass
class JwtAuthResult:
    """Normalized JWT claims for downstream authorization."""

    token: str
    claims: Dict[str, Any]
    permissions: List[str]
    buckets: List[str]
    roles: List[str]
    aws_credentials: Optional[Dict[str, str]] = None
    aws_role_arn: Optional[str] = None
    user_id: Optional[str] = None
    username: Optional[str] = None
    raw_payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthorizationDecision:
    """Outcome of an authorization check."""

    allowed: bool
    reason: Optional[str] = None
    missing_permissions: List[str] = field(default_factory=list)
    missing_buckets: List[str] = field(default_factory=list)


class BearerAuthService:
    """Authenticate enhanced Quilt JWTs and authorize tool access."""

    def __init__(self) -> None:
        self.jwt_secret = os.getenv("MCP_ENHANCED_JWT_SECRET", "development-enhanced-jwt-secret")
        self.jwt_kid = os.getenv("MCP_ENHANCED_JWT_KID", "frontend-enhanced")
        self.tool_permissions: Dict[str, List[str]] = self._build_tool_permissions()
        self._session_cache: Dict[str, Dict[str, boto3.Session]] = {}

    # ------------------------------------------------------------------
    # JWT processing
    # ------------------------------------------------------------------

    def authenticate_header(self, header_value: str | None) -> JwtAuthResult:
        if not header_value or not header_value.startswith("Bearer "):
            raise JwtAuthError("missing_authorization", "Bearer token required on tool endpoints")

        token = header_value[7:].strip()
        if not token:
            raise JwtAuthError("missing_authorization", "Bearer token required on tool endpoints")

        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
        except jwt.ExpiredSignatureError as exc:  # pragma: no cover
            raise JwtAuthError("token_expired", "JWT token expired") from exc
        except jwt.InvalidTokenError as exc:
            raise JwtAuthError("invalid_token", "JWT token could not be verified") from exc

        normalized = safe_decompress_jwt(payload)
        aws_credentials = self._extract_optional_credentials(payload)
        aws_role_arn = self._extract_optional_role(payload)

        result = JwtAuthResult(
            token=token,
            claims=normalized,
            permissions=normalized.get("permissions", []),
            buckets=normalized.get("buckets", []),
            roles=normalized.get("roles", []),
            aws_credentials=aws_credentials,
            aws_role_arn=aws_role_arn,
            user_id=payload.get("sub") or payload.get("id"),
            username=payload.get("username"),
            raw_payload=payload,
        )

        logger.info(
            "JWT authentication succeeded for sub=%s (permissions=%d, buckets=%d, roles=%d)",
            result.user_id,
            len(result.permissions),
            len(result.buckets),
            len(result.roles),
        )

        return result

    # ------------------------------------------------------------------
    # Authorization helpers
    # ------------------------------------------------------------------

    def authorize_tool(self, result: JwtAuthResult, tool_name: str, tool_args: Dict[str, Any]) -> AuthorizationDecision:
        required_permissions = self.tool_permissions.get(tool_name, [])

        missing_perms = [perm for perm in required_permissions if perm not in result.permissions]
        if missing_perms:
            return AuthorizationDecision(
                allowed=False,
                reason=f"Missing required permission(s): {', '.join(missing_perms)}",
                missing_permissions=missing_perms,
            )

        bucket_name = tool_args.get("bucket") or tool_args.get("bucket_name")
        if bucket_name:
            if not self._is_bucket_authorized(bucket_name, result.buckets):
                return AuthorizationDecision(
                    allowed=False,
                    reason=f"Access denied to bucket {bucket_name}",
                    missing_buckets=[bucket_name],
                )

        return AuthorizationDecision(allowed=True)

    # ------------------------------------------------------------------
    # boto3 client construction
    # ------------------------------------------------------------------

    def build_boto3_session(self, result: JwtAuthResult) -> boto3.Session:
        cached = self._session_cache.setdefault(result.token, {})
        session = cached.get("default")
        if session:
            return session

        credentials = result.aws_credentials
        if credentials:
            session = boto3.Session(
                aws_access_key_id=credentials.get("access_key_id"),
                aws_secret_access_key=credentials.get("secret_access_key"),
                aws_session_token=credentials.get("session_token"),
                region_name=credentials.get("region") or "us-east-1",
            )
            cached["default"] = session
            return session

        if result.aws_role_arn:
            session = self._assume_role_session(result.aws_role_arn)
            cached["default"] = session
            return session

        # Final fallback: use ambient credentials (useful for dev containers)
        session = boto3.Session()
        cached["default"] = session
        return session

    def build_boto3_client(self, result: JwtAuthResult, service: str):
        session = self.build_boto3_session(result)
        return session.client(service)

    # ------------------------------------------------------------------
    # Backwards compatibility helpers
    # ------------------------------------------------------------------

    def decode_jwt_token(self, header_value: str) -> Optional[Dict[str, Any]]:
        try:
            result = self.authenticate_header(header_value)
            return result.raw_payload
        except JwtAuthError:
            return None

    def extract_auth_claims(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return safe_decompress_jwt(payload)

    def authorize_mcp_tool(self, tool_name: str, tool_args: Dict[str, Any], claims: Dict[str, Any]) -> bool:
        result = JwtAuthResult(
            token="compat",
            claims=claims,
            permissions=claims.get("permissions", []),
            buckets=claims.get("buckets", []),
            roles=claims.get("roles", []),
        )
        decision = self.authorize_tool(result, tool_name, tool_args)
        return decision.allowed

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _assume_role_session(self, role_arn: str) -> boto3.Session:
        sts = boto3.client("sts")
        session_name = f"mcp-server-{int(time.time())}"
        response = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName=session_name,
            DurationSeconds=3600,
        )
        credentials = response["Credentials"]
        return boto3.Session(
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
            region_name="us-east-1",
        )

    @staticmethod
    def _extract_optional_credentials(payload: Dict[str, Any]) -> Optional[Dict[str, str]]:
        candidate = payload.get("aws_credentials") or payload.get("awsCredentials")
        if not isinstance(candidate, dict):
            return None
        if not candidate.get("access_key_id") or not candidate.get("secret_access_key"):
            return None
        return {
            "access_key_id": candidate.get("access_key_id"),
            "secret_access_key": candidate.get("secret_access_key"),
            "session_token": candidate.get("session_token"),
            "region": candidate.get("region") or "us-east-1",
        }

    @staticmethod
    def _extract_optional_role(payload: Dict[str, Any]) -> Optional[str]:
        role = (
            payload.get("aws_role_arn")
            or payload.get("awsRoleArn")
            or payload.get("role_arn")
            or payload.get("roleArn")
        )
        if isinstance(role, str) and role.startswith("arn:aws:iam::"):
            return role
        roles = payload.get("roles") or []
        if isinstance(roles, list):
            for candidate in roles:
                if isinstance(candidate, str) and candidate.startswith("arn:aws:iam::"):
                    return candidate
        return None

    @staticmethod
    def _build_tool_permissions() -> Dict[str, List[str]]:
        return {
            # S3 bucket operations
            "bucket_objects_list": ["s3:ListBucket", "s3:GetBucketLocation"],
            "bucket_object_info": ["s3:GetObject", "s3:GetObjectVersion"],
            "bucket_object_text": ["s3:GetObject"],
            "bucket_object_fetch": ["s3:GetObject"],
            "bucket_objects_put": ["s3:PutObject", "s3:PutObjectAcl", "s3:AbortMultipartUpload"],
            "bucket_object_link": ["s3:GetObject"],
            # Package operations
            "package_create": ["s3:ListBucket", "s3:GetObject", "s3:PutObject"],
            "package_update": ["s3:ListBucket", "s3:GetObject", "s3:PutObject"],
            "package_delete": ["s3:ListBucket", "s3:DeleteObject"],
            "package_browse": ["s3:ListBucket", "s3:GetObject"],
            "package_contents_search": ["s3:ListBucket"],
            "package_diff": ["s3:GetObject", "s3:ListBucket"],
            "create_package_enhanced": ["s3:ListBucket", "s3:GetObject", "s3:PutObject"],
            "create_package_from_s3": ["s3:ListBucket", "s3:GetObject", "s3:PutObject"],
            "package_create_from_s3": ["s3:ListBucket", "s3:GetObject", "s3:PutObject"],
            # Athena / Glue operations
            "athena_query_execute": ["athena:StartQueryExecution", "athena:GetQueryResults"],
            "athena_databases_list": ["glue:GetDatabases"],
            "athena_tables_list": ["glue:GetTables"],
            "athena_table_schema": ["glue:GetTable"],
            "athena_workgroups_list": ["athena:ListWorkGroups"],
            "athena_query_history": ["athena:ListQueryExecutions"],
            # Search operations
            "unified_search": ["s3:ListBucket"],
            "packages_search": ["s3:ListBucket"],
        }

    @staticmethod
    def _is_bucket_authorized(target: str, allowed: List[str]) -> bool:
        if "*" in allowed:
            return True
        return target in allowed


_auth_service: Optional[BearerAuthService] = None


def get_bearer_auth_service() -> BearerAuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = BearerAuthService()
    return _auth_service
