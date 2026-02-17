"""Unit tests for package tool response serialization.

These tests verify that package tools correctly serialize domain objects to JSON-safe types.
Regression tests for serialization bugs where Package objects were returned instead of strings.
"""

import pytest
from pydantic import ValidationError
from unittest.mock import Mock, patch
from quilt3 import Package

from quilt_mcp.domain.package_creation import Package_Creation_Result
from quilt_mcp.tools.package_crud import package_update
from quilt_mcp.tools.s3_package_ingestion import package_create_from_s3
from quilt_mcp.tools.responses import PackageUpdateSuccess, PackageUpdateError


class TestPackageUpdateResponseSerialization:
    """Test that package_update correctly serializes responses."""

    @pytest.fixture
    def mock_quilt_ops(self):
        """Mock QuiltOps instance."""
        return Mock()

    def test_package_update_success_response_validates_string_hash(self):
        """Test that PackageUpdateSuccess validates top_hash as string.

        Regression test for bug where Package objects were passed to Pydantic models
        expecting strings, causing validation errors like:
        "Input should be a valid string [type=string_type, input_value=(remote Package)..., input_type=Package]"

        This is a focused unit test that directly validates Pydantic serialization.
        """
        # Test 1: Valid string hash - should succeed
        result = PackageUpdateSuccess(
            package_name="test/package",
            registry="s3://test-bucket",
            top_hash="abc123def456",  # Valid string
            files_added=5,
            package_url="https://example.com/package",
            files=[],
            message="Updated successfully",
        )

        assert isinstance(result, PackageUpdateSuccess)
        assert isinstance(result.top_hash, str)
        assert result.top_hash == "abc123def456"
        assert result.package_name == "test/package"
        assert result.files_added == 5

        # Test 2: Package object - should fail validation
        fake_package = Package()
        with pytest.raises(Exception) as exc_info:
            PackageUpdateSuccess(
                package_name="test/package",
                registry="s3://test-bucket",
                top_hash=fake_package,  # Invalid: Package object instead of string
                files_added=5,
                package_url="https://example.com/package",
                files=[],
                message="Updated",
            )

        error_msg = str(exc_info.value).lower()
        assert "validation" in error_msg or "string" in error_msg

    def test_package_update_detects_package_object_in_top_hash(self, mock_quilt_ops):
        """Test that Pydantic validation catches Package objects in top_hash field.

        This test simulates the bug condition: QuiltOps (or backend) accidentally
        returns a Package object instead of a string hash. Pydantic should catch this.
        """
        # Setup: Simulate bug - return Package object instead of string
        fake_package = Package()  # This is a Package object, not a string!

        # Create a result with a Package object where string is expected
        # This should fail Pydantic validation when constructing PackageUpdateSuccess
        with pytest.raises(Exception) as exc_info:
            PackageUpdateSuccess(
                package_name="test/package",
                registry="s3://test-bucket",
                top_hash=fake_package,  # BUG: Package object instead of string
                files_added=5,
                package_url="https://example.com/package",
                files=[],
                message="Updated",
            )

        # Verify: Pydantic raises validation error mentioning type mismatch
        error_msg = str(exc_info.value)
        assert "validation error" in error_msg.lower() or "string" in error_msg.lower()

    def test_package_update_handles_backend_returning_package_object(self, mock_quilt_ops):
        """Test error handling when backend mistakenly returns Package object.

        If the backend's _backend_push_package() returns a Package object instead
        of a string hash, the tool should catch this and return a proper error response.
        """
        # Setup: Simulate backend bug - Package_Creation_Result with Package object
        fake_package = Package()
        mock_result = Mock(spec=Package_Creation_Result)
        mock_result.package_name = "test/package"
        mock_result.top_hash = fake_package  # BUG CONDITION
        mock_result.registry = "s3://test-bucket"
        mock_result.catalog_url = "https://example.com"
        mock_result.file_count = 5
        mock_result.success = True

        mock_quilt_ops.update_package_revision.return_value = mock_result

        # Mock authentication to avoid JWT/IAM requirements in unit tests
        mock_auth_ctx = Mock()
        mock_auth_ctx.authorized = True
        mock_auth_ctx.auth_type = "iam"
        mock_auth_ctx.error = None

        with (
            patch('quilt_mcp.tools.package_crud.QuiltOpsFactory') as mock_factory,
            patch('quilt_mcp.tools.package_crud.check_package_authorization', return_value=mock_auth_ctx),
        ):
            mock_factory.create.return_value = mock_quilt_ops

            # Execute: This should either fail gracefully or catch the validation error
            result = package_update(
                package_name="test/package",
                s3_uris=["s3://bucket/file.csv"],
                registry="s3://test-bucket",
            )

        # Verify: Should return an error response, not crash
        # The Pydantic validation will raise an exception that gets caught
        assert isinstance(result, PackageUpdateError)
        assert "validation error" in result.error.lower() or "package update failed" in result.error.lower()


class TestPackageCreateFromS3ResponseSerialization:
    """Test that package_create_from_s3 correctly serializes responses."""

    @pytest.fixture
    def mock_quilt_summary(self):
        """Mock the create_quilt_summary_files function."""
        return Mock(
            return_value={
                "summary_package": {
                    "quilt_summarize.json": {},
                    "visualizations": {},
                },
                "files_generated": {},
                "visualization_count": 0,
            }
        )

    def test_package_create_from_s3_returns_string_hash(self, mock_quilt_summary):
        """Test that package_create_from_s3 returns string hash, not Package object.

        Regression test for bug where package_hash field received Package object
        instead of string, causing: "Input should be a valid string [input_type=Package]"
        """
        mock_context = Mock()
        mock_context.registry = None

        with (
            patch('quilt_mcp.tools.s3_package_ingestion.create_quilt_summary_files', mock_quilt_summary),
            patch('quilt_mcp.tools.s3_package_ingestion.get_s3_client') as mock_s3_client,
            patch('quilt_mcp.tools.s3_package_ingestion.bucket_recommendations_get') as mock_recommendations,
        ):
            # Setup S3 mock
            mock_client = Mock()
            mock_client.list_objects_v2.return_value = {
                'Contents': [],
                'IsTruncated': False,
            }
            mock_s3_client.return_value = mock_client

            # Mock recommendations
            mock_recommendations.return_value = {"registries": ["s3://test-registry"]}

            # Dry run mode to test response construction
            result = package_create_from_s3(
                source_bucket="test-bucket",
                package_name="test/package",
                dry_run=True,
                context=mock_context,
            )

        # In dry run mode, package_hash should be None (not a Package object)
        from quilt_mcp.tools.responses import PackageCreateFromS3Success

        if isinstance(result, PackageCreateFromS3Success):
            assert result.package_hash is None or isinstance(result.package_hash, str)
            assert not isinstance(result.package_hash, Package)


class TestDomainObjectSerialization:
    """Test that domain objects have proper serialization."""

    def test_package_creation_result_top_hash_is_string(self):
        """Test that Package_Creation_Result enforces string type for top_hash."""
        result = Package_Creation_Result(
            package_name="test/pkg",
            top_hash="abc123",
            registry="s3://bucket",
            catalog_url="https://example.com",
            file_count=3,
            success=True,
        )

        assert isinstance(result.top_hash, str)
        assert result.top_hash == "abc123"

    def test_package_creation_result_rejects_package_object(self):
        """Test that Package_Creation_Result validation catches non-string top_hash."""
        fake_package = Package()

        # dataclass doesn't enforce types at runtime by default, but we document the contract
        # The bug would manifest when this gets passed to Pydantic models
        result = Package_Creation_Result(
            package_name="test/pkg",
            top_hash=fake_package,  # Wrong type - should be str
            registry="s3://bucket",
            catalog_url=None,
            file_count=0,
            success=False,
        )

        # This should work (dataclass doesn't validate), but Pydantic models will reject it
        assert result.top_hash == fake_package

        # Now try to use it in a Pydantic model - this should fail
        with pytest.raises(ValidationError):
            PackageUpdateSuccess(
                package_name="test/pkg",
                registry="s3://bucket",
                top_hash=result.top_hash,  # Package object will fail validation
                files_added=0,
                files=[],
            )
