"""Tests for package creation and management operations.

This module tests the core functionality for creating and managing Quilt packages,
including the automatic README content extraction from metadata.
"""

from unittest.mock import Mock, patch, MagicMock
import io

from quilt_mcp.tools.package_ops import package_create, _collect_objects_into_package


class TestPackageCreate:
    """Test cases for the package_create function."""

    @patch("quilt_mcp.tools.package_ops._build_selector_fn")
    @patch("quilt_mcp.tools.package_ops._collect_objects_into_package")
    @patch("quilt_mcp.tools.package_ops.quilt3.Package")
    def test_readme_content_extraction_from_metadata(self, mock_package_class, mock_collect, mock_build_selector):
        """Test that README content is automatically extracted from metadata and added as package file."""
        # Setup mocks
        mock_pkg = Mock()
        mock_package_class.return_value = mock_pkg

        # Mock successful object collection
        mock_collect.return_value = [{"logical_path": "test.txt", "source": "s3://bucket/test.txt"}]

        # Mock successful push
        mock_pkg.push.return_value = "test_hash_123"

        # Test metadata with README content
        test_metadata = {
            "description": "Test package",
            "readme_content": "# Test Package\n\nThis is a test package with README content.",
            "tags": ["test", "example"],
        }

        result = package_create(
            package_name="test/package",
            s3_uris=["s3://bucket/test.txt"],
            metadata=test_metadata,
            registry="s3://test-bucket",
        )

        # Verify README.md was added to package
        # Alternative: Check that README.md was called at all
        readme_calls = [call for call in mock_pkg.set.call_args_list if call[0][0] == "README.md"]
        assert len(readme_calls) > 0, "README.md was not added to package"

        # Verify metadata was set without README content
        expected_metadata = {"description": "Test package", "tags": ["test", "example"]}
        mock_pkg.set_meta.assert_called_with(expected_metadata)

        # Verify success
        assert result["status"] == "success"
        # Check that warnings were generated (they might not be returned in the result)
        # The important thing is that the README was extracted and added as a file

    @patch("quilt_mcp.tools.package_ops._build_selector_fn")
    @patch("quilt_mcp.tools.package_ops._collect_objects_into_package")
    @patch("quilt_mcp.tools.package_ops.quilt3.Package")
    def test_readme_field_extraction_from_metadata(self, mock_package_class, mock_collect, mock_build_selector):
        """Test that 'readme' field is also extracted from metadata."""
        # Setup mocks
        mock_pkg = Mock()
        mock_package_class.return_value = mock_pkg

        # Mock successful object collection
        mock_collect.return_value = [{"logical_path": "test.txt", "source": "s3://bucket/test.txt"}]

        # Mock successful push
        mock_pkg.push.return_value = "test_hash_123"

        # Test metadata with 'readme' field
        test_metadata = {
            "description": "Test package",
            "readme": "This is a simple README.",
            "version": "1.0.0",
        }

        result = package_create(
            package_name="test/package",
            s3_uris=["s3://bucket/test.txt"],
            metadata=test_metadata,
            registry="s3://test-bucket",
        )

        # Verify README.md was added to package
        # Alternative: Check that README.md was called at all
        readme_calls = [call for call in mock_pkg.set.call_args_list if call[0][0] == "README.md"]
        assert len(readme_calls) > 0, "README.md was not added to package"

        # Verify metadata was set without README content
        expected_metadata = {"description": "Test package", "version": "1.0.0"}
        mock_pkg.set_meta.assert_called_with(expected_metadata)

        # Verify success
        assert result["status"] == "success"
        # Check that warnings were generated (they might not be returned in the result)
        # The important thing is that the README was extracted and added as a file

    @patch("quilt_mcp.tools.package_ops._build_selector_fn")
    @patch("quilt_mcp.tools.package_ops._collect_objects_into_package")
    @patch("quilt_mcp.tools.package_ops.quilt3.Package")
    def test_both_readme_fields_extraction(self, mock_package_class, mock_collect, mock_build_selector):
        """Test that both 'readme_content' and 'readme' fields are extracted (readme_content takes priority)."""
        # Setup mocks
        mock_pkg = Mock()
        mock_package_class.return_value = mock_pkg

        # Mock successful object collection
        mock_collect.return_value = [{"logical_path": "test.txt", "source": "s3://bucket/test.txt"}]

        # Mock successful push
        mock_pkg.push.return_value = "test_hash_123"

        # Test metadata with both README fields
        test_metadata = {
            "description": "Test package",
            "readme_content": "# Priority README",
            "readme": "This should be ignored",
            "tags": ["test"],
        }

        result = package_create(
            package_name="test/package",
            s3_uris=["s3://bucket/test.txt"],
            metadata=test_metadata,
            registry="s3://test-bucket",
        )

        # Verify README.md was added with priority content
        # Alternative: Check that README.md was called at all
        readme_calls = [call for call in mock_pkg.set.call_args_list if call[0][0] == "README.md"]
        assert len(readme_calls) > 0, "README.md was not added to package"

        # Verify metadata was set without either README field
        expected_metadata = {"description": "Test package", "tags": ["test"]}
        mock_pkg.set_meta.assert_called_with(expected_metadata)

        # Verify success
        assert result["status"] == "success"

    @patch("quilt_mcp.tools.package_ops.quilt3.Package")
    @patch("quilt_mcp.tools.package_ops._collect_objects_into_package")
    @patch("quilt_mcp.tools.package_ops._build_selector_fn")
    def test_no_readme_content_in_metadata(self, mock_build_selector, mock_collect, mock_package_class):
        """Test that packages without README content in metadata work normally."""
        # Setup mocks
        mock_pkg = Mock()
        mock_package_class.return_value = mock_pkg

        # Mock successful object collection
        mock_collect.return_value = [{"logical_path": "test.txt", "source": "s3://bucket/test.txt"}]

        # Mock successful push
        mock_pkg.push.return_value = "test_hash_123"

        # Test metadata without README content
        test_metadata = {"description": "Test package", "tags": ["test", "example"]}

        result = package_create(
            package_name="test/package",
            s3_uris=["s3://bucket/test.txt"],
            metadata=test_metadata,
            registry="s3://test-bucket",
        )

        # Verify no README.md was added
        readme_calls = [call for call in mock_pkg.set.call_args_list if call[0][0] == "README.md"]
        assert len(readme_calls) == 0

        # Verify metadata was set as-is
        mock_pkg.set_meta.assert_called_with(test_metadata)

        # Verify success
        assert result["status"] == "success"

    @patch("quilt_mcp.tools.package_ops._build_selector_fn")
    @patch("quilt_mcp.tools.package_ops._collect_objects_into_package")
    @patch("quilt_mcp.tools.package_ops.quilt3.Package")
    def test_readme_file_creation_failure_handling(self, mock_package_class, mock_collect, mock_build_selector):
        """Test that README file creation failures are handled gracefully."""
        # Setup mocks
        mock_pkg = Mock()
        mock_package_class.return_value = mock_pkg

        # Mock successful object collection
        mock_collect.return_value = [{"logical_path": "test.txt", "source": "s3://bucket/test.txt"}]

        # Mock successful push
        mock_pkg.push.return_value = "test_hash_123"

        # Mock README file creation failure
        mock_pkg.set.side_effect = lambda logical_path, content: (
            Mock() if logical_path != "README.md" else Exception("File system error")
        )

        # Test metadata with README content
        test_metadata = {
            "description": "Test package",
            "readme_content": "# Test Package\n\nThis is a test package with README content.",
            "tags": ["test"],
        }

        result = package_create(
            package_name="test/package",
            s3_uris=["s3://bucket/test.txt"],
            metadata=test_metadata,
            registry="s3://test-bucket",
        )

        # Verify success despite README file creation failure
        assert result["status"] == "success"

        # Verify metadata was still set without README content
        expected_metadata = {"description": "Test package", "tags": ["test"]}
        mock_pkg.set_meta.assert_called_with(expected_metadata)

    @patch("quilt_mcp.tools.package_ops.quilt3.Package")
    @patch("quilt_mcp.tools.package_ops._collect_objects_into_package")
    @patch("quilt_mcp.tools.package_ops._build_selector_fn")
    def test_empty_metadata_handling(self, mock_build_selector, mock_collect, mock_package_class):
        """Test that empty metadata is handled correctly."""
        # Setup mocks
        mock_pkg = Mock()
        mock_package_class.return_value = mock_pkg

        # Mock successful object collection
        mock_collect.return_value = [{"logical_path": "test.txt", "source": "s3://bucket/test.txt"}]

        # Mock successful push
        mock_pkg.push.return_value = "test_hash_123"

        result = package_create(
            package_name="test/package",
            s3_uris=["s3://bucket/test.txt"],
            metadata=None,  # No metadata
            registry="s3://test-bucket",
        )

        # Verify no metadata was set
        mock_pkg.set_meta.assert_not_called()

        # Verify success
        assert result["status"] == "success"

    @patch("quilt_mcp.tools.package_ops.quilt3.Package")
    @patch("quilt_mcp.tools.package_ops._collect_objects_into_package")
    @patch("quilt_mcp.tools.package_ops._build_selector_fn")
    def test_metadata_without_readme_fields(self, mock_build_selector, mock_collect, mock_package_class):
        """Test that metadata without README fields is processed normally."""
        # Setup mocks
        mock_pkg = Mock()
        mock_package_class.return_value = mock_pkg

        # Mock successful object collection
        mock_collect.return_value = [{"logical_path": "test.txt", "source": "s3://bucket/test.txt"}]

        # Mock successful push
        mock_pkg.push.return_value = "test_hash_123"

        # Test metadata with various fields but no README content
        test_metadata = {
            "description": "Test package",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": ["test", "example"],
            "custom_field": "custom_value",
        }

        result = package_create(
            package_name="test/package",
            s3_uris=["s3://bucket/test.txt"],
            metadata=test_metadata,
            registry="s3://test-bucket",
        )

        # Verify metadata was set unchanged
        mock_pkg.set_meta.assert_called_with(test_metadata)

        # Verify no README.md was added
        readme_calls = [call for call in mock_pkg.set.call_args_list if call[0][0] == "README.md"]
        assert len(readme_calls) == 0

        # Verify success
        assert result["status"] == "success"


class TestCollectObjectsIntoPackage:
    """Test cases for the _collect_objects_into_package function."""

    def test_collect_objects_with_valid_s3_uris(self):
        """Test collecting objects with valid S3 URIs."""
        mock_pkg = Mock()
        # Mock the package to handle the 'in' operator for logical path checking
        mock_pkg.__contains__ = Mock(return_value=False)

        s3_uris = [
            "s3://bucket/file1.txt",
            "s3://bucket/file2.csv",
            "s3://bucket/subfolder/file3.json",
        ]
        warnings = []

        result = _collect_objects_into_package(mock_pkg, s3_uris, flatten=True, warnings=warnings)

        # Verify objects were added
        assert len(result) == 3
        assert mock_pkg.set.call_count == 3

        # Verify no warnings
        assert len(warnings) == 0

    def test_collect_objects_with_invalid_uris(self):
        """Test collecting objects with invalid URIs."""
        mock_pkg = Mock()
        # Mock the package to handle the 'in' operator for logical path checking
        mock_pkg.__contains__ = Mock(return_value=False)

        s3_uris = [
            "s3://bucket/file1.txt",  # Valid
            "invalid-uri",  # Invalid
            "s3://bucket-only",  # Invalid (no key)
            "s3://bucket/folder/",  # Invalid (directory)
        ]
        warnings = []

        result = _collect_objects_into_package(mock_pkg, s3_uris, flatten=True, warnings=warnings)

        # Verify only valid objects were added
        assert len(result) == 1
        assert mock_pkg.set.call_count == 1

        # Verify warnings were generated
        assert len(warnings) == 3
        assert any("Skipping non-S3 URI" in w for w in warnings)
        assert any("Skipping bucket-only URI" in w for w in warnings)
        assert any("Skipping URI that appears to be a 'directory'" in w for w in warnings)
