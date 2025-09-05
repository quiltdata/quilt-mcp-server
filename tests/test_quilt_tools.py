from unittest.mock import Mock, patch
import pytest

from quilt_mcp.tools.auth import (
    auth_status,
    catalog_info,
    catalog_name,
    catalog_uri,
    catalog_url,
)
from quilt_mcp.tools.buckets import bucket_objects_search
from quilt_mcp.tools.packages import (
    package_browse,
    package_contents_search,
    package_diff,
    packages_list,
    packages_search,
)


class TestQuiltTools:
    """Test suite for Quilt MCP tools."""

    def test_auth_status_authenticated(self):
        """Test auth_status when user is authenticated."""
        with patch("quilt3.logged_in", return_value="https://open.quiltdata.com"):
            result = auth_status()

            assert result["status"] == "authenticated"
            assert result["catalog_url"] == "https://open.quiltdata.com"
            assert result["search_available"] is True

    def test_auth_status_not_authenticated(self):
        """Test auth_status when user is not authenticated."""
        with patch("quilt3.logged_in", return_value=None):
            result = auth_status()

            assert result["status"] == "not_authenticated"
            assert result["search_available"] is False
            assert "setup_instructions" in result

    def test_auth_status_error(self):
        """Test auth_status when an error occurs."""
        with patch("quilt3.logged_in", side_effect=Exception("Test error")):
            result = auth_status()

            assert result["status"] == "error"
            assert "Failed to check authentication" in result["error"]
            assert "setup_instructions" in result

    def test_packages_list_success(self):
        """Test packages_list with successful response."""
        mock_packages = ["user/package1", "user/package2"]
        mock_package = Mock()
        mock_package.meta = {"description": "Test package"}

        with (
            patch("quilt3.list_packages", return_value=mock_packages),
            patch("quilt3.Package.browse", return_value=mock_package),
        ):
            result = packages_list()

            # Result now has packages structure
            assert isinstance(result, dict)
            assert "packages" in result

            packages = result["packages"]
            assert len(packages) == 2
            assert packages[0] == "user/package1"
            assert packages[1] == "user/package2"

    def test_packages_list_with_prefix(self):
        """Test packages_list with prefix filter."""
        mock_packages = ["user/package1", "user/package2", "other/package3"]
        mock_package = Mock()
        mock_package.meta = {}

        with (
            patch("quilt3.list_packages", return_value=mock_packages),
            patch("quilt3.Package.browse", return_value=mock_package),
        ):
            result = packages_list(prefix="user/")

            # Result now has packages structure
            assert isinstance(result, dict)
            assert "packages" in result

            packages = result["packages"]
            assert len(packages) == 2
            assert all(pkg.startswith("user/") for pkg in packages)

    def test_packages_list_error(self):
        """Test packages_list with error."""
        with patch("quilt3.list_packages", side_effect=Exception("Test error")):
            try:
                packages_list()
                assert False, "Expected exception"
            except Exception as e:
                assert "Test error" in str(e)

    def test_package_browse_success(self):
        """Test package_browse with successful response."""
        mock_package = Mock()
        mock_package.keys.return_value = ["file1.txt", "file2.csv"]

        with patch("quilt3.Package.browse", return_value=mock_package):
            result = package_browse("user/test-package")

            assert isinstance(result, dict)
            assert "entries" in result
            assert "package_name" in result
            assert "total_entries" in result
            assert len(result["entries"]) == 2
            assert result["entries"][0]["logical_key"] == "file1.txt"
            assert result["entries"][1]["logical_key"] == "file2.csv"

    def test_package_browse_error(self):
        """Test package_browse with error."""
        with patch("quilt3.Package.browse", side_effect=Exception("Package not found")):
            result = package_browse("user/nonexistent")

            assert result["success"] is False
            assert "Failed to browse package" in result["error"]
            assert "Package not found" in result["cause"]
            assert "possible_fixes" in result
            assert "suggested_actions" in result

    def test_package_contents_search_success(self):
        """Test package_contents_search with matches."""
        mock_package = Mock()
        mock_package.keys.return_value = ["test_file.txt", "data.csv"]

        with patch("quilt3.Package.browse", return_value=mock_package):
            result = package_contents_search("user/test-package", "test")

            assert isinstance(result, dict)
            assert "matches" in result
            assert "count" in result
            assert "package_name" in result
            assert "query" in result
            assert len(result["matches"]) == 1  # Only 'test_file.txt' matches 'test'
            assert result["matches"][0]["logical_key"] == "test_file.txt"

    @pytest.mark.parametrize(
        "error_message,test_description",
        [
            ("401 Unauthorized", "authentication error"),
            ("Invalid URL - No scheme supplied", "configuration error"),
        ],
    )
    def test_packages_search_error_scenarios(self, error_message, test_description):
        """Test packages_search with various error scenarios."""
        # Mock both search methods to fail using patch.multiple for cleaner code
        mock_bucket = Mock()
        mock_bucket.search.side_effect = Exception(f"{error_message} - fallback failed")

        with (
            patch.multiple(
                "quilt_mcp.tools.stack_buckets",
                build_stack_search_indices=Mock(side_effect=Exception(error_message)),
            ),
            patch("quilt3.Bucket", return_value=mock_bucket),
        ):
            result = packages_search("test query")

            assert isinstance(result, dict)
            assert "error" in result
            # The error gets wrapped as "All search methods failed: <original error>"
            assert "All search methods failed" in result["error"]
            assert result["results"] == []

    def test_packages_search_success(self):
        """Test packages_search with successful results."""
        mock_search_results = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "name": "user/package1",
                            "description": "Test package 1",
                        }
                    },
                    {
                        "_source": {
                            "name": "user/package2",
                            "description": "Test package 2",
                        }
                    },
                ],
                "total": {"value": 2},
            },
            "took": 10,
            "timed_out": False,
        }

        with patch(
            "quilt_mcp.tools.stack_buckets.build_stack_search_indices",
            return_value="test-bucket",
        ):
            with patch(
                "quilt3.search_util.search_api", return_value=mock_search_results
            ):
                result = packages_search("test query", limit=2)

                assert isinstance(result, dict)
                assert "results" in result
                assert "registry" in result
                assert "bucket" in result
                assert len(result["results"]) == 2
                assert result["results"][0]["_source"]["name"] == "user/package1"
                assert result["results"][1]["_source"]["name"] == "user/package2"

    def test_catalog_info_success(self):
        """Test catalog_info with successful response."""
        with patch("quilt3.logged_in", return_value="https://test.catalog.com"):
            with patch(
                "quilt3.config",
                return_value={
                    "navigator_url": "https://test.catalog.com",
                    "registryUrl": "https://registry.test.com",
                },
            ):
                result = catalog_info()

                assert isinstance(result, dict)
                assert result["status"] == "success"
                assert result["catalog_name"] == "test.catalog.com"
                assert result["is_authenticated"] is True
                assert "navigator_url" in result
                assert "registry_url" in result

    def test_catalog_info_not_authenticated(self):
        """Test catalog_info when not authenticated."""
        with (
            patch("quilt3.logged_in", return_value=None),
            patch(
                "quilt3.config",
                return_value={"navigator_url": "https://test.catalog.com"},
            ),
        ):
            result = catalog_info()

            assert isinstance(result, dict)
            assert result["status"] == "success"
            assert result["catalog_name"] == "test.catalog.com"
            assert result["is_authenticated"] is False

    def test_catalog_name_from_authentication(self):
        """Test catalog_name when detected from authentication."""
        with (
            patch("quilt3.logged_in", return_value="https://test.catalog.com"),
            patch("quilt3.config", return_value={}),
        ):
            result = catalog_name()

            assert isinstance(result, dict)
            assert result["status"] == "success"
            assert result["catalog_name"] == "test.catalog.com"
            assert result["detection_method"] == "authentication"
            assert result["is_authenticated"] is True

    def test_catalog_name_from_config(self):
        """Test catalog_name when detected from config."""
        with (
            patch("quilt3.logged_in", return_value=None),
            patch(
                "quilt3.config",
                return_value={"navigator_url": "https://config.catalog.com"},
            ),
        ):
            result = catalog_name()

            assert isinstance(result, dict)
            assert result["status"] == "success"
            assert result["catalog_name"] == "config.catalog.com"
            assert result["detection_method"] == "navigator_config"
            assert result["is_authenticated"] is False

    def test_catalog_url_package_view(self):
        """Test catalog_url for package view."""
        with patch("quilt3.logged_in", return_value="https://test.catalog.com"):
            result = catalog_url(
                registry="s3://test-bucket",
                package_name="user/package",
                path="data.csv",
            )

            assert isinstance(result, dict)
            assert result["status"] == "success"
            assert result["view_type"] == "package"
            assert (
                result["catalog_url"]
                == "https://test.catalog.com/b/test-bucket/packages/user/package/tree/latest/data.csv"
            )
            assert result["bucket"] == "test-bucket"

    def test_catalog_url_bucket_view(self):
        """Test catalog_url for bucket view."""
        with patch("quilt3.logged_in", return_value="https://test.catalog.com"):
            result = catalog_url(registry="s3://test-bucket", path="data/file.csv")

            assert isinstance(result, dict)
            assert result["status"] == "success"
            assert result["view_type"] == "bucket"
            assert (
                result["catalog_url"]
                == "https://test.catalog.com/b/test-bucket/tree/data/file.csv"
            )
            assert result["bucket"] == "test-bucket"

    def test_catalog_uri_basic(self):
        """Test catalog_uri with basic parameters."""
        with patch("quilt3.logged_in", return_value="https://test.catalog.com"):
            result = catalog_uri(
                registry="s3://test-bucket",
                package_name="user/package",
                path="data.csv",
            )

            assert isinstance(result, dict)
            assert result["status"] == "success"
            assert (
                result["quilt_plus_uri"]
                == "quilt+s3://test-bucket#package=user/package&path=data.csv&catalog=test.catalog.com"
            )
            assert result["bucket"] == "test-bucket"

    def test_catalog_uri_with_version(self):
        """Test catalog_uri with version hash."""
        with patch("quilt3.logged_in", return_value="https://test.catalog.com"):
            result = catalog_uri(
                registry="s3://test-bucket",
                package_name="user/package",
                top_hash="abc123def456",
            )

            assert isinstance(result, dict)
            assert result["status"] == "success"
            assert "package=user/package@abc123def456" in result["quilt_plus_uri"]
            assert result["top_hash"] == "abc123def456"

    def test_catalog_uri_with_tag(self):
        """Test catalog_uri with version tag."""
        with patch("quilt3.logged_in", return_value="https://test.catalog.com"):
            result = catalog_uri(
                registry="s3://test-bucket", package_name="user/package", tag="v1.0"
            )

            assert isinstance(result, dict)
            assert result["status"] == "success"
            assert "package=user/package:v1.0" in result["quilt_plus_uri"]
            assert result["tag"] == "v1.0"

    def test_bucket_objects_search_success(self):
        """Test bucket_objects_search with successful results."""
        mock_results = [
            {"_source": {"key": "data/file1.csv", "size": 1024}},
            {"_source": {"key": "data/file2.json", "size": 512}},
        ]
        mock_bucket = Mock()
        mock_bucket.search.return_value = mock_results

        with patch("quilt3.Bucket", return_value=mock_bucket):
            result = bucket_objects_search("test-bucket", "data", limit=10)

            assert isinstance(result, dict)
            assert result["bucket"] == "test-bucket"
            assert result["query"] == "data"
            assert result["limit"] == 10
            assert result["results"] == mock_results
            mock_bucket.search.assert_called_once_with("data", limit=10)

    def test_bucket_objects_search_with_dict_query(self):
        """Test bucket_objects_search with dictionary DSL query."""
        query_dsl = {"query": {"match": {"key": "test"}}}
        mock_results = [{"_source": {"key": "test.txt", "size": 256}}]
        mock_bucket = Mock()
        mock_bucket.search.return_value = mock_results

        with patch("quilt3.Bucket", return_value=mock_bucket):
            result = bucket_objects_search("test-bucket", query_dsl, limit=5)

            assert isinstance(result, dict)
            assert result["bucket"] == "test-bucket"
            assert result["query"] == query_dsl
            assert result["limit"] == 5
            assert result["results"] == mock_results
            mock_bucket.search.assert_called_once_with(query_dsl, limit=5)

    def test_bucket_objects_search_s3_uri_normalization(self):
        """Test bucket_objects_search normalizes s3:// URI to bucket name."""
        mock_results = []
        mock_bucket = Mock()
        mock_bucket.search.return_value = mock_results

        with patch("quilt3.Bucket", return_value=mock_bucket) as mock_bucket_class:
            result = bucket_objects_search("s3://test-bucket", "query")

            assert result["bucket"] == "test-bucket"
            mock_bucket_class.assert_called_once_with("s3://test-bucket")

    def test_bucket_objects_search_error(self):
        """Test bucket_objects_search with search error."""
        with patch(
            "quilt3.Bucket", side_effect=Exception("Search endpoint not configured")
        ):
            result = bucket_objects_search("test-bucket", "query")

            assert isinstance(result, dict)
            assert "error" in result
            assert "Failed to search bucket" in result["error"]
            assert result["bucket"] == "test-bucket"
            assert result["query"] == "query"

    def test_package_diff_success(self):
        """Test package_diff with successful diff."""
        mock_pkg1 = Mock()
        mock_pkg2 = Mock()
        mock_diff_result = {
            "added": ["new_file.txt"],
            "deleted": ["old_file.txt"],
            "modified": ["changed_file.txt"],
        }
        mock_pkg1.diff.return_value = mock_diff_result

        with patch("quilt3.Package.browse") as mock_browse:
            mock_browse.side_effect = [mock_pkg1, mock_pkg2]

            result = package_diff(
                "user/package1",
                "user/package2",
                package1_hash="abc123",
                package2_hash="def456",
            )

            assert isinstance(result, dict)
            assert result["package1"] == "user/package1"
            assert result["package2"] == "user/package2"
            assert result["package1_hash"] == "abc123"
            assert result["package2_hash"] == "def456"
            assert result["diff"] == mock_diff_result
            mock_pkg1.diff.assert_called_once_with(mock_pkg2)

    def test_package_diff_same_package_different_versions(self):
        """Test package_diff comparing different versions of same package."""
        mock_pkg1 = Mock()
        mock_pkg2 = Mock()
        mock_diff_result = {
            "added": [],
            "deleted": [],
            "modified": ["updated_file.txt"],
        }
        mock_pkg1.diff.return_value = mock_diff_result

        with patch("quilt3.Package.browse") as mock_browse:
            mock_browse.side_effect = [mock_pkg1, mock_pkg2]

            result = package_diff(
                "user/package",
                "user/package",
                package1_hash="old_hash",
                package2_hash="new_hash",
            )

            assert isinstance(result, dict)
            assert result["package1"] == "user/package"
            assert result["package2"] == "user/package"
            assert result["package1_hash"] == "old_hash"
            assert result["package2_hash"] == "new_hash"
            assert result["diff"] == mock_diff_result

    def test_package_diff_latest_versions(self):
        """Test package_diff with latest versions (no hashes)."""
        mock_pkg1 = Mock()
        mock_pkg2 = Mock()
        mock_diff_result = {"added": ["file1.txt"], "deleted": [], "modified": []}
        mock_pkg1.diff.return_value = mock_diff_result

        with patch("quilt3.Package.browse") as mock_browse:
            mock_browse.side_effect = [mock_pkg1, mock_pkg2]

            result = package_diff("user/package1", "user/package2")

            assert isinstance(result, dict)
            assert result["package1_hash"] == "latest"
            assert result["package2_hash"] == "latest"
            assert result["diff"] == mock_diff_result
            # Should call browse without top_hash
            assert mock_browse.call_count == 2

    def test_package_diff_browse_error(self):
        """Test package_diff with package browse error."""
        with patch("quilt3.Package.browse", side_effect=Exception("Package not found")):
            result = package_diff("user/nonexistent1", "user/nonexistent2")

            assert isinstance(result, dict)
            assert "error" in result
            assert "Failed to browse packages" in result["error"]
            assert "Package not found" in result["error"]

    def test_package_diff_diff_error(self):
        """Test package_diff with diff operation error."""
        mock_pkg1 = Mock()
        mock_pkg2 = Mock()
        mock_pkg1.diff.side_effect = Exception("Diff operation failed")

        with patch("quilt3.Package.browse") as mock_browse:
            mock_browse.side_effect = [mock_pkg1, mock_pkg2]

            result = package_diff("user/package1", "user/package2")

            assert isinstance(result, dict)
            assert "error" in result
            assert "Failed to diff packages" in result["error"]
            assert "Diff operation failed" in result["error"]
