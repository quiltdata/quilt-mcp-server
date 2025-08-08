import pytest
from unittest.mock import patch, MagicMock
from quilt import search_packages, list_packages, browse_package, search_package_contents, get_package_versions


class TestQuiltAPI:
    """Test suite for quilt MCP server."""

    @patch('quilt.quilt3.search')
    def test_search_packages_success(self, mock_search):
        """Test successful package search."""
        mock_search.return_value = [
            {
                "name": "test-package",
                "registry": "s3://quilt-example",
                "hash": "abc123",
                "metadata": {"title": "Test Package"}
            }
        ]
        
        result = search_packages("test query")
        
        assert len(result) == 1
        assert result[0]["name"] == "test-package"
        mock_search.assert_called_once_with("test query", registry="s3://quilt-example", limit=10)

    @patch('quilt.quilt3.search')
    def test_search_packages_error(self, mock_search):
        """Test package search with error."""
        mock_search.side_effect = Exception("API Error")
        
        result = search_packages("test query")
        
        assert len(result) == 1
        assert "error" in result[0]
        assert "Search failed" in result[0]["error"]

    @patch('quilt.quilt3.search')
    def test_search_packages_custom_params(self, mock_search):
        """Test package search with custom parameters."""
        mock_search.return_value = []
        
        search_packages("query", registry="s3://custom-bucket", limit=20)
        
        mock_search.assert_called_once_with("query", registry="s3://custom-bucket", limit=20)

    @patch('quilt.quilt3.Bucket')
    @patch('quilt.quilt3.Package.browse')
    def test_list_packages_success(self, mock_browse, mock_bucket):
        """Test successful package listing."""
        mock_bucket_instance = MagicMock()
        mock_bucket_instance.list_packages.return_value = ["package1", "package2"]
        mock_bucket.return_value = mock_bucket_instance
        
        mock_pkg = MagicMock()
        mock_pkg.meta = {"description": "Test package"}
        mock_browse.return_value = mock_pkg
        
        result = list_packages()
        
        assert len(result) == 2
        assert result[0]["name"] == "package1"
        assert result[1]["name"] == "package2"
        mock_bucket.assert_called_once_with("s3://quilt-example")

    @patch('quilt.quilt3.Bucket')
    def test_list_packages_bucket_error(self, mock_bucket):
        """Test package listing with bucket error."""
        mock_bucket.side_effect = Exception("Bucket error")
        
        result = list_packages()
        
        assert len(result) == 1
        assert "error" in result[0]
        assert "Failed to list packages" in result[0]["error"]

    @patch('quilt.quilt3.Bucket')
    @patch('quilt.quilt3.Package.browse')
    def test_list_packages_with_prefix(self, mock_browse, mock_bucket):
        """Test package listing with prefix filter."""
        mock_bucket_instance = MagicMock()
        mock_bucket_instance.list_packages.return_value = ["test-package"]
        mock_bucket.return_value = mock_bucket_instance
        
        mock_pkg = MagicMock()
        mock_pkg.meta = {}
        mock_browse.return_value = mock_pkg
        
        list_packages(prefix="test-")
        
        mock_bucket_instance.list_packages.assert_called_once_with(prefix="test-")

    @patch('quilt.quilt3.Package.browse')
    def test_browse_package_success(self, mock_browse):
        """Test successful package browsing."""
        mock_pkg = MagicMock()
        mock_pkg.meta = {"title": "Test Package"}
        mock_pkg.top_hash = "abc123"
        mock_pkg.__iter__.return_value = ["file1.txt", "file2.csv"]
        
        # Mock file entries
        mock_entry1 = MagicMock()
        mock_entry1.size = 1024
        mock_entry1.hash = "hash1"
        mock_entry1.meta = {"type": "text"}
        
        mock_entry2 = MagicMock()
        mock_entry2.size = 2048
        mock_entry2.hash = "hash2"
        mock_entry2.meta = {"type": "csv"}
        
        mock_pkg.__getitem__.side_effect = lambda key: mock_entry1 if key == "file1.txt" else mock_entry2
        mock_browse.return_value = mock_pkg
        
        result = browse_package("test-package")
        
        assert result["name"] == "test-package"
        assert result["hash"] == "abc123"
        assert len(result["files"]) == 2
        assert result["files"][0]["path"] == "file1.txt"
        assert result["files"][0]["size"] == 1024

    @patch('quilt.quilt3.Package.browse')
    def test_browse_package_error(self, mock_browse):
        """Test package browsing with error."""
        mock_browse.side_effect = Exception("Package not found")
        
        result = browse_package("nonexistent-package")
        
        assert "error" in result
        assert "Failed to browse package" in result["error"]

    @patch('quilt.quilt3.Package.browse')
    def test_browse_package_with_version(self, mock_browse):
        """Test package browsing with specific version."""
        mock_pkg = MagicMock()
        mock_pkg.meta = {}
        mock_pkg.__iter__.return_value = []
        mock_browse.return_value = mock_pkg
        
        browse_package("test-package", hash_or_tag="v1.0")
        
        mock_browse.assert_called_once_with("test-package", registry="s3://quilt-example", top_hash="v1.0")

    @patch('quilt.quilt3.Package.browse')
    def test_search_package_contents_success(self, mock_browse):
        """Test successful package content search."""
        mock_pkg = MagicMock()
        mock_pkg.meta = {"description": "Test package with data"}
        mock_pkg.__iter__.return_value = ["data/test.csv", "docs/readme.md"]
        
        # Mock file entries
        mock_entry1 = MagicMock()
        mock_entry1.size = 1024
        mock_entry1.hash = "hash1"
        mock_entry1.meta = {"type": "data file"}
        
        mock_entry2 = MagicMock()
        mock_entry2.size = 512
        mock_entry2.hash = "hash2"
        mock_entry2.meta = {"type": "documentation"}
        
        mock_pkg.__getitem__.side_effect = lambda key: mock_entry1 if key == "data/test.csv" else mock_entry2
        mock_browse.return_value = mock_pkg
        
        result = search_package_contents("test-package", "data")
        
        matches = [m for m in result if m.get("type") == "file_path"]
        assert len(matches) >= 1
        assert any("data/test.csv" in m["path"] for m in matches)

    @patch('quilt.quilt3.Package.browse')
    def test_search_package_contents_metadata_match(self, mock_browse):
        """Test package content search finding metadata matches."""
        mock_pkg = MagicMock()
        mock_pkg.meta = {"description": "Contains important data"}
        mock_pkg.__iter__.return_value = ["file.txt"]
        
        mock_entry = MagicMock()
        mock_entry.size = 100
        mock_entry.hash = "hash1"
        mock_entry.meta = {}
        
        mock_pkg.__getitem__.return_value = mock_entry
        mock_browse.return_value = mock_pkg
        
        result = search_package_contents("test-package", "important")
        
        metadata_matches = [m for m in result if m.get("match_type") == "metadata"]
        assert len(metadata_matches) >= 1

    @patch('quilt.quilt3.Package.browse')
    def test_search_package_contents_error(self, mock_browse):
        """Test package content search with error."""
        mock_browse.side_effect = Exception("Package error")
        
        result = search_package_contents("test-package", "query")
        
        assert len(result) == 1
        assert "error" in result[0]

    @patch('quilt.quilt3.Bucket')
    def test_get_package_versions_success(self, mock_bucket):
        """Test successful package version retrieval."""
        mock_bucket_instance = MagicMock()
        mock_bucket_instance.list_package_versions.return_value = [
            {
                "hash": "abc123",
                "modified": "2024-01-01T00:00:00Z",
                "size": 1024,
                "metadata": {"version": "1.0"}
            },
            {
                "hash": "def456",
                "modified": "2024-01-02T00:00:00Z", 
                "size": 2048,
                "metadata": {"version": "1.1"}
            }
        ]
        mock_bucket.return_value = mock_bucket_instance
        
        result = get_package_versions("test-package")
        
        assert len(result) == 2
        assert result[0]["hash"] == "abc123"
        assert result[1]["hash"] == "def456"
        mock_bucket_instance.list_package_versions.assert_called_once_with("test-package")

    @patch('quilt.quilt3.Bucket')
    def test_get_package_versions_error(self, mock_bucket):
        """Test package version retrieval with error."""
        mock_bucket.side_effect = Exception("Bucket error")
        
        result = get_package_versions("test-package")
        
        assert len(result) == 1
        assert "error" in result[0]
        assert "Failed to get package versions" in result[0]["error"]

    @patch('quilt.quilt3.Bucket')
    def test_get_package_versions_custom_registry(self, mock_bucket):
        """Test package version retrieval with custom registry."""
        mock_bucket_instance = MagicMock()
        mock_bucket_instance.list_package_versions.return_value = []
        mock_bucket.return_value = mock_bucket_instance
        
        get_package_versions("test-package", registry="s3://custom-bucket")
        
        mock_bucket.assert_called_once_with("s3://custom-bucket")


if __name__ == "__main__":
    pytest.main([__file__])
