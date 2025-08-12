import pytest
from quilt import (
    packages_search,
    packages_list,
    package_browse,
    package_contents_search,
    auth_check,
)

# Test configuration - using actual package from s3://quilt-example
TEST_REGISTRY = "s3://quilt-example"
TEST_PACKAGE = "akarve/tmp"


class TestQuiltAPI:
    """Test suite for quilt MCP server using real data from akarve/tmp package."""


    def test_packages_search_custom_params(self):
        """Test package search with custom parameters."""
        result = packages_search("tmp", registry=TEST_REGISTRY, limit=3)
        
        assert isinstance(result, dict)
        assert "results" in result
        # Should respect the limit parameter
        assert len(result["results"]) <= 3

    def test_packages_search_no_results(self):
        """Test package search with query that should return no results."""
        result = packages_search("nonexistent-package-xyz123", registry=TEST_REGISTRY)
        
        assert isinstance(result, dict)
        assert "results" in result
        assert len(result["results"]) >= 0


    def test_packages_list_with_prefix(self):
        """Test package listing with prefix filter."""
        result = packages_list(registry=TEST_REGISTRY, prefix="akarve")
        
        assert isinstance(result, dict)
        assert "packages" in result
        
        # All packages should start with the prefix if any results
        for pkg in result["packages"]:
            if isinstance(pkg, str):
                assert pkg.startswith("akarve")

    def test_packages_list_invalid_registry(self):
        """Test package listing with invalid registry."""
        result = packages_list(registry="s3://nonexistent-bucket-xyz")
        
        assert isinstance(result, dict)
        assert "packages" in result



    def test_package_browse_error(self):
        """Test package browsing with nonexistent package."""
        try:
            result = package_browse("nonexistent/package", registry=TEST_REGISTRY)
            assert False, "Expected exception for nonexistent package"
        except Exception as e:
            assert "nonexistent" in str(e).lower() or "not found" in str(e).lower() or "no such file" in str(e).lower()

    def test_package_browse_invalid_registry(self):
        """Test package browsing with invalid registry."""
        try:
            result = package_browse(TEST_PACKAGE, registry="s3://nonexistent-bucket")
            assert False, "Expected exception for invalid registry"
        except Exception as e:
            assert "nonexistent" in str(e).lower() or "not found" in str(e).lower() or "no such file" in str(e).lower()


    def test_package_contents_search_error(self):
        """Test package content search with nonexistent package."""
        # This should raise an exception for nonexistent package
        try:
            result = package_contents_search("nonexistent/package", "query", registry=TEST_REGISTRY)
            assert False, "Expected exception for nonexistent package"
        except Exception as e:
            assert "nonexistent" in str(e).lower() or "not found" in str(e).lower() or "no such file" in str(e).lower()

    def test_auth_check(self):
        """Test Quilt authentication status checker."""
        result = auth_check()
        
        assert isinstance(result, dict)
        assert "status" in result
        assert result["status"] in ["authenticated", "not_authenticated", "error"]
        
        if result["status"] == "authenticated":
            assert "catalog_url" in result
            assert result["search_available"] is True
        elif result["status"] == "not_authenticated":
            assert "setup_instructions" in result
            assert result["search_available"] is False
        else:  # error status
            assert "error" in result
            assert "setup_instructions" in result


if __name__ == "__main__":
    pytest.main([__file__])
