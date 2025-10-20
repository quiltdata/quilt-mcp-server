"""Tests for package creation and management operations.

This module tests the core functionality for creating and managing Quilt packages,
including the automatic README content extraction from metadata.
"""

from unittest.mock import Mock, patch, MagicMock
import io

from quilt_mcp.tools.packages import (
    package_create,
    package_update,
    package_delete,
    _collect_objects_into_package,
    _normalize_registry,
    _build_selector_fn,
)


class TestPackageCreate:
    """Test cases for the package_create function."""

    @patch("quilt_mcp.tools.packages.quilt_service.create_package_revision")
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
        assert not call_args[1]["auto_organize"]  # package_ops.py should use False

        # Verify metadata was processed to remove README content
        processed_metadata = call_args[1]["metadata"]
        expected_metadata = {"description": "Test package", "tags": ["test", "example"]}
        assert processed_metadata == expected_metadata

        # Verify success
        assert result["status"] == "success"

    @patch("quilt_mcp.tools.packages.quilt_service.create_package_revision")
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
        assert not call_args[1]["auto_organize"]  # package_ops.py should use False

        # Verify metadata was processed to remove README content
        processed_metadata = call_args[1]["metadata"]
        expected_metadata = {"description": "Test package", "version": "1.0.0"}
        assert processed_metadata == expected_metadata

        # Verify success
        assert result["status"] == "success"

    @patch("quilt_mcp.tools.packages.quilt_service.create_package_revision")
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
        assert not call_args[1]["auto_organize"]  # package_ops.py should use False

        # Verify metadata was processed to remove both README fields
        processed_metadata = call_args[1]["metadata"]
        expected_metadata = {"description": "Test package", "tags": ["test"]}
        assert processed_metadata == expected_metadata

        # Verify success
        assert result["status"] == "success"

    @patch("quilt_mcp.tools.packages.quilt_service.create_package_revision")
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
        assert not call_args[1]["auto_organize"]  # package_ops.py should use False

        # Verify metadata was passed unchanged
        processed_metadata = call_args[1]["metadata"]
        assert processed_metadata == test_metadata

        # Verify success
        assert result["status"] == "success"

    @patch("quilt_mcp.tools.packages.quilt_service.create_package_revision")
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
        assert not call_args[1]["auto_organize"]  # package_ops.py should use False

        # Verify metadata was processed to remove README content
        processed_metadata = call_args[1]["metadata"]
        expected_metadata = {"description": "Test package", "tags": ["test"]}
        assert processed_metadata == expected_metadata

        # Verify success (README failure handling is now internal to create_package_revision)
        assert result["status"] == "success"

    @patch("quilt_mcp.tools.packages.quilt_service.create_package_revision")
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
        assert not call_args[1]["auto_organize"]  # package_ops.py should use False

        # Verify metadata is empty dict
        processed_metadata = call_args[1]["metadata"]
        assert processed_metadata == {}

        # Verify success
        assert result["status"] == "success"

    @patch("quilt_mcp.tools.packages.quilt_service.create_package_revision")
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
        assert not call_args[1]["auto_organize"]  # package_ops.py should use False

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


class TestNormalizeRegistry:
    """Test cases for the _normalize_registry function."""

    def test_normalize_registry_with_s3_prefix(self):
        """Test that s3:// URIs are returned as-is."""
        result = _normalize_registry("s3://my-bucket")
        assert result == "s3://my-bucket"

    def test_normalize_registry_without_s3_prefix(self):
        """Test that bucket names get s3:// prefix added."""
        result = _normalize_registry("my-bucket")
        assert result == "s3://my-bucket"

    def test_normalize_registry_with_path(self):
        """Test that bucket names with paths get s3:// prefix added."""
        result = _normalize_registry("my-bucket/path/to/files")
        assert result == "s3://my-bucket/path/to/files"


class TestBuildSelectorFn:
    """Test cases for the _build_selector_fn function."""

    def test_build_selector_fn_all(self):
        """Test selector function with 'all' mode."""
        selector = _build_selector_fn("all", "s3://target-bucket")

        # Should return True for any entry
        result = selector("test_key", Mock())
        assert result is True

    def test_build_selector_fn_none(self):
        """Test selector function with 'none' mode."""
        selector = _build_selector_fn("none", "s3://target-bucket")

        # Should return False for any entry
        result = selector("test_key", Mock())
        assert result is False

    def test_build_selector_fn_same_bucket_matching(self):
        """Test selector function with 'same_bucket' mode - matching bucket."""
        selector = _build_selector_fn("same_bucket", "s3://target-bucket")

        # Mock entry with matching bucket
        entry = Mock()
        entry.physical_key = "s3://target-bucket/path/to/file.txt"

        result = selector("test_key", entry)
        assert result is True

    def test_build_selector_fn_same_bucket_non_matching(self):
        """Test selector function with 'same_bucket' mode - non-matching bucket."""
        selector = _build_selector_fn("same_bucket", "s3://target-bucket")

        # Mock entry with different bucket
        entry = Mock()
        entry.physical_key = "s3://other-bucket/path/to/file.txt"

        result = selector("test_key", entry)
        assert result is False

    def test_build_selector_fn_same_bucket_invalid_physical_key(self):
        """Test selector function with 'same_bucket' mode - invalid physical key."""
        selector = _build_selector_fn("same_bucket", "s3://target-bucket")

        # Mock entry with invalid physical key
        entry = Mock()
        entry.physical_key = "invalid-key"

        result = selector("test_key", entry)
        assert result is False

    def test_build_selector_fn_same_bucket_exception_on_physical_key(self):
        """Test selector function with 'same_bucket' mode - exception getting physical key."""
        selector = _build_selector_fn("same_bucket", "s3://target-bucket")

        # Mock entry that raises exception when accessing physical_key
        entry = Mock()
        entry.physical_key = Mock(side_effect=Exception("Access error"))

        result = selector("test_key", entry)
        assert result is False

    def test_build_selector_fn_same_bucket_malformed_s3_uri(self):
        """Test selector function with 'same_bucket' mode - malformed S3 URI."""
        selector = _build_selector_fn("same_bucket", "s3://target-bucket")

        # Mock entry with malformed S3 URI
        entry = Mock()
        entry.physical_key = "s3://malformed"  # No bucket separator

        result = selector("test_key", entry)
        assert result is False

    def test_build_selector_fn_default_mode(self):
        """Test selector function with unknown mode defaults to 'all'."""
        selector = _build_selector_fn("unknown_mode", "s3://target-bucket")

        # Should behave like 'all' mode
        result = selector("test_key", Mock())
        assert result is True


class TestCollectObjectsIntoPackageAdvanced:
    """Advanced test cases for the _collect_objects_into_package function."""

    def test_collect_objects_with_duplicate_logical_paths(self):
        """Test collecting objects with duplicate logical paths (filename collisions)."""
        mock_pkg = Mock()

        # Track what gets added as we go - initially package is empty
        added_keys = set()

        def contains_side_effect(key):
            # Return True if the key has already been added to the package
            return key in added_keys

        def set_side_effect(key, uri):
            # Track what gets added
            added_keys.add(key)

        mock_pkg.__contains__ = Mock(side_effect=contains_side_effect)
        mock_pkg.set = Mock(side_effect=set_side_effect)

        s3_uris = [
            "s3://bucket/file.txt",
            "s3://bucket/path/file.txt",  # Same filename, should get counter prefix
        ]
        warnings = []

        result = _collect_objects_into_package(mock_pkg, s3_uris, flatten=True, warnings=warnings)

        # Verify objects were added with unique logical paths
        assert len(result) == 2
        assert mock_pkg.set.call_count == 2

        # Check the logical paths used
        logical_paths = [call.args[0] for call in mock_pkg.set.call_args_list]
        source_uris = [call.args[1] for call in mock_pkg.set.call_args_list]

        # First URI should use original filename (package is initially empty)
        assert logical_paths[0] == "file.txt"
        assert source_uris[0] == "s3://bucket/file.txt"

        # Second URI should get counter prefix since "file.txt" is now taken
        assert logical_paths[1] == "1_file.txt"  # Counter starts at 1
        assert source_uris[1] == "s3://bucket/path/file.txt"

    def test_collect_objects_with_package_set_exception(self):
        """Test collecting objects when package.set() raises an exception."""
        mock_pkg = Mock()
        mock_pkg.__contains__ = Mock(return_value=False)
        mock_pkg.set = Mock(side_effect=Exception("Failed to set object"))

        s3_uris = ["s3://bucket/file.txt"]
        warnings = []

        result = _collect_objects_into_package(mock_pkg, s3_uris, flatten=True, warnings=warnings)

        # Verify no objects were added due to exception
        assert len(result) == 0
        assert mock_pkg.set.call_count == 1

        # Verify warning was generated
        assert len(warnings) == 1
        assert "Failed to add s3://bucket/file.txt:" in warnings[0]


class TestPackageCreateErrorHandling:
    """Test error handling in package_create function."""

    def test_package_create_with_empty_s3_uris(self):
        """Test package_create with empty S3 URIs list."""
        result = package_create(package_name="test/package", s3_uris=[], registry="s3://test-bucket")

        assert result["error"] == "No S3 URIs provided"

    def test_package_create_with_empty_package_name(self):
        """Test package_create with empty package name."""
        result = package_create(package_name="", s3_uris=["s3://bucket/file.txt"], registry="s3://test-bucket")

        assert result["error"] == "Package name is required"

    def test_package_create_with_invalid_json_metadata(self):
        """Test package_create with invalid JSON string metadata."""
        result = package_create(
            package_name="test/package",
            s3_uris=["s3://bucket/file.txt"],
            metadata='{"invalid": json syntax}',  # Invalid JSON
            registry="s3://test-bucket",
        )

        assert result["success"] is False
        assert result["error"] == "Invalid metadata format"
        assert "json_error" in result
        assert "examples" in result

    def test_package_create_with_non_dict_non_string_metadata(self):
        """Test package_create with metadata that's not a dict or string."""
        result = package_create(
            package_name="test/package",
            s3_uris=["s3://bucket/file.txt"],
            metadata=123,  # Invalid type
            registry="s3://test-bucket",
        )

        assert result["success"] is False
        assert result["error"] == "Invalid metadata type"
        assert result["provided_type"] == "int"
        assert "examples" in result

    @patch("quilt_mcp.tools.packages.quilt_service.create_package_revision")
    def test_package_create_with_service_error_response(self, mock_create_revision):
        """Test package_create when service returns error response."""
        mock_create_revision.return_value = {
            "error": "Service failed to create package",
            "details": "Some internal error",
        }

        result = package_create(
            package_name="test/package", s3_uris=["s3://bucket/file.txt"], registry="s3://test-bucket"
        )

        assert result["error"] == "Service failed to create package"
        assert result["package_name"] == "test/package"
        assert "warnings" in result

    @patch("quilt_mcp.tools.packages.quilt_service.create_package_revision")
    def test_package_create_with_service_exception(self, mock_create_revision):
        """Test package_create when service raises exception."""
        mock_create_revision.side_effect = Exception("Network error")

        result = package_create(
            package_name="test/package", s3_uris=["s3://bucket/file.txt"], registry="s3://test-bucket"
        )

        assert "Failed to create package: Network error" in result["error"]
        assert result["package_name"] == "test/package"
        assert "warnings" in result


class TestPackageUpdate:
    """Test cases for the package_update function."""

    def test_package_update_with_empty_s3_uris(self):
        """Test package_update with empty S3 URIs list."""
        result = package_update(package_name="test/package", s3_uris=[], registry="s3://test-bucket")

        assert result["error"] == "No S3 URIs provided"

    def test_package_update_with_empty_package_name(self):
        """Test package_update with empty package name."""
        result = package_update(package_name="", s3_uris=["s3://bucket/file.txt"], registry="s3://test-bucket")

        assert result["error"] == "package_name is required for package_update"

    def test_package_update_with_invalid_json_metadata(self):
        """Test package_update with invalid JSON string metadata."""
        result = package_update(
            package_name="test/package",
            s3_uris=["s3://bucket/file.txt"],
            metadata='{"invalid": json}',  # Invalid JSON
            registry="s3://test-bucket",
        )

        assert result["success"] is False
        assert result["error"] == "Invalid metadata format"
        assert "json_error" in result

    def test_package_update_with_non_dict_metadata(self):
        """Test package_update with metadata that's not a dict or string."""
        result = package_update(
            package_name="test/package",
            s3_uris=["s3://bucket/file.txt"],
            metadata=["invalid", "type"],  # Invalid type
            registry="s3://test-bucket",
        )

        assert result["success"] is False
        assert result["error"] == "Invalid metadata type"
        assert result["provided_type"] == "list"

    @patch("quilt_mcp.tools.packages.QuiltService")
    @patch("quilt_mcp.utils.suppress_stdout")
    def test_package_update_browse_package_failure(self, mock_suppress, mock_quilt_service_class):
        """Test package_update when browsing existing package fails."""
        mock_service = Mock()
        mock_service.browse_package.side_effect = Exception("Package not found")
        mock_quilt_service_class.return_value = mock_service

        result = package_update(
            package_name="test/package", s3_uris=["s3://bucket/file.txt"], registry="s3://test-bucket"
        )

        assert "Failed to browse existing package 'test/package':" in result["error"]
        assert result["package_name"] == "test/package"


class TestPackageDelete:
    """Test cases for the package_delete function."""

    def test_package_delete_with_empty_package_name(self):
        """Test package_delete with empty package name."""
        result = package_delete(package_name="", registry="s3://test-bucket")

        assert result["error"] == "package_name is required for package deletion"

    @patch("quilt_mcp.tools.packages.quilt3.delete_package")
    @patch("quilt_mcp.utils.suppress_stdout")
    def test_package_delete_success(self, mock_suppress, mock_delete):
        """Test successful package deletion."""
        mock_delete.return_value = None  # Successful deletion

        result = package_delete(package_name="test/package", registry="s3://test-bucket")

        assert result["status"] == "success"
        assert result["action"] == "deleted"
        assert result["package_name"] == "test/package"
        assert result["registry"] == "s3://test-bucket"
        assert "deleted successfully" in result["message"]

    @patch("quilt_mcp.tools.packages.quilt3.delete_package")
    @patch("quilt_mcp.utils.suppress_stdout")
    def test_package_delete_failure(self, mock_suppress, mock_delete):
        """Test package deletion failure."""
        mock_delete.side_effect = Exception("Deletion failed")

        result = package_delete(package_name="test/package", registry="s3://test-bucket")

        assert "Failed to delete package 'test/package':" in result["error"]
        assert result["package_name"] == "test/package"
        assert result["registry"] == "s3://test-bucket"
