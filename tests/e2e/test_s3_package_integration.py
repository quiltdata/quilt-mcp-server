"""Integration tests for S3-to-package creation."""

import pytest

from quilt_mcp.constants import KNOWN_TEST_PACKAGE
from quilt_mcp.tools.packages import package_create_from_s3

pytestmark = pytest.mark.usefixtures("backend_mode")


class TestPackageCreateFromS3Integration:
    """Integration tests that hit real S3 buckets."""

    def test_successful_package_creation(self, test_bucket, test_registry):
        """Test successful package creation with real S3 integration.

        This test uses test_bucket fixture (from QUILT_TEST_BUCKET env var).
        The test will be skipped if the bucket is not set.
        """
        result = package_create_from_s3(
            source_bucket=test_bucket,
            package_name=KNOWN_TEST_PACKAGE,
            description="Integration test package",
            target_registry=test_registry,
            dry_run=True,  # Use dry_run to avoid creating actual packages in tests
        )

        # Convert Pydantic model to dict for easier access
        result_dict = result.model_dump()

        # MUST FAIL with helpful error message if the bucket is not accessible
        assert result_dict.get("success") is True, (
            f"Package creation failed. Error: {result_dict.get('error', 'Unknown error')}. "
            f"Bucket: {test_bucket}. "
            f"This means the bucket is not accessible in the test environment. "
            f"Check AWS credentials and bucket permissions. "
            f"Full result: {result_dict}"
        )

        # Verify the dry_run returned the expected preview structure
        assert result_dict.get("action") == "preview", (
            f"Expected action='preview' for dry_run=True, got {result_dict.get('action')}. Full result: {result_dict}"
        )

        assert "package_name" in result_dict, f"Missing 'package_name' in preview result. Full result: {result_dict}"

        assert result_dict["package_name"] == KNOWN_TEST_PACKAGE, (
            f"Expected package_name='{KNOWN_TEST_PACKAGE}', got {result_dict.get('package_name')}"
        )

        # Verify structure preview is present (it's nested in confirmation)
        assert "confirmation" in result_dict, f"Missing 'confirmation' in dry_run result. Full result: {result_dict}"
        assert "structure_preview" in result_dict["confirmation"], (
            f"Missing 'structure_preview' in confirmation. Full result: {result_dict}"
        )

        # Verify registry was set correctly
        assert result_dict.get("registry") == test_registry, (
            f"Expected registry='{test_registry}', got {result_dict.get('registry')}"
        )
