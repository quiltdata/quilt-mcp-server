"""JWT decoding and validation utilities for Quilt MCP server."""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import boto3
import jwt

logger = logging.getLogger(__name__)


SOFT_REFRESH_SECONDS = 300
HARD_TTL_SECONDS = 3600


class JwtConfigError(RuntimeError):
    """Raised when JWT configuration is invalid."""


class JwtDecodeError(RuntimeError):
    """Raised when JWT validation fails."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass
class _SecretCache:
    value: str
    source: str
    loaded_at: float
    refreshed_at: float


class JwtSecretProvider:
    """Resolve JWT secrets with SSM caching and rotation support."""

    def __init__(self) -> None:
        self._cache: Optional[_SecretCache] = None
        self._previous: Optional[_SecretCache] = None
        self._lock = threading.Lock()

    def validate_config(self) -> None:
        """Validate configuration for JWT secrets."""
        env_secret = os.getenv("MCP_JWT_SECRET")
        ssm_param = os.getenv("MCP_JWT_SECRET_SSM_PARAMETER")

        if env_secret:
            return

        if not ssm_param:
            raise JwtConfigError("JWT mode requires MCP_JWT_SECRET or MCP_JWT_SECRET_SSM_PARAMETER to be set.")

        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        if not region:
            raise JwtConfigError("MCP_JWT_SECRET_SSM_PARAMETER is set but AWS_REGION/AWS_DEFAULT_REGION is missing.")

    def get_secret(self, *, force_refresh: bool = False) -> Tuple[str, str]:
        """Return the active secret and its source."""
        env_secret = os.getenv("MCP_JWT_SECRET")
        if env_secret:
            return env_secret, "env:MCP_JWT_SECRET"

        parameter_name = os.getenv("MCP_JWT_SECRET_SSM_PARAMETER")
        if not parameter_name:
            raise JwtConfigError("JWT secret is missing; set MCP_JWT_SECRET or MCP_JWT_SECRET_SSM_PARAMETER.")

        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        if not region:
            raise JwtConfigError("MCP_JWT_SECRET_SSM_PARAMETER is set but AWS_REGION/AWS_DEFAULT_REGION is missing.")

        now = time.time()
        with self._lock:
            cache = self._cache
            if cache and not force_refresh:
                age = now - cache.loaded_at
                since_refresh = now - cache.refreshed_at
                if age < HARD_TTL_SECONDS and since_refresh < SOFT_REFRESH_SECONDS:
                    return cache.value, cache.source

            secret = self._fetch_secret_from_ssm(parameter_name, region)
            if secret:
                self._previous = self._cache
                self._cache = _SecretCache(
                    value=secret,
                    source=f"ssm:{parameter_name}:{region}",
                    loaded_at=now,
                    refreshed_at=now,
                )
                return secret, self._cache.source

            if cache and (now - cache.loaded_at) < HARD_TTL_SECONDS:
                logger.warning(
                    "Using cached JWT secret after failed refresh from SSM (parameter=%s).",
                    parameter_name,
                )
                cache.refreshed_at = now
                return cache.value, cache.source

        raise JwtConfigError("Unable to load JWT secret from SSM.")

    def get_previous_secret(self) -> Optional[Tuple[str, str]]:
        """Return the previous cached secret if still valid."""
        previous = self._previous
        if not previous:
            return None
        if time.time() - previous.loaded_at > HARD_TTL_SECONDS:
            return None
        return previous.value, previous.source

    def _fetch_secret_from_ssm(self, parameter_name: str, region: str) -> Optional[str]:
        try:
            client = boto3.client("ssm", region_name=region)
            response = client.get_parameter(Name=parameter_name, WithDecryption=True)
            value = response.get("Parameter", {}).get("Value")
            if isinstance(value, str) and value:
                return value
            logger.error("SSM parameter %s did not return a secret value.", parameter_name)
        except Exception as exc:  # pragma: no cover - diagnostic aid
            logger.error("Error retrieving JWT secret from SSM parameter %s: %s", parameter_name, exc)
        return None


class JwtDecoder:
    """Decode and validate JWTs using HS256."""

    def __init__(self) -> None:
        self._secret_provider = JwtSecretProvider()

    def validate_config(self) -> None:
        self._secret_provider.validate_config()

    def decode(self, token: str) -> Dict[str, Any]:
        """Decode and validate a JWT token."""
        if not token:
            raise JwtDecodeError("missing_token", "JWT token is required.")

        if token.count(".") != 2:
            raise JwtDecodeError("invalid_token", "JWT token is malformed.")

        issuer = os.getenv("MCP_JWT_ISSUER")
        audience = os.getenv("MCP_JWT_AUDIENCE")
        secret, source = self._secret_provider.get_secret()

        options = {
            "require": ["exp"],
            "verify_aud": bool(audience),
            "verify_iss": bool(issuer),
        }

        try:
            claims = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience=audience,
                issuer=issuer,
                options=options,
            )
        except jwt.ExpiredSignatureError as exc:
            raise JwtDecodeError("token_expired", "JWT token expired.") from exc
        except jwt.InvalidIssuerError as exc:
            raise JwtDecodeError("invalid_issuer", "JWT issuer did not match expected issuer.") from exc
        except jwt.InvalidAudienceError as exc:
            raise JwtDecodeError("invalid_audience", "JWT audience did not match expected audience.") from exc
        except jwt.InvalidSignatureError as exc:
            retry_claims = self._retry_with_previous_secret(token, issuer, audience, options)
            if retry_claims is not None:
                return retry_claims
            raise JwtDecodeError("invalid_signature", "JWT signature validation failed.") from exc
        except jwt.DecodeError as exc:
            raise JwtDecodeError("invalid_token", "JWT token is malformed.") from exc
        except jwt.InvalidTokenError as exc:
            raise JwtDecodeError("invalid_token", "JWT token could not be verified.") from exc

        if not isinstance(claims, dict):
            raise JwtDecodeError("invalid_claims", "JWT claims must be a JSON object.")

        allowed_keys = {"id", "uuid", "exp"}
        if not (claims.get("id") or claims.get("uuid")):
            raise JwtDecodeError("invalid_claims", "JWT claims must include id or uuid.")
        extra_keys = set(claims.keys()) - allowed_keys
        if extra_keys:
            raise JwtDecodeError(
                "invalid_claims",
                f"JWT claims include unsupported fields: {sorted(extra_keys)}.",
            )

        if source.startswith("ssm:"):
            logger.debug("JWT decoded successfully using secret source %s", source)
        return claims

    def _retry_with_previous_secret(
        self,
        token: str,
        issuer: Optional[str],
        audience: Optional[str],
        options: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        previous = self._secret_provider.get_previous_secret()
        if previous:
            secret, _source = previous
            try:
                decoded = jwt.decode(
                    token,
                    secret,
                    algorithms=["HS256"],
                    audience=audience,
                    issuer=issuer,
                    options=options,
                )
                if isinstance(decoded, dict):
                    return decoded
            except jwt.InvalidTokenError:
                pass

        try:
            secret, _source = self._secret_provider.get_secret(force_refresh=True)
        except JwtConfigError:
            return None

        try:
            decoded = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience=audience,
                issuer=issuer,
                options=options,
            )
            if isinstance(decoded, dict):
                return decoded
        except jwt.InvalidTokenError:
            return None

        return None


_DECODER_INSTANCE: Optional[JwtDecoder] = None


def get_jwt_decoder() -> JwtDecoder:
    """Return a shared JwtDecoder instance."""
    global _DECODER_INSTANCE
    if _DECODER_INSTANCE is None:
        _DECODER_INSTANCE = JwtDecoder()
    return _DECODER_INSTANCE
