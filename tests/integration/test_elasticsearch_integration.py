"""Tests for Elasticsearch backend dependency injection."""

from __future__ import annotations

import pytest
from unittest.mock import Mock, patch

from quilt_mcp.search.backends.elasticsearch import Quilt3ElasticsearchBackend
from quilt_mcp.services.quilt_service import QuiltService


class TestElasticsearchBackendDependencyInjection:
    """Test Elasticsearch backend dependency injection with QuiltService."""

    def test_elasticsearch_backend_accepts_quilt_service_dependency(self):
        """Test that Elasticsearch backend can accept QuiltService as dependency."""
        mock_quilt_service = Mock(spec=QuiltService)
        mock_quilt_service.get_registry_url.return_value = "s3://test-bucket"

        # This test will verify the service accepts the dependency
        backend = Quilt3ElasticsearchBackend(quilt_service=mock_quilt_service)

        # Verify the service was created with the dependency
        assert hasattr(backend, 'quilt_service')
        assert backend.quilt_service == mock_quilt_service

        # Verify the dependency was used in session check
        mock_quilt_service.get_registry_url.assert_called()

    def test_elasticsearch_backend_uses_quilt_service_for_bucket_creation(self):
        """Test that Elasticsearch backend uses QuiltService.create_bucket()."""
        mock_quilt_service = Mock(spec=QuiltService)
        mock_quilt_service.get_registry_url.return_value = "s3://test-bucket"

        mock_bucket = Mock()
        mock_bucket.search.return_value = []
        mock_quilt_service.create_bucket.return_value = mock_bucket

        backend = Quilt3ElasticsearchBackend(quilt_service=mock_quilt_service)

        # Mock async method call
        with patch('quilt_mcp.utils.suppress_stdout'):
            import asyncio

            async def test_search():
                # This triggers _search_bucket which should use QuiltService
                await backend._search_bucket("test query", "test-bucket", None, 10)

            # Run the async test
            asyncio.run(test_search())

        # Verify QuiltService was used instead of direct quilt3 calls
        mock_quilt_service.create_bucket.assert_called_once_with("s3://test-bucket")
        mock_bucket.search.assert_called_once()

    def test_elasticsearch_backend_uses_quilt_service_for_registry_url(self):
        """Test that Elasticsearch backend uses QuiltService.get_registry_url()."""
        mock_quilt_service = Mock(spec=QuiltService)
        mock_quilt_service.get_registry_url.return_value = "s3://test-registry"

        backend = Quilt3ElasticsearchBackend(quilt_service=mock_quilt_service)

        # Test health check which should use QuiltService
        import asyncio

        async def test_health():
            result = await backend.health_check()
            return result

        result = asyncio.run(test_health())

        # Verify QuiltService was used
        assert mock_quilt_service.get_registry_url.call_count >= 2  # Once in init, once in health_check
        assert result is True  # Health check should pass

    def test_elasticsearch_backend_backwards_compatible_without_quilt_service(self):
        """Test that Elasticsearch backend creates default QuiltService when none provided."""
        # This should create a default QuiltService instance
        with patch('quilt_mcp.search.backends.elasticsearch.QuiltService') as mock_service_class:
            mock_service_instance = Mock()
            mock_service_instance.get_registry_url.return_value = "s3://default-bucket"
            mock_service_class.return_value = mock_service_instance

            backend = Quilt3ElasticsearchBackend()

            # Should have created default QuiltService
            mock_service_class.assert_called_once()
            assert backend.quilt_service == mock_service_instance
