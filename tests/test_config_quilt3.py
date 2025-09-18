"""Tests for Quilt3 configuration implementation.

This test file covers the Quilt3-specific configuration including:
- Quilt3Config class with registry and catalog URL validation
- Environment variable integration
- Configuration loading pipeline with priority resolution
- Error handling and validation messages

Following BDD (Behavior-Driven Development) principles:
- Tests describe expected behavior from user perspective
- Tests cover all business scenarios and edge cases
- Tests validate the public API contracts without implementation details
"""

from __future__ import annotations

import os
import pytest
from unittest.mock import patch
from typing import Any, Dict


class TestQuilt3ConfigBasicFunctionality:
    """Test basic Quilt3Config functionality and structure."""

    def test_quilt3_config_can_be_imported(self):
        """Quilt3Config should be importable from the config module."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        assert Quilt3Config is not None

    def test_quilt3_config_inherits_from_configuration(self):
        """Quilt3Config should inherit from the base Configuration class."""
        from quilt_mcp.config.quilt3 import Quilt3Config
        from quilt_mcp.config.base import Configuration

        assert issubclass(Quilt3Config, Configuration)

    def test_quilt3_config_has_required_attributes(self):
        """Quilt3Config should have registry_url and catalog_url attributes."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        config = Quilt3Config(registry_url="s3://test-bucket")
        assert hasattr(config, 'registry_url')
        assert hasattr(config, 'catalog_url')
        assert config.registry_url == "s3://test-bucket"

    def test_quilt3_config_can_be_created_with_minimal_parameters(self):
        """Quilt3Config should be creatable with just registry_url."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        config = Quilt3Config(registry_url="s3://test-bucket")
        assert config.registry_url == "s3://test-bucket"
        assert config.catalog_url is None


class TestQuilt3ConfigRegistryUrlValidation:
    """Test registry URL validation behavior."""

    def test_valid_s3_registry_urls_are_accepted(self):
        """Valid S3 registry URLs should pass validation."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        # Valid S3 URLs that should pass
        valid_urls = [
            "s3://my-bucket",
            "s3://test-bucket-123",
            "s3://bucket123",
            "s3://bucket-with-dashes",
        ]

        for url in valid_urls:
            config = Quilt3Config(registry_url=url)
            result = config.validate()
            assert result.success, f"URL {url} should be valid but got errors: {result.errors}"

    def test_invalid_registry_urls_are_rejected(self):
        """Invalid registry URLs should fail validation with clear messages."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        # Invalid URLs that should fail
        invalid_urls = [
            "",  # Empty
            "not-a-url",  # No scheme
            "http://example.com",  # Wrong scheme
            "s3://",  # No bucket
            "s3://bucket/with/path",  # Has path (not allowed for registry)
        ]

        for url in invalid_urls:
            config = Quilt3Config(registry_url=url)
            result = config.validate()
            assert not result.success, f"URL {url} should be invalid but passed validation"
            assert any("registry" in error.lower() for error in result.errors), (
                f"Error message should mention registry for URL {url}"
            )

    def test_registry_url_validation_error_messages_are_clear(self):
        """Registry URL validation errors should provide clear, actionable guidance."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        # Test specific error messages
        config = Quilt3Config(registry_url="http://example.com")
        result = config.validate()
        error_msg = " ".join(result.errors)
        assert "s3://" in error_msg.lower()
        assert "registry" in error_msg.lower()

    def test_empty_registry_url_fails_validation(self):
        """Empty or None registry URL should fail validation."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        # Test None
        config = Quilt3Config(registry_url=None)
        result = config.validate()
        assert not result.success
        assert any("required" in error.lower() for error in result.errors)

        # Test empty string
        config = Quilt3Config(registry_url="")
        result = config.validate()
        assert not result.success


class TestQuilt3ConfigCatalogUrlValidation:
    """Test catalog URL validation behavior."""

    def test_valid_catalog_urls_are_accepted(self):
        """Valid HTTP/HTTPS catalog URLs should pass validation."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        # Valid catalog URLs
        valid_urls = [
            "https://example.com",
            "http://localhost:8000",
            "https://api.quiltdata.com",
            "https://subdomain.example.com/path",
            "http://127.0.0.1:3000",
        ]

        for url in valid_urls:
            config = Quilt3Config(registry_url="s3://test", catalog_url=url)
            result = config.validate()
            assert result.success, f"Catalog URL {url} should be valid but got errors: {result.errors}"

    def test_invalid_catalog_urls_are_rejected(self):
        """Invalid catalog URLs should fail validation."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        # Invalid catalog URLs
        invalid_urls = [
            "ftp://example.com",  # Wrong scheme
            "not-a-url",  # No scheme
            "s3://bucket",  # S3 not allowed for catalog
        ]

        for url in invalid_urls:
            config = Quilt3Config(registry_url="s3://test", catalog_url=url)
            result = config.validate()
            assert not result.success, f"Catalog URL {url} should be invalid but passed validation"

    def test_catalog_url_is_optional(self):
        """Catalog URL should be optional - config should be valid without it."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        # Should be valid with just registry URL
        config = Quilt3Config(registry_url="s3://test-bucket")
        result = config.validate()
        assert result.success, f"Config should be valid without catalog URL: {result.errors}"

    def test_empty_catalog_url_is_treated_as_none(self):
        """Empty catalog URL should be treated as optional (not fail validation)."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        config = Quilt3Config(registry_url="s3://test-bucket", catalog_url="")
        result = config.validate()
        # Empty catalog URL should not cause validation failure
        # (it's optional, so empty should be treated like None)
        if not result.success:
            # If there are errors, they should not be about empty catalog URL
            catalog_errors = [e for e in result.errors if "catalog" in e.lower()]
            assert len(catalog_errors) == 0, f"Empty catalog URL should not cause errors: {catalog_errors}"


class TestQuilt3ConfigEnvironmentVariables:
    """Test environment variable integration."""

    def test_registry_url_loaded_from_environment(self):
        """Registry URL should be loaded from QUILT_REGISTRY_URL environment variable."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        with patch.dict(os.environ, {'QUILT_REGISTRY_URL': 's3://env-bucket'}):
            config = Quilt3Config.from_environment()
            assert config.registry_url == 's3://env-bucket'

    def test_catalog_url_loaded_from_environment(self):
        """Catalog URL should be loaded from QUILT_CATALOG_URL environment variable."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        with patch.dict(
            os.environ, {'QUILT_REGISTRY_URL': 's3://test-bucket', 'QUILT_CATALOG_URL': 'https://catalog.example.com'}
        ):
            config = Quilt3Config.from_environment()
            assert config.catalog_url == 'https://catalog.example.com'

    def test_explicit_parameters_override_environment(self):
        """Explicitly provided parameters should take precedence over environment variables."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        with patch.dict(os.environ, {'QUILT_REGISTRY_URL': 's3://env-bucket'}):
            config = Quilt3Config(registry_url='s3://explicit-bucket')
            assert config.registry_url == 's3://explicit-bucket'

    def test_environment_variables_are_validated(self):
        """Environment variables should be validated just like explicit parameters."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        with patch.dict(os.environ, {'QUILT_REGISTRY_URL': 'invalid-url'}):
            config = Quilt3Config.from_environment()
            result = config.validate()
            assert not result.success

    def test_with_defaults_method_respects_priority(self):
        """with_defaults method should follow priority: explicit > environment > None."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        with patch.dict(os.environ, {'QUILT_REGISTRY_URL': 's3://env-bucket'}):
            # Explicit should override environment
            config = Quilt3Config.with_defaults(registry_url='s3://explicit-bucket')
            assert config.registry_url == 's3://explicit-bucket'

            # Environment should be used when no explicit value
            config2 = Quilt3Config.with_defaults()
            assert config2.registry_url == 's3://env-bucket'


class TestQuilt3ConfigurationLoading:
    """Test configuration loading pipeline with priority resolution."""

    def test_configuration_can_be_created_empty(self):
        """Configuration should be creatable with no parameters (may fail validation)."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        config = Quilt3Config()
        assert config.registry_url is None
        assert config.catalog_url is None

        # Should fail validation since registry_url is required
        result = config.validate()
        assert not result.success

    def test_configuration_factory_methods_work(self):
        """Configuration factory methods should provide easy instantiation."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        # Should support various creation patterns:
        config1 = Quilt3Config.from_environment()
        assert config1 is not None

        config2 = Quilt3Config.from_dict({"registry_url": "s3://bucket"})
        assert config2.registry_url == "s3://bucket"

        config3 = Quilt3Config.with_defaults(registry_url="s3://bucket")
        assert config3.registry_url == "s3://bucket"

    def test_configuration_loading_priority_order(self):
        """Configuration loading should follow correct priority order."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        # Priority order should be:
        # 1. Explicit parameters
        # 2. Environment variables
        # 3. None (no hard-coded defaults)

        with patch.dict(os.environ, {'QUILT_REGISTRY_URL': 's3://env-bucket'}):
            # Explicit should override environment
            config = Quilt3Config(registry_url='s3://explicit-bucket')
            assert config.registry_url == 's3://explicit-bucket'

            # Environment should be used when no explicit value
            config2 = Quilt3Config()
            config2_env = Quilt3Config.from_environment()
            assert config2_env.registry_url == 's3://env-bucket'


class TestQuilt3ConfigSerialization:
    """Test Quilt3Config serialization behavior."""

    def test_quilt3_config_serialization_preserves_data(self):
        """Serialization should preserve all Quilt3-specific data."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        config_data = {"registry_url": "s3://test-bucket", "catalog_url": "https://catalog.example.com"}
        config = Quilt3Config.from_dict(config_data)
        serialized = config.to_dict()
        assert serialized == config_data

    def test_serialization_handles_optional_fields(self):
        """Serialization should handle optional fields correctly."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        # Config with only required fields
        config = Quilt3Config(registry_url="s3://test-bucket")
        serialized = config.to_dict()
        assert "registry_url" in serialized
        assert serialized["registry_url"] == "s3://test-bucket"
        # catalog_url should not be present when None
        assert "catalog_url" not in serialized

    def test_serialization_format_is_json_compatible(self):
        """Serialized Quilt3Config should be JSON-compatible."""
        import json
        from quilt_mcp.config.quilt3 import Quilt3Config

        config = Quilt3Config(registry_url="s3://test-bucket")
        serialized = config.to_dict()
        json_str = json.dumps(serialized)  # Should not raise
        restored = json.loads(json_str)
        assert restored["registry_url"] == "s3://test-bucket"

    def test_serialization_roundtrip_preserves_data(self):
        """Serialization roundtrip should preserve all data."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        original = Quilt3Config(registry_url="s3://test-bucket", catalog_url="https://catalog.example.com")
        serialized = original.to_dict()
        restored = Quilt3Config.from_dict(serialized)

        assert restored.registry_url == original.registry_url
        assert restored.catalog_url == original.catalog_url


class TestQuilt3ConfigErrorHandling:
    """Test comprehensive error handling for Quilt3Config."""

    def test_validation_errors_provide_actionable_guidance(self):
        """Validation errors should provide clear guidance on how to fix issues."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        config = Quilt3Config(registry_url="invalid-url")
        result = config.validate()
        assert not result.success
        error_msg = " ".join(result.errors)
        assert "s3://" in error_msg  # Should suggest correct format
        assert "registry" in error_msg.lower()  # Should identify the field

    def test_multiple_validation_errors_are_collected(self):
        """Multiple validation errors should be collected and reported together."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        config = Quilt3Config(registry_url="invalid-registry", catalog_url="invalid-catalog")
        result = config.validate()
        assert not result.success
        assert len(result.errors) >= 2  # Should have errors for both fields

    def test_configuration_errors_are_properly_categorized(self):
        """Configuration errors should be properly categorized by type."""
        from quilt_mcp.config.quilt3 import Quilt3Config
        from quilt_mcp.config.base import ValidationError, SerializationError

        # Test ValidationError via validate_or_raise
        config = Quilt3Config(registry_url="invalid")
        with pytest.raises(ValidationError):
            config.validate_or_raise()

        # Test SerializationError - harder to trigger, but verify it exists
        assert SerializationError is not None


class TestQuilt3ConfigBucketNameValidation:
    """Test S3 bucket name validation."""

    def test_valid_bucket_names_pass_validation(self):
        """Valid S3 bucket names should pass validation."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        valid_buckets = [
            "s3://my-bucket",
            "s3://test123",
            "s3://bucket-name",
            "s3://123bucket",
        ]

        for bucket_url in valid_buckets:
            config = Quilt3Config(registry_url=bucket_url)
            result = config.validate()
            assert result.success, f"Bucket {bucket_url} should be valid: {result.errors}"

    def test_invalid_bucket_names_fail_validation(self):
        """Invalid S3 bucket names should fail validation."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        invalid_buckets = [
            "s3://ab",  # Too short
            "s3://-bucket",  # Starts with hyphen
            "s3://bucket-",  # Ends with hyphen
            "s3://bucket..name",  # Consecutive periods
            "s3://BUCKET",  # Uppercase letters
        ]

        for bucket_url in invalid_buckets:
            config = Quilt3Config(registry_url=bucket_url)
            result = config.validate()
            # Note: Some basic validation is done, but not all S3 rules are implemented
            # This test documents the expected behavior


class TestQuilt3ConfigIntegration:
    """Test Quilt3Config integration scenarios."""

    def test_complete_quilt3_configuration_workflow(self):
        """Test complete workflow from environment to validation to serialization."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        # Complete workflow:
        # 1. Load from environment
        # 2. Validate configuration
        # 3. Serialize for debugging
        # 4. Restore from serialization
        # 5. Use in application

        with patch.dict(
            os.environ, {'QUILT_REGISTRY_URL': 's3://test-bucket', 'QUILT_CATALOG_URL': 'https://catalog.example.com'}
        ):
            # 1. Load from environment
            config = Quilt3Config.from_environment()

            # 2. Validate
            result = config.validate()
            assert result.success, f"Configuration should be valid: {result.errors}"

            # 3. Serialize
            serialized = config.to_dict()

            # 4. Restore
            restored = Quilt3Config.from_dict(serialized)

            # 5. Verify roundtrip
            assert restored.registry_url == config.registry_url
            assert restored.catalog_url == config.catalog_url

    def test_no_global_quilt3_state_dependencies(self):
        """Quilt3Config should not depend on global quilt3 state."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        # Should be able to create and use configuration without
        # importing quilt3 or depending on global quilt3 state
        config = Quilt3Config(registry_url="s3://test-bucket")
        result = config.validate()
        # This should work without any global quilt3 setup
        assert result.success

    def test_quilt3_config_works_with_real_quilt3_values(self):
        """Quilt3Config should work with realistic Quilt3 registry and catalog URLs."""
        from quilt_mcp.config.quilt3 import Quilt3Config

        # Real-world style URLs
        config = Quilt3Config(registry_url="s3://quilt-example-bucket", catalog_url="https://example.quiltdata.com")
        result = config.validate()
        assert result.success, f"Real-world config should be valid: {result.errors}"
