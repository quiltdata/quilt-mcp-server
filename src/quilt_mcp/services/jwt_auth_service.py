"""JWT-based authentication service for Quilt MCP server."""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, List, Literal, Optional

import boto3

from quilt_mcp.runtime_context import (
    get_runtime_auth,
    get_runtime_claims,
    get_runtime_metadata,
    update_runtime_metadata,
)
from quilt_mcp.services.auth_metrics import record_role_assumption
from quilt_mcp.services.jwt_decoder import JwtDecodeError, get_jwt_decoder

logger = logging.getLogger(__name__)


class JwtAuthServiceError(RuntimeError):
    """Raised when JWT auth cannot produce AWS credentials."""

    def __init__(self, message: str, *, code: str = "jwt_auth_error") -> None:
        super().__init__(message)
        self.code = code


def _safe_session_name(value: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9+=,.@-]", "-", value or "user")
    if not sanitized:
        sanitized = "user"
    return sanitized[:64]


def _normalize_tags(raw_tags: Any) -> List[Dict[str, str]]:
    if not raw_tags:
        return []
    tags: List[Dict[str, str]] = []
    if isinstance(raw_tags, dict):
        for key, value in raw_tags.items():
            tags.append({"Key": str(key), "Value": str(value)})
        return tags
    if isinstance(raw_tags, list):
        for item in raw_tags:
            if isinstance(item, dict) and "Key" in item and "Value" in item:
                tags.append({"Key": str(item["Key"]), "Value": str(item["Value"])})
        return tags
    return []


class JWTAuthService:
    """Resolve authentication context for Quilt MCP tools using JWT claims."""

    auth_type: Literal["jwt"] = "jwt"

    def __init__(self) -> None:
        self._decoder = get_jwt_decoder()
        self._catalog_configured = False

    def get_boto3_session(self) -> boto3.Session:
        """Assume an AWS role using JWT claims and return a boto3 session."""
        runtime_auth = get_runtime_auth()
        if runtime_auth is None:
            raise JwtAuthServiceError(
                "JWT authentication required. Provide Authorization: Bearer header.",
                code="missing_jwt",
            )

        claims = runtime_auth.claims or get_runtime_claims()
        if not claims and runtime_auth.access_token:
            try:
                claims = self._decoder.decode(runtime_auth.access_token)
            except JwtDecodeError as exc:
                raise JwtAuthServiceError(f"Invalid JWT: {exc.detail}", code=exc.code) from exc

        # Setup catalog authentication if present
        self._setup_catalog_authentication(claims)

        role_arn = self._extract_role_arn(claims)
        if not role_arn:
            raise JwtAuthServiceError(
                "JWT claim 'role_arn' is required for role assumption.",
                code="missing_role_arn",
            )

        subject = claims.get("sub") or claims.get("user_id") or claims.get("id")
        if not subject:
            raise JwtAuthServiceError("JWT claim 'sub' is required for SourceIdentity.", code="missing_sub")

        metadata = get_runtime_metadata()
        cached_session = metadata.get("jwt_assumed_session")
        cached_expiration = metadata.get("jwt_assumed_expiration")
        if cached_session and cached_expiration and cached_expiration > time.time() + 60:
            return cached_session

        session, expiration = self._assume_role_session(role_arn, claims, subject)
        update_runtime_metadata(jwt_assumed_session=session, jwt_assumed_expiration=expiration)
        return session

    def _setup_catalog_authentication(self, claims: Dict[str, Any]) -> None:
        """Setup catalog authentication from JWT claims."""
        if self._catalog_configured:
            return
            
        catalog_claims = self.extract_catalog_claims(claims)
        if not catalog_claims:
            logger.warning("No catalog authentication found in JWT - catalog operations may fail")
            return
            
        try:
            self._configure_quilt3_session(
                catalog_claims.get("catalog_token"),
                catalog_claims.get("catalog_url"),
                catalog_claims.get("registry_url")
            )
            self._catalog_configured = True
            logger.info("Catalog authentication configured from JWT claims")
        except Exception as exc:
            logger.warning("Failed to configure catalog authentication: %s", exc)

    def extract_catalog_claims(self, claims: Dict[str, Any]) -> Dict[str, str]:
        """Extract catalog authentication claims from JWT.
        
        Returns:
            Dictionary with catalog_token, catalog_url, registry_url
        """
        catalog_claims = {}
        
        # Extract catalog token
        catalog_token = claims.get("catalog_token")
        if catalog_token:
            catalog_claims["catalog_token"] = catalog_token
            
        # Extract catalog URL
        catalog_url = claims.get("catalog_url")
        if catalog_url:
            catalog_claims["catalog_url"] = catalog_url
            
        # Extract registry URL
        registry_url = claims.get("registry_url")
        if registry_url:
            catalog_claims["registry_url"] = registry_url
            
        return catalog_claims

    def _configure_quilt3_session(self, token: Optional[str], catalog_url: Optional[str], registry_url: Optional[str]) -> None:
        """Configure quilt3 with catalog session information."""
        if not token or not catalog_url:
            return
            
        try:
            # Import quilt3 here to avoid import issues if not available
            import quilt3
            
            # Configure quilt3 with the catalog URL
            quilt3.config(catalog_url)
            
            # Store catalog authentication in runtime metadata for later use
            update_runtime_metadata(
                catalog_token=token,
                catalog_url=catalog_url,
                registry_url=registry_url,
                catalog_session_configured=True
            )
            
        except ImportError:
            logger.warning("quilt3 not available - catalog operations will not work")
        except Exception as exc:
            logger.warning("Failed to configure quilt3 session: %s", exc)

    def validate_catalog_authentication(self, claims: Dict[str, Any]) -> bool:
        """Validate that catalog authentication is present in JWT claims.
        
        Returns:
            True if catalog authentication is present, False otherwise
        """
        catalog_claims = self.extract_catalog_claims(claims)
        return bool(catalog_claims.get("catalog_token") and catalog_claims.get("catalog_url"))

    def _assume_role_session(self, role_arn: str, claims: Dict[str, Any], subject: str) -> tuple[boto3.Session, float]:
        tags = _normalize_tags(claims.get("session_tags") or claims.get("sessionTags") or claims.get("tags"))
        transitive_tag_keys = claims.get("transitive_tag_keys") or claims.get("transitiveTagKeys")
        if isinstance(transitive_tag_keys, list):
            transitive_tag_keys = [str(key) for key in transitive_tag_keys if key]
        else:
            transitive_tag_keys = []

        session_name = _safe_session_name(f"mcp-{subject}-{int(time.time())}")

        duration = int(os.getenv("MCP_JWT_SESSION_DURATION", "3600"))
        duration = min(max(duration, 900), 43200)

        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        sts = boto3.client("sts", region_name=region)

        assume_kwargs: Dict[str, Any] = {
            "RoleArn": role_arn,
            "RoleSessionName": session_name,
            "DurationSeconds": duration,
            "SourceIdentity": str(subject),
        }
        if tags:
            assume_kwargs["Tags"] = tags
        if transitive_tag_keys:
            assume_kwargs["TransitiveTagKeys"] = transitive_tag_keys

        start = time.perf_counter()
        try:
            response = sts.assume_role(**assume_kwargs)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error("Role assumption failed for %s: %s", role_arn, exc)
            logger.info(
                "Role assumption attempt completed for sub=%s (duration_ms=%.2f).",
                subject,
                duration_ms,
            )
            record_role_assumption("failure", duration_ms=duration_ms, reason="assume_role_failed")
            raise JwtAuthServiceError("Failed to assume AWS role from JWT claims.", code="assume_role_failed") from exc

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "Role assumption attempt completed for sub=%s (duration_ms=%.2f).",
            subject,
            duration_ms,
        )
        record_role_assumption("success", duration_ms=duration_ms)

        credentials = response["Credentials"]
        logger.info("JWT authentication successful for sub=%s role=%s", subject, role_arn)
        expiration = credentials.get("Expiration")
        expiration_ts = expiration.timestamp() if hasattr(expiration, "timestamp") else time.time() + duration

        session = boto3.Session(
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
            region_name=region or "us-east-1",
        )
        return session, expiration_ts

    @staticmethod
    def _extract_role_arn(claims: Dict[str, Any]) -> Optional[str]:
        for key in ("role_arn", "roleArn", "aws_role_arn", "awsRoleArn"):
            value = claims.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None
