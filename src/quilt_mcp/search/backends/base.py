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
    description: str = ""
    url: Optional[str] = None
    s3_uri: Optional[str] = None
    package_name: Optional[str] = None
    logical_key: Optional[str] = None
    size: Optional[int] = None
    last_modified: Optional[str] = None
    metadata: Dict[str, Any] | None = None
    score: float = 0.0
    backend: str = ""
    # New fields for simplified search API
    name: str = ""
    bucket: Optional[str] = None
    content_type: Optional[str] = None
    extension: Optional[str] = None
    content_preview: Optional[str] = None

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
        self._initialized = False

    @property
    def status(self) -> BackendStatus:
        """Get current backend status."""
        return self._status

    @property
    def last_error(self) -> Optional[str]:
        """Get last error message."""
        return self._last_error

    @property
    def initialized(self) -> bool:
        """Check if backend has been initialized."""
        return self._initialized

    def ensure_initialized(self):
        """Ensure backend is initialized before use.

        This method performs lazy initialization, deferring authentication checks
        and resource allocation until the backend is actually needed.
        Subclasses should override _initialize() to implement their specific
        initialization logic.
        """
        if not self._initialized:
            self._initialize()
            self._initialized = True

    @abstractmethod
    def _initialize(self):
        """Initialize backend resources and check availability.

        This method is called by ensure_initialized() on first use.
        Subclasses must implement this to perform authentication checks,
        resource setup, and availability verification.

        Should update status and set error messages appropriately.
        """
        pass

    async def refresh_status(self) -> bool:
        """Re-check backend availability and update status.

        This method allows re-evaluation of backend availability without
        full reinitialization. Useful for recovering from transient failures.

        Returns:
            True if backend is available, False otherwise
        """
        return await self.health_check()

    @abstractmethod
    async def search(
        self,
        query: str,
        scope: str = "global",
        bucket: str = "",
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
    ) -> BackendResponse:
        """Execute a search query.

        Args:
            query: Search query string
            scope: Search scope (global, package, file)
            bucket: S3 bucket to search in (empty = all buckets)
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
            backend = self.get_backend(backend_type)
            if backend:
                # Ensure backend is initialized when accessed by name
                backend.ensure_initialized()
            return backend
        except ValueError:
            return None

    def _select_primary_backend(self) -> Optional[SearchBackend]:
        """Select single primary backend based on availability and preference.

        Selection priority:
        1. GraphQL (Enterprise features) - if available
        2. Elasticsearch (Standard) - if available
        3. None - if no backends available

        Returns:
            The selected backend, or None if no backends available
        """
        # Prefer GraphQL if available (Enterprise features)
        graphql_backend = self.get_backend(BackendType.GRAPHQL)
        if graphql_backend:
            # Ensure backend is initialized before checking availability
            graphql_backend.ensure_initialized()
            if graphql_backend.status == BackendStatus.AVAILABLE:
                return graphql_backend

        # Fallback to Elasticsearch (standard)
        elasticsearch_backend = self.get_backend(BackendType.ELASTICSEARCH)
        if elasticsearch_backend:
            # Ensure backend is initialized before checking availability
            elasticsearch_backend.ensure_initialized()
            if elasticsearch_backend.status == BackendStatus.AVAILABLE:
                return elasticsearch_backend

        # No backends available
        return None

    def get_backend_statuses(self) -> Dict[str, str]:
        """Get status of all registered backends.

        Returns:
            Dictionary mapping backend names to status strings
        """
        return {backend.backend_type.value: backend.status.value for backend in self._backends.values()}

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
