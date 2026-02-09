"""Unit tests for quilt3 backend primitive implementations.

Tests the seam between our backend and the quilt3 library, ensuring
correct type coercion regardless of quilt3 library behavior changes.

This module focuses on the backend primitives that directly interact with
the quilt3 library, particularly handling varying return types and ensuring
proper serialization to domain objects.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Any

from quilt_mcp.backends.quilt3_backend import Quilt3_Backend


@pytest.fixture
def backend():
    """Create Quilt3_Backend instance with mocked quilt3."""
    with patch('quilt_mcp.backends.quilt3_backend_base.quilt3') as mock_quilt3:
        backend = Quilt3_Backend()
        # Store mock for easy access in tests
        backend._mock_quilt3 = mock_quilt3
        return backend


class TestBackendPushPackage:
    """Test _backend_push_package() handles varying quilt3 return types.

    Critical for preventing serialization bugs where Package objects are
    passed to response models expecting strings.
    """

    def test_push_returns_package_object(self, backend):
        """Regression test: When quilt3.Package.push() returns Package object, extract top_hash.

        This is the bug scenario that was discovered in integration tests.
        quilt3.Package.push() sometimes returns a Package object instead of a string,
        and the backend must extract the top_hash attribute correctly.
        """
        # Create a mock Package object with top_hash attribute
        mock_package_instance = Mock()
        mock_package_instance.top_hash = "abc123def456"

        # Create a mock Package class that returns the instance on push()
        mock_package_class = Mock()
        mock_package_class.return_value = Mock()
        mock_package_class.return_value.set = Mock()
        mock_package_class.return_value.set_meta = Mock()
        mock_package_class.return_value.push = Mock(return_value=mock_package_instance)

        # Inject the mock into backend
        backend.quilt3.Package = mock_package_class

        # Execute backend primitive
        pkg_builder = {"entries": [], "metadata": {}}
        top_hash = backend._backend_push_package(pkg_builder, "test/pkg", "s3://bucket", "msg", copy=False)

        # CRITICAL: Must return string, not Package object
        assert isinstance(top_hash, str), f"Expected string, got {type(top_hash)}"
        assert top_hash == "abc123def456"

    def test_push_returns_string_hash(self, backend):
        """Test normal case where quilt3.Package.push() returns string directly.

        This is the expected behavior according to quilt3 documentation,
        but the library behavior varies in practice.
        """
        # Create mock Package that returns string from push()
        mock_package_instance = Mock()
        mock_package_class = Mock()
        mock_package_class.return_value = Mock()
        mock_package_class.return_value.set = Mock()
        mock_package_class.return_value.set_meta = Mock()
        mock_package_class.return_value.push = Mock(return_value="xyz789")

        # Inject the mock into backend
        backend.quilt3.Package = mock_package_class

        # Execute backend primitive
        pkg_builder = {"entries": [], "metadata": {}}
        top_hash = backend._backend_push_package(pkg_builder, "test/pkg", "s3://bucket", "msg", copy=False)

        # Verify string is preserved
        assert isinstance(top_hash, str)
        assert top_hash == "xyz789"

    def test_push_returns_none(self, backend):
        """Test push failure case where None is returned.

        When push fails, ensure we return empty string instead of None
        to prevent downstream type errors.
        """
        # Create mock Package that returns None from push()
        mock_package_class = Mock()
        mock_package_class.return_value = Mock()
        mock_package_class.return_value.set = Mock()
        mock_package_class.return_value.set_meta = Mock()
        mock_package_class.return_value.push = Mock(return_value=None)

        # Inject the mock into backend
        backend.quilt3.Package = mock_package_class

        # Execute backend primitive
        pkg_builder = {"entries": [], "metadata": {}}
        top_hash = backend._backend_push_package(pkg_builder, "test/pkg", "s3://bucket", "msg", copy=False)

        # Should return empty string, not None
        assert isinstance(top_hash, str)
        assert top_hash == ""

    def test_push_returns_empty_string(self, backend):
        """Test push returning empty string (edge case)."""
        # Create mock Package that returns empty string from push()
        mock_package_class = Mock()
        mock_package_class.return_value = Mock()
        mock_package_class.return_value.set = Mock()
        mock_package_class.return_value.set_meta = Mock()
        mock_package_class.return_value.push = Mock(return_value="")

        # Inject the mock into backend
        backend.quilt3.Package = mock_package_class

        # Execute backend primitive
        pkg_builder = {"entries": [], "metadata": {}}
        top_hash = backend._backend_push_package(pkg_builder, "test/pkg", "s3://bucket", "msg", copy=False)

        # Should preserve empty string
        assert isinstance(top_hash, str)
        assert top_hash == ""

    def test_push_returns_package_with_none_top_hash(self, backend):
        """Test Package object with None top_hash attribute.

        Edge case where Package object exists but top_hash is None.
        """
        # Create mock Package with None top_hash
        mock_package_instance = Mock()
        mock_package_instance.top_hash = None

        mock_package_class = Mock()
        mock_package_class.return_value = Mock()
        mock_package_class.return_value.set = Mock()
        mock_package_class.return_value.set_meta = Mock()
        mock_package_class.return_value.push = Mock(return_value=mock_package_instance)

        # Inject the mock into backend
        backend.quilt3.Package = mock_package_class

        # Execute backend primitive
        pkg_builder = {"entries": [], "metadata": {}}
        top_hash = backend._backend_push_package(pkg_builder, "test/pkg", "s3://bucket", "msg", copy=False)

        # Should return empty string when top_hash is None
        assert isinstance(top_hash, str)
        assert top_hash == ""

    def test_push_with_copy_true(self, backend):
        """Verify copy=True uses correct push parameters (deep copy)."""
        # Create mock Package
        mock_package_instance = Mock()
        mock_package_class = Mock()
        mock_package_class.return_value = mock_package_instance
        mock_package_instance.set = Mock()
        mock_package_instance.set_meta = Mock()
        mock_package_instance.push = Mock(return_value="hash123")

        # Inject the mock into backend
        backend.quilt3.Package = mock_package_class

        # Execute with copy=True
        pkg_builder = {"entries": [], "metadata": {}}
        backend._backend_push_package(pkg_builder, "test/pkg", "s3://bucket", "msg", copy=True)

        # Verify push was called with correct parameters for deep copy
        mock_package_instance.push.assert_called_once()
        call_kwargs = mock_package_instance.push.call_args[1]
        assert call_kwargs['registry'] == "s3://bucket"
        assert call_kwargs['message'] == "msg"
        assert call_kwargs['force'] is True
        # When copy=True, selector_fn should NOT be in kwargs
        assert 'selector_fn' not in call_kwargs

    def test_push_with_copy_false(self, backend):
        """Verify copy=False uses selector_fn correctly (shallow references)."""
        # Create mock Package
        mock_package_instance = Mock()
        mock_package_class = Mock()
        mock_package_class.return_value = mock_package_instance
        mock_package_instance.set = Mock()
        mock_package_instance.set_meta = Mock()
        mock_package_instance.push = Mock(return_value="hash456")

        # Inject the mock into backend
        backend.quilt3.Package = mock_package_class

        # Execute with copy=False
        pkg_builder = {"entries": [], "metadata": {}}
        backend._backend_push_package(pkg_builder, "test/pkg", "s3://bucket", "msg", copy=False)

        # Verify push was called with selector_fn
        mock_package_instance.push.assert_called_once()
        call_kwargs = mock_package_instance.push.call_args[1]
        assert call_kwargs['registry'] == "s3://bucket"
        assert call_kwargs['message'] == "msg"
        assert call_kwargs['force'] is True
        # When copy=False, selector_fn should be present
        assert 'selector_fn' in call_kwargs
        # The selector_fn should return False (no copy)
        selector_fn = call_kwargs['selector_fn']
        assert callable(selector_fn)
        assert selector_fn("any", "args") is False

    def test_push_with_entries(self, backend):
        """Test that package entries are correctly added to quilt3 Package."""
        # Create mock Package
        mock_package_instance = Mock()
        mock_package_class = Mock()
        mock_package_class.return_value = mock_package_instance
        mock_package_instance.set = Mock()
        mock_package_instance.set_meta = Mock()
        mock_package_instance.push = Mock(return_value="hash789")

        # Inject the mock into backend
        backend.quilt3.Package = mock_package_class

        # Execute with entries
        pkg_builder = {
            "entries": [
                {"logicalKey": "file1.txt", "physicalKey": "s3://bucket/file1.txt"},
                {"logicalKey": "data/file2.csv", "physicalKey": "s3://bucket/dir/file2.csv"},
            ],
            "metadata": {},
        }
        backend._backend_push_package(pkg_builder, "test/pkg", "s3://bucket", "msg", copy=False)

        # Verify entries were added via set()
        assert mock_package_instance.set.call_count == 2
        mock_package_instance.set.assert_any_call("file1.txt", "s3://bucket/file1.txt")
        mock_package_instance.set.assert_any_call("data/file2.csv", "s3://bucket/dir/file2.csv")

    def test_push_with_metadata(self, backend):
        """Test that package metadata is correctly set on quilt3 Package."""
        # Create mock Package
        mock_package_instance = Mock()
        mock_package_class = Mock()
        mock_package_class.return_value = mock_package_instance
        mock_package_instance.set = Mock()
        mock_package_instance.set_meta = Mock()
        mock_package_instance.push = Mock(return_value="hashABC")

        # Inject the mock into backend
        backend.quilt3.Package = mock_package_class

        # Execute with metadata
        pkg_builder = {
            "entries": [],
            "metadata": {"author": "test", "version": "1.0"},
        }
        backend._backend_push_package(pkg_builder, "test/pkg", "s3://bucket", "msg", copy=False)

        # Verify metadata was set
        mock_package_instance.set_meta.assert_called_once_with({"author": "test", "version": "1.0"})

    def test_push_with_empty_metadata(self, backend):
        """Test that empty metadata doesn't call set_meta."""
        # Create mock Package
        mock_package_instance = Mock()
        mock_package_class = Mock()
        mock_package_class.return_value = mock_package_instance
        mock_package_instance.set = Mock()
        mock_package_instance.set_meta = Mock()
        mock_package_instance.push = Mock(return_value="hashDEF")

        # Inject the mock into backend
        backend.quilt3.Package = mock_package_class

        # Execute with empty metadata
        pkg_builder = {"entries": [], "metadata": {}}
        backend._backend_push_package(pkg_builder, "test/pkg", "s3://bucket", "msg", copy=False)

        # Verify set_meta was NOT called for empty metadata
        mock_package_instance.set_meta.assert_not_called()

    def test_push_normalizes_registry_url(self, backend):
        """Test that registry URLs without s3:// prefix are normalized."""
        # Create mock Package
        mock_package_instance = Mock()
        mock_package_class = Mock()
        mock_package_class.return_value = mock_package_instance
        mock_package_instance.set = Mock()
        mock_package_instance.set_meta = Mock()
        mock_package_instance.push = Mock(return_value="hashXYZ")

        # Inject the mock into backend
        backend.quilt3.Package = mock_package_class

        # Execute with registry missing s3:// prefix
        pkg_builder = {"entries": [], "metadata": {}}
        backend._backend_push_package(pkg_builder, "test/pkg", "my-bucket", "msg", copy=False)

        # Verify registry was normalized to include s3:// prefix
        call_kwargs = mock_package_instance.push.call_args[1]
        assert call_kwargs['registry'] == "s3://my-bucket"


class TestBackendGetPackage:
    """Test _backend_get_package() handles missing packages and versions."""

    def test_get_existing_package(self, backend):
        """Successfully retrieve package by name."""
        # Mock Package.browse to return a package
        mock_package = Mock()
        mock_package.name = "test/pkg"

        backend.quilt3.Package.browse = Mock(return_value=mock_package)

        # Execute backend primitive
        result = backend._backend_get_package("test/pkg", "s3://bucket")

        # Verify correct package was returned
        assert result == mock_package
        backend.quilt3.Package.browse.assert_called_once_with("test/pkg", registry="s3://bucket")

    def test_get_package_with_hash(self, backend):
        """Retrieve specific version by hash."""
        # Mock Package.browse to return a package
        mock_package = Mock()
        mock_package.top_hash = "abc123"

        backend.quilt3.Package.browse = Mock(return_value=mock_package)

        # Execute backend primitive with top_hash
        result = backend._backend_get_package("test/pkg", "s3://bucket", top_hash="abc123")

        # Verify correct version was requested
        assert result == mock_package
        backend.quilt3.Package.browse.assert_called_once_with("test/pkg", registry="s3://bucket", top_hash="abc123")

    def test_get_package_without_hash(self, backend):
        """Retrieve latest version when no hash specified."""
        # Mock Package.browse to return a package
        mock_package = Mock()

        backend.quilt3.Package.browse = Mock(return_value=mock_package)

        # Execute backend primitive without top_hash
        result = backend._backend_get_package("test/pkg", "s3://bucket", top_hash=None)

        # Verify no top_hash was passed (defaults to latest)
        assert result == mock_package
        backend.quilt3.Package.browse.assert_called_once_with("test/pkg", registry="s3://bucket")

    def test_get_nonexistent_package(self, backend):
        """Raise appropriate error for missing package."""
        # Mock Package.browse to raise exception
        backend.quilt3.Package.browse = Mock(side_effect=Exception("Package not found"))

        # Execute backend primitive - should propagate exception
        with pytest.raises(Exception) as exc_info:
            backend._backend_get_package("missing/pkg", "s3://bucket")

        assert "Package not found" in str(exc_info.value)


class TestBackendDiffPackages:
    """Test _backend_diff_packages() comparison logic."""

    def test_diff_identical_packages(self, backend):
        """Return empty diff for identical packages."""
        # Create two identical mock packages
        mock_pkg1 = Mock()
        mock_pkg2 = Mock()

        # Mock diff to return empty changes
        mock_pkg1.diff = Mock(return_value=([], [], []))

        # Execute backend primitive
        result = backend._backend_diff_packages(mock_pkg1, mock_pkg2)

        # Verify empty diff
        assert result == {"added": [], "deleted": [], "modified": []}
        mock_pkg1.diff.assert_called_once_with(mock_pkg2)

    def test_diff_with_additions(self, backend):
        """Detect added files correctly."""
        # Create mock packages
        mock_pkg1 = Mock()
        mock_pkg2 = Mock()

        # Mock diff to return additions
        mock_pkg1.diff = Mock(return_value=(["new_file.txt", "data/another.csv"], [], []))

        # Execute backend primitive
        result = backend._backend_diff_packages(mock_pkg1, mock_pkg2)

        # Verify additions detected
        assert result["added"] == ["new_file.txt", "data/another.csv"]
        assert result["deleted"] == []
        assert result["modified"] == []

    def test_diff_with_deletions(self, backend):
        """Detect deleted files correctly."""
        # Create mock packages
        mock_pkg1 = Mock()
        mock_pkg2 = Mock()

        # Mock diff to return deletions
        mock_pkg1.diff = Mock(return_value=([], ["removed_file.txt"], []))

        # Execute backend primitive
        result = backend._backend_diff_packages(mock_pkg1, mock_pkg2)

        # Verify deletions detected
        assert result["added"] == []
        assert result["deleted"] == ["removed_file.txt"]
        assert result["modified"] == []

    def test_diff_with_modifications(self, backend):
        """Detect modified files correctly."""
        # Create mock packages
        mock_pkg1 = Mock()
        mock_pkg2 = Mock()

        # Mock diff to return modifications
        mock_pkg1.diff = Mock(return_value=([], [], ["changed_file.txt", "data/updated.csv"]))

        # Execute backend primitive
        result = backend._backend_diff_packages(mock_pkg1, mock_pkg2)

        # Verify modifications detected
        assert result["added"] == []
        assert result["deleted"] == []
        assert result["modified"] == ["changed_file.txt", "data/updated.csv"]

    def test_diff_with_all_change_types(self, backend):
        """Detect all types of changes in a single diff."""
        # Create mock packages
        mock_pkg1 = Mock()
        mock_pkg2 = Mock()

        # Mock diff to return all change types
        mock_pkg1.diff = Mock(return_value=(["added.txt"], ["deleted.txt"], ["modified.txt"]))

        # Execute backend primitive
        result = backend._backend_diff_packages(mock_pkg1, mock_pkg2)

        # Verify all changes detected
        assert result["added"] == ["added.txt"]
        assert result["deleted"] == ["deleted.txt"]
        assert result["modified"] == ["modified.txt"]

    def test_diff_returns_dict_directly(self, backend):
        """Handle case where diff returns dict instead of tuple (edge case)."""
        # Create mock packages
        mock_pkg1 = Mock()
        mock_pkg2 = Mock()

        # Mock diff to return dict directly (unexpected format)
        mock_pkg1.diff = Mock(return_value={"added": ["file.txt"], "deleted": []})

        # Execute backend primitive
        result = backend._backend_diff_packages(mock_pkg1, mock_pkg2)

        # Verify dict is returned as-is
        assert result == {"added": ["file.txt"], "deleted": []}

    def test_diff_handles_non_string_paths(self, backend):
        """Convert non-string path objects to strings."""
        # Create mock packages
        mock_pkg1 = Mock()
        mock_pkg2 = Mock()

        # Mock diff to return path objects (not strings)
        class MockPath:
            def __init__(self, path):
                self.path = path

            def __str__(self):
                return self.path

        mock_pkg1.diff = Mock(return_value=([MockPath("new.txt")], [MockPath("old.txt")], [MockPath("changed.txt")]))

        # Execute backend primitive
        result = backend._backend_diff_packages(mock_pkg1, mock_pkg2)

        # Verify paths are converted to strings
        assert result["added"] == ["new.txt"]
        assert result["deleted"] == ["old.txt"]
        assert result["modified"] == ["changed.txt"]


class TestBackendGetPackageEntries:
    """Test _backend_get_package_entries() normalizes quilt3 types."""

    def test_get_entries_from_package(self, backend):
        """Extract entries with normalized types from quilt3 Package."""
        # Create mock package with entries
        mock_package = Mock()

        # Mock entry objects with quilt3-specific types
        class MockPhysicalKey:
            def __init__(self, uri):
                self.uri = uri

            def __str__(self):
                return self.uri

        mock_entry1 = Mock()
        mock_entry1.physical_key = MockPhysicalKey("s3://bucket/file1.txt")
        mock_entry1.size = 1024
        mock_entry1.hash = "hash1"
        mock_entry1.meta = {"type": "text"}

        mock_entry2 = Mock()
        mock_entry2.physical_key = MockPhysicalKey("s3://bucket/file2.csv")
        mock_entry2.size = 2048
        mock_entry2.hash = "hash2"
        mock_entry2.meta = None

        # Mock walk() to yield entries
        mock_package.walk = Mock(
            return_value=[
                ("file1.txt", mock_entry1),
                ("data/file2.csv", mock_entry2),
            ]
        )

        # Execute backend primitive
        result = backend._backend_get_package_entries(mock_package)

        # Verify entries are normalized to domain types
        assert len(result) == 2
        assert "file1.txt" in result
        assert "data/file2.csv" in result

        # Check first entry
        entry1 = result["file1.txt"]
        assert entry1["logicalKey"] == "file1.txt"
        assert entry1["physicalKey"] == "s3://bucket/file1.txt"  # Converted from PhysicalKey object
        assert entry1["size"] == 1024
        assert entry1["hash"] == "hash1"
        assert entry1["meta"] == {"type": "text"}

        # Check second entry
        entry2 = result["data/file2.csv"]
        assert entry2["logicalKey"] == "data/file2.csv"
        assert entry2["physicalKey"] == "s3://bucket/file2.csv"
        assert entry2["size"] == 2048
        assert entry2["hash"] == "hash2"
        assert entry2["meta"] is None

    def test_get_entries_from_empty_package(self, backend):
        """Return empty dict for package with no entries."""
        # Create mock package with no entries
        mock_package = Mock()
        mock_package.walk = Mock(return_value=[])

        # Execute backend primitive
        result = backend._backend_get_package_entries(mock_package)

        # Verify empty result
        assert result == {}


class TestBackendGetPackageMetadata:
    """Test _backend_get_package_metadata() extracts metadata correctly."""

    def test_get_metadata_from_package(self, backend):
        """Extract metadata dictionary from package."""
        # Create mock package with metadata
        mock_package = Mock()
        mock_package.meta = {"author": "test", "version": "1.0"}

        # Execute backend primitive
        result = backend._backend_get_package_metadata(mock_package)

        # Verify metadata extracted
        assert result == {"author": "test", "version": "1.0"}

    def test_get_metadata_from_package_without_metadata(self, backend):
        """Return empty dict when package has no metadata."""
        # Create mock package with None metadata
        mock_package = Mock()
        mock_package.meta = None

        # Execute backend primitive
        result = backend._backend_get_package_metadata(mock_package)

        # Verify empty dict returned
        assert result == {}

    def test_get_metadata_from_package_with_empty_metadata(self, backend):
        """Return empty dict when package has empty metadata dict."""
        # Create mock package with empty metadata
        mock_package = Mock()
        mock_package.meta = {}

        # Execute backend primitive
        result = backend._backend_get_package_metadata(mock_package)

        # Verify empty dict returned
        assert result == {}
