"""JWT authentication and authorization service for the Quilt MCP server."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import boto3
import jwt

from quilt_mcp.services.jwt_decoder import safe_decompress_jwt

logger = logging.getLogger(__name__)


_SECRET_CACHE: Dict[Tuple[str, str], str] = {}


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
        self.jwt_secret, self._jwt_secret_source = self._resolve_jwt_secret()
        self.jwt_kid = os.getenv("MCP_ENHANCED_JWT_KID", "frontend-enhanced")
        self.tool_permissions: Dict[str, List[str]] = self._build_tool_permissions()
        self._session_cache: Dict[str, Dict[str, boto3.Session]] = {}
        logger.info(
            "BearerAuthService initialized (secret_source=%s, secret_length=%d, kid=%s)",
            self._jwt_secret_source,
            len(self.jwt_secret) if self.jwt_secret else 0,
            self.jwt_kid,
        )

    # ------------------------------------------------------------------
    # JWT processing
    # ------------------------------------------------------------------

    def _resolve_jwt_secret(self) -> Tuple[str, str]:
        """Resolve the JWT signing secret from env vars or SSM."""

        env_secret = os.getenv("MCP_ENHANCED_JWT_SECRET")
        if env_secret:
            logger.debug("Loaded JWT secret from environment variable MCP_ENHANCED_JWT_SECRET")
            return env_secret, "env:MCP_ENHANCED_JWT_SECRET"

        parameter_name = os.getenv("MCP_ENHANCED_JWT_SECRET_SSM_PARAMETER") or os.getenv(
            "MCP_ENHANCED_JWT_SECRET_PARAM"
        )
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")

        if parameter_name and not region:
            logger.error(
                "MCP_ENHANCED_JWT_SECRET_SSM_PARAMETER is set but AWS region is missing; "
                "unable to retrieve JWT secret from SSM"
            )

        if parameter_name and region:
            secret = self._get_secret_from_ssm(parameter_name, region)
            if secret:
                logger.info(
                    "Loaded JWT secret from SSM parameter %s (region=%s, length=%d)",
                    parameter_name,
                    region,
                    len(secret),
                )
                return secret, f"ssm:{parameter_name}:{region}"

        if not parameter_name and region and self._running_in_aws():
            default_parameter = "/quilt/mcp-server/jwt-secret"
            secret = self._get_secret_from_ssm(default_parameter, region)
            if secret:
                logger.info(
                    "Loaded JWT secret from default SSM parameter %s (region=%s, length=%d)",
                    default_parameter,
                    region,
                    len(secret),
                )
                return secret, f"ssm:{default_parameter}:{region}"

        logger.warning(
            "Falling back to development JWT secret; configure MCP_ENHANCED_JWT_SECRET or "
            "MCP_ENHANCED_JWT_SECRET_SSM_PARAMETER to avoid signature mismatches."
        )
        return "development-enhanced-jwt-secret", "fallback:development"

    def _get_secret_from_ssm(self, parameter_name: str, region: str) -> Optional[str]:
        cache_key = (parameter_name, region)
        if cache_key in _SECRET_CACHE:
            logger.debug("Using cached JWT secret for SSM parameter %s", parameter_name)
            return _SECRET_CACHE[cache_key]

        try:
            client = boto3.client("ssm", region_name=region)
            response = client.get_parameter(Name=parameter_name, WithDecryption=True)
            value = response.get("Parameter", {}).get("Value")
            if value:
                _SECRET_CACHE[cache_key] = value
                return value
            logger.error("SSM parameter %s did not return a value", parameter_name)
        except Exception as exc:  # pragma: no cover - logged for troubleshooting
            logger.error("Error retrieving JWT secret from SSM parameter %s: %s", parameter_name, exc)
        return None

    @staticmethod
    def _running_in_aws() -> bool:
        return bool(os.getenv("AWS_EXECUTION_ENV") or os.getenv("ECS_CONTAINER_METADATA_URI_V4"))

    def authenticate_header(self, header_value: str | None) -> JwtAuthResult:
        if not header_value or not header_value.startswith("Bearer "):
            raise JwtAuthError("missing_authorization", "Bearer token required on tool endpoints")

        token = header_value[7:].strip()
        if not token:
            raise JwtAuthError("missing_authorization", "Bearer token required on tool endpoints")

        try:
            logger.debug(
                "Validating JWT: secret_source=%s kid=%s token_length=%d",
                self._jwt_secret_source,
                self.jwt_kid,
                len(token),
            )

            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            logger.debug("JWT decode successful, payload keys: %s", list(payload.keys()))
        except jwt.ExpiredSignatureError as exc:  # pragma: no cover
            logger.error("JWT token expired: %s", exc)
            raise JwtAuthError("token_expired", "JWT token expired") from exc
        except jwt.InvalidTokenError as exc:
            logger.error(
                "JWT validation failed: %s (secret_length=%d, kid=%s)", str(exc), len(self.jwt_secret), self.jwt_kid
            )
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
            "JWT authentication successful for user=%s buckets=%d permissions=%d",
            result.username or result.user_id,
            len(result.buckets),
            len(result.permissions),
        )
        return result

    # ------------------------------------------------------------------
    # Authorization
    # ------------------------------------------------------------------

    def _build_tool_permissions(self) -> Dict[str, List[str]]:
        base_permissions = {
            "bucket_object_info": ["s3:GetObject", "s3:ListBucket"],
            "bucket_object_text": ["s3:GetObject"],
            "bucket_objects_list": ["s3:ListBucket"],
            "bucket_object_fetch": ["s3:GetObject"],
            "bucket_objects_put": ["s3:PutObject"],
            "package_create_from_s3": ["s3:GetObject", "s3:ListBucket"],
            "package_browse": ["quilt:BrowsePackages"],
            "package_create": ["quilt:UpdatePackage"],
            "package_update": ["quilt:UpdatePackage"],
            "package_delete": ["quilt:UpdatePackage"],
            "unified_search": ["quilt:BrowsePackages"],
        }

        overrides_env = os.getenv("MCP_TOOL_PERMISSIONS")
        if overrides_env:
            try:
                import json

                overrides = json.loads(overrides_env)
                if isinstance(overrides, dict):
                    for key, value in overrides.items():
                        if isinstance(value, list):
                            base_permissions[key] = value
                        elif isinstance(value, str):
                            base_permissions[key] = [value]
            except Exception as exc:  # pragma: no cover
                logger.error("Failed to parse MCP_TOOL_PERMISSIONS override: %s", exc)

        return base_permissions

    def authorize_tool(
        self, result: JwtAuthResult, tool_name: str, tool_args: Dict[str, Any]
    ) -> AuthorizationDecision:
        required_permissions = self.tool_permissions.get(tool_name)
        if not required_permissions:
            return AuthorizationDecision(allowed=True)

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

        normalized = {
            "access_key_id": candidate.get("accessKeyId") or candidate.get("access_key_id"),
            "secret_access_key": candidate.get("secretAccessKey") or candidate.get("secret_access_key"),
            "session_token": candidate.get("sessionToken") or candidate.get("session_token"),
            "region": candidate.get("region"),
        }

        if not normalized["access_key_id"] or not normalized["secret_access_key"]:
            return None

        return normalized

    @staticmethod
    def _extract_optional_role(payload: Dict[str, Any]) -> Optional[str]:
        role_arn = payload.get("aws_role_arn") or payload.get("awsRoleArn")
        if isinstance(role_arn, str) and role_arn.strip():
            return role_arn.strip()
        return None

    @staticmethod
    def _is_bucket_authorized(bucket: str, allowed_buckets: List[str]) -> bool:
        if not allowed_buckets:
            return False

        if bucket in allowed_buckets:
            return True

        for pattern in allowed_buckets:
            if pattern.endswith("*") and bucket.startswith(pattern[:-1]):
                return True

        return False


_SERVICE_INSTANCE: Optional[BearerAuthService] = None


def get_bearer_auth_service() -> BearerAuthService:
    """Return the shared BearerAuthService instance."""
    global _SERVICE_INSTANCE
    if _SERVICE_INSTANCE is None:
        _SERVICE_INSTANCE = BearerAuthService()
    return _SERVICE_INSTANCE
