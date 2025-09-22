"""
Test that validates functions are removed during consolidation.

These tests will fail when the legacy functions are removed,
confirming that the consolidation is complete.
"""

import pytest


class TestFunctionRemovalValidation:
    """Tests that verify legacy functions are removed."""

    def test_packages_search_should_not_exist(self):
        """Given packages_search function should be removed
        When attempting to import it
        Then it should not be available
        """
        # This test will pass once the function is removed
        with pytest.raises(ImportError):
            from quilt_mcp.tools.packages import packages_search

    def test_bucket_objects_search_should_not_exist(self):
        """Given bucket_objects_search function should be removed
        When attempting to import it
        Then it should not be available
        """
        # This test will pass once the function is removed
        with pytest.raises(ImportError):
            from quilt_mcp.tools.buckets import bucket_objects_search

    def test_bucket_objects_search_graphql_should_not_exist(self):
        """Given bucket_objects_search_graphql function should be removed
        When attempting to import it
        Then it should not be available
        """
        # This test will pass once the function is removed
        with pytest.raises(ImportError):
            from quilt_mcp.tools.buckets import bucket_objects_search_graphql

    def test_catalog_search_still_exists(self):
        """Given catalog_search should remain after consolidation
        When attempting to import it
        Then it should be available
        """
        try:
            from quilt_mcp.tools.search import catalog_search
            assert callable(catalog_search)
        except ImportError:
            pytest.fail("catalog_search should still be available after consolidation")