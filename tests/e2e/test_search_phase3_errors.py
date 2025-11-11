"""Tests for Phase 3 search error handling."""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from quilt_mcp.search.exceptions import (
    ErrorCategory,
    SearchException,
    AuthenticationRequired,
    SearchNotAvailable,
    BackendError,
    InvalidQueryError,
)
from quilt_mcp.search.backends.base import BackendStatus, BackendType
from quilt_mcp.search.backends.elasticsearch import Quilt3ElasticsearchBackend
from quilt_mcp.search.tools.unified_search import unified_search


class TestSearchExceptions:
    """Test cases for search exception classes."""

    def test_authentication_required_structure(self):
        """Test AuthenticationRequired exception structure."""
        exc = AuthenticationRequired()

        response = exc.to_response()

        assert response["success"] is False
        assert response["error_category"] == "authentication"
        assert "authentication" in response["error"].lower()
        assert "details" in response
        assert response["details"]["authenticated"] is False
        assert "fix" in response
        assert "quilt3.login()" in response["fix"].get("command", "")
        assert "alternatives" in response
        assert "bucket_objects_list" in response["alternatives"]

    def test_search_not_available_structure(self):
        """Test SearchNotAvailable exception structure."""
        backend_statuses = {"elasticsearch": "unavailable", "graphql": "error"}
        exc = SearchNotAvailable(backend_statuses=backend_statuses)

        response = exc.to_response()

        assert response["success"] is False
        assert response["error_category"] == "not_applicable"
        assert "not available" in response["error"].lower()
        assert response["details"]["authenticated"] is True
        assert "elasticsearch: unavailable" in response["details"]["cause"]
        assert "graphql: error" in response["details"]["cause"]
        assert "alternatives" in response
        assert "bucket_objects_list" in response["alternatives"]

    def test_backend_error_structure(self):
        """Test BackendError exception structure."""
        exc = BackendError(
            backend_name="elasticsearch",
            cause="Connection timeout",
            authenticated=True,
            catalog_url="https://example.com",
        )

        response = exc.to_response()

        assert response["success"] is False
        assert response["error_category"] == "backend_error"
        assert "elasticsearch" in response["error"]
        assert "Connection timeout" in response["details"]["cause"]
        assert response["details"]["authenticated"] is True
        assert response["details"]["catalog_url"] == "https://example.com"

    def test_invalid_query_error_structure(self):
        """Test InvalidQueryError exception structure."""
        exc = InvalidQueryError(
            query="bad{query",
            cause="Malformed Elasticsearch query syntax",
        )

        response = exc.to_response()

        assert response["success"] is False
        assert response["error_category"] == "invalid_input"
        assert "bad{query" in response["error"]
        assert "Malformed" in response["details"]["cause"]


class TestErrorHandlingIntegration:
    """Test error handling in unified search integration.

    Note: These are structural tests to verify error handling code paths exist.
    Full integration tests would require proper quilt3 session setup.
    """

    def test_authentication_error_structure_in_backend(self):
        """Test that Elasticsearch backend stores authentication errors properly."""
        with patch("quilt_mcp.search.backends.elasticsearch.QuiltService") as mock_service:
            # Mock no session available
            mock_service.return_value.get_registry_url.return_value = None

            backend = Quilt3ElasticsearchBackend()

            # Verify backend is unavailable and has auth error
            assert backend.status == BackendStatus.UNAVAILABLE
            assert hasattr(backend, "_auth_error")
            assert isinstance(backend._auth_error, AuthenticationRequired)

    def test_backend_error_handling_structure(self):
        """Test that BackendError structure is properly defined."""
        # This tests the error structure without requiring full backend setup
        error = BackendError(
            backend_name="test_backend",
            cause="Test error",
            authenticated=True,
        )

        response = error.to_response()

        assert response["success"] is False
        assert response["error_category"] == "backend_error"
        assert "test_backend" in response["error"]
        assert response["details"]["cause"] == "Test error"

    def test_search_not_available_structure_complete(self):
        """Test SearchNotAvailable exception with backend statuses."""
        backend_statuses = {
            "elasticsearch": "unavailable",
            "graphql": "error",
        }

        error = SearchNotAvailable(
            authenticated=True,
            catalog_url="https://test.example.com",
            cause="No backends available",
            backend_statuses=backend_statuses,
        )

        response = error.to_response()

        assert response["success"] is False
        assert response["error_category"] == "not_applicable"
        assert response["details"]["authenticated"] is True
        assert response["details"]["catalog_url"] == "https://test.example.com"
        assert "elasticsearch: unavailable" in response["details"]["cause"]
        assert "graphql: error" in response["details"]["cause"]
        assert "bucket_objects_list" in response["alternatives"]


class TestErrorCategoryEnum:
    """Test ErrorCategory enum."""

    def test_error_categories_defined(self):
        """Test that all error categories are properly defined."""
        categories = [
            ErrorCategory.AUTHENTICATION,
            ErrorCategory.AUTHORIZATION,
            ErrorCategory.NOT_APPLICABLE,
            ErrorCategory.CONFIGURATION,
            ErrorCategory.BACKEND_ERROR,
            ErrorCategory.INVALID_INPUT,
            ErrorCategory.TIMEOUT,
            ErrorCategory.NETWORK,
        ]

        # Verify all categories have string values
        for category in categories:
            assert isinstance(category.value, str)
            assert len(category.value) > 0

    def test_error_category_values(self):
        """Test specific error category values."""
        assert ErrorCategory.AUTHENTICATION.value == "authentication"
        assert ErrorCategory.NOT_APPLICABLE.value == "not_applicable"
        assert ErrorCategory.BACKEND_ERROR.value == "backend_error"


class TestErrorResponseSchema:
    """Test that error responses match the specification schema."""

    def test_error_response_has_required_fields(self):
        """Test that error responses contain all required fields per spec."""
        exc = AuthenticationRequired()
        response = exc.to_response()

        # Required top-level fields
        assert "success" in response
        assert "error" in response
        assert "error_category" in response
        assert "details" in response
        assert "fix" in response
        assert "alternatives" in response

        # Required detail fields
        assert "cause" in response["details"]
        assert "authenticated" in response["details"]
        assert "catalog_url" in response["details"]

        # Required fix fields
        assert "required_action" in response["fix"]

        # Optional fix fields (may or may not be present)
        # command and documentation are optional

    def test_alternatives_format(self):
        """Test that alternatives field has correct format."""
        exc = SearchNotAvailable()
        response = exc.to_response()

        alternatives = response["alternatives"]
        assert isinstance(alternatives, dict)
        assert len(alternatives) > 0

        # Each alternative should have a string description
        for tool_name, description in alternatives.items():
            assert isinstance(tool_name, str)
            assert isinstance(description, str)
            assert len(description) > 0
