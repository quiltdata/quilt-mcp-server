"""
Tests for Quilt3_Backend content operations.

This module tests content/object-related operations including content retrieval,
transformations, file type detection, and error handling for the Quilt3_Backend implementation.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime
from typing import List, Optional

from quilt_mcp.ops.exceptions import AuthenticationError, BackendError, ValidationError
from quilt_mcp.domain.package_info import Package_Info
from quilt_mcp.domain.content_info import Content_Info
from quilt_mcp.domain.bucket_info import Bucket_Info


class TestQuilt3BackendContentOperations:
    """Test content browsing and URL generation operations."""

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_browse_content_with_mocked_package_browsing(self, mock_quilt3):
        """Test browse_content() with mocked quilt3 package browsing."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock package and content
        mock_package = Mock()
        mock_entry = Mock()
        mock_entry.name = "data.csv"
        mock_entry.size = 1024
        mock_entry.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_entry.is_dir = False

        mock_package.__iter__ = Mock(return_value=iter([mock_entry]))
        mock_quilt3.Package.browse.return_value = mock_package

        # Execute
        result = backend.browse_content("test/package", "s3://test-registry", "")

        # Verify
        assert len(result) == 1
        assert isinstance(result[0], Content_Info)
        assert result[0].path == "data.csv"
        assert result[0].size == 1024
        assert result[0].type == "file"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_browse_content_root_path_browsing(self, mock_quilt3):
        """Test browse_content() browsing at root path with multiple entries."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock multiple entries at root
        mock_entries = []

        # File entry
        mock_file = Mock()
        mock_file.name = "README.md"
        mock_file.size = 512
        mock_file.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_file.is_dir = False
        mock_entries.append(mock_file)

        # Directory entry
        mock_dir = Mock()
        mock_dir.name = "data/"
        mock_dir.size = None
        mock_dir.modified = datetime(2024, 1, 2, 12, 0, 0)
        mock_dir.is_dir = True
        mock_entries.append(mock_dir)

        # Another file
        mock_file2 = Mock()
        mock_file2.name = "config.json"
        mock_file2.size = 256
        mock_file2.modified = datetime(2024, 1, 3, 12, 0, 0)
        mock_file2.is_dir = False
        mock_entries.append(mock_file2)

        mock_package = Mock()
        mock_package.__iter__ = Mock(return_value=iter(mock_entries))
        mock_quilt3.Package.browse.return_value = mock_package

        # Execute - browse root path
        result = backend.browse_content("test/package", "s3://test-registry", "")

        # Verify
        assert len(result) == 3

        # Verify quilt3.Package.browse was called correctly
        mock_quilt3.Package.browse.assert_called_once_with("test/package", registry="s3://test-registry")

        # Verify entries are properly transformed
        readme = next(r for r in result if r.path == "README.md")
        assert readme.type == "file"
        assert readme.size == 512
        assert readme.modified_date == "2024-01-01T12:00:00"

        data_dir = next(r for r in result if r.path == "data/")
        assert data_dir.type == "directory"
        assert data_dir.size is None
        assert data_dir.modified_date == "2024-01-02T12:00:00"

        config = next(r for r in result if r.path == "config.json")
        assert config.type == "file"
        assert config.size == 256
        assert config.modified_date == "2024-01-03T12:00:00"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_browse_content_subdirectory_path_browsing(self, mock_quilt3):
        """Test browse_content() browsing within a subdirectory path."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock subdirectory content
        mock_entries = []

        mock_file1 = Mock()
        mock_file1.name = "data/file1.csv"
        mock_file1.size = 1024
        mock_file1.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_file1.is_dir = False
        mock_entries.append(mock_file1)

        mock_file2 = Mock()
        mock_file2.name = "data/file2.csv"
        mock_file2.size = 2048
        mock_file2.modified = datetime(2024, 1, 2, 12, 0, 0)
        mock_file2.is_dir = False
        mock_entries.append(mock_file2)

        # Mock the package browsing behavior
        mock_root_package = Mock()
        mock_subdir_package = Mock()
        mock_subdir_package.__iter__ = Mock(return_value=iter(mock_entries))

        # Mock package[path] access
        mock_root_package.__getitem__ = Mock(return_value=mock_subdir_package)
        mock_quilt3.Package.browse.return_value = mock_root_package

        # Execute - browse subdirectory
        result = backend.browse_content("test/package", "s3://test-registry", "data/")

        # Verify
        assert len(result) == 2

        # Verify quilt3.Package.browse was called correctly
        mock_quilt3.Package.browse.assert_called_once_with("test/package", registry="s3://test-registry")

        # Verify subdirectory access
        mock_root_package.__getitem__.assert_called_once_with("data/")

        # Verify entries
        file1 = next(r for r in result if r.path == "data/file1.csv")
        assert file1.type == "file"
        assert file1.size == 1024

        file2 = next(r for r in result if r.path == "data/file2.csv")
        assert file2.type == "file"
        assert file2.size == 2048

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_browse_content_nested_path_browsing(self, mock_quilt3):
        """Test browse_content() browsing deeply nested paths."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock deeply nested content
        mock_entry = Mock()
        mock_entry.name = "data/processed/2024/january/results.csv"
        mock_entry.size = 4096
        mock_entry.modified = datetime(2024, 1, 15, 12, 0, 0)
        mock_entry.is_dir = False

        # Mock the nested package browsing
        mock_root_package = Mock()
        mock_nested_package = Mock()
        mock_nested_package.__iter__ = Mock(return_value=iter([mock_entry]))

        mock_root_package.__getitem__ = Mock(return_value=mock_nested_package)
        mock_quilt3.Package.browse.return_value = mock_root_package

        # Execute - browse nested path
        nested_path = "data/processed/2024/january/"
        result = backend.browse_content("test/package", "s3://test-registry", nested_path)

        # Verify
        assert len(result) == 1

        # Verify correct path access
        mock_root_package.__getitem__.assert_called_once_with(nested_path)

        # Verify entry
        assert result[0].path == "data/processed/2024/january/results.csv"
        assert result[0].type == "file"
        assert result[0].size == 4096

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_browse_content_empty_directory(self, mock_quilt3):
        """Test browse_content() with empty directory."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock empty directory
        mock_package = Mock()
        mock_package.__iter__ = Mock(return_value=iter([]))  # Empty iterator
        mock_quilt3.Package.browse.return_value = mock_package

        # Execute
        result = backend.browse_content("test/package", "s3://test-registry", "")

        # Verify
        assert len(result) == 0
        assert isinstance(result, list)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_browse_content_package_not_found_error(self, mock_quilt3):
        """Test browse_content() error handling when package is not found."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock package not found error
        mock_quilt3.Package.browse.side_effect = Exception("Package not found")

        # Execute and verify error
        with pytest.raises(BackendError) as exc_info:
            backend.browse_content("nonexistent/package", "s3://test-registry", "")

        error_message = str(exc_info.value)
        assert "quilt3 backend browse_content failed" in error_message.lower()
        assert "package not found" in error_message.lower()

        # Verify error context
        assert exc_info.value.context['package_name'] == "nonexistent/package"
        assert exc_info.value.context['registry'] == "s3://test-registry"
        assert exc_info.value.context['path'] == ""

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_browse_content_path_not_found_error(self, mock_quilt3):
        """Test browse_content() error handling when path is not found."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock path not found error
        mock_package = Mock()
        # Configure the mock to support item access and raise KeyError
        mock_package.__getitem__ = Mock(side_effect=KeyError("Path not found"))
        mock_quilt3.Package.browse.return_value = mock_package

        # Execute and verify error
        with pytest.raises(BackendError) as exc_info:
            backend.browse_content("test/package", "s3://test-registry", "nonexistent/path/")

        error_message = str(exc_info.value)
        assert "quilt3 backend browse_content failed" in error_message.lower()
        assert "path not found" in error_message.lower()

        # Verify error context
        assert exc_info.value.context['package_name'] == "test/package"
        assert exc_info.value.context['path'] == "nonexistent/path/"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_browse_content_permission_denied_error(self, mock_quilt3):
        """Test browse_content() error handling for permission denied."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock permission denied error
        mock_quilt3.Package.browse.side_effect = PermissionError("Access denied")

        # Execute and verify error
        with pytest.raises(BackendError) as exc_info:
            backend.browse_content("restricted/package", "s3://test-registry", "")

        error_message = str(exc_info.value)
        assert "quilt3 backend browse_content failed" in error_message.lower()
        assert "access denied" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_browse_content_network_error(self, mock_quilt3):
        """Test browse_content() error handling for network errors."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock network error
        mock_quilt3.Package.browse.side_effect = ConnectionError("Network timeout")

        # Execute and verify error
        with pytest.raises(BackendError) as exc_info:
            backend.browse_content("test/package", "s3://test-registry", "")

        error_message = str(exc_info.value)
        assert "quilt3 backend browse_content failed" in error_message.lower()
        assert "network timeout" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_browse_content_transformation_error(self, mock_quilt3):
        """Test browse_content() error handling when content transformation fails."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock entry that will cause transformation error
        mock_entry = Mock()
        mock_entry.name = None  # This will cause transformation to fail

        mock_package = Mock()
        mock_package.__iter__ = Mock(return_value=iter([mock_entry]))
        mock_quilt3.Package.browse.return_value = mock_package

        # Execute and verify error
        with pytest.raises(BackendError) as exc_info:
            backend.browse_content("test/package", "s3://test-registry", "")

        error_message = str(exc_info.value)
        assert "quilt3 backend browse_content failed" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_browse_content_calls_quilt3_correctly(self, mock_quilt3):
        """Test that browse_content() correctly calls quilt3.Package.browse with proper parameters."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test different parameter combinations
        test_cases = [
            ("simple/package", "s3://registry1", ""),
            ("complex/package-name", "s3://another-registry", ""),
            ("user/dataset", "s3://test-bucket", "data/"),
            ("org/project", "s3://prod-registry", "results/2024/"),
        ]

        for package_name, registry, path in test_cases:
            # Reset mock
            mock_quilt3.Package.browse.reset_mock()

            # Mock simple content
            mock_entry = Mock()
            mock_entry.name = "test.txt"
            mock_entry.size = 100
            mock_entry.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_entry.is_dir = False

            # Create fresh mock package for each test case
            mock_package = Mock()
            mock_package.__iter__ = Mock(return_value=iter([mock_entry]))

            # Configure mock for path access if needed
            if path:
                mock_subdir_package = Mock()
                mock_subdir_package.__iter__ = Mock(return_value=iter([mock_entry]))
                mock_package.__getitem__ = Mock(return_value=mock_subdir_package)

            mock_quilt3.Package.browse.return_value = mock_package

            # Execute
            result = backend.browse_content(package_name, registry, path)

            # Verify quilt3.Package.browse was called correctly
            mock_quilt3.Package.browse.assert_called_once_with(package_name, registry=registry)

            # Verify path access if path was provided
            if path:
                mock_package.__getitem__.assert_called_once_with(path)

            # Verify result
            assert len(result) == 1
            assert isinstance(result[0], Content_Info)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_browse_content_with_mixed_content_types(self, mock_quilt3):
        """Test browse_content() with mixed files and directories."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create mixed content types
        mock_entries = []

        # Regular file
        mock_file = Mock()
        mock_file.name = "document.pdf"
        mock_file.size = 1048576  # 1MB
        mock_file.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_file.is_dir = False
        mock_entries.append(mock_file)

        # Directory
        mock_dir = Mock()
        mock_dir.name = "images/"
        mock_dir.size = None
        mock_dir.modified = datetime(2024, 1, 2, 12, 0, 0)
        mock_dir.is_dir = True
        mock_entries.append(mock_dir)

        # Large file
        mock_large_file = Mock()
        mock_large_file.name = "dataset.parquet"
        mock_large_file.size = 104857600  # 100MB
        mock_large_file.modified = datetime(2024, 1, 3, 12, 0, 0)
        mock_large_file.is_dir = False
        mock_entries.append(mock_large_file)

        # Empty file
        mock_empty_file = Mock()
        mock_empty_file.name = "empty.txt"
        mock_empty_file.size = 0
        mock_empty_file.modified = datetime(2024, 1, 4, 12, 0, 0)
        mock_empty_file.is_dir = False
        mock_entries.append(mock_empty_file)

        mock_package = Mock()
        mock_package.__iter__ = Mock(return_value=iter(mock_entries))
        mock_quilt3.Package.browse.return_value = mock_package

        # Execute
        result = backend.browse_content("mixed/content", "s3://test-registry", "")

        # Verify
        assert len(result) == 4

        # Verify each content type
        pdf = next(r for r in result if r.path == "document.pdf")
        assert pdf.type == "file"
        assert pdf.size == 1048576

        images_dir = next(r for r in result if r.path == "images/")
        assert images_dir.type == "directory"
        assert images_dir.size is None

        parquet = next(r for r in result if r.path == "dataset.parquet")
        assert parquet.type == "file"
        assert parquet.size == 104857600

        empty = next(r for r in result if r.path == "empty.txt")
        assert empty.type == "file"
        assert empty.size == 0

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_browse_content_with_special_characters_in_paths(self, mock_quilt3):
        """Test browse_content() with special characters in file/directory names."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create entries with special characters
        mock_entries = []

        special_names = [
            "file with spaces.txt",
            "file-with-dashes.csv",
            "file_with_underscores.json",
            "file.with.dots.xml",
            "file(with)parentheses.log",
            "file[with]brackets.md",
            "file{with}braces.yaml",
            "file@symbol.txt",
            "file#hash.txt",
            "file$dollar.txt",
            "file%percent.txt",
            "file&ampersand.txt",
            "file+plus.txt",
            "file=equals.txt",
            "unicode_测试文件.txt",
            "émoji_file_🚀.txt",
        ]

        for i, name in enumerate(special_names):
            mock_entry = Mock()
            mock_entry.name = name
            mock_entry.size = 100 + i
            mock_entry.modified = datetime(2024, 1, 1, 12, i, 0)
            mock_entry.is_dir = False
            mock_entries.append(mock_entry)

        mock_package = Mock()
        mock_package.__iter__ = Mock(return_value=iter(mock_entries))
        mock_quilt3.Package.browse.return_value = mock_package

        # Execute
        result = backend.browse_content("special/chars", "s3://test-registry", "")

        # Verify
        assert len(result) == len(special_names)

        # Verify all special character names are preserved
        result_names = {r.path for r in result}
        expected_names = set(special_names)
        assert result_names == expected_names

        # Verify each entry is properly transformed
        for entry in result:
            assert isinstance(entry, Content_Info)
            assert entry.type == "file"
            assert entry.size >= 100
            assert entry.modified_date is not None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_browse_content_directory_vs_file_detection(self, mock_quilt3):
        """Test browse_content() correctly detects directories vs files."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock directory and file entries
        mock_dir = Mock()
        mock_dir.name = "folder/"
        mock_dir.is_dir = True
        mock_dir.size = None

        mock_file = Mock()
        mock_file.name = "file.txt"
        mock_file.is_dir = False
        mock_file.size = 512

        mock_package = Mock()
        mock_package.__iter__ = Mock(return_value=iter([mock_dir, mock_file]))
        mock_quilt3.Package.browse.return_value = mock_package

        # Execute
        result = backend.browse_content("test/package", "s3://test-registry", "")

        # Verify
        assert len(result) == 2
        dir_result = next(r for r in result if r.path == "folder/")
        file_result = next(r for r in result if r.path == "file.txt")

        assert dir_result.type == "directory"
        assert dir_result.size is None
        assert file_result.type == "file"
        assert file_result.size == 512

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_content_url_with_mocked_url_generation(self, mock_quilt3):
        """Test get_content_url() with mocked quilt3 URL generation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock URL generation
        expected_url = "https://s3.amazonaws.com/test-bucket/test-package/data.csv?signature=abc123"
        mock_package = Mock()
        mock_package.get_url.return_value = expected_url
        mock_quilt3.Package.browse.return_value = mock_package

        # Execute
        result = backend.get_content_url("test/package", "s3://test-registry", "data.csv")

        # Verify
        assert result == expected_url
        mock_package.get_url.assert_called_once_with("data.csv")

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_content_url_calls_quilt3_methods_correctly(self, mock_quilt3):
        """Test that get_content_url() correctly calls quilt3.Package.browse and get_url methods."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock package and URL generation
        expected_url = "https://s3.amazonaws.com/bucket/package/file.txt?AWSAccessKeyId=KEY&Signature=SIG"
        mock_package = Mock()
        mock_package.get_url.return_value = expected_url
        mock_quilt3.Package.browse.return_value = mock_package

        # Execute
        result = backend.get_content_url("user/dataset", "s3://my-registry", "folder/file.txt")

        # Verify quilt3 methods were called correctly
        mock_quilt3.Package.browse.assert_called_once_with("user/dataset", registry="s3://my-registry")
        mock_package.get_url.assert_called_once_with("folder/file.txt")
        assert result == expected_url

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_content_url_returns_proper_url_string(self, mock_quilt3):
        """Test that get_content_url() returns a proper URL string."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various URL formats that quilt3 might return
        test_urls = [
            "https://s3.amazonaws.com/bucket/path/file.csv?signature=abc123",
            "https://bucket.s3.amazonaws.com/path/file.json?AWSAccessKeyId=KEY&Expires=123&Signature=SIG",
            "https://s3.us-west-2.amazonaws.com/bucket/data.parquet?X-Amz-Algorithm=AWS4-HMAC-SHA256",
            "s3://bucket/path/file.txt",  # Direct S3 URI
        ]

        for expected_url in test_urls:
            mock_package = Mock()
            mock_package.get_url.return_value = expected_url
            mock_quilt3.Package.browse.return_value = mock_package

            result = backend.get_content_url("test/package", "s3://test-registry", "test/path")

            # Verify result is a string and matches expected URL
            assert isinstance(result, str)
            assert result == expected_url
            assert len(result) > 0

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_content_url_with_various_path_scenarios(self, mock_quilt3):
        """Test get_content_url() with various path scenarios and file types."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test different path scenarios
        path_scenarios = [
            # (path, expected_url_suffix, description)
            ("data.csv", "data.csv", "root level file"),
            ("folder/data.csv", "folder/data.csv", "nested file"),
            ("deep/nested/folder/file.json", "deep/nested/folder/file.json", "deeply nested file"),
            ("data with spaces.txt", "data with spaces.txt", "file with spaces"),
            ("data-with-dashes.csv", "data-with-dashes.csv", "file with dashes"),
            ("data_with_underscores.parquet", "data_with_underscores.parquet", "file with underscores"),
            ("folder/", "folder/", "directory path"),
            ("", "", "empty path"),
        ]

        for path, expected_path, description in path_scenarios:
            # Mock package and URL generation
            expected_url = f"https://s3.amazonaws.com/bucket/{expected_path}?signature=test"
            mock_package = Mock()
            mock_package.get_url.return_value = expected_url
            mock_quilt3.Package.browse.return_value = mock_package

            # Execute
            result = backend.get_content_url("test/package", "s3://test-registry", path)

            # Verify
            assert result == expected_url, f"Failed for {description}: {path}"
            mock_package.get_url.assert_called_with(path)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_content_url_with_different_file_types(self, mock_quilt3):
        """Test get_content_url() with various file types and extensions."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test different file types
        file_types = [
            "data.csv",
            "data.json",
            "data.parquet",
            "data.xlsx",
            "image.png",
            "image.jpg",
            "document.pdf",
            "archive.zip",
            "script.py",
            "notebook.ipynb",
            "data.h5",
            "model.pkl",
            "file_without_extension",
            ".hidden_file",
        ]

        for filename in file_types:
            # Mock package and URL generation
            expected_url = f"https://s3.amazonaws.com/bucket/{filename}?signature=test"
            mock_package = Mock()
            mock_package.get_url.return_value = expected_url
            mock_quilt3.Package.browse.return_value = mock_package

            # Execute
            result = backend.get_content_url("test/package", "s3://test-registry", filename)

            # Verify
            assert result == expected_url
            assert isinstance(result, str)
            mock_package.get_url.assert_called_with(filename)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_content_url_error_handling_package_not_found(self, mock_quilt3):
        """Test get_content_url() error handling when package is not found."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock Package.browse to raise exception
        mock_quilt3.Package.browse.side_effect = Exception("Package not found")

        with pytest.raises(BackendError) as exc_info:
            backend.get_content_url("nonexistent/package", "s3://test-registry", "data.csv")

        error_message = str(exc_info.value)
        assert "quilt3 backend get_content_url failed" in error_message.lower()
        assert "package not found" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_content_url_error_handling_file_not_found(self, mock_quilt3):
        """Test get_content_url() error handling when file is not found in package."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock package that exists but file doesn't
        mock_package = Mock()
        mock_package.get_url.side_effect = KeyError("File not found in package")
        mock_quilt3.Package.browse.return_value = mock_package

        with pytest.raises(BackendError) as exc_info:
            backend.get_content_url("test/package", "s3://test-registry", "nonexistent.csv")

        error_message = str(exc_info.value)
        assert "quilt3 backend get_content_url failed" in error_message.lower()
        assert "file not found" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_content_url_error_handling_permission_denied(self, mock_quilt3):
        """Test get_content_url() error handling for permission denied scenarios."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock permission error during package browsing
        mock_quilt3.Package.browse.side_effect = PermissionError("Access denied to package")

        with pytest.raises(BackendError) as exc_info:
            backend.get_content_url("private/package", "s3://test-registry", "data.csv")

        error_message = str(exc_info.value)
        assert "quilt3 backend get_content_url failed" in error_message.lower()
        assert "access denied" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_content_url_error_handling_network_errors(self, mock_quilt3):
        """Test get_content_url() error handling for network-related errors."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various network errors
        network_errors = [
            ConnectionError("Connection failed"),
            TimeoutError("Request timed out"),
            Exception("Network unreachable"),
        ]

        for error in network_errors:
            mock_quilt3.Package.browse.side_effect = error

            with pytest.raises(BackendError) as exc_info:
                backend.get_content_url("test/package", "s3://test-registry", "data.csv")

            error_message = str(exc_info.value)
            assert "quilt3 backend get_content_url failed" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_content_url_error_handling_url_generation_failure(self, mock_quilt3):
        """Test get_content_url() error handling when URL generation fails."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock package that exists but URL generation fails
        mock_package = Mock()
        mock_package.get_url.side_effect = Exception("Failed to generate presigned URL")
        mock_quilt3.Package.browse.return_value = mock_package

        with pytest.raises(BackendError) as exc_info:
            backend.get_content_url("test/package", "s3://test-registry", "data.csv")

        error_message = str(exc_info.value)
        assert "quilt3 backend get_content_url failed" in error_message.lower()
        assert "failed to generate presigned url" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_content_url_error_context_information(self, mock_quilt3):
        """Test that get_content_url() includes proper context information in errors."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock error
        mock_quilt3.Package.browse.side_effect = Exception("Test error")

        with pytest.raises(BackendError) as exc_info:
            backend.get_content_url("test/package", "s3://my-registry", "folder/file.csv")

        # Verify error context is included
        error = exc_info.value
        assert hasattr(error, 'context')
        assert error.context['package_name'] == "test/package"
        assert error.context['registry'] == "s3://my-registry"
        assert error.context['path'] == "folder/file.csv"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_content_url_with_different_registries(self, mock_quilt3):
        """Test get_content_url() works with different registry formats."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test different registry formats
        registries = [
            "s3://my-bucket",
            "s3://another-registry-bucket",
            "s3://test-bucket-with-dashes",
            "s3://bucket.with.dots",
        ]

        for registry in registries:
            # Mock package and URL generation
            expected_url = f"https://s3.amazonaws.com/{registry.replace('s3://', '')}/data.csv?signature=test"
            mock_package = Mock()
            mock_package.get_url.return_value = expected_url
            mock_quilt3.Package.browse.return_value = mock_package

            # Execute
            result = backend.get_content_url("test/package", registry, "data.csv")

            # Verify correct registry was passed to quilt3
            mock_quilt3.Package.browse.assert_called_with("test/package", registry=registry)
            assert result == expected_url

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_content_url_with_complex_package_names(self, mock_quilt3):
        """Test get_content_url() works with complex package names."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various package name formats
        package_names = [
            "simple-package",
            "user/dataset",
            "organization/project/dataset",
            "user-name/dataset-name",
            "org.domain/project.name",
        ]

        for package_name in package_names:
            # Mock package and URL generation
            expected_url = f"https://s3.amazonaws.com/bucket/{package_name}/data.csv?signature=test"
            mock_package = Mock()
            mock_package.get_url.return_value = expected_url
            mock_quilt3.Package.browse.return_value = mock_package

            # Execute
            result = backend.get_content_url(package_name, "s3://test-registry", "data.csv")

            # Verify correct package name was passed to quilt3
            mock_quilt3.Package.browse.assert_called_with(package_name, registry="s3://test-registry")
            assert result == expected_url

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_content_url_with_empty_and_special_paths(self, mock_quilt3):
        """Test get_content_url() handles empty and special path cases."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test special path cases
        special_paths = [
            ("", "empty path"),
            (".", "current directory"),
            ("./file.csv", "relative path with dot"),
            ("../file.csv", "relative path with parent"),
            ("path/with/many/levels/file.csv", "deeply nested path"),
        ]

        for path, description in special_paths:
            # Mock package and URL generation
            expected_url = f"https://s3.amazonaws.com/bucket/{path}?signature=test"
            mock_package = Mock()
            mock_package.get_url.return_value = expected_url
            mock_quilt3.Package.browse.return_value = mock_package

            # Execute
            result = backend.get_content_url("test/package", "s3://test-registry", path)

            # Verify
            assert result == expected_url, f"Failed for {description}: {path}"
            mock_package.get_url.assert_called_with(path)


class TestQuilt3BackendDirectoryFileTypeDetection:
    """Test directory vs file type detection logic in Quilt3_Backend."""

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_determine_content_type_with_file_entries(self, mock_quilt3):
        """Test _determine_content_type() correctly identifies file entries."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various file entry scenarios
        file_scenarios = [
            # Standard file with is_dir=False
            {'name': 'data.csv', 'is_dir': False, 'expected': 'file'},
            # File with explicit is_dir=False
            {'name': 'document.pdf', 'is_dir': False, 'expected': 'file'},
            # File with no extension
            {'name': 'README', 'is_dir': False, 'expected': 'file'},
            # File with complex path
            {'name': 'data/processed/results.json', 'is_dir': False, 'expected': 'file'},
            # File with special characters
            {'name': 'file-name_with.special-chars.txt', 'is_dir': False, 'expected': 'file'},
        ]

        for scenario in file_scenarios:
            mock_entry = Mock()
            mock_entry.name = scenario['name']
            mock_entry.is_dir = scenario['is_dir']

            result = backend._determine_content_type(mock_entry)
            assert result == scenario['expected'], f"Failed for file: {scenario['name']}"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_determine_content_type_with_directory_entries(self, mock_quilt3):
        """Test _determine_content_type() correctly identifies directory entries."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various directory entry scenarios
        directory_scenarios = [
            # Standard directory with is_dir=True
            {'name': 'data/', 'is_dir': True, 'expected': 'directory'},
            # Directory without trailing slash
            {'name': 'folder', 'is_dir': True, 'expected': 'directory'},
            # Nested directory path
            {'name': 'data/processed/', 'is_dir': True, 'expected': 'directory'},
            # Directory with special characters
            {'name': 'folder-name_with.special-chars/', 'is_dir': True, 'expected': 'directory'},
            # Deep nested directory
            {'name': 'level1/level2/level3/', 'is_dir': True, 'expected': 'directory'},
        ]

        for scenario in directory_scenarios:
            mock_entry = Mock()
            mock_entry.name = scenario['name']
            mock_entry.is_dir = scenario['is_dir']

            result = backend._determine_content_type(mock_entry)
            assert result == scenario['expected'], f"Failed for directory: {scenario['name']}"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_determine_content_type_with_missing_is_dir_attribute(self, mock_quilt3):
        """Test _determine_content_type() defaults to 'file' when is_dir attribute is missing."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test entries without is_dir attribute using a custom class
        class EntryWithoutIsDir:
            def __init__(self):
                self.name = "unknown_type_entry"
                # Explicitly don't define is_dir attribute

        entry_without_is_dir = EntryWithoutIsDir()

        result = backend._determine_content_type(entry_without_is_dir)
        assert result == "file", "Should default to 'file' when is_dir attribute is missing"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_determine_content_type_with_none_is_dir_attribute(self, mock_quilt3):
        """Test _determine_content_type() defaults to 'file' when is_dir is None."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test entry with is_dir=None
        mock_entry = Mock()
        mock_entry.name = "none_is_dir_entry"
        mock_entry.is_dir = None

        result = backend._determine_content_type(mock_entry)
        assert result == "file", "Should default to 'file' when is_dir is None"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_determine_content_type_with_various_truthy_falsy_values(self, mock_quilt3):
        """Test _determine_content_type() with various truthy/falsy values for is_dir."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various truthy/falsy scenarios
        test_cases = [
            # Falsy values should result in 'file'
            (False, 'file'),
            (0, 'file'),
            ('', 'file'),
            ([], 'file'),
            ({}, 'file'),
            (None, 'file'),
            # Truthy values should result in 'directory'
            (True, 'directory'),
            (1, 'directory'),
            ('any_string', 'directory'),
            ([1, 2, 3], 'directory'),
            ({'key': 'value'}, 'directory'),
            (42, 'directory'),
        ]

        for is_dir_value, expected_type in test_cases:
            mock_entry = Mock()
            mock_entry.name = f"test_entry_{is_dir_value}"
            mock_entry.is_dir = is_dir_value

            result = backend._determine_content_type(mock_entry)
            assert result == expected_type, f"Failed for is_dir={is_dir_value}, expected {expected_type}, got {result}"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_determine_content_type_integration_with_transform_content(self, mock_quilt3):
        """Test that _determine_content_type() is properly integrated with _transform_content()."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test file entry transformation
        mock_file_entry = Mock()
        mock_file_entry.name = "test_file.txt"
        mock_file_entry.size = 1024
        mock_file_entry.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_file_entry.is_dir = False

        file_result = backend._transform_content(mock_file_entry)
        assert isinstance(file_result, Content_Info)
        assert file_result.type == "file"
        assert file_result.path == "test_file.txt"

        # Test directory entry transformation
        mock_dir_entry = Mock()
        mock_dir_entry.name = "test_directory/"
        mock_dir_entry.size = None
        mock_dir_entry.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_dir_entry.is_dir = True

        dir_result = backend._transform_content(mock_dir_entry)
        assert isinstance(dir_result, Content_Info)
        assert dir_result.type == "directory"
        assert dir_result.path == "test_directory/"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_determine_content_type_with_edge_case_quilt3_objects(self, mock_quilt3):
        """Test _determine_content_type() with edge case quilt3 object types."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with different mock object types
        mock_types = [
            Mock(),  # Standard Mock
            MagicMock(),  # MagicMock
            type('CustomEntry', (), {})(),  # Custom class instance
        ]

        for i, mock_entry in enumerate(mock_types):
            # Test as file
            mock_entry.name = f"file_{i}.txt"
            mock_entry.is_dir = False
            result = backend._determine_content_type(mock_entry)
            assert result == "file", f"Failed for mock type {type(mock_entry)} as file"

            # Test as directory
            mock_entry.name = f"directory_{i}/"
            mock_entry.is_dir = True
            result = backend._determine_content_type(mock_entry)
            assert result == "directory", f"Failed for mock type {type(mock_entry)} as directory"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_determine_content_type_with_property_access_errors(self, mock_quilt3):
        """Test _determine_content_type() handles property access errors gracefully."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create entry where is_dir property raises exception
        class ProblematicEntry:
            def __init__(self):
                self.name = "problematic_entry"

            @property
            def is_dir(self):
                raise AttributeError("Cannot access is_dir property")

        problematic_entry = ProblematicEntry()

        # Should default to 'file' when property access fails
        result = backend._determine_content_type(problematic_entry)
        assert result == "file", "Should default to 'file' when is_dir property access fails"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_content_type_detection_in_browse_content_workflow(self, mock_quilt3):
        """Test directory vs file type detection in complete browse_content() workflow."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create mixed content entries (files and directories)
        mock_entries = []

        # File entries
        file_entry1 = Mock()
        file_entry1.name = "data.csv"
        file_entry1.size = 1024
        file_entry1.modified = datetime(2024, 1, 1, 12, 0, 0)
        file_entry1.is_dir = False
        mock_entries.append(file_entry1)

        file_entry2 = Mock()
        file_entry2.name = "README.md"
        file_entry2.size = 512
        file_entry2.modified = datetime(2024, 1, 2, 12, 0, 0)
        file_entry2.is_dir = False
        mock_entries.append(file_entry2)

        # Directory entries
        dir_entry1 = Mock()
        dir_entry1.name = "images/"
        dir_entry1.size = None
        dir_entry1.modified = datetime(2024, 1, 3, 12, 0, 0)
        dir_entry1.is_dir = True
        mock_entries.append(dir_entry1)

        dir_entry2 = Mock()
        dir_entry2.name = "scripts/"
        dir_entry2.size = None
        dir_entry2.modified = datetime(2024, 1, 4, 12, 0, 0)
        dir_entry2.is_dir = True
        mock_entries.append(dir_entry2)

        # Entry with missing is_dir (should default to file)
        ambiguous_entry = type('AmbiguousEntry', (), {})()
        ambiguous_entry.name = "ambiguous_entry"
        ambiguous_entry.size = 256
        ambiguous_entry.modified = datetime(2024, 1, 5, 12, 0, 0)
        # Explicitly don't set is_dir attribute - this object type won't have it
        mock_entries.append(ambiguous_entry)

        # Mock package browsing
        mock_package = Mock()
        mock_package.__iter__ = Mock(return_value=iter(mock_entries))
        mock_quilt3.Package.browse.return_value = mock_package

        # Execute browse_content
        result = backend.browse_content("test/package", "s3://test-registry", "")

        # Verify results
        assert len(result) == 5

        # Verify file entries
        data_csv = next(r for r in result if r.path == "data.csv")
        assert data_csv.type == "file"
        assert data_csv.size == 1024

        readme_md = next(r for r in result if r.path == "README.md")
        assert readme_md.type == "file"
        assert readme_md.size == 512

        # Verify directory entries
        images_dir = next(r for r in result if r.path == "images/")
        assert images_dir.type == "directory"
        assert images_dir.size is None

        scripts_dir = next(r for r in result if r.path == "scripts/")
        assert scripts_dir.type == "directory"
        assert scripts_dir.size is None

        # Verify ambiguous entry defaults to file
        ambiguous = next(r for r in result if r.path == "ambiguous_entry")
        assert ambiguous.type == "file"
        assert ambiguous.size == 256

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_content_type_detection_with_various_quilt3_object_types(self, mock_quilt3):
        """Test content type detection works with various quilt3 object types and structures."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test different object structures that might come from quilt3
        test_objects = [
            # Standard object with boolean is_dir
            {'name': 'standard_file.txt', 'is_dir': False, 'expected': 'file'},
            {'name': 'standard_dir/', 'is_dir': True, 'expected': 'directory'},
            # Object with string representation of boolean
            {'name': 'string_false_file.txt', 'is_dir': 'False', 'expected': 'directory'},  # Truthy string
            {'name': 'string_true_dir/', 'is_dir': 'True', 'expected': 'directory'},
            # Object with numeric is_dir
            {'name': 'numeric_zero_file.txt', 'is_dir': 0, 'expected': 'file'},
            {'name': 'numeric_one_dir/', 'is_dir': 1, 'expected': 'directory'},
            # Object with None is_dir
            {'name': 'none_file.txt', 'is_dir': None, 'expected': 'file'},
        ]

        for test_obj in test_objects:
            mock_entry = Mock()
            mock_entry.name = test_obj['name']
            mock_entry.is_dir = test_obj['is_dir']

            result = backend._determine_content_type(mock_entry)
            assert result == test_obj['expected'], (
                f"Failed for {test_obj['name']} with is_dir={test_obj['is_dir']}, expected {test_obj['expected']}, got {result}"
            )


class TestQuilt3BackendContentTransformation:
    """Test content transformation methods in isolation."""

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_complete_entry(self, mock_quilt3):
        """Test _transform_content() method with complete quilt3 content object."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create mock content entry
        mock_entry = Mock()
        mock_entry.name = "data/file.csv"
        mock_entry.size = 2048
        mock_entry.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_entry.is_dir = False

        # Execute transformation
        result = backend._transform_content(mock_entry)

        # Verify
        assert isinstance(result, Content_Info)
        assert result.path == "data/file.csv"
        assert result.size == 2048
        assert result.type == "file"
        assert result.modified_date == "2024-01-01T12:00:00"
        assert result.download_url is None  # URL not provided in transformation


class TestQuilt3BackendMockContentTransformation:
    """Test transformation with mock quilt3 content objects with various configurations."""

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_complete_mock_file_object(self, mock_quilt3):
        """Test _transform_content() with complete mock quilt3 file content object."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create comprehensive mock file content with all fields
        mock_content = Mock()
        mock_content.name = "datasets/experiment_data.csv"
        mock_content.size = 1048576  # 1MB
        mock_content.modified = datetime(2024, 3, 15, 14, 30, 45, 123456)
        mock_content.is_dir = False

        # Execute transformation
        result = backend._transform_content(mock_content)

        # Verify complete transformation
        assert isinstance(result, Content_Info)
        assert result.path == "datasets/experiment_data.csv"
        assert result.size == 1048576
        assert result.type == "file"
        assert result.modified_date == "2024-03-15T14:30:45.123456"
        assert result.download_url is None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_complete_mock_directory_object(self, mock_quilt3):
        """Test _transform_content() with complete mock quilt3 directory content object."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create comprehensive mock directory content with all fields
        mock_content = Mock()
        mock_content.name = "datasets/raw_data/"
        mock_content.size = None  # Directories typically don't have size
        mock_content.modified = datetime(2024, 2, 20, 10, 15, 30)
        mock_content.is_dir = True

        # Execute transformation
        result = backend._transform_content(mock_content)

        # Verify complete transformation
        assert isinstance(result, Content_Info)
        assert result.path == "datasets/raw_data/"
        assert result.size is None
        assert result.type == "directory"
        assert result.modified_date == "2024-02-20T10:15:30"
        assert result.download_url is None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_minimal_mock_object(self, mock_quilt3):
        """Test _transform_content() with minimal mock quilt3 content object (only required fields)."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create minimal mock content with only required fields
        mock_content = Mock()
        mock_content.name = "minimal.txt"
        mock_content.size = None  # Optional field
        mock_content.modified = None  # Optional field
        mock_content.is_dir = False

        # Execute transformation
        result = backend._transform_content(mock_content)

        # Verify minimal transformation handles None values correctly
        assert isinstance(result, Content_Info)
        assert result.path == "minimal.txt"
        assert result.size is None
        assert result.type == "file"
        assert result.modified_date is None
        assert result.download_url is None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_edge_case_mock_configurations(self, mock_quilt3):
        """Test _transform_content() with edge case mock quilt3 content configurations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various edge case configurations
        edge_cases = [
            {
                'name': "",  # Empty string name (should cause validation error)
                'size': 0,  # Zero size file
                'modified': datetime(1970, 1, 1, 0, 0, 0),  # Unix epoch
                'is_dir': False,
                'should_fail': True,  # This configuration should fail validation
            },
            {
                'name': "a" * 1000,  # Very long filename
                'size': 999999999999,  # Very large file size
                'modified': datetime(2099, 12, 31, 23, 59, 59),  # Future date
                'is_dir': False,
                'should_fail': False,
            },
            {
                'name': "unicode/测试文件.txt",  # Unicode filename
                'size': 2048,
                'modified': datetime(2024, 6, 15, 12, 30, 45),
                'is_dir': False,
                'should_fail': False,
            },
            {
                'name': "special-chars/file!@#$%^&*()_+.txt",  # Special characters
                'size': 1024,
                'modified': datetime(2024, 1, 1, 12, 0, 0),
                'is_dir': False,
                'should_fail': False,
            },
            {
                'name': "deep/nested/directory/structure/file.json",  # Deep nesting
                'size': 512,
                'modified': datetime(2024, 1, 1, 12, 0, 0),
                'is_dir': False,
                'should_fail': False,
            },
        ]

        for i, case in enumerate(edge_cases):
            mock_content = Mock()
            for attr, value in case.items():
                if attr != 'should_fail':
                    setattr(mock_content, attr, value)

            if case['should_fail']:
                with pytest.raises(BackendError):
                    backend._transform_content(mock_content)
            else:
                result = backend._transform_content(mock_content)
                assert isinstance(result, Content_Info)
                assert result.path == case['name']
                assert result.size == case['size']
                assert result.type == "file" if not case['is_dir'] else "directory"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_various_size_configurations(self, mock_quilt3):
        """Test _transform_content() with various size configurations in mock content objects."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test different size configurations
        size_configurations = [
            (None, None),  # None size
            (0, 0),  # Zero size file
            (1, 1),  # Single byte file
            (1024, 1024),  # 1KB file
            (1048576, 1048576),  # 1MB file
            (1073741824, 1073741824),  # 1GB file
            (999999999999, 999999999999),  # Very large file
            ("1024", 1024),  # String size (should be converted to int)
            (1024.5, 1024),  # Float size (should be converted to int)
            ("invalid", None),  # Invalid size (should default to None)
        ]

        for input_size, expected_size in size_configurations:
            mock_content = Mock()
            mock_content.name = f"test_file_{input_size}.txt"
            mock_content.size = input_size
            mock_content.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_content.is_dir = False

            result = backend._transform_content(mock_content)
            assert result.size == expected_size, f"Failed for input size: {input_size}"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_various_datetime_configurations(self, mock_quilt3):
        """Test _transform_content() with various datetime configurations in mock content objects."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test different datetime configurations
        datetime_configurations = [
            (None, None),  # None datetime
            (datetime(2024, 1, 1, 12, 0, 0), "2024-01-01T12:00:00"),  # Standard datetime
            (datetime(2024, 12, 31, 23, 59, 59, 999999), "2024-12-31T23:59:59.999999"),  # With microseconds
            ("2024-01-01T12:00:00Z", "2024-01-01T12:00:00Z"),  # String datetime
            ("custom_date_string", "custom_date_string"),  # Custom string
            (123456789, "123456789"),  # Numeric timestamp
        ]

        for input_datetime, expected_datetime in datetime_configurations:
            mock_content = Mock()
            mock_content.name = f"test_file_{hash(str(input_datetime))}.txt"
            mock_content.size = 1024
            mock_content.modified = input_datetime
            mock_content.is_dir = False

            result = backend._transform_content(mock_content)
            assert result.modified_date == expected_datetime, f"Failed for input datetime: {input_datetime}"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_various_path_configurations(self, mock_quilt3):
        """Test _transform_content() with various path configurations in mock content objects."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test different path configurations
        path_configurations = [
            ("simple.txt", "file"),
            ("folder/", "directory"),
            ("deep/nested/path/file.json", "file"),
            ("deep/nested/path/", "directory"),
            ("file-with-dashes.csv", "file"),
            ("file_with_underscores.txt", "file"),
            ("file.with.dots.log", "file"),
            ("UPPERCASE_FILE.TXT", "file"),
            ("mixedCaseFile.Json", "file"),
            ("123numeric-file.dat", "file"),
            ("unicode-文件.txt", "file"),
            ("special!@#$%file.bin", "file"),
            ("very-long-filename-with-many-characters-and-extensions.data.backup.gz", "file"),
        ]

        for path, expected_type in path_configurations:
            mock_content = Mock()
            mock_content.name = path
            mock_content.size = 1024 if expected_type == "file" else None
            mock_content.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_content.is_dir = expected_type == "directory"

            result = backend._transform_content(mock_content)
            assert result.path == path, f"Failed for path: {path}"
            assert result.type == expected_type, f"Failed for path type: {path}"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_mock_object_missing_attributes(self, mock_quilt3):
        """Test _transform_content() with mock content objects missing required attributes."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test missing required attributes
        required_attributes = ['name']  # Only 'name' is truly required for content

        for missing_attr in required_attributes:
            mock_content = Mock()
            # Set all typical attributes
            mock_content.name = "test_file.txt"
            mock_content.size = 1024
            mock_content.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_content.is_dir = False

            # Remove the specific required attribute
            delattr(mock_content, missing_attr)

            with pytest.raises(BackendError) as exc_info:
                backend._transform_content(mock_content)

            assert "missing name" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_mock_object_none_attributes(self, mock_quilt3):
        """Test _transform_content() with mock content objects having None required attributes."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test None values for required attributes
        required_attributes = ['name']

        for none_attr in required_attributes:
            mock_content = Mock()
            # Set all typical attributes
            mock_content.name = "test_file.txt"
            mock_content.size = 1024
            mock_content.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_content.is_dir = False

            # Set the specific required attribute to None
            setattr(mock_content, none_attr, None)

            with pytest.raises(BackendError) as exc_info:
                backend._transform_content(mock_content)

            assert "missing name" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_mock_object_type_variations(self, mock_quilt3):
        """Test _transform_content() with different types of mock content objects."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with different mock object types
        mock_types = [
            Mock(),  # Standard Mock
            MagicMock(),  # MagicMock
            type('CustomContent', (), {})(),  # Custom class instance
            type('MockContent', (object,), {})(),  # Object subclass
        ]

        for i, mock_content in enumerate(mock_types):
            # Set required attributes
            mock_content.name = f"test_file_{i}.txt"
            mock_content.size = 1024 + i
            mock_content.modified = datetime(2024, 1, 1, 12, i, 0)
            mock_content.is_dir = False

            result = backend._transform_content(mock_content)
            assert isinstance(result, Content_Info)
            assert result.path == f"test_file_{i}.txt"
            assert result.size == 1024 + i
            assert result.type == "file"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_mock_object_directory_detection(self, mock_quilt3):
        """Test _transform_content() correctly detects directories vs files with mock objects."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test directory detection scenarios
        detection_scenarios = [
            # (name, is_dir, expected_type)
            ("file.txt", False, "file"),
            ("directory/", True, "directory"),
            ("file_without_extension", False, "file"),
            ("nested/directory/", True, "directory"),
            ("file.with.multiple.dots.txt", False, "file"),
            ("UPPERCASE_DIRECTORY/", True, "directory"),
            ("123numeric_directory/", True, "directory"),
            ("unicode_目录/", True, "directory"),
            ("special-chars!@#$/", True, "directory"),
        ]

        for name, is_dir, expected_type in detection_scenarios:
            mock_content = Mock()
            mock_content.name = name
            mock_content.size = None if is_dir else 1024
            mock_content.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_content.is_dir = is_dir

            result = backend._transform_content(mock_content)
            assert result.type == expected_type, f"Failed for {name} (is_dir={is_dir})"
            assert result.path == name

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_mock_object_attribute_access_patterns(self, mock_quilt3):
        """Test _transform_content() handles various attribute access patterns with mock objects."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test content with attributes that raise exceptions when accessed
        class ProblematicContent:
            def __init__(self):
                self.name = "problematic_file.txt"
                self.is_dir = False

            @property
            def size(self):
                # This property raises an exception when accessed
                raise AttributeError("Size access failed")

            @property
            def modified(self):
                # This property returns an unexpected type
                return {"not": "a datetime"}

        problematic_content = ProblematicContent()

        # The transformation should succeed because size and modified are optional
        # and the implementation handles exceptions gracefully by using getattr with defaults
        result = backend._transform_content(problematic_content)

        # Verify it still creates a valid Content_Info object
        assert isinstance(result, Content_Info)
        assert result.path == "problematic_file.txt"
        assert result.type == "file"
        # Size should be None due to the exception being caught by getattr default
        assert result.size is None
        # Modified should be handled by the normalization function
        assert result.modified_date is not None  # The normalization converts the dict to string

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_mock_object_performance_edge_cases(self, mock_quilt3):
        """Test _transform_content() handles performance edge cases with large mock data."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with very large data structures
        mock_content = Mock()
        mock_content.name = "performance/" + "x" * 1000 + ".txt"  # Very long path
        mock_content.size = 999999999999  # Very large size
        mock_content.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_content.is_dir = False

        # Should handle large data without issues
        result = backend._transform_content(mock_content)

        assert isinstance(result, Content_Info)
        assert len(result.path) == 1016  # "performance/" + 1000 x's + ".txt"
        assert result.size == 999999999999
        assert result.type == "file"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_mock_object_comprehensive_validation(self, mock_quilt3):
        """Test _transform_content() comprehensive validation with various mock object configurations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test comprehensive validation scenarios
        validation_scenarios = [
            {
                'name': 'valid_file_complete',
                'config': {
                    'name': 'valid/file.txt',
                    'size': 2048,
                    'modified': datetime(2024, 1, 1, 12, 0, 0),
                    'is_dir': False,
                },
                'should_pass': True,
                'expected_type': 'file',
            },
            {
                'name': 'valid_directory_complete',
                'config': {
                    'name': 'valid/directory/',
                    'size': None,
                    'modified': datetime(2024, 1, 1, 12, 0, 0),
                    'is_dir': True,
                },
                'should_pass': True,
                'expected_type': 'directory',
            },
            {
                'name': 'empty_name',
                'config': {'name': '', 'size': 1024, 'modified': datetime(2024, 1, 1, 12, 0, 0), 'is_dir': False},
                'should_pass': False,
                'expected_error': 'empty',
            },
            {
                'name': 'none_name',
                'config': {'name': None, 'size': 1024, 'modified': datetime(2024, 1, 1, 12, 0, 0), 'is_dir': False},
                'should_pass': False,
                'expected_error': 'missing name',
            },
        ]

        for scenario in validation_scenarios:
            mock_content = Mock()
            for attr, value in scenario['config'].items():
                setattr(mock_content, attr, value)

            if scenario['should_pass']:
                result = backend._transform_content(mock_content)
                assert isinstance(result, Content_Info)
                assert result.path == scenario['config']['name']
                assert result.type == scenario['expected_type']
            else:
                with pytest.raises(BackendError) as exc_info:
                    backend._transform_content(mock_content)

                error_message = str(exc_info.value).lower()
                assert scenario['expected_error'] in error_message

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_missing_fields(self, mock_quilt3):
        """Test _transform_content() handles missing/null fields in quilt3 objects."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create mock content entry with missing fields
        mock_entry = Mock()
        mock_entry.name = "folder/"
        mock_entry.size = None
        mock_entry.modified = None
        mock_entry.is_dir = True

        # Execute transformation
        result = backend._transform_content(mock_entry)

        # Verify
        assert result.path == "folder/"
        assert result.size is None
        assert result.type == "directory"
        assert result.modified_date is None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_error_handling(self, mock_quilt3):
        """Test _transform_content() error handling in transformation logic."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create mock entry that will cause transformation error
        mock_entry = Mock()
        mock_entry.name = None  # Invalid name

        with pytest.raises(BackendError):
            backend._transform_content(mock_entry)

        # Create mock entry that will cause transformation error
        mock_entry = Mock()
        mock_entry.name = None  # Invalid name

        with pytest.raises(BackendError):
            backend._transform_content(mock_entry)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_error_wrapping_and_context(self, mock_quilt3):
        """Test that content transformation errors are properly wrapped in BackendError with context."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various error scenarios for content transformation
        error_scenarios = [
            # Missing name attribute
            {
                'setup': lambda entry: delattr(entry, 'name'),
                'expected_message': 'missing name',
                'description': 'missing name attribute',
            },
            # None name
            {
                'setup': lambda entry: setattr(entry, 'name', None),
                'expected_message': 'missing name',
                'description': 'None name',
            },
            # Empty name
            {
                'setup': lambda entry: setattr(entry, 'name', ''),
                'expected_message': 'empty name',
                'description': 'empty name',
            },
        ]

        for scenario in error_scenarios:
            # Create fresh mock entry for each test
            mock_entry = Mock()
            mock_entry.name = "test_file.txt"
            mock_entry.size = 1024
            mock_entry.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_entry.is_dir = False

            # Apply the error scenario setup
            scenario['setup'](mock_entry)

            # Test that error is wrapped in BackendError
            with pytest.raises(BackendError) as exc_info:
                backend._transform_content(mock_entry)

            error = exc_info.value
            error_message = str(error)

            # Verify error message contains expected content
            assert scenario['expected_message'].lower() in error_message.lower(), (
                f"Expected '{scenario['expected_message']}' in error message for {scenario['description']}"
            )

            # Verify error is properly wrapped as BackendError
            assert isinstance(error, BackendError), f"Error should be BackendError for {scenario['description']}"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_error_message_clarity(self, mock_quilt3):
        """Test that content transformation error messages are clear and actionable."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test error message clarity for different failure types
        clarity_tests = [
            {
                'name': 'missing_name_attribute',
                'setup': lambda entry: delattr(entry, 'name'),
                'expected_keywords': ['missing', 'name', 'content', 'transformation'],
            },
            {
                'name': 'empty_name_field',
                'setup': lambda entry: setattr(entry, 'name', ''),
                'expected_keywords': ['empty', 'name', 'content', 'transformation'],
            },
        ]

        for test_case in clarity_tests:
            mock_entry = Mock()
            mock_entry.name = "test_file.txt"
            mock_entry.size = 1024
            mock_entry.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_entry.is_dir = False

            test_case['setup'](mock_entry)

            with pytest.raises(BackendError) as exc_info:
                backend._transform_content(mock_entry)

            error_message = str(exc_info.value).lower()

            # Verify error message contains expected keywords for clarity
            for keyword in test_case['expected_keywords']:
                assert keyword.lower() in error_message, (
                    f"Error message should contain '{keyword}' for {test_case['name']}: {error_message}"
                )

            # Verify error message mentions the backend type
            assert 'quilt3' in error_message, (
                f"Error message should mention backend type for {test_case['name']}: {error_message}"
            )

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_error_propagation_from_helpers(self, mock_quilt3):
        """Test that errors from content transformation helper methods are properly propagated."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test error propagation from validation helper
        mock_entry = Mock()
        mock_entry.name = None  # This will trigger _validate_content_fields error

        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(mock_entry)

        # Verify the validation error is properly propagated
        assert "missing name" in str(exc_info.value).lower()

        # Test error propagation from normalization helpers
        mock_entry.name = "test_file.txt"

        # Mock the _normalize_datetime method to raise an error
        with patch.object(backend, '_normalize_datetime', side_effect=ValueError("Invalid datetime format")):
            mock_entry.modified = "invalid-datetime"

            with pytest.raises(BackendError) as exc_info:
                backend._transform_content(mock_entry)

            # Verify the normalization error is properly propagated
            assert "transformation failed" in str(exc_info.value).lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_various_transformation_failures(self, mock_quilt3):
        """Test various types of content transformation failures and their error handling."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test different types of transformation failures
        failure_scenarios = [
            {
                'name': 'content_info_creation_failure',
                'mock_target': 'quilt_mcp.backends.quilt3_backend_content.Content_Info',
                'mock_side_effect': ValueError("Content_Info creation failed"),
                'expected_error': 'content_info creation failed',
            }
        ]

        for scenario in failure_scenarios:
            with patch(scenario['mock_target'], side_effect=scenario['mock_side_effect']):
                mock_entry = Mock()
                mock_entry.name = "test_file.txt"
                mock_entry.size = 1024
                mock_entry.modified = datetime(2024, 1, 1, 12, 0, 0)
                mock_entry.is_dir = False

                with pytest.raises(BackendError) as exc_info:
                    backend._transform_content(mock_entry)

                assert scenario['expected_error'] in str(exc_info.value).lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_various_path_formats(self, mock_quilt3):
        """Test _transform_content() handles various path formats correctly."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        path_formats = [
            "simple.txt",
            "folder/file.csv",
            "deep/nested/folder/structure/file.json",
            "file-with-dashes.txt",
            "file_with_underscores.py",
            "file.with.dots.in.name.txt",
            "123numeric-file.dat",
            "unicode-文件名.txt",
            "folder/",  # Directory
            "nested/folder/",  # Nested directory
        ]

        for path in path_formats:
            mock_entry = Mock()
            mock_entry.name = path
            mock_entry.size = 1024 if not path.endswith('/') else None
            mock_entry.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_entry.is_dir = path.endswith('/')

            result = backend._transform_content(mock_entry)

            assert isinstance(result, Content_Info)
            assert result.path == path
            assert result.type == ("directory" if path.endswith('/') else "file")

        # Test empty path (should cause error due to validation)
        mock_entry = Mock()
        mock_entry.name = ""  # Empty path
        mock_entry.size = 0
        mock_entry.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_entry.is_dir = False

        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(mock_entry)

        assert "transformation failed" in str(exc_info.value).lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_various_sizes(self, mock_quilt3):
        """Test _transform_content() handles various file sizes correctly."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        size_scenarios = [
            0,  # Empty file
            1,  # Single byte
            1024,  # 1KB
            1024 * 1024,  # 1MB
            1024 * 1024 * 1024,  # 1GB
            None,  # No size (directory or unknown)
        ]

        for size in size_scenarios:
            mock_entry = Mock()
            mock_entry.name = f"file_{size}.txt" if size is not None else "folder/"
            mock_entry.size = size
            mock_entry.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_entry.is_dir = size is None

            result = backend._transform_content(mock_entry)

            assert result.size == size
            assert result.type == ("directory" if size is None else "file")

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_various_date_formats(self, mock_quilt3):
        """Test _transform_content() handles various date formats correctly."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        date_scenarios = [
            datetime(2024, 1, 1, 12, 0, 0),  # datetime object
            None,  # No modification date
            "2024-01-01T12:00:00Z",  # String date (if passed as string)
        ]

        for modified_date in date_scenarios:
            mock_entry = Mock()
            mock_entry.name = "test_file.txt"
            mock_entry.size = 1024
            mock_entry.modified = modified_date
            mock_entry.is_dir = False

            result = backend._transform_content(mock_entry)

            if modified_date is None:
                assert result.modified_date is None
            elif isinstance(modified_date, datetime):
                assert result.modified_date == modified_date.isoformat()
            else:
                assert result.modified_date == str(modified_date)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_directory_vs_file_detection(self, mock_quilt3):
        """Test _transform_content() correctly detects directories vs files."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test file
        mock_file = Mock()
        mock_file.name = "data.csv"
        mock_file.size = 2048
        mock_file.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_file.is_dir = False

        result = backend._transform_content(mock_file)
        assert result.type == "file"
        assert result.size == 2048

        # Test directory
        mock_dir = Mock()
        mock_dir.name = "folder/"
        mock_dir.size = None
        mock_dir.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_dir.is_dir = True

        result = backend._transform_content(mock_dir)
        assert result.type == "directory"
        assert result.size is None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_missing_optional_attributes(self, mock_quilt3):
        """Test _transform_content() handles missing optional attributes gracefully."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create minimal mock entry with only required attributes
        mock_entry = Mock()
        mock_entry.name = "minimal_file.txt"
        # Set default values for attributes that might be missing
        mock_entry.size = None
        mock_entry.modified = None
        mock_entry.is_dir = False

        result = backend._transform_content(mock_entry)

        assert result.path == "minimal_file.txt"
        assert result.size is None
        assert result.type == "file"
        assert result.modified_date is None
        assert result.download_url is None


class TestQuilt3BackendContentTransformationIsolated:
    """Test _transform_content() method in complete isolation with focus on transformation logic."""

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_isolated_with_complete_mock_entry(self, mock_quilt3):
        """Test _transform_content() method in isolation with complete mock quilt3 content entry."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create complete mock content entry with all fields
        mock_entry = Mock()
        mock_entry.name = "complete/data.csv"
        mock_entry.size = 2048
        mock_entry.modified = datetime(2024, 3, 15, 14, 30, 45)
        mock_entry.is_dir = False

        # Execute transformation in isolation
        result = backend._transform_content(mock_entry)

        # Verify transformation produces correct Content_Info
        assert isinstance(result, Content_Info)
        assert result.path == "complete/data.csv"
        assert result.size == 2048
        assert result.type == "file"
        assert result.modified_date == "2024-03-15T14:30:45"
        assert result.download_url is None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_isolated_with_minimal_mock_entry(self, mock_quilt3):
        """Test _transform_content() method in isolation with minimal mock quilt3 content entry."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create minimal mock content entry with only required fields
        mock_entry = Mock()
        mock_entry.name = "minimal/file.txt"
        mock_entry.size = None  # Optional field
        mock_entry.modified = None  # Optional field
        mock_entry.is_dir = False  # Optional field (defaults to False)

        # Execute transformation in isolation
        result = backend._transform_content(mock_entry)

        # Verify transformation handles minimal data correctly
        assert isinstance(result, Content_Info)
        assert result.path == "minimal/file.txt"
        assert result.size is None
        assert result.type == "file"  # Should default to file when is_dir is False
        assert result.modified_date is None
        assert result.download_url is None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_isolated_directory_detection(self, mock_quilt3):
        """Test _transform_content() directory detection logic in isolation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test directory detection scenarios
        directory_scenarios = [
            (True, "directory"),  # is_dir=True -> directory
            (False, "file"),  # is_dir=False -> file
            (None, "file"),  # is_dir=None -> file (default)
        ]

        for is_dir_value, expected_type in directory_scenarios:
            mock_entry = Mock()
            mock_entry.name = f"test-{expected_type}"
            mock_entry.size = None if expected_type == "directory" else 1024
            mock_entry.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_entry.is_dir = is_dir_value

            result = backend._transform_content(mock_entry)

            assert result.type == expected_type, f"Failed for is_dir={is_dir_value}"
            assert result.path == f"test-{expected_type}"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_isolated_validation_logic(self, mock_quilt3):
        """Test _transform_content() validation logic in isolation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test validation of required fields
        required_field_tests = [
            (None, "missing name"),
            ("", "empty name"),
        ]

        for name_value, expected_error in required_field_tests:
            mock_entry = Mock()
            mock_entry.name = name_value
            mock_entry.size = 1024
            mock_entry.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_entry.is_dir = False

            with pytest.raises(BackendError) as exc_info:
                backend._transform_content(mock_entry)

            assert expected_error in str(exc_info.value).lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_isolated_helper_method_integration(self, mock_quilt3):
        """Test _transform_content() integration with helper methods in isolation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create mock entry that exercises all helper methods
        mock_entry = Mock()
        mock_entry.name = "helper/integration.txt"
        mock_entry.size = 0  # Tests _normalize_size with zero
        mock_entry.modified = datetime(2024, 2, 15, 14, 30, 45)  # Tests _normalize_datetime
        mock_entry.is_dir = False  # Tests _determine_content_type

        # Execute transformation
        result = backend._transform_content(mock_entry)

        # Verify helper method results are correctly integrated
        assert result.path == "helper/integration.txt"
        assert result.size == 0  # _normalize_size preserves zero
        assert result.type == "file"  # _determine_content_type returns file for is_dir=False
        assert result.modified_date == "2024-02-15T14:30:45"  # _normalize_datetime converts datetime
        assert result.download_url is None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_isolated_error_context_preservation(self, mock_quilt3):
        """Test _transform_content() error context preservation in isolation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create mock entry that will cause a domain validation error
        # Use negative size which should trigger Content_Info validation error
        mock_entry = Mock()
        mock_entry.name = "error-test.txt"  # Valid name to pass validation
        mock_entry.size = -1  # Negative size will cause Content_Info validation error
        mock_entry.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_entry.is_dir = False

        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(mock_entry)

        error_message = str(exc_info.value)
        # Verify error context is preserved for domain validation errors
        assert "quilt3 backend content transformation failed" in error_message.lower()
        assert "size field cannot be negative" in error_message.lower()

        # Verify error context includes entry information
        error_context = exc_info.value.context
        assert error_context['entry_name'] == "error-test.txt"
        assert error_context['entry_type'] == "Mock"
        assert 'available_attributes' in error_context

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_isolated_with_edge_case_inputs(self, mock_quilt3):
        """Test _transform_content() with edge case inputs in isolation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with edge case values
        edge_cases = [
            {
                'name': "a" * 1000,  # Very long name
                'size': 0,  # Zero size
                'modified': datetime(1970, 1, 1, 0, 0, 0),  # Unix epoch
                'is_dir': False,
            },
            {
                'name': "unicode/测试文件.txt",  # Unicode filename
                'size': 999999999999,  # Very large size
                'modified': datetime(2099, 12, 31, 23, 59, 59),  # Future date
                'is_dir': False,
            },
            {
                'name': "special-chars/file!@#$%^&*()_+.txt",  # Special characters
                'size': None,  # None size
                'modified': None,  # None modified
                'is_dir': True,  # Directory
            },
        ]

        for i, edge_case in enumerate(edge_cases):
            mock_entry = Mock()
            for attr, value in edge_case.items():
                setattr(mock_entry, attr, value)

            # Should handle edge cases without error
            result = backend._transform_content(mock_entry)

            assert isinstance(result, Content_Info)
            assert result.path == edge_case['name']
            assert result.size == edge_case['size']
            assert result.type == ("directory" if edge_case['is_dir'] else "file")


class TestQuilt3BackendContentTransformationMissingNullFields:
    """Test handling of missing/null fields in quilt3 content objects during transformation."""

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_missing_optional_attributes_comprehensive(self, mock_quilt3):
        """Test _transform_content() handles missing optional attributes comprehensively."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test scenarios where optional attributes are completely missing
        missing_attribute_scenarios = [
            {'missing': 'size', 'expected_size': None},
            {'missing': 'modified', 'expected_modified': None},
            {'missing': 'is_dir', 'expected_type': 'file'},  # Should default to file
        ]

        for scenario in missing_attribute_scenarios:
            mock_entry = Mock()
            mock_entry.name = f"missing-{scenario['missing']}.txt"

            # Set all attributes first
            mock_entry.size = 1024
            mock_entry.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_entry.is_dir = False

            # Remove the specific attribute to test missing field handling
            delattr(mock_entry, scenario['missing'])

            result = backend._transform_content(mock_entry)

            assert isinstance(result, Content_Info)
            assert result.path == f"missing-{scenario['missing']}.txt"

            # Verify missing field handling
            if 'expected_size' in scenario:
                assert result.size == scenario['expected_size']
            if 'expected_modified' in scenario:
                assert result.modified_date == scenario['expected_modified']
            if 'expected_type' in scenario:
                assert result.type == scenario['expected_type']

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_null_optional_fields_comprehensive(self, mock_quilt3):
        """Test _transform_content() handles null/None values in optional fields comprehensively."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various null/None scenarios for optional fields
        null_scenarios = [
            {
                'name': 'all-null.txt',
                'size': None,
                'modified': None,
                'is_dir': None,
                'expected_size': None,
                'expected_modified': None,
                'expected_type': 'file',  # None is_dir should default to file
            },
            {
                'name': 'mixed-null.txt',
                'size': 0,  # Valid zero size
                'modified': None,  # Null modified
                'is_dir': False,  # Valid is_dir
                'expected_size': 0,
                'expected_modified': None,
                'expected_type': 'file',
            },
            {
                'name': 'directory-null.txt',
                'size': None,  # Null size (common for directories)
                'modified': datetime(2024, 1, 1, 12, 0, 0),  # Valid modified
                'is_dir': True,  # Directory
                'expected_size': None,
                'expected_modified': '2024-01-01T12:00:00',
                'expected_type': 'directory',
            },
        ]

        for scenario in null_scenarios:
            mock_entry = Mock()
            mock_entry.name = scenario['name']
            mock_entry.size = scenario['size']
            mock_entry.modified = scenario['modified']
            mock_entry.is_dir = scenario['is_dir']

            result = backend._transform_content(mock_entry)

            assert isinstance(result, Content_Info)
            assert result.path == scenario['name']
            assert result.size == scenario['expected_size']
            assert result.modified_date == scenario['expected_modified']
            assert result.type == scenario['expected_type']
            assert result.download_url is None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_missing_required_name_attribute(self, mock_quilt3):
        """Test _transform_content() properly fails when required name attribute is missing."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test missing name attribute
        mock_entry = Mock()
        mock_entry.size = 1024
        mock_entry.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_entry.is_dir = False

        # Remove the required name attribute
        if hasattr(mock_entry, 'name'):
            delattr(mock_entry, 'name')

        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(mock_entry)

        error_message = str(exc_info.value)
        assert "missing name" in error_message.lower()
        assert "content transformation failed" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_null_required_name_field(self, mock_quilt3):
        """Test _transform_content() properly fails when required name field is None or empty."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test None name
        mock_entry = Mock()
        mock_entry.name = None
        mock_entry.size = 1024
        mock_entry.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_entry.is_dir = False

        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(mock_entry)

        error_message = str(exc_info.value)
        assert "missing name" in error_message.lower()

        # Test empty name
        mock_entry.name = ""

        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(mock_entry)

        error_message = str(exc_info.value)
        assert "empty name" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_empty_string_fields(self, mock_quilt3):
        """Test _transform_content() handles empty string values appropriately."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test empty strings in various fields
        mock_entry = Mock()
        mock_entry.name = "valid-name.txt"  # Valid name
        mock_entry.size = ""  # Empty string size (should be handled by normalization)
        mock_entry.modified = ""  # Empty string modified (should be handled by normalization)
        mock_entry.is_dir = False

        # Should handle empty strings gracefully through normalization
        result = backend._transform_content(mock_entry)

        assert isinstance(result, Content_Info)
        assert result.path == "valid-name.txt"
        # Empty string size should be normalized to None or handled appropriately
        # Empty string modified should be normalized to None or handled appropriately
        assert result.type == "file"
        assert result.download_url is None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_malformed_size_fields(self, mock_quilt3):
        """Test _transform_content() handles malformed size fields appropriately."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various malformed size scenarios
        size_scenarios = [
            (None, None),  # None size (should be handled gracefully)
            (0, 0),  # Zero size (valid)
            (-1, None),  # Negative size (should cause domain validation error)
            ("invalid-size", None),  # String size (should be normalized to None)
            (3.14, 3),  # Float size (should be converted to int)
            ({"invalid": "object"}, None),  # Invalid object type (should be normalized to None)
        ]

        for i, (size_value, expected_result) in enumerate(size_scenarios):
            mock_entry = Mock()
            mock_entry.name = f"size-test-{i}.txt"
            mock_entry.size = size_value
            mock_entry.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_entry.is_dir = False

            if size_value == -1:
                # Negative size should cause domain validation error in Content_Info
                with pytest.raises(BackendError) as exc_info:
                    backend._transform_content(mock_entry)
                assert "size field cannot be negative" in str(exc_info.value)
            else:
                # Other cases should be handled gracefully
                result = backend._transform_content(mock_entry)
                assert isinstance(result, Content_Info)
                assert result.path == f"size-test-{i}.txt"
                assert result.size == expected_result

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_malformed_datetime_fields(self, mock_quilt3):
        """Test _transform_content() handles malformed datetime fields appropriately."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various malformed datetime scenarios
        datetime_scenarios = [
            None,  # None datetime (should be handled gracefully)
            "invalid-date-string",  # Invalid string
            "",  # Empty string
            123456789,  # Numeric timestamp (should be converted to string)
            "2024-13-45T25:70:80",  # Invalid date components
            {"invalid": "object"},  # Invalid object type
        ]

        for i, modified_value in enumerate(datetime_scenarios):
            mock_entry = Mock()
            mock_entry.name = f"datetime-test-{i}.txt"
            mock_entry.size = 1024
            mock_entry.modified = modified_value
            mock_entry.is_dir = False

            # All cases should be handled gracefully by _normalize_datetime
            result = backend._transform_content(mock_entry)
            assert isinstance(result, Content_Info)
            assert result.path == f"datetime-test-{i}.txt"

            if modified_value is None:
                assert result.modified_date is None
            else:
                assert isinstance(result.modified_date, str)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_unexpected_field_types(self, mock_quilt3):
        """Test _transform_content() handles unexpected field types gracefully."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test unexpected types for various fields
        mock_entry = Mock()
        mock_entry.name = "valid-name.txt"  # Use valid string name to avoid domain validation error
        mock_entry.size = "1024"  # String instead of number (should be normalized)
        mock_entry.modified = "2024-01-01T12:00:00Z"  # String datetime (should be handled)
        mock_entry.is_dir = "false"  # String instead of boolean (should be handled)

        # Should handle type conversion gracefully for most fields
        result = backend._transform_content(mock_entry)

        assert isinstance(result, Content_Info)
        assert result.path == "valid-name.txt"  # Valid string name preserved
        assert result.size == 1024  # String size normalized to int
        assert result.modified_date == "2024-01-01T12:00:00Z"  # String datetime preserved
        # Type determination should handle string is_dir appropriately

        # Test case that should fail due to domain validation (non-string path)
        mock_entry_invalid = Mock()
        mock_entry_invalid.name = 12345  # Number instead of string (should cause domain validation error)
        mock_entry_invalid.size = 1024
        mock_entry_invalid.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_entry_invalid.is_dir = False

        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(mock_entry_invalid)

        assert "path field must be a string" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_mock_entry_missing_attributes(self, mock_quilt3):
        """Test _transform_content() with mock entries missing various attributes."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test missing optional attributes one by one
        optional_attributes = ['size', 'modified', 'is_dir']

        for missing_attr in optional_attributes:
            mock_entry = Mock()
            # Set all attributes first
            mock_entry.name = f"missing-{missing_attr}.txt"
            mock_entry.size = 1024
            mock_entry.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_entry.is_dir = False

            # Remove the specific optional attribute
            delattr(mock_entry, missing_attr)

            # Should handle missing optional attributes gracefully
            result = backend._transform_content(mock_entry)

            assert isinstance(result, Content_Info)
            assert result.path == f"missing-{missing_attr}.txt"

            # Verify defaults for missing attributes
            if missing_attr == 'size':
                assert result.size is None
            if missing_attr == 'modified':
                assert result.modified_date is None
            if missing_attr == 'is_dir':
                assert result.type == "file"  # Should default to file

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_error_handling_comprehensive(self, mock_quilt3):
        """Test comprehensive error handling in _transform_content() transformation logic."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various error scenarios that should be caught and wrapped
        error_scenarios = [
            {
                'name': None,  # None name should cause validation error
                'size': 1024,
                'modified': datetime(2024, 1, 1),
                'is_dir': False,
                'expected_error': 'missing name',
                'has_context': False,  # Validation errors don't have context
            },
            {
                'name': "",  # Empty name should cause validation error
                'size': 1024,
                'modified': datetime(2024, 1, 1),
                'is_dir': False,
                'expected_error': 'empty name',
                'has_context': False,  # Validation errors don't have context
            },
        ]

        for scenario in error_scenarios:
            mock_entry = Mock()
            mock_entry.name = scenario['name']
            mock_entry.size = scenario['size']
            mock_entry.modified = scenario['modified']
            mock_entry.is_dir = scenario['is_dir']

            with pytest.raises(BackendError) as exc_info:
                backend._transform_content(mock_entry)

            error_message = str(exc_info.value)
            assert scenario['expected_error'] in error_message.lower()
            # The actual error message format from _validate_content_fields
            assert "content transformation failed" in error_message.lower()

            # Verify error context is included only for non-validation errors
            if scenario['has_context']:
                assert hasattr(exc_info.value, 'context')
                assert 'entry_name' in exc_info.value.context
                assert 'entry_type' in exc_info.value.context
                assert 'available_attributes' in exc_info.value.context
            else:
                # Validation errors don't include context
                assert not hasattr(exc_info.value, 'context') or not exc_info.value.context

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_edge_case_attribute_access_patterns(self, mock_quilt3):
        """Test transformation handles various attribute access patterns and edge cases."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test entry with attributes that cause domain validation errors
        # Use negative size which will cause Content_Info validation error
        mock_entry = Mock()
        mock_entry.name = "problematic/file.txt"
        mock_entry.size = -1  # Negative size causes domain validation error
        mock_entry.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_entry.is_dir = False

        # Should handle domain validation errors by raising BackendError
        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(mock_entry)

        error_message = str(exc_info.value)
        assert "transformation failed" in error_message.lower()
        # The error should be wrapped in the general transformation error
        assert "quilt3 backend content transformation failed" in error_message.lower()
        assert "size field cannot be negative" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_various_mock_object_types(self, mock_quilt3):
        """Test _transform_content() with different types of mock content objects."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with different mock object types
        mock_types = [
            Mock(),  # Standard Mock
            MagicMock(),  # MagicMock
            type('MockEntry', (), {})(),  # Custom class instance
        ]

        for i, mock_entry in enumerate(mock_types):
            # Set attributes on each mock type
            mock_entry.name = f"test/file-{i}.txt"
            mock_entry.size = 1024 * (i + 1)
            mock_entry.modified = datetime(2024, 1, 1, 12, i, 0)
            mock_entry.is_dir = i % 2 == 0  # Alternate between file and directory

            result = backend._transform_content(mock_entry)

            assert isinstance(result, Content_Info)
            assert result.path == f"test/file-{i}.txt"
            assert result.size == 1024 * (i + 1)
            assert result.type == ("file" if i % 2 != 0 else "directory")


class TestQuilt3BackendTransformContentMethodIsolated:
    """Dedicated unit tests for _transform_content() method in complete isolation.

    This test class focuses specifically on testing the _transform_content() method
    with mock quilt3 content objects, testing transformation logic, error handling,
    and edge cases in isolation from broader integration concerns.
    """

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_complete_mock_quilt3_object(self, mock_quilt3):
        """Test _transform_content() with a complete mock quilt3 content object."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create comprehensive mock quilt3 content object
        mock_content = Mock()
        mock_content.name = "data/analysis/results.csv"
        mock_content.size = 1048576  # 1MB
        mock_content.modified = datetime(2024, 3, 15, 14, 30, 45, 123456)
        mock_content.is_dir = False

        # Execute transformation in isolation
        result = backend._transform_content(mock_content)

        # Verify complete transformation
        assert isinstance(result, Content_Info)
        assert result.path == "data/analysis/results.csv"
        assert result.size == 1048576
        assert result.type == "file"
        assert result.modified_date == "2024-03-15T14:30:45.123456"
        assert result.download_url is None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_directory_mock_object(self, mock_quilt3):
        """Test _transform_content() with mock quilt3 directory object."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create mock directory object
        mock_directory = Mock()
        mock_directory.name = "data/raw_data/"
        mock_directory.size = None  # Directories typically don't have size
        mock_directory.modified = datetime(2024, 2, 10, 9, 15, 30)
        mock_directory.is_dir = True

        # Execute transformation
        result = backend._transform_content(mock_directory)

        # Verify directory transformation
        assert isinstance(result, Content_Info)
        assert result.path == "data/raw_data/"
        assert result.size is None
        assert result.type == "directory"
        assert result.modified_date == "2024-02-10T09:15:30"
        assert result.download_url is None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_minimal_mock_object(self, mock_quilt3):
        """Test _transform_content() with minimal mock quilt3 content object."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create minimal mock content object (only required fields)
        mock_content = Mock()
        mock_content.name = "minimal.txt"
        # Optional fields are missing or None
        mock_content.size = None
        mock_content.modified = None
        mock_content.is_dir = None  # Should default to False

        # Execute transformation
        result = backend._transform_content(mock_content)

        # Verify minimal transformation handles defaults correctly
        assert isinstance(result, Content_Info)
        assert result.path == "minimal.txt"
        assert result.size is None
        assert result.type == "file"  # Should default to file when is_dir is None
        assert result.modified_date is None
        assert result.download_url is None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_various_size_values(self, mock_quilt3):
        """Test _transform_content() handles various size values correctly."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test different size scenarios
        size_scenarios = [
            (None, None),  # None size
            (0, 0),  # Zero size (empty file)
            (1, 1),  # Single byte
            (1024, 1024),  # 1KB
            (1048576, 1048576),  # 1MB
            (1073741824, 1073741824),  # 1GB
            ("1024", 1024),  # String number (should convert)
            ("invalid", None),  # Invalid string (should convert to None)
        ]

        for input_size, expected_size in size_scenarios:
            mock_content = Mock()
            mock_content.name = f"test-size-{input_size}.txt"
            mock_content.size = input_size
            mock_content.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_content.is_dir = False

            result = backend._transform_content(mock_content)

            assert result.size == expected_size, f"Failed for input size: {input_size}"
            assert result.path == f"test-size-{input_size}.txt"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_various_datetime_formats(self, mock_quilt3):
        """Test _transform_content() handles various datetime formats correctly."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test different datetime scenarios
        datetime_scenarios = [
            (None, None),  # None datetime
            (datetime(2024, 1, 1, 12, 0, 0), "2024-01-01T12:00:00"),  # Standard datetime
            (datetime(2024, 12, 31, 23, 59, 59, 999999), "2024-12-31T23:59:59.999999"),  # With microseconds
            ("2024-01-01T12:00:00Z", "2024-01-01T12:00:00Z"),  # String datetime (preserved)
            ("custom_timestamp", "custom_timestamp"),  # Custom string (preserved)
        ]

        for input_datetime, expected_datetime in datetime_scenarios:
            mock_content = Mock()
            mock_content.name = "test-datetime.txt"
            mock_content.size = 1024
            mock_content.modified = input_datetime
            mock_content.is_dir = False

            result = backend._transform_content(mock_content)

            assert result.modified_date == expected_datetime, f"Failed for input datetime: {input_datetime}"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_various_path_formats(self, mock_quilt3):
        """Test _transform_content() handles various path formats correctly."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test different path formats
        path_scenarios = [
            "simple.txt",  # Simple filename
            "data/file.csv",  # Nested path
            "deep/nested/path/file.json",  # Deep nesting
            "file with spaces.txt",  # Spaces in filename
            "file-with-dashes_and_underscores.txt",  # Special characters
            "unicode_文件名.txt",  # Unicode characters
            "file.with.multiple.dots.txt",  # Multiple dots
            "UPPERCASE_FILE.TXT",  # Uppercase
            "123numeric_start.txt",  # Numeric start
            ".hidden_file",  # Hidden file
            "folder/",  # Directory path
        ]

        for path in path_scenarios:
            mock_content = Mock()
            mock_content.name = path
            mock_content.size = 1024 if not path.endswith('/') else None
            mock_content.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_content.is_dir = path.endswith('/')

            result = backend._transform_content(mock_content)

            assert result.path == path, f"Path not preserved correctly for: {path}"
            assert result.type == ("directory" if path.endswith('/') else "file")

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_missing_required_fields(self, mock_quilt3):
        """Test _transform_content() error handling when required fields are missing."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test missing name attribute
        mock_content_no_name = Mock()
        mock_content_no_name.size = 1024
        mock_content_no_name.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_content_no_name.is_dir = False
        # Remove name attribute
        if hasattr(mock_content_no_name, 'name'):
            delattr(mock_content_no_name, 'name')

        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(mock_content_no_name)

        assert "missing name" in str(exc_info.value).lower()
        assert "content transformation failed" in str(exc_info.value).lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_null_required_fields(self, mock_quilt3):
        """Test _transform_content() error handling when required fields are None or empty."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test None name
        mock_content_none_name = Mock()
        mock_content_none_name.name = None
        mock_content_none_name.size = 1024
        mock_content_none_name.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_content_none_name.is_dir = False

        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(mock_content_none_name)

        assert "missing name" in str(exc_info.value).lower()

        # Test empty name
        mock_content_empty_name = Mock()
        mock_content_empty_name.name = ""
        mock_content_empty_name.size = 1024
        mock_content_empty_name.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_content_empty_name.is_dir = False

        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(mock_content_empty_name)

        assert "empty name" in str(exc_info.value).lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_helper_method_integration(self, mock_quilt3):
        """Test _transform_content() integration with helper methods."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create mock that exercises all helper methods
        mock_content = Mock()
        mock_content.name = "integration/test.txt"
        mock_content.size = "2048"  # String that needs normalization
        mock_content.modified = datetime(2024, 1, 15, 10, 30, 45)  # Datetime that needs normalization
        mock_content.is_dir = False  # Boolean that needs type determination

        result = backend._transform_content(mock_content)

        # Verify helper methods worked correctly
        assert result.path == "integration/test.txt"
        assert result.size == 2048  # _normalize_size converted string to int
        assert result.type == "file"  # _determine_content_type returned file for is_dir=False
        assert result.modified_date == "2024-01-15T10:30:45"  # _normalize_datetime converted to ISO
        assert result.download_url is None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_error_context_preservation(self, mock_quilt3):
        """Test _transform_content() error handling and context preservation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test validation errors (raised directly from _validate_content_fields)
        class MissingNameContent:
            def __init__(self):
                pass  # No name attribute - will cause validation error

            @property
            def size(self):
                return 1024

            @property
            def modified(self):
                return datetime(2024, 1, 1, 12, 0, 0)

            @property
            def is_dir(self):
                return False

        missing_name_content = MissingNameContent()

        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(missing_name_content)

        error = exc_info.value
        error_message = str(error)

        # Verify error message for validation errors
        assert "quilt3 backend content transformation failed" in error_message.lower()
        assert "missing name" in error_message.lower()

        # Validation errors have empty context (raised directly from _validate_content_fields)
        assert hasattr(error, 'context')
        context = error.context
        assert context == {}  # Empty context for validation errors

        # Test empty name validation error
        class EmptyNameContent:
            def __init__(self):
                self.name = ""  # Empty name - will cause validation error

            @property
            def size(self):
                return 1024

            @property
            def modified(self):
                return datetime(2024, 1, 1, 12, 0, 0)

            @property
            def is_dir(self):
                return False

        empty_name_content = EmptyNameContent()

        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(empty_name_content)

        error = exc_info.value
        error_message = str(error)

        # Verify error message for empty name validation
        assert "quilt3 backend content transformation failed" in error_message.lower()
        assert "empty name" in error_message.lower()

        # Validation errors have empty context
        assert hasattr(error, 'context')
        context = error.context
        assert context == {}  # Empty context for validation errors

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_edge_case_mock_objects(self, mock_quilt3):
        """Test _transform_content() with edge case mock objects."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with very large file
        large_file_mock = Mock()
        large_file_mock.name = "large_file.bin"
        large_file_mock.size = 10737418240  # 10GB
        large_file_mock.modified = datetime(2024, 1, 1, 12, 0, 0)
        large_file_mock.is_dir = False

        result = backend._transform_content(large_file_mock)
        assert result.size == 10737418240
        assert result.type == "file"

        # Test with very old timestamp
        old_file_mock = Mock()
        old_file_mock.name = "old_file.txt"
        old_file_mock.size = 1024
        old_file_mock.modified = datetime(1970, 1, 1, 0, 0, 0)  # Unix epoch
        old_file_mock.is_dir = False

        result = backend._transform_content(old_file_mock)
        assert result.modified_date == "1970-01-01T00:00:00"

        # Test with future timestamp
        future_file_mock = Mock()
        future_file_mock.name = "future_file.txt"
        future_file_mock.size = 512
        future_file_mock.modified = datetime(2099, 12, 31, 23, 59, 59)
        future_file_mock.is_dir = False

        result = backend._transform_content(future_file_mock)
        assert result.modified_date == "2099-12-31T23:59:59"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_different_mock_object_types(self, mock_quilt3):
        """Test _transform_content() works with different types of mock objects."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with different mock object types
        mock_types = [
            Mock(),  # Standard Mock
            MagicMock(),  # MagicMock
            type('CustomContent', (), {})(),  # Custom class instance
        ]

        for i, mock_content in enumerate(mock_types):
            # Set attributes on each mock type
            mock_content.name = f"test-{i}.txt"
            mock_content.size = 1024 * (i + 1)
            mock_content.modified = datetime(2024, 1, i + 1, 12, 0, 0)
            mock_content.is_dir = False

            result = backend._transform_content(mock_content)

            assert isinstance(result, Content_Info)
            assert result.path == f"test-{i}.txt"
            assert result.size == 1024 * (i + 1)
            assert result.type == "file"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_attribute_access_error_handling(self, mock_quilt3):
        """Test _transform_content() handles attribute access errors gracefully."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create mock that raises AttributeError on size access but has valid name
        class AttributeErrorContent:
            def __init__(self):
                self.name = "attribute_error.txt"

            @property
            def size(self):
                raise AttributeError("Size access denied")

            @property
            def modified(self):
                return datetime(2024, 1, 1, 12, 0, 0)

            @property
            def is_dir(self):
                return False

        error_content = AttributeErrorContent()

        # The transformation should succeed because _normalize_size handles AttributeError gracefully
        result = backend._transform_content(error_content)

        # Verify the transformation succeeded with None size
        assert isinstance(result, Content_Info)
        assert result.path == "attribute_error.txt"
        assert result.size is None  # _normalize_size should return None for AttributeError
        assert result.type == "file"
        assert result.modified_date == "2024-01-01T12:00:00"

        # Test with an error that actually causes transformation failure (missing name)
        class MissingNameContent:
            @property
            def size(self):
                return 1024

            @property
            def modified(self):
                return datetime(2024, 1, 1, 12, 0, 0)

            @property
            def is_dir(self):
                return False

        missing_name_content = MissingNameContent()

        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(missing_name_content)

        error_message = str(exc_info.value)
        assert "transformation failed" in error_message.lower()
        assert "missing name" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_performance_with_large_mock_data(self, mock_quilt3):
        """Test _transform_content() performance with large mock data structures."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create mock with very long path name
        long_path = "a" * 1000 + ".txt"
        mock_content = Mock()
        mock_content.name = long_path
        mock_content.size = 999999999999  # Very large size
        mock_content.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_content.is_dir = False

        # Should handle large data without issues
        result = backend._transform_content(mock_content)

        assert result.path == long_path
        assert result.size == 999999999999
        assert result.type == "file"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_unicode_and_special_characters(self, mock_quilt3):
        """Test _transform_content() handles unicode and special characters correctly."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various unicode and special character scenarios
        special_names = [
            "测试文件.txt",  # Chinese characters
            "файл.txt",  # Cyrillic characters
            "αρχείο.txt",  # Greek characters
            "ファイル.txt",  # Japanese characters
            "file_with_émojis_🚀📊.txt",  # Emojis
            "file!@#$%^&*()_+.txt",  # Special ASCII characters
            "file with spaces and tabs\t.txt",  # Whitespace
            "file\nwith\nnewlines.txt",  # Newlines (unusual but possible)
        ]

        for special_name in special_names:
            mock_content = Mock()
            mock_content.name = special_name
            mock_content.size = 1024
            mock_content.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_content.is_dir = False

            result = backend._transform_content(mock_content)

            assert result.path == special_name, f"Failed to preserve special name: {special_name}"
            assert isinstance(result, Content_Info)
            assert result.type == "file"
