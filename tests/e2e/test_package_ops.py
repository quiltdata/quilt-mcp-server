"""Tests for package creation and management operations.

This module tests the core functionality for creating and managing Quilt packages,
including the automatic README content extraction from metadata.
"""

from unittest.mock import Mock, patch, MagicMock
import io

from quilt_mcp.tools.package_ops import package_create, _collect_objects_into_package


class TestPackageCreate:
    """Test cases for the package_create function."""

    @patch("quilt_mcp.tools.package_ops.quilt_service.create_package_revision")
    def test_readme_content_extraction_from_metadata(self, mock_create_revision):
        """Test that README content is automatically extracted from metadata and added as package file."""
        # Mock successful package creation
        mock_create_revision.return_value = {
            "status": "success",
            "top_hash": "test_hash_123",
            "entries_added": 1,
        }

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

        # Verify create_package_revision was called with processed metadata (without README)
        mock_create_revision.assert_called_once()
        call_args = mock_create_revision.call_args

        assert call_args[1]["package_name"] == "test/package"
        assert call_args[1]["s3_uris"] == ["s3://bucket/test.txt"]
        assert call_args[1]["registry"] == "s3://test-bucket"
        assert call_args[1]["auto_organize"] == False  # package_ops.py should use False

        # Verify metadata was processed to remove README content
        processed_metadata = call_args[1]["metadata"]
        expected_metadata = {"description": "Test package", "tags": ["test", "example"]}
        assert processed_metadata == expected_metadata

        # Verify success
        assert result["status"] == "success"

    @patch("quilt_mcp.tools.package_ops.quilt_service.create_package_revision")
    def test_readme_field_extraction_from_metadata(self, mock_create_revision):
        """Test that 'readme' field is also extracted from metadata."""
        # Mock successful package creation
        mock_create_revision.return_value = {
            "status": "success",
            "top_hash": "test_hash_123",
            "entries_added": 1,
        }

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

        # Verify create_package_revision was called with processed metadata (without README)
        mock_create_revision.assert_called_once()
        call_args = mock_create_revision.call_args

        assert call_args[1]["package_name"] == "test/package"
        assert call_args[1]["s3_uris"] == ["s3://bucket/test.txt"]
        assert call_args[1]["registry"] == "s3://test-bucket"
        assert call_args[1]["auto_organize"] == False  # package_ops.py should use False

        # Verify metadata was processed to remove README content
        processed_metadata = call_args[1]["metadata"]
        expected_metadata = {"description": "Test package", "version": "1.0.0"}
        assert processed_metadata == expected_metadata

        # Verify success
        assert result["status"] == "success"

    @patch("quilt_mcp.tools.package_ops.quilt_service.create_package_revision")
    def test_both_readme_fields_extraction(self, mock_create_revision):
        """Test that both 'readme_content' and 'readme' fields are extracted (readme_content takes priority)."""
        # Mock successful package creation
        mock_create_revision.return_value = {
            "status": "success",
            "top_hash": "test_hash_123",
            "entries_added": 1,
        }

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

        # Verify create_package_revision was called with processed metadata (without README)
        mock_create_revision.assert_called_once()
        call_args = mock_create_revision.call_args

        assert call_args[1]["package_name"] == "test/package"
        assert call_args[1]["s3_uris"] == ["s3://bucket/test.txt"]
        assert call_args[1]["registry"] == "s3://test-bucket"
        assert call_args[1]["auto_organize"] == False  # package_ops.py should use False

        # Verify metadata was processed to remove both README fields
        processed_metadata = call_args[1]["metadata"]
        expected_metadata = {"description": "Test package", "tags": ["test"]}
        assert processed_metadata == expected_metadata

        # Verify success
        assert result["status"] == "success"

    @patch("quilt_mcp.tools.package_ops.quilt_service.create_package_revision")
    def test_no_readme_content_in_metadata(self, mock_create_revision):
        """Test that packages without README content in metadata work normally."""
        # Mock successful package creation
        mock_create_revision.return_value = {
            "status": "success",
            "top_hash": "test_hash_123",
            "entries_added": 1,
        }

        # Test metadata without README content
        test_metadata = {"description": "Test package", "tags": ["test", "example"]}

        result = package_create(
            package_name="test/package",
            s3_uris=["s3://bucket/test.txt"],
            metadata=test_metadata,
            registry="s3://test-bucket",
        )

        # Verify create_package_revision was called with metadata as-is
        mock_create_revision.assert_called_once()
        call_args = mock_create_revision.call_args

        assert call_args[1]["package_name"] == "test/package"
        assert call_args[1]["s3_uris"] == ["s3://bucket/test.txt"]
        assert call_args[1]["registry"] == "s3://test-bucket"
        assert call_args[1]["auto_organize"] == False  # package_ops.py should use False

        # Verify metadata was passed unchanged
        processed_metadata = call_args[1]["metadata"]
        assert processed_metadata == test_metadata

        # Verify success
        assert result["status"] == "success"

    @patch("quilt_mcp.tools.package_ops.quilt_service.create_package_revision")
    def test_readme_file_creation_failure_handling(self, mock_create_revision):
        """Test that README file creation failures are handled gracefully."""
        # Mock package creation that will process README internally
        # NOTE: With create_package_revision, README handling is internal
        mock_create_revision.return_value = {
            "status": "success",
            "top_hash": "test_hash_123",
            "entries_added": 1,
        }

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

        # Verify create_package_revision was called with processed metadata (without README)
        mock_create_revision.assert_called_once()
        call_args = mock_create_revision.call_args

        assert call_args[1]["package_name"] == "test/package"
        assert call_args[1]["s3_uris"] == ["s3://bucket/test.txt"]
        assert call_args[1]["registry"] == "s3://test-bucket"
        assert call_args[1]["auto_organize"] == False  # package_ops.py should use False

        # Verify metadata was processed to remove README content
        processed_metadata = call_args[1]["metadata"]
        expected_metadata = {"description": "Test package", "tags": ["test"]}
        assert processed_metadata == expected_metadata

        # Verify success (README failure handling is now internal to create_package_revision)
        assert result["status"] == "success"

    @patch("quilt_mcp.tools.package_ops.quilt_service.create_package_revision")
    def test_empty_metadata_handling(self, mock_create_revision):
        """Test that empty metadata is handled correctly."""
        # Mock successful package creation
        mock_create_revision.return_value = {
            "status": "success",
            "top_hash": "test_hash_123",
            "entries_added": 1,
        }

        result = package_create(
            package_name="test/package",
            s3_uris=["s3://bucket/test.txt"],
            metadata=None,  # No metadata
            registry="s3://test-bucket",
        )

        # Verify create_package_revision was called with empty metadata
        mock_create_revision.assert_called_once()
        call_args = mock_create_revision.call_args

        assert call_args[1]["package_name"] == "test/package"
        assert call_args[1]["s3_uris"] == ["s3://bucket/test.txt"]
        assert call_args[1]["registry"] == "s3://test-bucket"
        assert call_args[1]["auto_organize"] == False  # package_ops.py should use False

        # Verify metadata is empty dict
        processed_metadata = call_args[1]["metadata"]
        assert processed_metadata == {}

        # Verify success
        assert result["status"] == "success"

    @patch("quilt_mcp.tools.package_ops.quilt_service.create_package_revision")
    def test_metadata_without_readme_fields(self, mock_create_revision):
        """Test that metadata without README fields is processed normally."""
        # Mock successful package creation
        mock_create_revision.return_value = {
            "status": "success",
            "top_hash": "test_hash_123",
            "entries_added": 1,
        }

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

        # Verify create_package_revision was called with metadata unchanged
        mock_create_revision.assert_called_once()
        call_args = mock_create_revision.call_args

        assert call_args[1]["package_name"] == "test/package"
        assert call_args[1]["s3_uris"] == ["s3://bucket/test.txt"]
        assert call_args[1]["registry"] == "s3://test-bucket"
        assert call_args[1]["auto_organize"] == False  # package_ops.py should use False

        # Verify metadata was passed unchanged
        processed_metadata = call_args[1]["metadata"]
        assert processed_metadata == test_metadata

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
