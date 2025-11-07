from unittest.mock import Mock, patch

from quilt_mcp.models import (
    PackagesListParams,
    PackageBrowseParams,
    PackageDiffParams,
)
from quilt_mcp.services.auth_metadata import auth_status, catalog_info, catalog_name
from quilt_mcp.tools.catalog import catalog_uri, catalog_url
from quilt_mcp.tools.packages import (
    package_browse,
    package_diff,
    packages_list,
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
        """Test auth_status when an error occurs - now gracefully handled as not_authenticated."""
        with patch("quilt3.logged_in", side_effect=Exception("Test error")):
            result = auth_status()

            # The improved implementation gracefully handles errors as not_authenticated
            # instead of crashing, providing better user experience
            assert result["status"] == "not_authenticated"
            assert "setup_instructions" in result
            assert result["search_available"] is False

    def test_packages_list_success(self):
        """Test packages_list with successful response."""
        mock_packages = ["user/package1", "user/package2"]
        mock_package = Mock()
        mock_package.meta = {"description": "Test package"}

        with (
            patch("quilt3.list_packages", return_value=mock_packages),
            patch("quilt3.Package.browse", return_value=mock_package),
        ):
            params = PackagesListParams()  # Uses default registry
            result = packages_list(params)

            # Result now has packages structure
            assert hasattr(result, 'success')
            assert result.success is True
            assert hasattr(result, 'packages')

            packages = result.packages
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
            params = PackagesListParams(prefix="user/")
            result = packages_list(params)

            # Result now has packages structure
            assert hasattr(result, 'success')
            assert result.success is True
            assert hasattr(result, 'packages')

            packages = result.packages
            assert len(packages) == 2
            assert all(pkg.startswith("user/") for pkg in packages)

    def test_packages_list_error(self):
        """Test packages_list with error."""
        with patch("quilt3.list_packages", side_effect=Exception("Test error")):
            params = PackagesListParams()
            result = packages_list(params)

            # Should return an error response, not raise exception
            assert hasattr(result, 'success')
            assert result.success is False
            assert "Test error" in result.error

    def test_package_browse_success(self):
        """Test package_browse with successful response."""
        mock_package = Mock()
        mock_package.keys.return_value = ["file1.txt", "file2.csv"]

        # Create mock entries with required attributes
        mock_entries = {}
        for key in ["file1.txt", "file2.csv"]:
            mock_entry = Mock()
            mock_entry.size = 1000
            mock_entry.hash = "abc123"
            mock_entry.physical_key = f"s3://test-bucket/{key}"
            mock_entries[key] = mock_entry

        # Make mock_package support item access
        mock_package.__getitem__ = lambda self, key: mock_entries.get(key)

        with patch("quilt3.Package.browse", return_value=mock_package):
            params = PackageBrowseParams(package_name="user/test-package")
            result = package_browse(params)

            assert hasattr(result, 'success')
            assert result.success is True
            assert hasattr(result, 'entries')
            assert hasattr(result, 'package_name')
            assert hasattr(result, 'total_entries')
            assert len(result.entries) == 2
            assert result.entries[0]["logical_key"] == "file1.txt"
            assert result.entries[1]["logical_key"] == "file2.csv"

    def test_package_browse_error(self):
        """Test package_browse with error."""
        with patch("quilt3.Package.browse", side_effect=Exception("Package not found")):
            params = PackageBrowseParams(package_name="user/nonexistent")
            result = package_browse(params)

            assert hasattr(result, 'success')
            assert result.success is False
            assert "Failed to browse package" in result.error
            assert "Package not found" in result.cause
            assert hasattr(result, 'possible_fixes')
            assert hasattr(result, 'suggested_actions')

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

            assert isinstance(result, dict) or hasattr(result, 'success')
            assert result.success is True
            assert result.view_type == "package"
            assert (
                result.catalog_url
                == "https://test.catalog.com/b/test-bucket/packages/user/package/tree/latest/data.csv"
            )
            assert result.bucket == "test-bucket"

    def test_catalog_url_bucket_view(self):
        """Test catalog_url for bucket view."""
        with patch("quilt3.logged_in", return_value="https://test.catalog.com"):
            result = catalog_url(registry="s3://test-bucket", path="data/file.csv")

            assert isinstance(result, dict) or hasattr(result, 'success')
            assert result.success is True
            assert result.view_type == "bucket"
            assert result.catalog_url == "https://test.catalog.com/b/test-bucket/tree/data/file.csv"
            assert result.bucket == "test-bucket"

    def test_catalog_uri_basic(self):
        """Test catalog_uri with basic parameters."""
        with patch("quilt3.logged_in", return_value="https://test.catalog.com"):
            result = catalog_uri(
                registry="s3://test-bucket",
                package_name="user/package",
                path="data.csv",
            )

            assert isinstance(result, dict) or hasattr(result, 'success')
            assert result.success is True
            assert (
                result.quilt_plus_uri
                == "quilt+s3://test-bucket#package=user/package&path=data.csv&catalog=test.catalog.com"
            )
            assert result.bucket == "test-bucket"

    def test_catalog_uri_with_version(self):
        """Test catalog_uri with version hash."""
        with patch("quilt3.logged_in", return_value="https://test.catalog.com"):
            result = catalog_uri(
                registry="s3://test-bucket",
                package_name="user/package",
                top_hash="abc123def456",
            )

            assert isinstance(result, dict) or hasattr(result, 'success')
            assert result.success is True
            assert "package=user/package@abc123def456" in result.quilt_plus_uri
            assert result.top_hash == "abc123def456"

    def test_catalog_uri_with_tag(self):
        """Test catalog_uri with version tag."""
        with patch("quilt3.logged_in", return_value="https://test.catalog.com"):
            result = catalog_uri(registry="s3://test-bucket", package_name="user/package", tag="v1.0")

            assert isinstance(result, dict) or hasattr(result, 'success')
            assert result.success is True
            assert "package=user/package:v1.0" in result.quilt_plus_uri
            assert result.tag == "v1.0"

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

            params = PackageDiffParams(
                package1_name="user/package1",
                package2_name="user/package2",
                package1_hash="abc123",
                package2_hash="def456",
            )
            result = package_diff(params)

            assert hasattr(result, 'success')
            assert result.success is True
            assert result.package1 == "user/package1"
            assert result.package2 == "user/package2"
            assert result.package1_hash == "abc123"
            assert result.package2_hash == "def456"
            assert result.diff == mock_diff_result
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

            params = PackageDiffParams(
                package1_name="user/package",
                package2_name="user/package",
                package1_hash="old_hash",
                package2_hash="new_hash",
            )
            result = package_diff(params)

            assert hasattr(result, 'success')
            assert result.success is True
            assert result.package1 == "user/package"
            assert result.package2 == "user/package"
            assert result.package1_hash == "old_hash"
            assert result.package2_hash == "new_hash"
            assert result.diff == mock_diff_result

    def test_package_diff_latest_versions(self):
        """Test package_diff with latest versions (no hashes)."""
        mock_pkg1 = Mock()
        mock_pkg2 = Mock()
        mock_diff_result = {"added": ["file1.txt"], "deleted": [], "modified": []}
        mock_pkg1.diff.return_value = mock_diff_result

        with patch("quilt3.Package.browse") as mock_browse:
            mock_browse.side_effect = [mock_pkg1, mock_pkg2]

            params = PackageDiffParams(
                package1_name="user/package1",
                package2_name="user/package2",
            )
            result = package_diff(params)

            assert hasattr(result, 'success')
            assert result.success is True
            assert result.package1_hash == "latest"
            assert result.package2_hash == "latest"
            assert result.diff == mock_diff_result
            # Should call browse without top_hash
            assert mock_browse.call_count == 2

    def test_package_diff_browse_error(self):
        """Test package_diff with package browse error."""
        with patch("quilt3.Package.browse", side_effect=Exception("Package not found")):
            params = PackageDiffParams(
                package1_name="user/nonexistent1",
                package2_name="user/nonexistent2",
            )
            result = package_diff(params)

            assert hasattr(result, 'success')
            assert result.success is False
            assert "Failed to browse packages" in result.error
            assert "Package not found" in str(result.error)

    def test_package_diff_diff_error(self):
        """Test package_diff with diff operation error."""
        mock_pkg1 = Mock()
        mock_pkg2 = Mock()
        mock_pkg1.diff.side_effect = Exception("Diff operation failed")

        with patch("quilt3.Package.browse") as mock_browse:
            mock_browse.side_effect = [mock_pkg1, mock_pkg2]

            params = PackageDiffParams(
                package1_name="user/package1",
                package2_name="user/package2",
            )
            result = package_diff(params)

            assert hasattr(result, 'success')
            assert result.success is False
            assert "Failed to diff packages" in result.error
            assert "Diff operation failed" in str(result.error)
