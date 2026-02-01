"""Tests for Package_Creation_Result domain object."""

import pytest
from dataclasses import FrozenInstanceError
from quilt_mcp.domain.package_creation import Package_Creation_Result


class TestPackageCreationResult:
    """Test cases for Package_Creation_Result domain object."""

    def test_package_creation_result_creation_with_required_fields(self):
        """Test creating Package_Creation_Result with all required fields."""
        result = Package_Creation_Result(
            package_name="user/test-package",
            top_hash="abc123def456",
            registry="s3://test-registry-bucket",
            catalog_url="https://test.quiltdata.com/b/test-registry-bucket/packages/user/test-package",
            file_count=5,
            success=True,
        )

        assert result.package_name == "user/test-package"
        assert result.top_hash == "abc123def456"
        assert result.registry == "s3://test-registry-bucket"
        assert result.catalog_url == "https://test.quiltdata.com/b/test-registry-bucket/packages/user/test-package"
        assert result.file_count == 5
        assert result.success is True

    def test_package_creation_result_with_optional_catalog_url_none(self):
        """Test creating Package_Creation_Result with catalog_url as None."""
        result = Package_Creation_Result(
            package_name="user/test-package",
            top_hash="abc123def456",
            registry="s3://test-registry-bucket",
            catalog_url=None,
            file_count=3,
            success=True,
        )

        assert result.catalog_url is None
        assert result.package_name == "user/test-package"
        assert result.success is True

    def test_package_creation_result_failed_creation(self):
        """Test Package_Creation_Result for failed package creation."""
        result = Package_Creation_Result(
            package_name="user/failed-package",
            top_hash="",
            registry="s3://test-registry-bucket",
            catalog_url=None,
            file_count=0,
            success=False,
        )

        assert result.success is False
        assert result.top_hash == ""
        assert result.file_count == 0
        assert result.catalog_url is None

    def test_package_creation_result_validation_empty_package_name(self):
        """Test validation fails for empty package name."""
        with pytest.raises(ValueError, match="Package name cannot be empty"):
            Package_Creation_Result(
                package_name="",
                top_hash="abc123def456",
                registry="s3://test-registry-bucket",
                catalog_url=None,
                file_count=5,
                success=True,
            )

    def test_package_creation_result_validation_invalid_package_name_format(self):
        """Test validation fails for invalid package name format."""
        with pytest.raises(ValueError, match="Package name must be in 'user/package' format"):
            Package_Creation_Result(
                package_name="invalid-package-name",
                top_hash="abc123def456",
                registry="s3://test-registry-bucket",
                catalog_url=None,
                file_count=5,
                success=True,
            )

    def test_package_creation_result_validation_empty_registry(self):
        """Test validation fails for empty registry."""
        with pytest.raises(ValueError, match="Registry cannot be empty"):
            Package_Creation_Result(
                package_name="user/test-package",
                top_hash="abc123def456",
                registry="",
                catalog_url=None,
                file_count=5,
                success=True,
            )

    def test_package_creation_result_validation_invalid_registry_format(self):
        """Test validation fails for invalid registry format."""
        with pytest.raises(ValueError, match="Registry must be an S3 URL"):
            Package_Creation_Result(
                package_name="user/test-package",
                top_hash="abc123def456",
                registry="invalid-registry",
                catalog_url=None,
                file_count=5,
                success=True,
            )

    def test_package_creation_result_validation_negative_file_count(self):
        """Test validation fails for negative file count."""
        with pytest.raises(ValueError, match="File count cannot be negative"):
            Package_Creation_Result(
                package_name="user/test-package",
                top_hash="abc123def456",
                registry="s3://test-registry-bucket",
                catalog_url=None,
                file_count=-1,
                success=True,
            )

    def test_package_creation_result_validation_success_true_requires_top_hash(self):
        """Test validation fails when success=True but top_hash is empty."""
        with pytest.raises(ValueError, match="Top hash is required when success=True"):
            Package_Creation_Result(
                package_name="user/test-package",
                top_hash="",
                registry="s3://test-registry-bucket",
                catalog_url=None,
                file_count=5,
                success=True,
            )

    def test_package_creation_result_validation_success_true_requires_positive_file_count(self):
        """Test validation fails when success=True but file_count is zero."""
        with pytest.raises(ValueError, match="File count must be positive when success=True"):
            Package_Creation_Result(
                package_name="user/test-package",
                top_hash="abc123def456",
                registry="s3://test-registry-bucket",
                catalog_url=None,
                file_count=0,
                success=True,
            )

    def test_package_creation_result_immutable(self):
        """Test that Package_Creation_Result is immutable."""
        result = Package_Creation_Result(
            package_name="user/test-package",
            top_hash="abc123def456",
            registry="s3://test-registry-bucket",
            catalog_url=None,
            file_count=5,
            success=True,
        )

        with pytest.raises(FrozenInstanceError):
            result.package_name = "user/other-package"

    def test_package_creation_result_equality(self):
        """Test Package_Creation_Result equality comparison."""
        result1 = Package_Creation_Result(
            package_name="user/test-package",
            top_hash="abc123def456",
            registry="s3://test-registry-bucket",
            catalog_url="https://test.quiltdata.com/b/test-registry-bucket/packages/user/test-package",
            file_count=5,
            success=True,
        )

        result2 = Package_Creation_Result(
            package_name="user/test-package",
            top_hash="abc123def456",
            registry="s3://test-registry-bucket",
            catalog_url="https://test.quiltdata.com/b/test-registry-bucket/packages/user/test-package",
            file_count=5,
            success=True,
        )

        result3 = Package_Creation_Result(
            package_name="user/different-package",
            top_hash="abc123def456",
            registry="s3://test-registry-bucket",
            catalog_url=None,
            file_count=5,
            success=True,
        )

        assert result1 == result2
        assert result1 != result3

    def test_package_creation_result_string_representation(self):
        """Test Package_Creation_Result string representation."""
        result = Package_Creation_Result(
            package_name="user/test-package",
            top_hash="abc123def456",
            registry="s3://test-registry-bucket",
            catalog_url="https://test.quiltdata.com/b/test-registry-bucket/packages/user/test-package",
            file_count=5,
            success=True,
        )

        str_repr = str(result)
        assert "user/test-package" in str_repr
        assert "abc123def456" in str_repr
        assert "success=True" in str_repr

    def test_package_creation_result_valid_catalog_url_formats(self):
        """Test Package_Creation_Result accepts various valid catalog URL formats."""
        valid_urls = [
            "https://example.quiltdata.com/b/bucket/packages/user/package",
            "https://catalog.example.com/b/my-bucket/packages/org/dataset",
            None,  # None should be allowed
        ]

        for url in valid_urls:
            result = Package_Creation_Result(
                package_name="user/test-package",
                top_hash="abc123def456",
                registry="s3://test-registry-bucket",
                catalog_url=url,
                file_count=5,
                success=True,
            )
            assert result.catalog_url == url

    def test_package_creation_result_edge_cases(self):
        """Test Package_Creation_Result with edge case values."""
        # Test with very long package name (but valid format)
        long_name = "user/" + "a" * 100
        result = Package_Creation_Result(
            package_name=long_name,
            top_hash="abc123def456",
            registry="s3://test-registry-bucket",
            catalog_url=None,
            file_count=1,
            success=True,
        )
        assert result.package_name == long_name

        # Test with very long top_hash
        long_hash = "a" * 64  # SHA-256 length
        result = Package_Creation_Result(
            package_name="user/test-package",
            top_hash=long_hash,
            registry="s3://test-registry-bucket",
            catalog_url=None,
            file_count=1,
            success=True,
        )
        assert result.top_hash == long_hash

        # Test with large file count
        result = Package_Creation_Result(
            package_name="user/test-package",
            top_hash="abc123def456",
            registry="s3://test-registry-bucket",
            catalog_url=None,
            file_count=10000,
            success=True,
        )
        assert result.file_count == 10000
