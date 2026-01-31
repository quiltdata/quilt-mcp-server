"""Tests for migrating package tools to use QuiltOps instead of QuiltService."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import asdict

from quilt_mcp.domain.package_info import Package_Info
from quilt_mcp.domain.content_info import Content_Info
from quilt_mcp.ops.quilt_ops import QuiltOps
from quilt_mcp.tools.packages import packages_list, package_browse


class TestPackagesListQuiltOpsMigration:
    """Test packages_list migration to QuiltOps."""

    @pytest.fixture
    def mock_quilt_ops(self):
        """Mock QuiltOps instance for testing."""
        mock_ops = Mock(spec=QuiltOps)
        return mock_ops

    @pytest.fixture
    def sample_package_info_list(self):
        """Sample Package_Info objects for testing."""
        return [
            Package_Info(
                name="test/package1",
                description="Test package 1",
                tags=["test", "data"],
                modified_date="2024-01-15T10:30:00Z",
                registry="s3://test-bucket",
                bucket="test-bucket",
                top_hash="abc123",
            ),
            Package_Info(
                name="test/package2",
                description="Test package 2",
                tags=["test", "analysis"],
                modified_date="2024-01-16T11:45:00Z",
                registry="s3://test-bucket",
                bucket="test-bucket",
                top_hash="def456",
            ),
            Package_Info(
                name="demo/package3",
                description=None,
                tags=[],
                modified_date="2024-01-17T09:15:00Z",
                registry="s3://test-bucket",
                bucket="test-bucket",
                top_hash="ghi789",
            ),
        ]

    def test_packages_list_with_prefix_filter(self, mock_quilt_ops, sample_package_info_list):
        """Test that packages_list applies prefix filtering correctly."""
        # Setup mock to return all packages
        mock_quilt_ops.search_packages.return_value = sample_package_info_list

        with patch('quilt_mcp.ops.factory.QuiltOpsFactory') as mock_factory:
            mock_factory.create.return_value = mock_quilt_ops

            # Call with prefix filter
            result = packages_list(registry="s3://test-bucket", prefix="test", limit=10)

        # Verify QuiltOps was called
        mock_quilt_ops.search_packages.assert_called_once_with(query="", registry="s3://test-bucket")

        # Verify prefix filtering is applied to results
        assert hasattr(result, 'packages')
        assert len(result.packages) == 2  # Only "test/" packages
        assert result.packages[0] == "test/package1"
        assert result.packages[1] == "test/package2"
        assert "demo/package3" not in result.packages

    def test_packages_list_transforms_package_info_to_names(self, mock_quilt_ops):
        """Test that Package_Info objects are transformed to package names."""
        package_infos = [
            Package_Info(
                name="namespace/package",
                description="Test",
                tags=["tag1"],
                modified_date="2024-01-01T00:00:00Z",
                registry="s3://bucket",
                bucket="bucket",
                top_hash="hash123",
            )
        ]
        mock_quilt_ops.search_packages.return_value = package_infos

        with patch('quilt_mcp.ops.factory.QuiltOpsFactory') as mock_factory:
            mock_factory.create.return_value = mock_quilt_ops

            result = packages_list(registry="s3://bucket")

        # Verify transformation to package names
        assert result.packages == ["namespace/package"]

    def test_packages_list_error_handling(self, mock_quilt_ops):
        """Test that packages_list handles QuiltOps errors gracefully."""
        # Setup mock to raise exception
        mock_quilt_ops.search_packages.side_effect = Exception("Authentication failed")

        with patch('quilt_mcp.ops.factory.QuiltOpsFactory') as mock_factory:
            mock_factory.create.return_value = mock_quilt_ops

            result = packages_list(registry="s3://test-bucket")

        # Verify error response format is maintained
        assert hasattr(result, 'error')
        assert "Authentication failed" in result.error

    def test_packages_list_maintains_response_format(self, mock_quilt_ops, sample_package_info_list):
        """Test that packages_list maintains the same response format after migration."""
        mock_quilt_ops.search_packages.return_value = sample_package_info_list

        with patch('quilt_mcp.ops.factory.QuiltOpsFactory') as mock_factory:
            mock_factory.create.return_value = mock_quilt_ops

            result = packages_list(registry="s3://test-bucket", limit=5, prefix="test")

        # Verify all expected response fields are present
        assert hasattr(result, 'packages')
        assert hasattr(result, 'registry')
        assert hasattr(result, 'count')
        assert hasattr(result, 'prefix_filter')

        # Verify field values
        assert result.registry == "s3://test-bucket"
        assert result.count == 2  # After prefix filtering
        assert result.prefix_filter == "test"


class TestPackageBrowseQuiltOpsMigration:
    """Test package_browse migration to QuiltOps."""

    @pytest.fixture
    def mock_quilt_ops(self):
        """Mock QuiltOps instance for testing."""
        mock_ops = Mock(spec=QuiltOps)
        return mock_ops

    @pytest.fixture
    def sample_content_info_list(self):
        """Sample Content_Info objects for testing."""
        return [
            Content_Info(
                path="file1.txt", size=100, type="file", modified_date="2024-01-15T10:30:00Z", download_url=None
            ),
            Content_Info(path="data/", size=None, type="directory", modified_date=None, download_url=None),
            Content_Info(
                path="data/file2.csv", size=250, type="file", modified_date="2024-01-16T11:45:00Z", download_url=None
            ),
        ]

    def test_package_browse_transforms_content_info_to_entries(self, mock_quilt_ops, sample_content_info_list):
        """Test that Content_Info objects are transformed to entry format."""
        mock_quilt_ops.browse_content.return_value = sample_content_info_list

        with patch('quilt_mcp.ops.factory.QuiltOpsFactory') as mock_factory:
            mock_factory.create.return_value = mock_quilt_ops

            result = package_browse(package_name="test/package1", registry="s3://test-bucket")

        # Verify transformation to entry format
        assert len(result.entries) == 3

        # Check first entry (file) - entries use logical_key not path
        entry1 = result.entries[0]
        assert entry1['logical_key'] == "file1.txt"
        assert entry1['size'] == 100

        # Check second entry (directory)
        entry2 = result.entries[1]
        assert entry2['logical_key'] == "data/"
        assert entry2['size'] is None

    def test_package_browse_error_handling(self, mock_quilt_ops):
        """Test that package_browse handles QuiltOps errors gracefully."""
        # Setup mock to raise exception
        mock_quilt_ops.browse_content.side_effect = Exception("Package not found")

        with patch('quilt_mcp.ops.factory.QuiltOpsFactory') as mock_factory:
            mock_factory.create.return_value = mock_quilt_ops

            result = package_browse(package_name="nonexistent/package", registry="s3://test-bucket")

        # Verify error response format is maintained - check the cause field
        assert hasattr(result, 'error')
        assert hasattr(result, 'cause')
        assert "Package not found" in result.cause

    def test_package_browse_maintains_response_format(self, mock_quilt_ops, sample_content_info_list):
        """Test that package_browse maintains the same response format after migration."""
        mock_quilt_ops.browse_content.return_value = sample_content_info_list

        with patch('quilt_mcp.ops.factory.QuiltOpsFactory') as mock_factory:
            mock_factory.create.return_value = mock_quilt_ops

            result = package_browse(package_name="test/package1", registry="s3://test-bucket", recursive=False)

        # Verify all expected response fields are present
        assert hasattr(result, 'entries')
        assert hasattr(result, 'package_name')
        assert hasattr(result, 'registry')
        assert hasattr(result, 'total_entries')
        assert hasattr(result, 'view_type')

        # Verify field values
        assert result.package_name == "test/package1"
        assert result.registry == "s3://test-bucket"
        assert result.total_entries == 3
        assert result.view_type == "flat"  # recursive=False
