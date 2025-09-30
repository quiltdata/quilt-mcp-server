"""Session-based JWT authentication for MCP server.

Instead of validating JWT on every request, we:
1. Validate JWT once when session is established
2. Cache the auth result by MCP session ID
3. Reuse cached auth for all requests in that session
4. Expire sessions after timeout or when JWT expires
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import boto3

from quilt_mcp.services.bearer_auth_service import JwtAuthResult, JwtAuthError, get_bearer_auth_service

logger = logging.getLogger(__name__)


@dataclass
class SessionAuth:
    """Cached authentication for an MCP session."""
    
    session_id: str
    jwt_result: JwtAuthResult
    boto3_session: boto3.Session
    created_at: float
    last_used: float
    
    def is_expired(self, max_age: int = 3600) -> bool:
        """Check if session has expired."""
        return (time.time() - self.created_at) > max_age
    
    def touch(self) -> None:
        """Update last used timestamp."""
        self.last_used = time.time()


class SessionAuthManager:
    """Manages session-based JWT authentication."""
    
    def __init__(self, session_timeout: int = 3600):
        """Initialize the session auth manager.
        
        Args:
            session_timeout: Session timeout in seconds (default: 1 hour)
        """
        self._sessions: Dict[str, SessionAuth] = {}
        self._session_timeout = session_timeout
        
    def authenticate_session(
        self,
        session_id: str,
        authorization_header: str | None
    ) -> tuple[Optional[SessionAuth], Optional[str]]:
        """Authenticate a session using JWT.
        
        Args:
            session_id: MCP session ID
            authorization_header: Authorization header value
            
        Returns:
            Tuple of (SessionAuth, error_message)
            If successful: (SessionAuth, None)
            If failed: (None, error_message)
        """
        # Check if we have a cached valid session
        if session_id in self._sessions:
            cached = self._sessions[session_id]
            
            # Check if session is expired
            if cached.is_expired(self._session_timeout):
                logger.info("Session %s expired, removing from cache", session_id)
                del self._sessions[session_id]
            else:
                # Session is valid, update last used and return
                cached.touch()
                logger.debug("Reusing cached auth for session %s", session_id)
                return cached, None
        
        # No cached session or expired, validate JWT
        if not authorization_header:
            return None, "Missing Authorization header"
        
        bearer_service = get_bearer_auth_service()
        
        try:
            jwt_result = bearer_service.authenticate_header(authorization_header)
            logger.info(
                "Session %s: JWT authenticated for user %s (buckets=%d, permissions=%d)",
                session_id,
                jwt_result.username or jwt_result.user_id,
                len(jwt_result.buckets),
                len(jwt_result.permissions)
            )
            
            # Build boto3 session from JWT
            boto3_session = bearer_service.build_boto3_session(jwt_result)
            
            # Cache the session
            session_auth = SessionAuth(
                session_id=session_id,
                jwt_result=jwt_result,
                boto3_session=boto3_session,
                created_at=time.time(),
                last_used=time.time()
            )
            
            self._sessions[session_id] = session_auth
            logger.info("Cached auth for session %s", session_id)
            
            return session_auth, None
            
        except JwtAuthError as exc:
            logger.error("JWT authentication failed for session %s: %s", session_id, exc.detail)
            return None, exc.detail
        except Exception as exc:
            logger.error("Unexpected error authenticating session %s: %s", session_id, exc)
            return None, str(exc)
    
    def get_session(self, session_id: str) -> Optional[SessionAuth]:
        """Get cached session auth.
        
        Args:
            session_id: MCP session ID
            
        Returns:
            SessionAuth if cached and valid, None otherwise
        """
        if session_id in self._sessions:
            session = self._sessions[session_id]
            if not session.is_expired(self._session_timeout):
                session.touch()
                return session
            else:
                # Remove expired session
                del self._sessions[session_id]
        return None
    
    def invalidate_session(self, session_id: str) -> None:
        """Invalidate a session.
        
        Args:
            session_id: MCP session ID
        """
        if session_id in self._sessions:
            logger.info("Invalidating session %s", session_id)
            del self._sessions[session_id]
    
    def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions from cache.
        
        Returns:
            Number of sessions removed
        """
        expired = [
            sid for sid, session in self._sessions.items()
            if session.is_expired(self._session_timeout)
        ]
        
        for sid in expired:
            del self._sessions[sid]
        
        if expired:
            logger.info("Cleaned up %d expired sessions", len(expired))
        
        return len(expired)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get session cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        return {
            "total_sessions": len(self._sessions),
            "session_ids": list(self._sessions.keys()),
            "session_timeout": self._session_timeout,
        }


# Global session manager instance
_session_manager: Optional[SessionAuthManager] = None


def get_session_auth_manager() -> SessionAuthManager:
    """Get the global session auth manager.
    
    Returns:
        SessionAuthManager instance
    """
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionAuthManager()
    return _session_manager
