"""Browsing session client for Platform-backed content access."""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, Optional
from urllib.parse import quote

from quilt_mcp.ops.exceptions import AuthenticationError, BackendError, NotFoundError
from quilt_mcp.utils.common import normalize_url

if TYPE_CHECKING:
    import requests

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BrowsingSession:
    """Cached browsing session metadata."""

    session_id: str
    expires_at: float
    scope: str


class BrowsingSessionClient:
    """Client for Platform browsing session API with in-memory caching."""

    _cache_lock = threading.Lock()
    _cache: Dict[str, BrowsingSession] = {}

    def __init__(
        self,
        *,
        catalog_url: str,
        graphql_endpoint: str,
        access_token: str,
        session: Optional[requests.Session] = None,
        ttl_seconds: int = 180,
    ) -> None:
        if not catalog_url:
            raise BackendError("QUILT_CATALOG_URL is required for browsing sessions.")
        if not graphql_endpoint:
            raise BackendError("GraphQL endpoint is required for browsing sessions.")
        if not access_token:
            raise AuthenticationError("JWT access token is required for browsing sessions.")

        import requests

        self._catalog_url = normalize_url(catalog_url)
        self._graphql_endpoint = graphql_endpoint
        self._access_token = access_token
        self._ttl_seconds = max(30, int(ttl_seconds))
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def get_presigned_url(self, *, scope: str, path: str) -> str:
        """Return a presigned URL for the given browsing scope + path."""
        session = self._get_or_create_session(scope)
        return self._fetch_browse_url(session.session_id, path)

    def _get_or_create_session(self, scope: str) -> BrowsingSession:
        key = self._cache_key(scope)
        now = time.time()

        with self._cache_lock:
            cached = self._cache.get(key)
            if cached and cached.expires_at > now + 10:
                return cached

        session = self._create_session(scope)
        with self._cache_lock:
            self._cache[key] = session
        return session

    def _create_session(self, scope: str) -> BrowsingSession:
        mutation = """
        mutation BrowsingSessionCreate($scope: String!, $ttl: Int!) {
          browsingSessionCreate(scope: $scope, ttl: $ttl) {
            __typename
            ... on BrowsingSession {
              id
              expires
            }
            ... on InvalidInput {
              errors { path message name context }
            }
            ... on OperationError {
              message
              name
              context
            }
          }
        }
        """
        payload = {"query": mutation, "variables": {"scope": scope, "ttl": self._ttl_seconds}}

        try:
            response = self._session.post(self._graphql_endpoint, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
        except Exception as exc:
            raise BackendError(f"Browsing session creation failed: {exc}") from exc

        data = result.get("data", {}) if isinstance(result, dict) else {}
        session_data = data.get("browsingSessionCreate") or {}
        typename = session_data.get("__typename")
        if typename == "BrowsingSession":
            session_id = session_data.get("id")
            expires_raw = session_data.get("expires")
            if not session_id:
                raise BackendError("Browsing session response missing id.")
            expires_at = self._parse_expires(expires_raw)
            return BrowsingSession(session_id=session_id, expires_at=expires_at, scope=scope)

        if typename == "InvalidInput":
            errors = session_data.get("errors", [])
            message = "; ".join(err.get("message", "invalid input") for err in errors)
            raise BackendError(f"Browsing session invalid input: {message}")

        if typename == "OperationError":
            raise BackendError(session_data.get("message", "Browsing session creation failed"))

        raise BackendError("Unexpected browsing session response.")

    def _fetch_browse_url(self, session_id: str, path: str) -> str:
        cleaned_path = path.lstrip("/")
        encoded_path = quote(cleaned_path, safe="/")
        url = f"{self._catalog_url}/browse/{session_id}/{encoded_path}"

        try:
            response = self._session.get(url, allow_redirects=False, timeout=30)
        except Exception as exc:
            raise BackendError(f"Browsing session request failed: {exc}") from exc

        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location")
            if not location:
                raise BackendError("Browsing session redirect missing Location header.")
            return location

        if response.status_code == 404:
            raise NotFoundError("Browse path not found.")
        if response.status_code in {401, 403}:
            raise AuthenticationError("Browse request not authorized.")
        if response.ok:
            return response.url

        raise BackendError(f"Browsing session request failed: {response.status_code}")

    def _parse_expires(self, expires_raw: Optional[str]) -> float:
        if not expires_raw:
            return time.time() + self._ttl_seconds
        try:
            normalized = expires_raw.replace("Z", "+00:00")
            expires_dt = datetime.fromisoformat(normalized)
            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=timezone.utc)
            return expires_dt.timestamp()
        except Exception:
            return time.time() + self._ttl_seconds

    def _cache_key(self, scope: str) -> str:
        token_hash = hashlib.sha256(self._access_token.encode("utf-8")).hexdigest()
        return f"{token_hash}:{scope}"
