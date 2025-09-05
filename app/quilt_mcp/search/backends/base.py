"""Base backend interface for unified search.

This module defines the abstract interface that all search backends must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Union
from enum import Enum


class BackendType(Enum):
    """Types of search backends."""

    ELASTICSEARCH = "elasticsearch"
    GRAPHQL = "graphql"
    S3 = "s3"


class BackendStatus(Enum):
    """Backend availability status."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class SearchResult:
    """Standardized search result structure."""

    id: str
    type: str  # 'file', 'package', 'object'
    title: str
    description: Optional[str] = None
    url: Optional[str] = None
    s3_uri: Optional[str] = None
    package_name: Optional[str] = None
    logical_key: Optional[str] = None
    size: Optional[int] = None
    last_modified: Optional[str] = None
    metadata: Dict[str, Any] = None
    score: float = 0.0
    backend: str = ""

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class BackendResponse:
    """Response from a search backend."""

    backend_type: BackendType
    status: BackendStatus
    results: List[SearchResult]
    total: Optional[int] = None
    query_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.results is None:
            self.results = []


class SearchBackend(ABC):
    """Abstract base class for search backends."""

    def __init__(self, backend_type: BackendType):
        self.backend_type = backend_type
        self._status = BackendStatus.UNAVAILABLE
        self._last_error: Optional[str] = None

    @property
    def status(self) -> BackendStatus:
        """Get current backend status."""
        return self._status

    @property
    def last_error(self) -> Optional[str]:
        """Get last error message."""
        return self._last_error

    @abstractmethod
    async def search(
        self,
        query: str,
        scope: str = "global",
        target: str = "",
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
    ) -> BackendResponse:
        """Execute a search query.

        Args:
            query: Search query string
            scope: Search scope (global, catalog, package, bucket)
            target: Specific target when scope is narrow
            filters: Additional filters to apply
            limit: Maximum number of results

        Returns:
            BackendResponse with results and metadata
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the backend is available and healthy.

        Returns:
            True if backend is available, False otherwise
        """
        pass

    def _update_status(self, status: BackendStatus, error: Optional[str] = None):
        """Update backend status and error state."""
        self._status = status
        self._last_error = error

    def _normalize_query_for_backend(
        self, query: str, filters: Optional[Dict[str, Any]] = None
    ) -> Union[str, Dict[str, Any]]:
        """Normalize query for this specific backend.

        Subclasses should override this to convert the generic query
        into backend-specific format (e.g., Elasticsearch DSL, GraphQL variables).
        """
        return query

    def _convert_to_standard_results(self, raw_results: Any) -> List[SearchResult]:
        """Convert backend-specific results to standardized format.

        Subclasses must implement this to convert their native result format
        to the standard SearchResult format.
        """
        return []


class BackendRegistry:
    """Registry for managing search backends."""

    def __init__(self):
        self._backends: Dict[BackendType, SearchBackend] = {}

    def register(self, backend: SearchBackend):
        """Register a search backend."""
        self._backends[backend.backend_type] = backend

    def get_backend(self, backend_type: BackendType) -> Optional[SearchBackend]:
        """Get a backend by type."""
        return self._backends.get(backend_type)

    def get_available_backends(self) -> List[SearchBackend]:
        """Get all available backends."""
        return [backend for backend in self._backends.values() if backend.status == BackendStatus.AVAILABLE]

    def get_backend_by_name(self, name: str) -> Optional[SearchBackend]:
        """Get a backend by string name."""
        try:
            backend_type = BackendType(name.lower())
            return self.get_backend(backend_type)
        except ValueError:
            return None

    async def health_check_all(self) -> Dict[BackendType, bool]:
        """Run health checks on all registered backends."""
        results = {}
        for backend_type, backend in self._backends.items():
            try:
                is_healthy = await backend.health_check()
                results[backend_type] = is_healthy
            except Exception:
                results[backend_type] = False
        return results
