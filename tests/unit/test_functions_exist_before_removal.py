"""
Test that confirms legacy functions exist before removal.

These tests should pass before consolidation and fail after removal.
This confirms the functions are actually present before we remove them.
"""

import pytest


class TestLegacyFunctionsExistBeforeRemoval:
    """Test that legacy functions are currently available."""

    def test_packages_search_currently_exists(self):
        """Given packages_search function currently exists
        When attempting to import it
        Then it should be available and callable
        """
        from quilt_mcp.tools.packages import packages_search
        assert callable(packages_search)

    def test_bucket_objects_search_currently_exists(self):
        """Given bucket_objects_search function currently exists
        When attempting to import it
        Then it should be available and callable
        """
        from quilt_mcp.tools.buckets import bucket_objects_search
        assert callable(bucket_objects_search)

    def test_bucket_objects_search_graphql_currently_exists(self):
        """Given bucket_objects_search_graphql function currently exists
        When attempting to import it
        Then it should be available and callable
        """
        from quilt_mcp.tools.buckets import bucket_objects_search_graphql
        assert callable(bucket_objects_search_graphql)

    def test_catalog_search_exists(self):
        """Given catalog_search should exist before and after consolidation
        When attempting to import it
        Then it should be available and callable
        """
        from quilt_mcp.tools.search import catalog_search
        assert callable(catalog_search)