"""Unit tests for package_management integration with package_ops layer.

These tests verify the integration between package_management.py and package_ops.py
without making real AWS calls. They use mocks to isolate the behavior being tested:
parameter transformation, metadata template processing, and call chain correctness.

For true end-to-end tests with real AWS operations, see tests/e2e/test_package_management.py
"""

import pytest
from unittest.mock import patch

from quilt_mcp.tools.package_management import create_package_enhanced


class TestPackageManagementToOpsIntegration:
    """Test integration between package_management and package_ops layers.

    These tests verify that:
    1. Metadata templates are correctly processed and passed through the call chain
    2. Critical parameters like auto_organize=False are preserved
    3. The integration between layers works without making AWS calls

    Note: These are fast unit tests (<100ms) that use mocks. For slow end-to-end
    tests with real AWS operations, see tests/e2e/test_package_management.py
    """

    @patch("quilt_mcp.tools.permissions.bucket_recommendations_get")
    @patch("quilt_mcp.tools.package_ops.quilt_service.create_package_revision")
    def test_template_processing_flows_to_quilt_service(self, mock_create_revision, mock_bucket_recs):
        """Verify metadata templates are correctly processed and passed to quilt_service.

        This tests the integration between:
        - package_management.py: Template selection and processing
        - package_ops.py: Parameter transformation and validation
        - quilt_service: Final package creation (mocked)

        Behavior tested:
        - Standard template adds creation_date
        - auto_organize=False is preserved through the call chain
        - Description is merged into template metadata
        - S3 URIs are passed through correctly

        Performance: <100ms (no AWS calls)
        """
        # Mock to prevent AWS calls
        mock_bucket_recs.return_value = {
            "success": True,
            "recommendations": {"primary_recommendations": [{"bucket_name": "test-bucket"}]},
        }

        # Mock successful package creation
        mock_create_revision.return_value = {
            "status": "success",
            "top_hash": "test_hash_123",
            "entries_added": 1,
            "files": [{"logical_path": "file.csv", "source": "s3://bucket/file.csv"}],
        }

        # Test the integration
        result = create_package_enhanced(
            name="test/package",
            files=["s3://bucket/file.csv"],
            description="Test package",
            metadata_template="standard",
        )

        # Verify success
        assert result["status"] == "success"

        # Verify call chain preserved critical parameters
        mock_create_revision.assert_called_once()
        call_args = mock_create_revision.call_args

        assert call_args[1]["package_name"] == "test/package"
        assert not call_args[1]["auto_organize"]  # Critical: must be False for package_ops
        assert call_args[1]["s3_uris"] == ["s3://bucket/file.csv"]

        # Verify template processing worked
        processed_metadata = call_args[1]["metadata"]
        assert "description" in processed_metadata
        assert processed_metadata["description"] == "Test package"
        assert "creation_date" in processed_metadata  # Added by standard template

    @patch("quilt_mcp.tools.permissions.bucket_recommendations_get")
    @patch("quilt_mcp.tools.package_ops.quilt_service.create_package_revision")
    def test_genomics_template_processing(self, mock_create_revision, mock_bucket_recs):
        """Verify genomics template is correctly processed with custom metadata.

        Performance: <100ms (no AWS calls)
        """
        # Mock to prevent AWS calls
        mock_bucket_recs.return_value = {
            "success": True,
            "recommendations": {"primary_recommendations": [{"bucket_name": "test-bucket"}]},
        }

        # Mock successful package creation
        mock_create_revision.return_value = {
            "status": "success",
            "top_hash": "test_hash_456",
            "entries_added": 2,
            "files": [
                {"logical_path": "sample1.vcf", "source": "s3://bucket/sample1.vcf"},
                {"logical_path": "sample2.vcf", "source": "s3://bucket/sample2.vcf"},
            ],
        }

        # Test with genomics template
        result = create_package_enhanced(
            name="genomics/study1",
            files=["s3://bucket/sample1.vcf", "s3://bucket/sample2.vcf"],
            description="Genomics study",
            metadata_template="genomics",
            metadata={"organism": "human", "genome_build": "GRCh38"},
        )

        # Verify success
        assert result["status"] == "success"

        # Verify template-specific metadata
        mock_create_revision.assert_called_once()
        call_args = mock_create_revision.call_args
        processed_metadata = call_args[1]["metadata"]

        # Genomics template fields
        assert processed_metadata["package_type"] == "genomics"
        assert processed_metadata["organism"] == "human"
        assert processed_metadata["genome_build"] == "GRCh38"
        assert "description" in processed_metadata

    @patch("quilt_mcp.tools.permissions.bucket_recommendations_get")
    @patch("quilt_mcp.tools.package_ops.quilt_service.create_package_revision")
    def test_explicit_registry_skips_bucket_recommendation(self, mock_create_revision, mock_bucket_recs):
        """Verify that providing explicit registry skips bucket recommendation lookup.

        This optimization avoids AWS calls when registry is known.

        Performance: <50ms (no AWS calls, skips bucket recommendation)
        """
        # Mock successful package creation
        mock_create_revision.return_value = {
            "status": "success",
            "top_hash": "test_hash_789",
            "entries_added": 1,
            "files": [{"logical_path": "data.csv", "source": "s3://bucket/data.csv"}],
        }

        # Test with explicit registry
        result = create_package_enhanced(
            name="test/package",
            files=["s3://bucket/data.csv"],
            description="Test with explicit registry",
            metadata_template="standard",
            registry="s3://explicit-bucket",
        )

        # Verify success
        assert result["status"] == "success"

        # Verify bucket_recommendations_get was NOT called (optimization)
        mock_bucket_recs.assert_not_called()

        # Verify explicit registry was used
        mock_create_revision.assert_called_once()
        call_args = mock_create_revision.call_args
        assert call_args[1]["registry"] == "s3://explicit-bucket"
