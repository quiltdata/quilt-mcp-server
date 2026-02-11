"""JWT-based authentication service for Quilt MCP server."""

from __future__ import annotations

import os
import time
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional, cast

from quilt_mcp.context.runtime_context import (
    get_runtime_auth,
)
from quilt_mcp.auth.jwt_discovery import JWTDiscovery


class JwtAuthServiceError(RuntimeError):
    """Raised when JWT auth cannot be resolved."""

    def __init__(self, message: str, *, code: str = "jwt_auth_error") -> None:
        super().__init__(message)
        self.code = code


class JWTAuthService:
    """
    JWT pass-through authentication service.

    This service extracts JWT tokens from the runtime context and exchanges
    them for temporary AWS credentials. It does NOT validate JWTs locally -
    all validation happens at the GraphQL backend.
    """

    auth_type: Literal["jwt"] = "jwt"

    def __init__(self) -> None:
        self._cached_credentials: Optional[Dict[str, Any]] = None
        self._credentials_lock = threading.Lock()

    def _resolve_access_token(self) -> Optional[str]:
        """Resolve JWT token from runtime context first, then discovery fallbacks."""
        runtime_auth = get_runtime_auth()
        if runtime_auth and runtime_auth.access_token:
            return runtime_auth.access_token
        return JWTDiscovery.discover()

    def get_session(self):
        """Get boto3 session with temporary AWS credentials from JWT.

        This method exchanges the JWT access token for temporary AWS credentials
        by calling the /api/auth/get_credentials endpoint, following the same
        pattern as the Quilt catalog frontend and quilt3 library.

        Raises:
            JwtAuthServiceError: If JWT token is missing, invalid, or expired,
                or if credential exchange fails.

        Returns:
            boto3.Session configured with temporary AWS credentials
        """
        return self.get_boto3_session()

    def get_boto3_session(self):
        """Get boto3 session with temporary AWS credentials from JWT.

        Exchanges JWT token for temporary AWS credentials and caches them
        with automatic refresh when expired.

        Note: This does NOT validate the JWT locally. The GraphQL backend
        will validate the JWT when we call the credential exchange endpoint.

        Returns:
            boto3.Session configured with temporary AWS credentials
        """
        import boto3

        access_token = self._resolve_access_token()
        if not access_token:
            raise JwtAuthServiceError(
                "JWT authentication required. Provide Authorization: Bearer header.",
                code="missing_jwt",
            )

        # Pass JWT directly to backend - GraphQL validates it
        credentials = self._get_or_refresh_credentials(access_token)

        # Create boto3 session with temporary credentials
        return boto3.Session(
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken'],
        )

    def _get_or_refresh_credentials(self, access_token: str) -> Dict[str, Any]:
        """Get cached credentials or fetch new ones if expired.

        Args:
            access_token: JWT access token for authentication

        Returns:
            Dictionary with AWS credentials (AccessKeyId, SecretAccessKey,
            SessionToken, Expiration)
        """
        with self._credentials_lock:
            # Check if we have cached credentials that are still valid
            if self._cached_credentials and self._are_credentials_valid():
                return self._cached_credentials

            # Fetch new credentials
            self._cached_credentials = self._fetch_temporary_credentials(access_token)
            return self._cached_credentials

    def _are_credentials_valid(self) -> bool:
        """Check if cached credentials are still valid.

        Returns:
            True if credentials exist and haven't expired (with 5 minute buffer)
        """
        if not self._cached_credentials:
            return False

        expiration = self._cached_credentials.get('Expiration')
        if not expiration:
            return False

        # Parse expiration time (ISO 8601 format from AWS)
        if isinstance(expiration, str):
            expiration_dt = datetime.fromisoformat(expiration.replace('Z', '+00:00'))
        else:
            # Already a datetime object
            expiration_dt = expiration

        # Add 5 minute buffer before expiration
        now = datetime.now(timezone.utc)
        buffer_seconds = 300  # 5 minutes
        return (expiration_dt.timestamp() - now.timestamp()) > buffer_seconds

    def _fetch_temporary_credentials(self, access_token: str) -> Dict[str, Any]:
        """Exchange JWT token for temporary AWS credentials.

        Calls the /api/auth/get_credentials endpoint following the same
        pattern as the Quilt catalog and quilt3 library.

        Args:
            access_token: JWT access token

        Returns:
            Dictionary with AWS credentials

        Raises:
            JwtAuthServiceError: If credential exchange fails
        """
        import requests

        registry_url = os.getenv("QUILT_REGISTRY_URL")
        if not registry_url:
            raise JwtAuthServiceError("QUILT_REGISTRY_URL environment variable not configured", code="missing_config")

        endpoint = f"{registry_url.rstrip('/')}/api/auth/get_credentials"
        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            response = requests.get(endpoint, headers=headers, timeout=30)

            if response.status_code == 401:
                raise JwtAuthServiceError("JWT token invalid or expired. Please re-authenticate.", code="invalid_jwt")

            if response.status_code == 403:
                raise JwtAuthServiceError("Access denied. Check your permissions.", code="forbidden")

            response.raise_for_status()
            credentials = cast(Dict[str, Any], response.json())

            # Validate response has required fields
            required_fields = ['AccessKeyId', 'SecretAccessKey', 'SessionToken', 'Expiration']
            missing_fields = [f for f in required_fields if f not in credentials]
            if missing_fields:
                raise JwtAuthServiceError(
                    f"Invalid credential response: missing fields {missing_fields}", code="invalid_response"
                )

            return credentials

        except requests.exceptions.Timeout:
            raise JwtAuthServiceError("Timeout while fetching AWS credentials", code="timeout")
        except requests.exceptions.RequestException as exc:
            raise JwtAuthServiceError(f"Failed to fetch AWS credentials: {str(exc)}", code="request_failed") from exc

    def is_valid(self) -> bool:
        """
        Check if JWT token is present and has correct structure.

        Note: This does NOT validate signatures, expiration, or claims.
        The GraphQL backend will perform full validation.

        Returns:
            True if token exists and has valid JWT structure (3 dot-separated parts)
        """
        token = self._resolve_access_token()
        if not token:
            return False

        # Check JWT structure only (3 dot-separated parts)
        return token.count(".") == 2

    def get_user_identity(self) -> Dict[str, str | None]:
        """
        Extract user identity from JWT claims in runtime context.

        Note: This uses claims from the runtime context (populated by middleware
        or GraphQL response). It does NOT decode JWTs locally.

        Returns:
            Dictionary with user_id, email, and name (values may be None)
        """
        runtime_auth = get_runtime_auth()
        claims: Dict[str, Any] = {}
        if runtime_auth:
            claims = runtime_auth.claims or {}
        if not claims:
            token = self._resolve_access_token()
            if token:
                try:
                    import jwt as pyjwt

                    claims = cast(Dict[str, Any], pyjwt.decode(token, options={"verify_signature": False}))
                except Exception:
                    claims = {}

        user_id = claims.get("id") or claims.get("uuid")
        if not user_id:
            return {"user_id": None, "email": None, "name": None}

        return {
            "user_id": user_id,
            "email": claims.get("email"),
            "name": claims.get("name"),
        }
