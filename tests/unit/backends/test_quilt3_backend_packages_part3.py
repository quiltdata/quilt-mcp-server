"""
Tests for Quilt3_Backend package operations, specifically create_package_revision().

This module tests the Quilt3_Backend implementation of package operations
following TDD principles, with focus on create_package_revision() method.
"""

import pytest
from unittest.mock import Mock, patch

from quilt_mcp.ops.exceptions import ValidationError, BackendError
from quilt_mcp.domain.package_creation import Package_Creation_Result


class TestQuilt3BackendDiffPackages:
    """Test diff_packages method implementation in Quilt3_Backend."""

    @pytest.fixture
    def backend(self):
        """Create Quilt3_Backend instance for testing."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        with patch('quilt_mcp.backends.quilt3_backend_base.quilt3'):
            return Quilt3_Backend()

    def test_diff_packages_without_hashes(self, backend):
        """Test package diffing without specific hashes (uses latest versions)."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            # Mock package objects
            mock_pkg1 = Mock()
            mock_pkg2 = Mock()

            # Mock Package.browse calls
            mock_quilt3.Package.browse.side_effect = [mock_pkg1, mock_pkg2]

            # Mock diff result as tuple (added, deleted, modified)
            mock_pkg1.diff.return_value = (
                ["new_file.txt", "folder/added.csv"],
                ["old_file.txt"],
                ["modified_file.txt", "data/changed.json"],
            )

            result = backend.diff_packages(
                package1_name="user/package1", package2_name="user/package2", registry="s3://test-registry"
            )

            # Verify Package.browse calls
            assert mock_quilt3.Package.browse.call_count == 2
            mock_quilt3.Package.browse.assert_any_call("user/package1", registry="s3://test-registry")
            mock_quilt3.Package.browse.assert_any_call("user/package2", registry="s3://test-registry")

            # Verify diff call
            mock_pkg1.diff.assert_called_once_with(mock_pkg2)

            # Verify result format
            expected_result = {
                "added": ["new_file.txt", "folder/added.csv"],
                "deleted": ["old_file.txt"],
                "modified": ["modified_file.txt", "data/changed.json"],
            }
            assert result == expected_result

    def test_diff_packages_with_hashes(self, backend):
        """Test package diffing with specific hashes."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            # Mock package objects
            mock_pkg1 = Mock()
            mock_pkg2 = Mock()

            # Mock Package.browse calls
            mock_quilt3.Package.browse.side_effect = [mock_pkg1, mock_pkg2]

            # Mock diff result
            mock_pkg1.diff.return_value = ([], ["removed.txt"], [])

            result = backend.diff_packages(
                package1_name="user/package1",
                package2_name="user/package2",
                registry="s3://test-registry",
                package1_hash="abc123",
                package2_hash="def456",
            )

            # Verify Package.browse calls with hashes
            mock_quilt3.Package.browse.assert_any_call(
                "user/package1", registry="s3://test-registry", top_hash="abc123"
            )
            mock_quilt3.Package.browse.assert_any_call(
                "user/package2", registry="s3://test-registry", top_hash="def456"
            )

            # Verify result
            expected_result = {"added": [], "deleted": ["removed.txt"], "modified": []}
            assert result == expected_result

    def test_diff_packages_conditional_hash_handling(self, backend):
        """Test conditional hash handling logic."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            # Mock package objects
            mock_pkg1 = Mock()
            mock_pkg2 = Mock()

            # Mock Package.browse calls
            mock_quilt3.Package.browse.side_effect = [mock_pkg1, mock_pkg2]

            # Mock diff result
            mock_pkg1.diff.return_value = ([], [], ["updated.txt"])

            # Test with only package1_hash provided
            result = backend.diff_packages(
                package1_name="user/package1",
                package2_name="user/package2",
                registry="s3://test-registry",
                package1_hash="abc123",
                package2_hash=None,
            )

            # Verify first call has hash, second doesn't
            mock_quilt3.Package.browse.assert_any_call(
                "user/package1", registry="s3://test-registry", top_hash="abc123"
            )
            mock_quilt3.Package.browse.assert_any_call("user/package2", registry="s3://test-registry")

    def test_diff_packages_tuple_to_dict_transformation(self, backend):
        """Test tuple-to-dict transformation logic."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            # Mock package objects
            mock_pkg1 = Mock()
            mock_pkg2 = Mock()

            # Mock Package.browse calls
            mock_quilt3.Package.browse.side_effect = [mock_pkg1, mock_pkg2]

            # Test with empty tuple elements
            mock_pkg1.diff.return_value = ([], None, ["modified.txt"])

            result = backend.diff_packages(
                package1_name="user/package1", package2_name="user/package2", registry="s3://test-registry"
            )

            # Verify empty/None values are handled correctly
            expected_result = {"added": [], "deleted": [], "modified": ["modified.txt"]}
            assert result == expected_result

    def test_diff_packages_non_tuple_result_handling(self, backend):
        """Test handling of non-tuple diff results."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            # Mock package objects
            mock_pkg1 = Mock()
            mock_pkg2 = Mock()

            # Mock Package.browse calls
            mock_quilt3.Package.browse.side_effect = [mock_pkg1, mock_pkg2]

            # Mock diff result as dict (unexpected format)
            mock_pkg1.diff.return_value = {"added": ["file1.txt"], "deleted": ["file2.txt"], "modified": ["file3.txt"]}

            result = backend.diff_packages(
                package1_name="user/package1", package2_name="user/package2", registry="s3://test-registry"
            )

            # Should return the dict as-is
            expected_result = {"added": ["file1.txt"], "deleted": ["file2.txt"], "modified": ["file3.txt"]}
            assert result == expected_result

    def test_diff_packages_unexpected_result_format(self, backend):
        """Test handling of completely unexpected diff result format."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            # Mock package objects
            mock_pkg1 = Mock()
            mock_pkg2 = Mock()

            # Mock Package.browse calls
            mock_quilt3.Package.browse.side_effect = [mock_pkg1, mock_pkg2]

            # Mock diff result as string (unexpected format)
            mock_pkg1.diff.return_value = "unexpected result"

            result = backend.diff_packages(
                package1_name="user/package1", package2_name="user/package2", registry="s3://test-registry"
            )

            # Should wrap in raw format
            expected_result = {"raw": ["unexpected result"]}
            assert result == expected_result

    def test_diff_packages_error_handling_package_not_found(self, backend):
        """Test error handling for missing packages."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            # Mock Package.browse to raise exception for first package
            mock_quilt3.Package.browse.side_effect = Exception("Package 'user/package1' not found")

            with pytest.raises(BackendError) as exc_info:
                backend.diff_packages(
                    package1_name="user/package1", package2_name="user/package2", registry="s3://test-registry"
                )

            assert "Quilt3 backend diff_packages failed" in str(exc_info.value)
            assert "Package 'user/package1' not found" in str(exc_info.value)

            # Verify error context
            assert exc_info.value.context['package1_name'] == "user/package1"
            assert exc_info.value.context['package2_name'] == "user/package2"
            assert exc_info.value.context['registry'] == "s3://test-registry"

    def test_diff_packages_error_handling_invalid_hash(self, backend):
        """Test error handling for invalid hashes."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            # Mock Package.browse to raise exception for invalid hash
            mock_quilt3.Package.browse.side_effect = Exception("Invalid hash: invalid-hash")

            with pytest.raises(BackendError) as exc_info:
                backend.diff_packages(
                    package1_name="user/package1",
                    package2_name="user/package2",
                    registry="s3://test-registry",
                    package1_hash="invalid-hash",
                )

            assert "Quilt3 backend diff_packages failed" in str(exc_info.value)
            assert "Invalid hash: invalid-hash" in str(exc_info.value)

            # Verify error context includes hash
            assert exc_info.value.context['package1_hash'] == "invalid-hash"

    def test_diff_packages_error_handling_diff_operation_failure(self, backend):
        """Test error handling for diff operation failure."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            # Mock package objects
            mock_pkg1 = Mock()
            mock_pkg2 = Mock()

            # Mock Package.browse calls
            mock_quilt3.Package.browse.side_effect = [mock_pkg1, mock_pkg2]

            # Mock diff to raise exception
            mock_pkg1.diff.side_effect = Exception("Diff operation failed")

            with pytest.raises(BackendError) as exc_info:
                backend.diff_packages(
                    package1_name="user/package1", package2_name="user/package2", registry="s3://test-registry"
                )

            assert "Quilt3 backend diff_packages failed" in str(exc_info.value)
            assert "Diff operation failed" in str(exc_info.value)

    def test_diff_packages_domain_dict_format_verification(self, backend):
        """Test that the method returns the correct domain dict format."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            # Mock package objects
            mock_pkg1 = Mock()
            mock_pkg2 = Mock()

            # Mock Package.browse calls
            mock_quilt3.Package.browse.side_effect = [mock_pkg1, mock_pkg2]

            # Mock comprehensive diff result
            mock_pkg1.diff.return_value = (
                ["added1.txt", "added2.csv", "folder/added3.json"],
                ["deleted1.txt", "deleted2.log"],
                ["modified1.txt", "data/modified2.csv", "config/modified3.yaml"],
            )

            result = backend.diff_packages(
                package1_name="user/package1", package2_name="user/package2", registry="s3://test-registry"
            )

            # Verify result is a dict with correct keys
            assert isinstance(result, dict)
            assert set(result.keys()) == {"added", "deleted", "modified"}

            # Verify all values are lists of strings
            for key, value in result.items():
                assert isinstance(value, list)
                for item in value:
                    assert isinstance(item, str)

            # Verify specific content
            assert len(result["added"]) == 3
            assert len(result["deleted"]) == 2
            assert len(result["modified"]) == 3

            # Verify string conversion works for path objects
            assert "added1.txt" in result["added"]
            assert "folder/added3.json" in result["added"]
