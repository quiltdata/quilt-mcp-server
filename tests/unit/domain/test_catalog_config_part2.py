"""Tests for Catalog_Config domain object.

This test suite validates the Catalog_Config dataclass that represents catalog
configuration information in a backend-agnostic way.
"""

import pytest
from quilt_mcp.domain import Catalog_Config


class TestCatalogConfigStringRepresentation:
    """Test Catalog_Config string representation."""

    def test_catalog_config_str_representation(self):
        """Test that Catalog_Config has a readable string representation."""
        catalog_config = Catalog_Config(
            region="us-east-1",
            api_gateway_endpoint="https://api.example.com",
            registry_url="https://example-registry.quiltdata.com",
            analytics_bucket="test-bucket",
            stack_prefix="test",
            tabulator_data_catalog="quilt-test-tabulator",
        )

        str_repr = str(catalog_config)

        # Should contain the class name and key information
        assert "Catalog_Config" in str_repr
        assert "us-east-1" in str_repr
        assert "https://api.example.com" in str_repr
        assert "test-bucket" in str_repr
        assert "test" in str_repr
        assert "quilt-test-tabulator" in str_repr

    def test_catalog_config_repr_representation(self):
        """Test that Catalog_Config has a proper repr representation."""
        catalog_config = Catalog_Config(
            region="us-east-1",
            api_gateway_endpoint="https://api.example.com",
            registry_url="https://example-registry.quiltdata.com",
            analytics_bucket="test-bucket",
            stack_prefix="test",
            tabulator_data_catalog="quilt-test-tabulator",
        )

        repr_str = repr(catalog_config)

        # Should contain the class name and all field values
        assert "Catalog_Config" in repr_str
        assert "region='us-east-1'" in repr_str
        assert "api_gateway_endpoint='https://api.example.com'" in repr_str
        assert "analytics_bucket='test-bucket'" in repr_str
        assert "stack_prefix='test'" in repr_str
        assert "tabulator_data_catalog='quilt-test-tabulator'" in repr_str


class TestCatalogConfigUsagePatterns:
    """Test common usage patterns for Catalog_Config."""

    def test_catalog_config_aws_region_access(self):
        """Test accessing AWS region for boto3 client creation."""
        catalog_config = Catalog_Config(
            region="us-west-2",
            api_gateway_endpoint="https://api.example.com",
            registry_url="https://example-registry.quiltdata.com",
            analytics_bucket="test-bucket",
            stack_prefix="test",
            tabulator_data_catalog="quilt-test-tabulator",
        )

        # Should be able to use region for AWS operations
        aws_region = catalog_config.region
        assert aws_region == "us-west-2"

    def test_catalog_config_api_endpoint_access(self):
        """Test accessing API endpoint for GraphQL operations."""
        catalog_config = Catalog_Config(
            region="us-east-1",
            api_gateway_endpoint="https://api.example.quiltdata.com",
            registry_url="https://example-registry.quiltdata.com",
            analytics_bucket="test-bucket",
            stack_prefix="test",
            tabulator_data_catalog="quilt-test-tabulator",
        )

        # Should be able to construct GraphQL endpoint
        graphql_endpoint = f"{catalog_config.api_gateway_endpoint}/graphql"
        assert graphql_endpoint == "https://api.example.quiltdata.com/graphql"

    def test_catalog_config_tabulator_access(self):
        """Test accessing tabulator catalog for Athena operations."""
        catalog_config = Catalog_Config(
            region="us-east-1",
            api_gateway_endpoint="https://api.example.com",
            registry_url="https://example-registry.quiltdata.com",
            analytics_bucket="test-bucket",
            stack_prefix="production",
            tabulator_data_catalog="quilt-production-tabulator",
        )

        # Should be able to use tabulator catalog name
        tabulator_catalog = catalog_config.tabulator_data_catalog
        assert tabulator_catalog == "quilt-production-tabulator"

    def test_catalog_config_in_collections(self):
        """Test using Catalog_Config in collections."""
        configs = [
            Catalog_Config(
                region="us-east-1",
                api_gateway_endpoint="https://api.prod.com",
                registry_url="https://example-registry.quiltdata.com",
                analytics_bucket="prod-bucket",
                stack_prefix="prod",
                tabulator_data_catalog="quilt-prod-tabulator",
            ),
            Catalog_Config(
                region="us-west-2",
                api_gateway_endpoint="https://api.staging.com",
                registry_url="https://example-registry.quiltdata.com",
                analytics_bucket="staging-bucket",
                stack_prefix="staging",
                tabulator_data_catalog="quilt-staging-tabulator",
            ),
        ]

        # Should be able to filter by region
        east_configs = [c for c in configs if c.region == "us-east-1"]
        assert len(east_configs) == 1
        assert east_configs[0].stack_prefix == "prod"

        # Should be able to get unique regions
        regions = {c.region for c in configs}
        assert len(regions) == 2
        assert "us-east-1" in regions
        assert "us-west-2" in regions


class TestCatalogConfigTypeHints:
    """Test Catalog_Config type hints and annotations."""

    def test_catalog_config_has_correct_type_annotations(self):
        """Test that Catalog_Config has correct type annotations."""
        import inspect
        from typing import get_type_hints

        # Get type hints for Catalog_Config
        type_hints = get_type_hints(Catalog_Config)

        # Check that all fields have correct types
        assert type_hints['region'] is str
        assert type_hints['api_gateway_endpoint'] is str
        assert type_hints['registry_url'] is str
        assert type_hints['analytics_bucket'] is str
        assert type_hints['stack_prefix'] is str
        assert type_hints['tabulator_data_catalog'] is str

    def test_catalog_config_dataclass_properties(self):
        """Test that Catalog_Config has correct dataclass properties."""
        import dataclasses

        # Should be a dataclass
        assert dataclasses.is_dataclass(Catalog_Config)

        # Check that all expected fields exist
        fields = dataclasses.fields(Catalog_Config)
        field_names = {f.name for f in fields}
        expected_fields = {
            'region',
            'api_gateway_endpoint',
            'registry_url',
            'analytics_bucket',
            'stack_prefix',
            'tabulator_data_catalog',
        }
        assert field_names == expected_fields

        # Check field types
        field_types = {f.name: f.type for f in fields}
        assert field_types['region'] is str
        assert field_types['api_gateway_endpoint'] is str
        assert field_types['registry_url'] is str
        assert field_types['analytics_bucket'] is str
        assert field_types['stack_prefix'] is str
        assert field_types['tabulator_data_catalog'] is str


class TestCatalogConfigErrorMessages:
    """Test Catalog_Config error messages are clear and helpful."""

    def test_clear_error_messages_for_validation_failures(self):
        """Test that validation errors have clear, helpful messages."""
        # Test region validation error messages
        with pytest.raises(TypeError) as exc_info:
            Catalog_Config(
                region=None,
                api_gateway_endpoint="https://api.example.com",
                registry_url="https://example-registry.quiltdata.com",
                analytics_bucket="test-bucket",
                stack_prefix="test",
                tabulator_data_catalog="quilt-test-tabulator",
            )
        assert "region field is required and cannot be None" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            Catalog_Config(
                region="",
                api_gateway_endpoint="https://api.example.com",
                registry_url="https://example-registry.quiltdata.com",
                analytics_bucket="test-bucket",
                stack_prefix="test",
                tabulator_data_catalog="quilt-test-tabulator",
            )
        assert "region field cannot be empty" in str(exc_info.value)

        with pytest.raises(TypeError) as exc_info:
            Catalog_Config(
                region=123,
                api_gateway_endpoint="https://api.example.com",
                registry_url="https://example-registry.quiltdata.com",
                analytics_bucket="test-bucket",
                stack_prefix="test",
                tabulator_data_catalog="quilt-test-tabulator",
            )
        assert "region field must be a string" in str(exc_info.value)

    def test_validation_error_messages_include_field_names(self):
        """Test that validation error messages clearly identify the problematic field."""
        # Test that each field's error message mentions the field name
        field_tests = [
            ("region", None, "region field is required and cannot be None"),
            ("api_gateway_endpoint", None, "api_gateway_endpoint field is required and cannot be None"),
            ("registry_url", None, "registry_url field is required and cannot be None"),
            ("analytics_bucket", None, "analytics_bucket field is required and cannot be None"),
            ("stack_prefix", None, "stack_prefix field is required and cannot be None"),
            ("tabulator_data_catalog", None, "tabulator_data_catalog field is required and cannot be None"),
        ]

        for field_name, invalid_value, expected_message in field_tests:
            kwargs = {
                "region": "us-east-1",
                "api_gateway_endpoint": "https://api.example.com",
                "registry_url": "https://example-registry.quiltdata.com",
                "analytics_bucket": "test-bucket",
                "stack_prefix": "test",
                "tabulator_data_catalog": "quilt-test-tabulator",
            }
            kwargs[field_name] = invalid_value

            with pytest.raises(TypeError) as exc_info:
                Catalog_Config(**kwargs)
            assert expected_message in str(exc_info.value)
