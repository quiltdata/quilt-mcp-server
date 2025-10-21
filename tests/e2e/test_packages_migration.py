"""Migration validation tests for packages.py to QuiltService.

This file validates that packages.py behavior remains identical
after migrating from direct quilt3 imports to QuiltService.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

from quilt_mcp.tools.packages import (
    packages_list,
    package_browse,
    package_diff,
)
from quilt_mcp.models import (
    PackagesListParams,
    PackageBrowseParams,
    PackageDiffParams,
)


class TestPackagesMigrationValidation:
    """Validate that packages.py functions work identically with QuiltService."""

    def test_packages_list_uses_quilt_service(self):
        """Test packages_list calls QuiltService.list_packages."""
        mock_service = Mock()
        mock_service.list_packages.return_value = iter(['user/package1', 'user/package2'])

        with (
            patch('quilt_mcp.tools.packages.QuiltService', return_value=mock_service),
            patch('quilt_mcp.utils.suppress_stdout'),
        ):
            params = PackagesListParams(registry='s3://test-bucket')
            result = packages_list(params)

        mock_service.list_packages.assert_called_once_with(registry='s3://test-bucket')
        assert result.packages == ['user/package1', 'user/package2']

    def test_package_browse_uses_quilt_service(self):
        """Test package_browse calls QuiltService.browse_package."""
        mock_service = Mock()
        mock_package = Mock()
        mock_package.keys.return_value = ['file1.txt', 'file2.csv']
        # Mock the __getitem__ method properly
        mock_entry = Mock()
        mock_entry.size = 1024
        mock_entry.hash = 'abc123'
        mock_entry.physical_key = 's3://bucket/path/file1.txt'
        mock_package.__getitem__ = Mock(return_value=mock_entry)
        mock_service.browse_package.return_value = mock_package

        with (
            patch('quilt_mcp.tools.packages.QuiltService', return_value=mock_service),
            patch('quilt_mcp.utils.suppress_stdout'),
            patch('quilt_mcp.tools.packages.generate_signed_url', return_value='signed_url'),
        ):
            params = PackageBrowseParams(package_name='user/package', registry='s3://test-bucket')
            result = package_browse(params)

        mock_service.browse_package.assert_called_once_with('user/package', registry='s3://test-bucket')
        assert result.success is True
        assert result.package_name == 'user/package'

    def test_package_diff_uses_quilt_service(self):
        """Test package_diff calls QuiltService.browse_package for both packages."""
        mock_service = Mock()
        mock_pkg1 = Mock()
        mock_pkg2 = Mock()
        mock_pkg1.diff.return_value = {'added': [], 'removed': [], 'modified': []}
        mock_service.browse_package.side_effect = [mock_pkg1, mock_pkg2]

        with (
            patch('quilt_mcp.tools.packages.QuiltService', return_value=mock_service),
            patch('quilt_mcp.utils.suppress_stdout'),
        ):
            params = PackageDiffParams(
                package1_name='user/package1',
                package2_name='user/package2',
                registry='s3://test-bucket'
            )
            result = package_diff(params)

        assert mock_service.browse_package.call_count == 2
        mock_service.browse_package.assert_any_call('user/package1', registry='s3://test-bucket')
        mock_service.browse_package.assert_any_call('user/package2', registry='s3://test-bucket')
        assert result.package1 == 'user/package1'
        assert result.package2 == 'user/package2'
