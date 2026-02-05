"""Tests for Catalog_Config domain object.

This test suite validates the Catalog_Config dataclass that represents catalog
configuration information in a backend-agnostic way.
"""

import pytest
from quilt_mcp.domain import Catalog_Config


class TestCatalogConfigCreation:
    """Test Catalog_Config dataclass creation and basic functionality."""

    def test_catalog_config_can_be_imported(self):
        """Test that Catalog_Config can be imported from domain module."""
        from quilt_mcp.domain import Catalog_Config

        assert Catalog_Config is not None

    def test_complete_catalog_config_creation(self):
        """Test creating a complete Catalog_Config with all fields."""
        catalog_config = Catalog_Config(
            region="us-east-1",
            api_gateway_endpoint="https://api.example.quiltdata.com",
            registry_url="https://example-registry.quiltdata.com",
            analytics_bucket="quilt-staging-analyticsbucket-10ort3e91tnoa",
            stack_prefix="quilt-staging",
            tabulator_data_catalog="quilt-quilt-staging-tabulator",
        )

        assert catalog_config.region == "us-east-1"
        assert catalog_config.api_gateway_endpoint == "https://api.example.quiltdata.com"
        assert catalog_config.analytics_bucket == "quilt-staging-analyticsbucket-10ort3e91tnoa"
        assert catalog_config.stack_prefix == "quilt-staging"
        assert catalog_config.tabulator_data_catalog == "quilt-quilt-staging-tabulator"

    def test_minimal_catalog_config_creation(self):
        """Test creating a minimal Catalog_Config with required fields only."""
        catalog_config = Catalog_Config(
            region="us-west-2",
            api_gateway_endpoint="https://api.minimal.com",
            registry_url="https://example-registry.quiltdata.com",
            analytics_bucket="minimal-analytics",
            stack_prefix="minimal",
            tabulator_data_catalog="quilt-minimal-tabulator",
        )

        assert catalog_config.region == "us-west-2"
        assert catalog_config.api_gateway_endpoint == "https://api.minimal.com"
        assert catalog_config.analytics_bucket == "minimal-analytics"
        assert catalog_config.stack_prefix == "minimal"
        assert catalog_config.tabulator_data_catalog == "quilt-minimal-tabulator"


class TestCatalogConfigValidation:
    """Test Catalog_Config field validation."""

    def test_region_field_validation(self):
        """Test that region field is properly validated."""
        # Valid region
        config = Catalog_Config(
            region="us-east-1",
            api_gateway_endpoint="https://api.example.com",
            registry_url="https://example-registry.quiltdata.com",
            analytics_bucket="test-bucket",
            stack_prefix="test",
            tabulator_data_catalog="quilt-test-tabulator",
        )
        assert config.region == "us-east-1"

        # Empty region should raise ValueError
        with pytest.raises(ValueError, match="region field cannot be empty"):
            Catalog_Config(
                region="",
                api_gateway_endpoint="https://api.example.com",
                registry_url="https://example-registry.quiltdata.com",
                analytics_bucket="test-bucket",
                stack_prefix="test",
                tabulator_data_catalog="quilt-test-tabulator",
            )

        # None region should raise TypeError
        with pytest.raises(TypeError, match="region field is required and cannot be None"):
            Catalog_Config(
                region=None,
                api_gateway_endpoint="https://api.example.com",
                registry_url="https://example-registry.quiltdata.com",
                analytics_bucket="test-bucket",
                stack_prefix="test",
                tabulator_data_catalog="quilt-test-tabulator",
            )

        # Non-string region should raise TypeError
        with pytest.raises(TypeError, match="region field must be a string"):
            Catalog_Config(
                region=123,
                api_gateway_endpoint="https://api.example.com",
                registry_url="https://example-registry.quiltdata.com",
                analytics_bucket="test-bucket",
                stack_prefix="test",
                tabulator_data_catalog="quilt-test-tabulator",
            )

    def test_api_gateway_endpoint_field_validation(self):
        """Test that api_gateway_endpoint field is properly validated."""
        # Valid endpoint
        config = Catalog_Config(
            region="us-east-1",
            api_gateway_endpoint="https://api.example.com",
            registry_url="https://example-registry.quiltdata.com",
            analytics_bucket="test-bucket",
            stack_prefix="test",
            tabulator_data_catalog="quilt-test-tabulator",
        )
        assert config.api_gateway_endpoint == "https://api.example.com"

        # Empty endpoint should raise ValueError
        with pytest.raises(ValueError, match="api_gateway_endpoint field cannot be empty"):
            Catalog_Config(
                region="us-east-1",
                api_gateway_endpoint="",
                registry_url="https://example-registry.quiltdata.com",
                analytics_bucket="test-bucket",
                stack_prefix="test",
                tabulator_data_catalog="quilt-test-tabulator",
            )

        # None endpoint should raise TypeError
        with pytest.raises(TypeError, match="api_gateway_endpoint field is required and cannot be None"):
            Catalog_Config(
                region="us-east-1",
                api_gateway_endpoint=None,
                registry_url="https://example-registry.quiltdata.com",
                analytics_bucket="test-bucket",
                stack_prefix="test",
                tabulator_data_catalog="quilt-test-tabulator",
            )

        # Non-string endpoint should raise TypeError
        with pytest.raises(TypeError, match="api_gateway_endpoint field must be a string"):
            Catalog_Config(
                region="us-east-1",
                api_gateway_endpoint=123,
                registry_url="https://example-registry.quiltdata.com",
                analytics_bucket="test-bucket",
                stack_prefix="test",
                tabulator_data_catalog="quilt-test-tabulator",
            )

    def test_analytics_bucket_field_validation(self):
        """Test that analytics_bucket field is properly validated."""
        # Valid bucket
        config = Catalog_Config(
            region="us-east-1",
            api_gateway_endpoint="https://api.example.com",
            registry_url="https://example-registry.quiltdata.com",
            analytics_bucket="my-analytics-bucket",
            stack_prefix="test",
            tabulator_data_catalog="quilt-test-tabulator",
        )
        assert config.analytics_bucket == "my-analytics-bucket"

        # Empty bucket should raise ValueError
        with pytest.raises(ValueError, match="analytics_bucket field cannot be empty"):
            Catalog_Config(
                region="us-east-1",
                api_gateway_endpoint="https://api.example.com",
                registry_url="https://example-registry.quiltdata.com",
                analytics_bucket="",
                stack_prefix="test",
                tabulator_data_catalog="quilt-test-tabulator",
            )

        # None bucket should raise TypeError
        with pytest.raises(TypeError, match="analytics_bucket field is required and cannot be None"):
            Catalog_Config(
                region="us-east-1",
                api_gateway_endpoint="https://api.example.com",
                registry_url="https://example-registry.quiltdata.com",
                analytics_bucket=None,
                stack_prefix="test",
                tabulator_data_catalog="quilt-test-tabulator",
            )

        # Non-string bucket should raise TypeError
        with pytest.raises(TypeError, match="analytics_bucket field must be a string"):
            Catalog_Config(
                region="us-east-1",
                api_gateway_endpoint="https://api.example.com",
                registry_url="https://example-registry.quiltdata.com",
                analytics_bucket=123,
                stack_prefix="test",
                tabulator_data_catalog="quilt-test-tabulator",
            )

    def test_stack_prefix_field_validation(self):
        """Test that stack_prefix field is properly validated."""
        # Valid stack prefix
        config = Catalog_Config(
            region="us-east-1",
            api_gateway_endpoint="https://api.example.com",
            registry_url="https://example-registry.quiltdata.com",
            analytics_bucket="test-bucket",
            stack_prefix="my-stack",
            tabulator_data_catalog="quilt-test-tabulator",
        )
        assert config.stack_prefix == "my-stack"

        # Empty stack prefix should raise ValueError
        with pytest.raises(ValueError, match="stack_prefix field cannot be empty"):
            Catalog_Config(
                region="us-east-1",
                api_gateway_endpoint="https://api.example.com",
                registry_url="https://example-registry.quiltdata.com",
                analytics_bucket="test-bucket",
                stack_prefix="",
                tabulator_data_catalog="quilt-test-tabulator",
            )

        # None stack prefix should raise TypeError
        with pytest.raises(TypeError, match="stack_prefix field is required and cannot be None"):
            Catalog_Config(
                region="us-east-1",
                api_gateway_endpoint="https://api.example.com",
                registry_url="https://example-registry.quiltdata.com",
                analytics_bucket="test-bucket",
                stack_prefix=None,
                tabulator_data_catalog="quilt-test-tabulator",
            )

        # Non-string stack prefix should raise TypeError
        with pytest.raises(TypeError, match="stack_prefix field must be a string"):
            Catalog_Config(
                region="us-east-1",
                api_gateway_endpoint="https://api.example.com",
                registry_url="https://example-registry.quiltdata.com",
                analytics_bucket="test-bucket",
                stack_prefix=123,
                tabulator_data_catalog="quilt-test-tabulator",
            )

    def test_tabulator_data_catalog_field_validation(self):
        """Test that tabulator_data_catalog field is properly validated."""
        # Valid tabulator catalog
        config = Catalog_Config(
            region="us-east-1",
            api_gateway_endpoint="https://api.example.com",
            registry_url="https://example-registry.quiltdata.com",
            analytics_bucket="test-bucket",
            stack_prefix="test",
            tabulator_data_catalog="quilt-test-tabulator",
        )
        assert config.tabulator_data_catalog == "quilt-test-tabulator"

        # Empty tabulator catalog should raise ValueError
        with pytest.raises(ValueError, match="tabulator_data_catalog field cannot be empty"):
            Catalog_Config(
                region="us-east-1",
                api_gateway_endpoint="https://api.example.com",
                registry_url="https://example-registry.quiltdata.com",
                analytics_bucket="test-bucket",
                stack_prefix="test",
                tabulator_data_catalog="",
            )

        # None tabulator catalog should raise TypeError
        with pytest.raises(TypeError, match="tabulator_data_catalog field is required and cannot be None"):
            Catalog_Config(
                region="us-east-1",
                api_gateway_endpoint="https://api.example.com",
                registry_url="https://example-registry.quiltdata.com",
                analytics_bucket="test-bucket",
                stack_prefix="test",
                tabulator_data_catalog=None,
            )

        # Non-string tabulator catalog should raise TypeError
        with pytest.raises(TypeError, match="tabulator_data_catalog field must be a string"):
            Catalog_Config(
                region="us-east-1",
                api_gateway_endpoint="https://api.example.com",
                registry_url="https://example-registry.quiltdata.com",
                analytics_bucket="test-bucket",
                stack_prefix="test",
                tabulator_data_catalog=123,
            )


class TestCatalogConfigImmutability:
    """Test that Catalog_Config is immutable (frozen dataclass)."""

    def test_catalog_config_is_frozen(self):
        """Test that Catalog_Config fields cannot be modified after creation."""
        catalog_config = Catalog_Config(
            region="us-east-1",
            api_gateway_endpoint="https://api.example.com",
            registry_url="https://example-registry.quiltdata.com",
            analytics_bucket="test-bucket",
            stack_prefix="test",
            tabulator_data_catalog="quilt-test-tabulator",
        )

        # Should not be able to modify any field
        with pytest.raises(AttributeError):
            catalog_config.region = "us-west-2"

        with pytest.raises(AttributeError):
            catalog_config.api_gateway_endpoint = "https://other-api.com"

        with pytest.raises(AttributeError):
            catalog_config.analytics_bucket = "other-bucket"

        with pytest.raises(AttributeError):
            catalog_config.stack_prefix = "other-stack"

        with pytest.raises(AttributeError):
            catalog_config.tabulator_data_catalog = "other-tabulator"

    def test_catalog_config_is_hashable(self):
        """Test that Catalog_Config can be used as dictionary key or in sets."""
        catalog_config1 = Catalog_Config(
            region="us-east-1",
            api_gateway_endpoint="https://api.example.com",
            registry_url="https://example-registry.quiltdata.com",
            analytics_bucket="test-bucket",
            stack_prefix="test",
            tabulator_data_catalog="quilt-test-tabulator",
        )

        catalog_config2 = Catalog_Config(
            region="us-east-1",
            api_gateway_endpoint="https://api.example.com",
            registry_url="https://example-registry.quiltdata.com",
            analytics_bucket="test-bucket",
            stack_prefix="test",
            tabulator_data_catalog="quilt-test-tabulator",
        )

        # Should be able to hash
        hash1 = hash(catalog_config1)
        hash2 = hash(catalog_config2)

        # Same content should have same hash
        assert hash1 == hash2

        # Should be able to use in set
        config_set = {catalog_config1, catalog_config2}
        assert len(config_set) == 1  # Same content, so only one item

        # Should be able to use as dict key
        config_dict = {catalog_config1: "production"}
        assert config_dict[catalog_config2] == "production"


class TestCatalogConfigEquality:
    """Test Catalog_Config equality comparison."""

    def test_identical_catalog_configs_are_equal(self):
        """Test that Catalog_Config objects with identical data are equal."""
        catalog_config1 = Catalog_Config(
            region="us-east-1",
            api_gateway_endpoint="https://api.example.com",
            registry_url="https://example-registry.quiltdata.com",
            analytics_bucket="test-bucket",
            stack_prefix="test",
            tabulator_data_catalog="quilt-test-tabulator",
        )

        catalog_config2 = Catalog_Config(
            region="us-east-1",
            api_gateway_endpoint="https://api.example.com",
            registry_url="https://example-registry.quiltdata.com",
            analytics_bucket="test-bucket",
            stack_prefix="test",
            tabulator_data_catalog="quilt-test-tabulator",
        )

        assert catalog_config1 == catalog_config2
        assert not (catalog_config1 != catalog_config2)

    def test_different_catalog_configs_are_not_equal(self):
        """Test that Catalog_Config objects with different data are not equal."""
        catalog_config1 = Catalog_Config(
            region="us-east-1",
            api_gateway_endpoint="https://api.example.com",
            registry_url="https://example-registry.quiltdata.com",
            analytics_bucket="test-bucket",
            stack_prefix="test",
            tabulator_data_catalog="quilt-test-tabulator",
        )

        catalog_config2 = Catalog_Config(
            region="us-west-2",
            api_gateway_endpoint="https://api.other.com",
            registry_url="https://example-registry.quiltdata.com",
            analytics_bucket="other-bucket",
            stack_prefix="other",
            tabulator_data_catalog="quilt-other-tabulator",
        )

        assert catalog_config1 != catalog_config2
        assert not (catalog_config1 == catalog_config2)

    def test_catalog_config_field_differences(self):
        """Test equality with individual field differences."""
        base_config = Catalog_Config(
            region="us-east-1",
            api_gateway_endpoint="https://api.example.com",
            registry_url="https://example-registry.quiltdata.com",
            analytics_bucket="test-bucket",
            stack_prefix="test",
            tabulator_data_catalog="quilt-test-tabulator",
        )

        # Different region
        different_region = Catalog_Config(
            region="us-west-2",
            api_gateway_endpoint="https://api.example.com",
            registry_url="https://example-registry.quiltdata.com",
            analytics_bucket="test-bucket",
            stack_prefix="test",
            tabulator_data_catalog="quilt-test-tabulator",
        )
        assert base_config != different_region

        # Different API endpoint
        different_endpoint = Catalog_Config(
            region="us-east-1",
            api_gateway_endpoint="https://api.other.com",
            registry_url="https://example-registry.quiltdata.com",
            analytics_bucket="test-bucket",
            stack_prefix="test",
            tabulator_data_catalog="quilt-test-tabulator",
        )
        assert base_config != different_endpoint

        # Different analytics bucket
        different_bucket = Catalog_Config(
            region="us-east-1",
            api_gateway_endpoint="https://api.example.com",
            registry_url="https://example-registry.quiltdata.com",
            analytics_bucket="other-bucket",
            stack_prefix="test",
            tabulator_data_catalog="quilt-test-tabulator",
        )
        assert base_config != different_bucket
