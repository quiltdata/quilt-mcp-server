"""Unit tests for package API validation.

Tests verify that package mutation operations (create, update, delete) require
explicit registry parameters and fail with clear error messages when registry
is not provided.

This addresses Phase 8, section 2.1 of spec/a10-no-default-registry.md.

NOTE: Package creation tools (package_create, package_create_from_s3) have been
migrated to use QuiltOps and are now thin wrappers. Trivial unit tests for
parameter validation have been removed as per the migration design.
"""

import pytest

from quilt_mcp.tools.packages import package_update, package_delete


# Removed TestPackageCreateValidation class - package_create now uses QuiltOps
# and is a thin wrapper. Parameter validation is handled by QuiltOps backend.


class TestPackageUpdateValidation:
    """Test package_update() requires explicit registry parameter."""

    def test_package_update_requires_registry(self):
        """package_update() should fail with clear error if registry not provided.

        Validates:
        - Function returns error response (success=False)
        - Error message mentions "registry" and "required"
        - Error message suggests proper format with "s3://"
        """
        result = package_update(
            package_name="test/data",
            s3_uris=["s3://test-bucket/updated.csv"],
            registry="",  # Empty string - should fail
            message="Update test",
        )

        # Should fail
        assert result.success is False

        # Error message should mention registry requirement
        error_text = result.error.lower()
        assert "registry" in error_text
        assert "required" in error_text

        # Should suggest proper S3 URI format
        assert "s3://" in result.error

    def test_package_update_with_explicit_registry(self, test_bucket):
        """package_update() works when registry explicitly provided.

        Validates:
        - Function accepts explicit registry parameter
        - If it fails, it's NOT due to missing registry (could be AWS/permissions error)
        """
        result = package_update(
            package_name="test/coverage-test",
            s3_uris=["s3://test-bucket/updated.csv"],
            registry=test_bucket,  # Explicit registry provided
            message="Update test",
        )

        # If it fails, it should NOT be a registry configuration error
        if not result.success:
            error_text = result.error.lower()
            # Should not contain the registry requirement error message
            if "registry" in error_text:
                assert "required" not in error_text


class TestPackageDeleteValidation:
    """Test package_delete() requires explicit registry parameter."""

    def test_package_delete_requires_registry(self):
        """package_delete() should fail with clear error if registry not provided.

        Validates:
        - Function returns error response (success=False)
        - Error message mentions "registry" and "required"
        - Error message suggests proper format with "s3://"
        """
        result = package_delete(
            package_name="test/data",
            registry="",  # Empty string - should fail
        )

        # Should fail
        assert result.success is False

        # Error message should mention registry requirement
        error_text = result.error.lower()
        assert "registry" in error_text
        assert "required" in error_text

        # Should suggest proper S3 URI format
        assert "s3://" in result.error

    def test_package_delete_with_explicit_registry(self, test_bucket):
        """package_delete() works when registry explicitly provided.

        Validates:
        - Function accepts explicit registry parameter
        - If it fails, it's NOT due to missing registry (could be AWS/permissions error)
        """
        result = package_delete(
            package_name="test/coverage-test",
            registry=test_bucket,  # Explicit registry provided
        )

        # If it fails, it should NOT be a registry configuration error
        if not result.success:
            error_text = result.error.lower()
            # Should not contain the registry requirement error message
            if "registry" in error_text:
                assert "required" not in error_text


class TestRegistryValidationErrorMessages:
    """Test that error messages are helpful and actionable."""

    # Removed test_create_error_includes_suggested_actions - package_create now uses QuiltOps

    def test_update_error_includes_suggested_actions(self):
        """Verify package_update error includes helpful suggested actions."""
        result = package_update(
            package_name="test/data",
            s3_uris=["s3://test-bucket/file.csv"],
            registry="",
            message="Test",
        )

        # Should include suggested actions in the error response
        assert hasattr(result, "suggested_actions")
        if result.suggested_actions:
            # Suggested actions should provide guidance
            actions_text = " ".join(result.suggested_actions).lower()
            assert "registry" in actions_text or "bucket" in actions_text

    def test_delete_error_includes_suggested_actions(self):
        """Verify package_delete error includes helpful suggested actions."""
        result = package_delete(
            package_name="test/data",
            registry="",
        )

        # Should include suggested actions in the error response
        assert hasattr(result, "suggested_actions")
        if result.suggested_actions:
            # Suggested actions should provide guidance
            actions_text = " ".join(result.suggested_actions).lower()
            assert "registry" in actions_text or "bucket" in actions_text


class TestRegistryParameterTypes:
    """Test that different types of invalid registry values are handled."""

    # Removed test_create_with_none_registry_fails - package_create now uses QuiltOps

    def test_update_with_none_registry_fails(self):
        """Verify package_update with None registry fails gracefully."""
        try:
            result = package_update(
                package_name="test/data",
                s3_uris=["s3://test-bucket/file.csv"],
                registry=None,  # type: ignore
                message="Test",
            )
            # Should either fail validation or return error
            assert not result.success
        except TypeError:
            # Type error is also acceptable for None value
            pass

    def test_delete_with_none_registry_fails(self):
        """Verify package_delete with None registry fails gracefully."""
        try:
            result = package_delete(
                package_name="test/data",
                registry=None,  # type: ignore
            )
            # Should either fail validation or return error
            assert not result.success
        except TypeError:
            # Type error is also acceptable for None value
            pass
