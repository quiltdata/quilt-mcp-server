"""Tests for configuration framework base classes and validation.

This test file covers the complete configuration framework including:
- Base configuration classes and validation interface
- Configuration error hierarchy
- Serialization support
- Module structure and imports

Following BDD (Behavior-Driven Development) principles:
- Tests describe expected behavior, not implementation details
- Tests are organized by business scenarios and user stories
- Tests validate the public API contracts
"""

from __future__ import annotations

import pytest
from typing import Any, Dict


class TestConfigurationModuleStructure:
    """Test configuration module can be imported and is properly structured."""

    def test_configuration_module_imports_successfully(self):
        """Configuration module should be importable without errors."""
        import quilt_mcp.config  # Should not raise ImportError
        assert hasattr(quilt_mcp.config, '__all__')

    def test_configuration_base_module_imports_successfully(self):
        """Configuration base module should be importable without errors."""
        from quilt_mcp.config import base  # Should not raise ImportError
        assert hasattr(base, 'Configuration')
        assert hasattr(base, 'ConfigValidationResult')

    def test_no_circular_import_dependencies(self):
        """Configuration module should not have circular import dependencies."""
        import quilt_mcp.config
        # Should be able to import without issues and have proper module structure
        assert hasattr(quilt_mcp.config, '__path__')

        # Should be able to import base classes through main module
        from quilt_mcp.config import Configuration, ConfigValidationResult
        assert Configuration is not None
        assert ConfigValidationResult is not None


class TestConfigurationValidationFramework:
    """Test the configuration validation framework behavior."""

    def test_abstract_configuration_class_cannot_be_instantiated(self):
        """Abstract Configuration class should not be directly instantiable."""
        from quilt_mcp.config.base import Configuration

        # Should raise TypeError when trying to instantiate abstract class
        with pytest.raises(TypeError):
            Configuration()

    def test_config_validation_result_provides_success_failure_states(self):
        """ConfigValidationResult should clearly indicate success/failure states."""
        from quilt_mcp.config.base import ConfigValidationResult

        # Test success result
        success_result = ConfigValidationResult.success_result()
        assert success_result.success is True
        assert success_result.is_valid is True
        assert success_result.errors == []
        assert success_result.error_count == 0

        # Test failure result
        failure_result = ConfigValidationResult.failure_result(["error1", "error2"])
        assert failure_result.success is False
        assert failure_result.is_valid is False
        assert failure_result.errors == ["error1", "error2"]
        assert failure_result.error_count == 2

    def test_configuration_error_hierarchy_exists(self):
        """Configuration errors should have appropriate hierarchy and messages."""
        from quilt_mcp.config.base import (
            ConfigurationError,
            ValidationError,
            SerializationError
        )

        # Test error hierarchy
        assert issubclass(ValidationError, ConfigurationError)
        assert issubclass(SerializationError, ConfigurationError)

        # Test error instantiation
        config_error = ConfigurationError("base error")
        assert str(config_error) == "base error"

        validation_error = ValidationError("validation failed")
        assert str(validation_error) == "validation failed"

        serialization_error = SerializationError("serialization failed")
        assert str(serialization_error) == "serialization failed"

    def test_validation_interface_works_consistently(self):
        """Validation interface should work consistently across implementations."""
        from quilt_mcp.config.base import Configuration, ConfigValidationResult

        # Create a concrete test implementation
        class TestConfig(Configuration):
            def __init__(self, valid: bool = True):
                self.valid = valid

            def validate(self) -> ConfigValidationResult:
                if self.valid:
                    return ConfigValidationResult.success_result()
                else:
                    return ConfigValidationResult.failure_result(["test error"])

            def to_dict(self) -> Dict[str, Any]:
                return {"valid": self.valid}

            @classmethod
            def from_dict(cls, data: Dict[str, Any]) -> 'TestConfig':
                return cls(data.get("valid", True))

        # Test validation interface
        valid_config = TestConfig(valid=True)
        result = valid_config.validate()
        assert result.success is True
        assert valid_config.is_valid() is True

        invalid_config = TestConfig(valid=False)
        result = invalid_config.validate()
        assert result.success is False
        assert invalid_config.is_valid() is False


class TestConfigurationErrorHandling:
    """Test configuration error handling behavior."""

    def test_validation_errors_have_clear_messages(self):
        """Configuration validation errors should have clear, actionable messages."""
        from quilt_mcp.config.base import ValidationError

        error = ValidationError("Invalid registry URL format")
        assert "registry URL" in str(error)
        assert "Invalid" in str(error)

    def test_serialization_errors_are_caught(self):
        """Serialization errors should be properly caught and categorized."""
        from quilt_mcp.config.base import SerializationError

        error = SerializationError("Failed to serialize configuration")
        assert "serialize" in str(error)
        assert isinstance(error, Exception)

    def test_validate_or_raise_method(self):
        """validate_or_raise should raise ValidationError when configuration is invalid."""
        from quilt_mcp.config.base import Configuration, ConfigValidationResult, ValidationError

        class TestConfig(Configuration):
            def __init__(self, valid: bool = True):
                self.valid = valid

            def validate(self) -> ConfigValidationResult:
                if self.valid:
                    return ConfigValidationResult.success_result()
                else:
                    return ConfigValidationResult.failure_result(["error 1", "error 2"])

            def to_dict(self) -> Dict[str, Any]:
                return {"valid": self.valid}

            @classmethod
            def from_dict(cls, data: Dict[str, Any]) -> 'TestConfig':
                return cls(data.get("valid", True))

        # Valid config should not raise
        valid_config = TestConfig(valid=True)
        valid_config.validate_or_raise()  # Should not raise

        # Invalid config should raise with all errors
        invalid_config = TestConfig(valid=False)
        with pytest.raises(ValidationError) as exc_info:
            invalid_config.validate_or_raise()

        error_msg = str(exc_info.value)
        assert "Configuration validation failed" in error_msg
        assert "error 1" in error_msg
        assert "error 2" in error_msg


class TestConfigurationSerialization:
    """Test configuration serialization behavior."""

    def test_serialization_roundtrip_preserves_data(self):
        """Configuration serialization should preserve all data through roundtrip."""
        from quilt_mcp.config.base import Configuration, ConfigValidationResult

        class TestConfig(Configuration):
            def __init__(self, data: Dict[str, Any]):
                self.data = data

            def validate(self) -> ConfigValidationResult:
                return ConfigValidationResult.success_result()

            def to_dict(self) -> Dict[str, Any]:
                return self.data.copy()

            @classmethod
            def from_dict(cls, data: Dict[str, Any]) -> 'TestConfig':
                return cls(data)

        # Test roundtrip with various data types
        original_data = {"key": "value", "number": 42, "bool": True, "none": None}
        config = TestConfig(original_data)
        serialized = config.to_dict()
        restored_config = TestConfig.from_dict(serialized)

        assert restored_config.to_dict() == original_data

    def test_serialization_handles_edge_cases(self):
        """Serialization should handle edge cases like None values, empty strings."""
        from quilt_mcp.config.base import Configuration, ConfigValidationResult

        class TestConfig(Configuration):
            def __init__(self, data: Dict[str, Any]):
                self.data = data

            def validate(self) -> ConfigValidationResult:
                return ConfigValidationResult.success_result()

            def to_dict(self) -> Dict[str, Any]:
                return self.data.copy()

            @classmethod
            def from_dict(cls, data: Dict[str, Any]) -> 'TestConfig':
                return cls(data)

        # Test edge cases
        edge_cases = {"key": None, "empty": "", "zero": 0, "false": False}
        config = TestConfig(edge_cases)
        serialized = config.to_dict()

        assert serialized == edge_cases

    def test_serialization_format_is_json_compatible(self):
        """Serialized configuration should be JSON-compatible."""
        import json
        from quilt_mcp.config.base import Configuration, ConfigValidationResult

        class TestConfig(Configuration):
            def __init__(self, data: Dict[str, Any]):
                self.data = data

            def validate(self) -> ConfigValidationResult:
                return ConfigValidationResult.success_result()

            def to_dict(self) -> Dict[str, Any]:
                return self.data.copy()

            @classmethod
            def from_dict(cls, data: Dict[str, Any]) -> 'TestConfig':
                return cls(data)

        # Test JSON compatibility
        config_data = {"key": "value", "number": 42, "list": [1, 2, 3]}
        config = TestConfig(config_data)
        serialized = config.to_dict()

        # Should be able to serialize to JSON and back
        json_str = json.dumps(serialized)
        restored_data = json.loads(json_str)
        assert restored_data == config_data


class TestConfigurationValidationResult:
    """Test ConfigValidationResult behavior in detail."""

    def test_validation_result_add_error_method(self):
        """ConfigValidationResult should support adding errors dynamically."""
        from quilt_mcp.config.base import ConfigValidationResult

        result = ConfigValidationResult.success_result()
        assert result.success is True
        assert result.error_count == 0

        result.add_error("first error")
        assert result.success is False
        assert result.error_count == 1
        assert "first error" in result.errors

        result.add_error("second error")
        assert result.error_count == 2
        assert "second error" in result.errors

    def test_validation_result_properties(self):
        """ConfigValidationResult properties should work correctly."""
        from quilt_mcp.config.base import ConfigValidationResult

        # Test success result properties
        success = ConfigValidationResult.success_result()
        assert success.success is True
        assert success.is_valid is True
        assert success.error_count == 0

        # Test failure result properties
        failure = ConfigValidationResult.failure_result(["error1", "error2"])
        assert failure.success is False
        assert failure.is_valid is False
        assert failure.error_count == 2


class TestConfigurationFrameworkExtensibility:
    """Test that configuration framework is extensible for new configurations."""

    def test_configuration_framework_supports_inheritance(self):
        """Framework should support creating new configuration types via inheritance."""
        from quilt_mcp.config.base import Configuration, ConfigValidationResult

        class CustomConfig(Configuration):
            def __init__(self, value: str):
                self.value = value

            def validate(self) -> ConfigValidationResult:
                if not self.value:
                    return ConfigValidationResult.failure_result(["value cannot be empty"])
                return ConfigValidationResult.success_result()

            def to_dict(self) -> Dict[str, Any]:
                return {"value": self.value}

            @classmethod
            def from_dict(cls, data: Dict[str, Any]) -> 'CustomConfig':
                return cls(data.get("value", ""))

        # Test that custom configuration works
        config = CustomConfig("test")
        assert config.validate().success is True
        assert config.to_dict() == {"value": "test"}

        # Test validation logic
        empty_config = CustomConfig("")
        result = empty_config.validate()
        assert result.success is False
        assert "value cannot be empty" in result.errors

    def test_custom_configuration_can_extend_validation(self):
        """Custom configurations should be able to extend validation logic."""
        from quilt_mcp.config.base import Configuration, ConfigValidationResult

        class ExtendedConfig(Configuration):
            def __init__(self, name: str, age: int):
                self.name = name
                self.age = age

            def validate(self) -> ConfigValidationResult:
                result = ConfigValidationResult.success_result()

                if not self.name or len(self.name.strip()) == 0:
                    result.add_error("name is required and cannot be empty")

                if self.age < 0:
                    result.add_error("age cannot be negative")

                if self.age > 150:
                    result.add_error("age seems unrealistic")

                return result

            def to_dict(self) -> Dict[str, Any]:
                return {"name": self.name, "age": self.age}

            @classmethod
            def from_dict(cls, data: Dict[str, Any]) -> 'ExtendedConfig':
                return cls(data.get("name", ""), data.get("age", 0))

        # Test valid configuration
        valid_config = ExtendedConfig("John", 30)
        assert valid_config.validate().success is True

        # Test multiple validation errors
        invalid_config = ExtendedConfig("", -5)
        result = invalid_config.validate()
        assert result.success is False
        assert result.error_count == 2
        assert any("name is required" in error for error in result.errors)
        assert any("age cannot be negative" in error for error in result.errors)


# Integration test to ensure all components work together
class TestConfigurationFrameworkIntegration:
    """Test configuration framework components work together properly."""

    def test_complete_configuration_workflow(self):
        """Complete workflow from creation to validation to serialization."""
        from quilt_mcp.config.base import Configuration, ConfigValidationResult, ValidationError

        class WorkflowConfig(Configuration):
            def __init__(self, url: str, timeout: int = 30):
                self.url = url
                self.timeout = timeout

            def validate(self) -> ConfigValidationResult:
                result = ConfigValidationResult.success_result()

                if not self.url:
                    result.add_error("URL is required")
                elif not self.url.startswith(('http://', 'https://')):
                    result.add_error("URL must start with http:// or https://")

                if self.timeout <= 0:
                    result.add_error("timeout must be positive")

                return result

            def to_dict(self) -> Dict[str, Any]:
                return {"url": self.url, "timeout": self.timeout}

            @classmethod
            def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowConfig':
                return cls(data.get("url", ""), data.get("timeout", 30))

        # 1. Create configuration from dict
        config_data = {"url": "https://example.com", "timeout": 60}
        config = WorkflowConfig.from_dict(config_data)

        # 2. Validate configuration
        validation_result = config.validate()
        assert validation_result.success is True

        # 3. Serialize back to dict
        serialized = config.to_dict()

        # 4. Verify roundtrip integrity
        assert serialized == config_data

        # 5. Test error handling with invalid config
        invalid_data = {"url": "not-a-url", "timeout": -1}
        invalid_config = WorkflowConfig.from_dict(invalid_data)

        validation_result = invalid_config.validate()
        assert validation_result.success is False
        assert validation_result.error_count == 2

        # Test validate_or_raise with invalid config
        with pytest.raises(ValidationError):
            invalid_config.validate_or_raise()