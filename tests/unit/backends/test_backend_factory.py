"""Tests for backend factory function.

This test module validates that the factory function correctly selects and
instantiates backend implementations based on environment configuration.
"""

import os
import pytest
from unittest.mock import patch, Mock
import time


class TestFactoryBasicFunctionality:
    """Test basic factory function behavior."""

    def test_factory_module_exists(self):
        """Test that factory module exists and is importable."""
        from quilt_mcp.backends import factory

        assert factory is not None

    def test_get_backend_function_exists(self):
        """Test that get_backend function is defined."""
        from quilt_mcp.backends.factory import get_backend

        assert get_backend is not None
        assert callable(get_backend)

    def test_get_backend_returns_backend_instance(self):
        """Test that get_backend returns a backend instance."""
        from quilt_mcp.backends.factory import get_backend

        backend = get_backend()
        assert backend is not None


class TestDefaultBackendSelection:
    """Test default backend selection (no env var set)."""

    def test_default_returns_quilt3_backend(self):
        """Test that default behavior returns Quilt3Backend."""
        from quilt_mcp.backends.factory import get_backend
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        # Ensure QUILT_BACKEND is not set
        with patch.dict(os.environ, {}, clear=True):
            backend = get_backend()
            assert isinstance(backend, Quilt3Backend)

    def test_default_logs_backend_selection(self, caplog):
        """Test that default backend selection is logged."""
        from quilt_mcp.backends.factory import get_backend

        with patch.dict(os.environ, {}, clear=True):
            with caplog.at_level('INFO'):
                backend = get_backend()
                assert any('quilt3' in record.message.lower() for record in caplog.records)


class TestExplicitQuilt3Selection:
    """Test explicit quilt3 backend selection via env var."""

    def test_explicit_quilt3_returns_quilt3_backend(self):
        """Test that QUILT_BACKEND=quilt3 returns Quilt3Backend."""
        from quilt_mcp.backends.factory import get_backend
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        with patch.dict(os.environ, {'QUILT_BACKEND': 'quilt3'}):
            backend = get_backend()
            assert isinstance(backend, Quilt3Backend)

    def test_quilt3_selection_logs(self, caplog):
        """Test that quilt3 selection is logged."""
        from quilt_mcp.backends.factory import get_backend

        with patch.dict(os.environ, {'QUILT_BACKEND': 'quilt3'}):
            with caplog.at_level('INFO'):
                backend = get_backend()
                assert any('quilt3' in record.message.lower() for record in caplog.records)

    def test_quilt3_selection_case_insensitive(self):
        """Test that backend selection is case insensitive."""
        from quilt_mcp.backends.factory import get_backend
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        for variant in ['quilt3', 'QUILT3', 'Quilt3', 'QuIlT3']:
            with patch.dict(os.environ, {'QUILT_BACKEND': variant}):
                backend = get_backend()
                assert isinstance(backend, Quilt3Backend)


class TestGraphQLBackendSelection:
    """Test GraphQL backend selection (not yet implemented)."""

    def test_graphql_raises_not_implemented(self):
        """Test that QUILT_BACKEND=graphql raises NotImplementedError."""
        from quilt_mcp.backends.factory import get_backend

        with patch.dict(os.environ, {'QUILT_BACKEND': 'graphql'}):
            with pytest.raises(NotImplementedError) as exc_info:
                get_backend()
            assert 'graphql' in str(exc_info.value).lower()
            assert 'not yet implemented' in str(exc_info.value).lower()


class TestInvalidBackendSelection:
    """Test handling of invalid backend types."""

    def test_unknown_backend_raises_value_error(self):
        """Test that unknown backend type raises ValueError."""
        from quilt_mcp.backends.factory import get_backend

        with patch.dict(os.environ, {'QUILT_BACKEND': 'unknown'}):
            with pytest.raises(ValueError) as exc_info:
                get_backend()
            assert 'unknown' in str(exc_info.value).lower()

    def test_invalid_backend_error_message_includes_valid_options(self):
        """Test that error message includes valid backend options."""
        from quilt_mcp.backends.factory import get_backend

        with patch.dict(os.environ, {'QUILT_BACKEND': 'invalid'}):
            with pytest.raises(ValueError) as exc_info:
                get_backend()
            error_message = str(exc_info.value).lower()
            assert 'quilt3' in error_message
            assert 'graphql' in error_message


class TestFactoryPerformance:
    """Test factory performance characteristics."""

    def test_factory_performance_fast(self):
        """Test that factory overhead is <1ms."""
        from quilt_mcp.backends.factory import get_backend

        with patch.dict(os.environ, {}, clear=True):
            # Warm up
            backend = get_backend()

            # Measure
            start = time.perf_counter()
            for _ in range(100):
                backend = get_backend()
            elapsed = time.perf_counter() - start

            # Average should be <1ms per call
            avg_ms = (elapsed / 100) * 1000
            assert avg_ms < 1.0, f"Factory overhead {avg_ms:.2f}ms exceeds 1ms threshold"


class TestFactoryBackendInterface:
    """Test that factory-created backends implement the protocol."""

    def test_factory_backend_implements_protocol(self):
        """Test that get_backend() returns object implementing QuiltBackend."""
        from quilt_mcp.backends.factory import get_backend
        from quilt_mcp.backends.protocol import QuiltBackend

        backend = get_backend()
        assert isinstance(backend, QuiltBackend)

    def test_factory_backend_has_required_methods(self):
        """Test that factory-created backend has all required methods."""
        from quilt_mcp.backends.factory import get_backend

        backend = get_backend()

        # Check key methods exist
        required_methods = [
            'is_authenticated',
            'list_packages',
            'browse_package',
            'create_package_revision',
            'get_catalog_info',
            'create_bucket',
            'get_search_api',
            'is_admin_available',
        ]

        for method_name in required_methods:
            assert hasattr(backend, method_name), f"Missing method: {method_name}"
            assert callable(getattr(backend, method_name)), f"{method_name} is not callable"
