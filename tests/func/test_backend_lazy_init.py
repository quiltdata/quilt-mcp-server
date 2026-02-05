"""Test that backend status properly handles lazy initialization.

This test validates the fix for the issue where get_search_backend_status()
was checking backend availability before backends were initialized, causing
them to appear as unavailable even when authentication was valid.
"""

import pytest
from quilt_mcp.search.utils.backend_status import get_search_backend_status
from quilt_mcp.search.backends.base import BackendStatus


class TestBackendLazyInitialization:
    """Test backend lazy initialization behavior."""

    def test_backend_status_initializes_backends(self):
        """Test that get_search_backend_status() properly initializes backends.

        This test verifies that when get_search_backend_status() is called,
        it ensures all backends are initialized before checking their status.
        This fixes the issue where backends appeared unavailable because they
        weren't initialized yet.
        """
        status = get_search_backend_status()

        # Should have overall status
        assert "available" in status
        assert "backend" in status
        assert "status" in status
        assert "backends" in status

        # Should have detailed backend info
        assert "elasticsearch" in status["backends"]

        # Check Elasticsearch backend status
        es_status = status["backends"]["elasticsearch"]

        # Check that backend has been initialized (not showing as "not_registered")
        assert es_status["status"] != "not_registered"

        # When authenticated, backend should be available
        if status["available"]:
            # Primary backend should be set
            assert status["backend"] is not None
            assert status["status"] == "ready"

            # Elasticsearch should be available
            assert es_status["available"]

            # Available backend should have capabilities
            if es_status["available"]:
                assert len(es_status["capabilities"]) > 0

    def test_backend_status_called_twice_consistency(self):
        """Test that calling get_search_backend_status() twice gives consistent results.

        This validates that the lazy initialization doesn't cause inconsistent
        results between calls.
        """
        status1 = get_search_backend_status()
        status2 = get_search_backend_status()

        # Results should be consistent
        assert status1["available"] == status2["available"]
        assert status1["backend"] == status2["backend"]
        assert status1["status"] == status2["status"]

        # Backend details should match
        assert status1["backends"]["elasticsearch"]["available"] == status2["backends"]["elasticsearch"]["available"]

    def test_backend_initialization_sets_status_correctly(self):
        """Test that backend initialization properly sets availability status.

        This verifies that after initialization, backends report their true
        availability based on authentication and configuration.
        """
        status = get_search_backend_status()

        # Check Elasticsearch backend status
        backend_info = status["backends"]["elasticsearch"]

        # Status should be one of the valid values
        assert backend_info["status"] in [
            "available",
            "unavailable",
            "error",
            "timeout",
        ]

        # If available, should have capabilities
        if backend_info["available"]:
            assert isinstance(backend_info["capabilities"], list)
            assert len(backend_info["capabilities"]) > 0
            assert backend_info["status"] == "available"

        # If not available, capabilities should be empty
        if not backend_info["available"]:
            assert backend_info["capabilities"] == []
