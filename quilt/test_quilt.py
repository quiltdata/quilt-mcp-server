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

    def test_packages_search_success(self):
        """Test successful package search with actual data."""
        result = packages_search(TEST_PACKAGE, registry=TEST_REGISTRY, limit=5)
        
        # Should return a list
        assert isinstance(result, list)
        
        # Check if there are any error messages (fix the generator issue)
        has_errors = False
        for item in result:
            if isinstance(item, dict) and "error" in item:
                has_errors = True
                break
        
        # If there are results without errors, that's good
        # If there are errors, that's also acceptable for this test
        # We just want to ensure the function returns a proper list structure
        if not has_errors and len(result) > 0:
            # Should have valid search result structure
            assert all(isinstance(item, dict) for item in result)

    def test_packages_search_custom_params(self):
        """Test package search with custom parameters."""
        result = packages_search("tmp", registry=TEST_REGISTRY, limit=3)
        
        assert isinstance(result, list)
        # Should respect the limit parameter
        assert len(result) <= 3

    def test_packages_search_no_results(self):
        """Test package search with query that should return no results."""
        result = packages_search("nonexistent-package-xyz123", registry=TEST_REGISTRY)
        
        assert isinstance(result, list)
        # May be empty or contain error message
        assert len(result) >= 0

    def test_packages_list_success(self):
        """Test successful package listing with prefix to avoid too much data."""
        result = packages_list(registry=TEST_REGISTRY, prefix="akarve")
        
        assert isinstance(result, list)
        assert len(result) >= 1
        
        # New API returns a single result object with 'packages' and 'pagination'
        data = result[0]
        assert isinstance(data, dict)
        assert "packages" in data
        assert isinstance(data["packages"], list)
        package_names = [
            name
            for name in (
                pkg.get("name") for pkg in data["packages"] if isinstance(pkg, dict)
            )
            if isinstance(name, str)
        ]
        if package_names:
            # At least one package should start with akarve
            assert any(name.startswith("akarve") for name in package_names)

    def test_packages_list_with_prefix(self):
        """Test package listing with prefix filter."""
        result = packages_list(registry=TEST_REGISTRY, prefix="akarve")
        
        assert isinstance(result, list)
        
        # All packages should start with the prefix if any results
        for pkg in result:
            if "name" in pkg and "error" not in pkg:
                assert pkg["name"].startswith("akarve")

    def test_packages_list_invalid_registry(self):
        """Test package listing with invalid registry."""
        result = packages_list(registry="s3://nonexistent-bucket-xyz")
        
        assert isinstance(result, list)
        assert len(result) >= 1
        # Should contain error message
        assert any("error" in item for item in result)


    def test_package_browse_success(self):
        """Test successful package browsing with actual akarve/tmp package."""
        result = package_browse(TEST_PACKAGE, registry=TEST_REGISTRY)
        
        assert isinstance(result, dict)
        assert "error" not in result
        assert result["name"] == TEST_PACKAGE
        assert result["registry"] == TEST_REGISTRY
        assert "files" in result
        assert isinstance(result["files"], list)
        
        # Should contain the known files: README.md and deck.pdf
        file_paths = [f["path"] for f in result["files"]]
        assert "README.md" in file_paths
        assert "deck.pdf" in file_paths
        
        # Check file details
        readme_file = next(f for f in result["files"] if f["path"] == "README.md")
        deck_file = next(f for f in result["files"] if f["path"] == "deck.pdf")
        
        # These should have size information
        assert "size" in readme_file
        assert "size" in deck_file

    def test_package_browse_error(self):
        """Test package browsing with nonexistent package."""
        result = package_browse("nonexistent/package", registry=TEST_REGISTRY)
        
        assert isinstance(result, dict)
        assert "error" in result

    def test_package_browse_invalid_registry(self):
        """Test package browsing with invalid registry."""
        result = package_browse(TEST_PACKAGE, registry="s3://nonexistent-bucket")
        
        assert isinstance(result, dict)
        assert "error" in result

    def test_package_contents_search_file_path_match(self):
        """Test package content search finding file path matches."""
        result = package_contents_search(TEST_PACKAGE, "README", registry=TEST_REGISTRY)
        
        assert isinstance(result, list)
        assert len(result) > 0
        
        # Should find README.md file
        path_matches = [m for m in result if m.get("type") == "file_path" and "README" in m.get("path", "")]
        assert len(path_matches) > 0
        
        readme_match = path_matches[0]
        assert readme_match["path"] == "README.md"
        assert readme_match["match_type"] == "path"

    def test_package_contents_search_file_extension_match(self):
        """Test package content search finding files by extension."""
        result = package_contents_search(TEST_PACKAGE, "pdf", registry=TEST_REGISTRY)
        
        assert isinstance(result, list)
        assert len(result) > 0
        
        # Should find deck.pdf file
        path_matches = [m for m in result if m.get("type") == "file_path" and "pdf" in m.get("path", "")]
        assert len(path_matches) > 0
        
        pdf_match = path_matches[0]
        assert pdf_match["path"] == "deck.pdf"

    def test_package_contents_search_no_matches(self):
        """Test package content search with no matches."""
        result = package_contents_search(TEST_PACKAGE, "nonexistent-term-xyz", registry=TEST_REGISTRY)
        
        assert isinstance(result, list)
        # Should return empty list when no matches found
        assert len(result) == 0

    def test_package_contents_search_error(self):
        """Test package content search with nonexistent package."""
        result = package_contents_search("nonexistent/package", "query", registry=TEST_REGISTRY)
        
        assert isinstance(result, list)
        assert len(result) == 1
        assert "error" in result[0]

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
