"""Tests for operation framework base classes and interfaces.

This test file covers the complete operation framework including:
- Base operation classes and interfaces
- OperationResult hierarchy for success/error states
- Error categorization for different failure modes
- Result serialization and standardization
- Operation lifecycle management and resource cleanup

Following BDD (Behavior-Driven Development) principles:
- Tests describe expected behavior from user perspective
- Tests cover all business scenarios and edge cases
- Tests validate the public API contracts without implementation details
"""

from __future__ import annotations

import pytest
from typing import Any, Dict, Optional
from unittest.mock import patch


class TestOperationModuleStructure:
    """Test operation module can be imported and is properly structured."""

    def test_operations_module_imports_successfully(self):
        """Operations module should be importable without errors."""
        import quilt_mcp.operations  # Should not raise ImportError
        assert hasattr(quilt_mcp.operations, '__all__')

    def test_operations_base_module_imports_successfully(self):
        """Operations base module should be importable without errors."""
        from quilt_mcp.operations import base  # Should not raise ImportError
        assert hasattr(base, 'Operation')
        assert hasattr(base, 'OperationResult')

    def test_no_circular_import_dependencies(self):
        """Operations module should not have circular import dependencies."""
        import quilt_mcp.operations
        # Should be able to import without issues and have proper module structure
        assert hasattr(quilt_mcp.operations, '__path__')

        # Should be able to import base classes through main module
        from quilt_mcp.operations import Operation, OperationResult
        assert Operation is not None
        assert OperationResult is not None

    def test_operations_module_documentation_is_comprehensive(self):
        """Operations module should have comprehensive documentation."""
        import quilt_mcp.operations
        assert hasattr(quilt_mcp.operations, '__doc__')
        assert quilt_mcp.operations.__doc__ is not None
        assert "operation framework" in quilt_mcp.operations.__doc__.lower()


class TestAbstractOperationClass:
    """Test abstract Operation class behavior and interface."""

    def test_abstract_operation_class_cannot_be_instantiated(self):
        """Abstract Operation class should not be directly instantiable."""
        from quilt_mcp.operations.base import Operation

        # Should raise TypeError when trying to instantiate abstract class
        with pytest.raises(TypeError):
            Operation()  # Missing config parameter and abstract methods

    def test_operation_class_enforces_proper_interface(self):
        """Operation class should enforce implementation of required methods."""
        from quilt_mcp.operations.base import Operation
        from quilt_mcp.config.base import Configuration, ConfigValidationResult

        # Create a test configuration
        class TestConfig(Configuration):
            def validate(self):
                return ConfigValidationResult.success_result()
            def to_dict(self):
                return {}
            @classmethod
            def from_dict(cls, data):
                return cls()

        # Incomplete operation should raise TypeError
        class IncompleteOperation(Operation):
            pass

        config = TestConfig()
        with pytest.raises(TypeError):
            IncompleteOperation(config)

    def test_operation_class_supports_configuration_injection(self):
        """Operation class should support configuration injection interface."""
        from quilt_mcp.operations.base import Operation, SuccessResult
        from quilt_mcp.config.base import Configuration, ConfigValidationResult

        # Create a test configuration
        class TestConfig(Configuration):
            def validate(self):
                return ConfigValidationResult.success_result()
            def to_dict(self):
                return {}
            @classmethod
            def from_dict(cls, data):
                return cls()

        class TestOperation(Operation):
            def execute(self):
                return SuccessResult(data={"config_received": True})

        config = TestConfig()
        operation = TestOperation(config)
        assert operation.config == config

    def test_operation_lifecycle_management_exists(self):
        """Operation should have lifecycle management for resource cleanup."""
        from quilt_mcp.operations.base import Operation, SuccessResult
        from quilt_mcp.config.base import Configuration, ConfigValidationResult

        # Create a test configuration
        class TestConfig(Configuration):
            def validate(self):
                return ConfigValidationResult.success_result()
            def to_dict(self):
                return {}
            @classmethod
            def from_dict(cls, data):
                return cls()

        class TestOperation(Operation):
            def execute(self):
                return SuccessResult()

        config = TestConfig()
        operation = TestOperation(config)

        # Should support context manager protocol
        with operation as op:
            assert op is operation
            assert operation._resources_acquired is True

        # Resources should be cleaned up after context exit
        assert operation._resources_acquired is False


class TestOperationResultHierarchy:
    """Test OperationResult hierarchy for success/error states."""

    def test_operation_result_hierarchy_exists(self):
        """OperationResult hierarchy should exist for all result types."""
        from quilt_mcp.operations.base import (
            OperationResult,
            SuccessResult,
            ErrorResult
        )

        assert issubclass(SuccessResult, OperationResult)
        assert issubclass(ErrorResult, OperationResult)

    def test_success_result_provides_clear_success_state(self):
        """SuccessResult should clearly indicate successful operation."""
        from quilt_mcp.operations.base import SuccessResult

        result = SuccessResult(data={"key": "value"})
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.timestamp is not None

    def test_error_result_provides_clear_error_state(self):
        """ErrorResult should clearly indicate operation failure."""
        from quilt_mcp.operations.base import ErrorResult

        result = ErrorResult(error_type="network", message="Connection failed")
        assert result.success is False
        assert result.error_type == "network"
        assert result.message == "Connection failed"
        assert result.timestamp is not None

    def test_operation_result_covers_all_scenarios(self):
        """OperationResult hierarchy should cover all success/error scenarios."""
        from quilt_mcp.operations.base import SuccessResult, ErrorResult

        # Success with data
        success_with_data = SuccessResult(data={"result": "value"})
        assert success_with_data.success is True
        assert success_with_data.data is not None

        # Success without data
        success_without_data = SuccessResult()
        assert success_without_data.success is True
        assert success_without_data.data is None

        # Various error types
        network_error = ErrorResult(error_type="network", message="Network failed")
        auth_error = ErrorResult(error_type="auth", message="Auth failed")
        config_error = ErrorResult(error_type="config", message="Config failed")
        authz_error = ErrorResult(error_type="authz", message="Permission denied")

        assert all(not result.success for result in [network_error, auth_error, config_error, authz_error])


class TestErrorCategorization:
    """Test error categorization framework."""

    def test_error_categorization_is_comprehensive(self):
        """Error categorization should cover all operation failure modes."""
        from quilt_mcp.operations.base import (
            NetworkError,
            AuthenticationError,
            ConfigurationError,
            AuthorizationError,
            OperationError
        )

        # Should have error types for different failure categories
        assert issubclass(NetworkError, OperationError)
        assert issubclass(AuthenticationError, OperationError)
        assert issubclass(ConfigurationError, OperationError)
        assert issubclass(AuthorizationError, OperationError)

    def test_error_categories_map_correctly(self):
        """Error categories should map correctly to operation failures."""
        from quilt_mcp.operations.base import ErrorResult

        network_error = ErrorResult(error_type="network", message="Timeout")
        auth_error = ErrorResult(error_type="auth", message="Invalid credentials")
        config_error = ErrorResult(error_type="config", message="Invalid URL")
        authz_error = ErrorResult(error_type="authz", message="Permission denied")

        assert network_error.error_type == "network"
        assert auth_error.error_type == "auth"
        assert config_error.error_type == "config"
        assert authz_error.error_type == "authz"

    def test_error_messages_are_actionable(self):
        """Error messages should provide actionable guidance for resolution."""
        from quilt_mcp.operations.base import ErrorResult

        error = ErrorResult(
            error_type="config",
            message="Invalid registry URL format. Use s3://bucket-name"
        )
        assert "s3://" in error.message
        assert "registry URL" in error.message

    def test_error_result_from_exception_categorizes_correctly(self):
        """ErrorResult.from_exception should categorize errors correctly."""
        from quilt_mcp.operations.base import (
            ErrorResult,
            NetworkError,
            AuthenticationError,
            ConfigurationError,
            AuthorizationError
        )

        # Test different exception types
        network_exc = NetworkError("Connection timeout")
        error_result = ErrorResult.from_exception(network_exc)
        assert error_result.error_type == "network"
        assert error_result.message == "Connection timeout"

        auth_exc = AuthenticationError("Invalid token")
        error_result = ErrorResult.from_exception(auth_exc)
        assert error_result.error_type == "auth"

        config_exc = ConfigurationError("Invalid URL")
        error_result = ErrorResult.from_exception(config_exc)
        assert error_result.error_type == "config"

        authz_exc = AuthorizationError("Permission denied")
        error_result = ErrorResult.from_exception(authz_exc)
        assert error_result.error_type == "authz"

        # Unknown exception type
        generic_exc = ValueError("Generic error")
        error_result = ErrorResult.from_exception(generic_exc)
        assert error_result.error_type == "unknown"


class TestResultSerialization:
    """Test result serialization and standardization."""

    def test_result_serialization_maintains_data_integrity(self):
        """Result serialization should maintain data integrity."""
        from quilt_mcp.operations.base import SuccessResult

        result = SuccessResult(data={"key": "value", "number": 42})
        serialized = result.to_dict()
        restored = SuccessResult.from_dict(serialized)
        assert restored.data == result.data

    def test_result_format_is_consistent(self):
        """Result format should be consistent across all operation types."""
        from quilt_mcp.operations.base import SuccessResult, ErrorResult

        success = SuccessResult(data={"test": "data"})
        error = ErrorResult(error_type="network", message="Failed")

        success_dict = success.to_dict()
        error_dict = error.to_dict()

        # Both should have consistent structure
        assert "success" in success_dict
        assert "success" in error_dict
        assert success_dict["success"] is True
        assert error_dict["success"] is False

        # Both should have timestamps
        assert "timestamp" in success_dict
        assert "timestamp" in error_dict

    def test_result_serialization_is_json_compatible(self):
        """Result serialization should be JSON-compatible."""
        import json
        from quilt_mcp.operations.base import SuccessResult, ErrorResult

        # Test SuccessResult
        result = SuccessResult(data={"key": "value"})
        serialized = result.to_dict()
        json_str = json.dumps(serialized)  # Should not raise
        restored_dict = json.loads(json_str)
        assert restored_dict["success"] is True

        # Test ErrorResult
        error = ErrorResult(error_type="network", message="Failed")
        serialized = error.to_dict()
        json_str = json.dumps(serialized)  # Should not raise
        restored_dict = json.loads(json_str)
        assert restored_dict["success"] is False

    def test_success_result_serialization_handles_optional_fields(self):
        """SuccessResult serialization should handle optional fields correctly."""
        from quilt_mcp.operations.base import SuccessResult

        # Result with minimal data
        result = SuccessResult()
        serialized = result.to_dict()
        assert "success" in serialized
        assert "timestamp" in serialized
        assert serialized["success"] is True

        # Result with all fields
        result = SuccessResult(
            data={"key": "value"},
            message="Operation completed",
            operation_id="test-123"
        )
        serialized = result.to_dict()
        assert serialized["data"] == {"key": "value"}
        assert serialized["message"] == "Operation completed"
        assert serialized["operation_id"] == "test-123"

    def test_error_result_serialization_handles_optional_fields(self):
        """ErrorResult serialization should handle optional fields correctly."""
        from quilt_mcp.operations.base import ErrorResult

        # Result with minimal data
        result = ErrorResult(error_type="network", message="Failed")
        serialized = result.to_dict()
        assert "success" in serialized
        assert "error_type" in serialized
        assert "message" in serialized
        assert "timestamp" in serialized

        # Result with all fields
        result = ErrorResult(
            error_type="auth",
            message="Authentication failed",
            details={"code": 401},
            traceback="Stack trace here",
            operation_id="test-456"
        )
        serialized = result.to_dict()
        assert serialized["details"] == {"code": 401}
        assert serialized["traceback"] == "Stack trace here"
        assert serialized["operation_id"] == "test-456"


class TestOperationLifecycleManagement:
    """Test operation lifecycle management and resource cleanup."""

    def test_operation_lifecycle_prevents_resource_leaks(self):
        """Operation lifecycle management should prevent resource leaks."""
        from quilt_mcp.operations.base import Operation, SuccessResult
        from quilt_mcp.config.base import Configuration, ConfigValidationResult

        # Create test configuration
        class TestConfig(Configuration):
            def validate(self):
                return ConfigValidationResult.success_result()
            def to_dict(self):
                return {}
            @classmethod
            def from_dict(cls, data):
                return cls()

        # Create operation with resource tracking
        class TestOperation(Operation):
            def __init__(self, config):
                super().__init__(config)
                self.resource_acquired = False
                self.resource_cleaned = False

            def _acquire_resources(self):
                super()._acquire_resources()
                self.resource_acquired = True

            def _cleanup_resources(self):
                super()._cleanup_resources()
                self.resource_cleaned = True

            def execute(self):
                return SuccessResult(data={"resources_acquired": self._resources_acquired})

        config = TestConfig()
        operation = TestOperation(config)

        # Test context manager resource management
        with operation as op:
            assert op.resource_acquired is True
            assert op._resources_acquired is True

        # Resources should be cleaned up after context exit
        assert operation.resource_cleaned is True
        assert operation._resources_acquired is False

    def test_operation_cleanup_is_always_called(self):
        """Operation cleanup should be called even when exceptions occur."""
        from quilt_mcp.operations.base import Operation
        from quilt_mcp.config.base import Configuration, ConfigValidationResult

        # Create test configuration
        class TestConfig(Configuration):
            def validate(self):
                return ConfigValidationResult.success_result()
            def to_dict(self):
                return {}
            @classmethod
            def from_dict(cls, data):
                return cls()

        cleanup_called = False

        class TestOperation(Operation):
            def _cleanup_resources(self):
                nonlocal cleanup_called
                cleanup_called = True
                super()._cleanup_resources()

            def execute(self):
                raise Exception("Test exception")

        config = TestConfig()
        operation = TestOperation(config)

        # Cleanup should be called even when exception occurs
        try:
            with operation as op:
                op.execute()
        except Exception:
            pass

        assert cleanup_called is True

    def test_operation_resources_are_properly_managed(self):
        """Operation should properly manage external resources."""
        from quilt_mcp.operations.base import Operation, SuccessResult
        from quilt_mcp.config.base import Configuration, ConfigValidationResult

        # Create test configuration
        class TestConfig(Configuration):
            def validate(self):
                return ConfigValidationResult.success_result()
            def to_dict(self):
                return {}
            @classmethod
            def from_dict(cls, data):
                return cls()

        class ResourceTrackingOperation(Operation):
            def __init__(self, config):
                super().__init__(config)
                self.connection_open = False

            def _acquire_resources(self):
                super()._acquire_resources()
                # Simulate opening a connection
                self.connection_open = True

            def _cleanup_resources(self):
                # Simulate closing connection
                self.connection_open = False
                super()._cleanup_resources()

            def execute(self):
                # Verify resources are available during execution
                assert self.connection_open is True
                return SuccessResult(data={"connection_status": "active"})

        config = TestConfig()
        operation = ResourceTrackingOperation(config)

        # Resources should be managed properly
        assert operation.connection_open is False

        with operation as op:
            assert op.connection_open is True
            result = op.execute()
            assert result.success is True

        assert operation.connection_open is False


class TestOperationExecution:
    """Test operation execution patterns and error handling."""

    def test_execute_safely_handles_configuration_validation(self):
        """execute_safely should validate configuration before execution."""
        from quilt_mcp.operations.base import Operation, SuccessResult
        from quilt_mcp.config.base import Configuration, ConfigValidationResult

        # Create invalid configuration
        class InvalidConfig(Configuration):
            def validate(self):
                return ConfigValidationResult.failure_result(["Configuration is invalid"])
            def to_dict(self):
                return {}
            @classmethod
            def from_dict(cls, data):
                return cls()

        class TestOperation(Operation):
            def execute(self):
                return SuccessResult()

        config = InvalidConfig()
        operation = TestOperation(config)

        result = operation.execute_safely()
        assert result.success is False
        assert result.error_type == "config"
        assert "Configuration validation failed" in result.message

    def test_execute_safely_handles_operation_errors(self):
        """execute_safely should handle various operation errors properly."""
        from quilt_mcp.operations.base import (
            Operation,
            NetworkError,
            AuthenticationError,
            ConfigurationError,
            AuthorizationError
        )
        from quilt_mcp.config.base import Configuration, ConfigValidationResult

        # Create valid configuration
        class ValidConfig(Configuration):
            def validate(self):
                return ConfigValidationResult.success_result()
            def to_dict(self):
                return {}
            @classmethod
            def from_dict(cls, data):
                return cls()

        config = ValidConfig()

        # Test different error types
        class NetworkErrorOperation(Operation):
            def execute(self):
                raise NetworkError("Connection timeout")

        result = NetworkErrorOperation(config).execute_safely()
        assert result.success is False
        assert result.error_type == "network"

        class AuthErrorOperation(Operation):
            def execute(self):
                raise AuthenticationError("Invalid token")

        result = AuthErrorOperation(config).execute_safely()
        assert result.success is False
        assert result.error_type == "auth"

    def test_execute_safely_handles_unexpected_errors(self):
        """execute_safely should handle unexpected errors gracefully."""
        from quilt_mcp.operations.base import Operation
        from quilt_mcp.config.base import Configuration, ConfigValidationResult

        # Create valid configuration
        class ValidConfig(Configuration):
            def validate(self):
                return ConfigValidationResult.success_result()
            def to_dict(self):
                return {}
            @classmethod
            def from_dict(cls, data):
                return cls()

        class UnexpectedErrorOperation(Operation):
            def execute(self):
                raise ValueError("Unexpected error")

        config = ValidConfig()
        operation = UnexpectedErrorOperation(config)

        result = operation.execute_safely()
        assert result.success is False
        assert result.error_type == "unknown"
        assert "Unexpected error during operation" in result.message

    def test_validate_config_or_raise_method(self):
        """validate_config_or_raise should raise ConfigurationError for invalid config."""
        from quilt_mcp.operations.base import Operation, ConfigurationError
        from quilt_mcp.config.base import Configuration, ConfigValidationResult

        # Create invalid configuration
        class InvalidConfig(Configuration):
            def validate(self):
                return ConfigValidationResult.failure_result(["Error 1", "Error 2"])
            def to_dict(self):
                return {}
            @classmethod
            def from_dict(cls, data):
                return cls()

        class TestOperation(Operation):
            def execute(self):
                pass  # Not relevant for this test

        config = InvalidConfig()
        operation = TestOperation(config)

        with pytest.raises(ConfigurationError) as exc_info:
            operation.validate_config_or_raise()

        error_msg = str(exc_info.value)
        assert "Configuration validation failed" in error_msg
        assert "Error 1" in error_msg
        assert "Error 2" in error_msg


class TestOperationFrameworkExtensibility:
    """Test that operation framework is extensible for new operation types."""

    def test_operation_framework_supports_inheritance(self):
        """Framework should support creating new operation types via inheritance."""
        from quilt_mcp.operations.base import Operation, SuccessResult
        from quilt_mcp.config.base import Configuration, ConfigValidationResult

        # Create test configuration
        class TestConfig(Configuration):
            def validate(self):
                return ConfigValidationResult.success_result()
            def to_dict(self):
                return {}
            @classmethod
            def from_dict(cls, data):
                return cls()

        class CustomOperation(Operation):
            def execute(self):
                return SuccessResult(data={"result": "custom"})

        config = TestConfig()
        operation = CustomOperation(config)
        result = operation.execute()

        assert result.success is True
        assert result.data == {"result": "custom"}

    def test_custom_operations_can_extend_error_handling(self):
        """Custom operations should be able to extend error handling."""
        from quilt_mcp.operations.base import Operation, ErrorResult, OperationError
        from quilt_mcp.config.base import Configuration, ConfigValidationResult

        # Create test configuration
        class TestConfig(Configuration):
            def validate(self):
                return ConfigValidationResult.success_result()
            def to_dict(self):
                return {}
            @classmethod
            def from_dict(cls, data):
                return cls()

        class CustomException(OperationError):
            pass

        class ExtendedOperation(Operation):
            def execute(self):
                try:
                    # Simulate custom operation that might fail
                    raise CustomException("Custom error occurred")
                except CustomException as e:
                    return ErrorResult(error_type="custom", message=str(e))

        config = TestConfig()
        operation = ExtendedOperation(config)
        result = operation.execute()

        assert result.success is False
        assert result.error_type == "custom"
        assert result.message == "Custom error occurred"

    def test_operation_framework_is_configuration_agnostic(self):
        """Operation framework should work with any Configuration subclass."""
        from quilt_mcp.operations.base import Operation, SuccessResult
        from quilt_mcp.config.quilt3 import Quilt3Config

        class TestOperation(Operation):
            def execute(self):
                return SuccessResult(data={"registry": self.config.registry_url})

        # Should work with Quilt3Config
        config = Quilt3Config(registry_url="s3://test-bucket")
        operation = TestOperation(config)
        result = operation.execute()

        assert result.success is True
        assert result.data["registry"] == "s3://test-bucket"


class TestOperationIntegrationWithConfiguration:
    """Test operation integration with configuration system."""

    def test_operations_receive_configuration_properly(self):
        """Operations should receive and use configuration properly."""
        from quilt_mcp.operations.base import Operation, SuccessResult
        from quilt_mcp.config.quilt3 import Quilt3Config

        class ConfigTestOperation(Operation):
            def execute(self):
                return SuccessResult(data={
                    "has_config": self.config is not None,
                    "config_type": type(self.config).__name__
                })

        config = Quilt3Config(registry_url="s3://test-bucket")
        operation = ConfigTestOperation(config)

        assert operation.config == config

        result = operation.execute()
        assert result.success is True
        assert result.data["has_config"] is True
        assert result.data["config_type"] == "Quilt3Config"

    def test_configuration_validation_is_enforced(self):
        """Operations should enforce configuration validation."""
        from quilt_mcp.operations.base import Operation, SuccessResult
        from quilt_mcp.config.quilt3 import Quilt3Config

        class TestOperation(Operation):
            def execute(self):
                return SuccessResult()

        # Invalid configuration should be caught by execute_safely
        invalid_config = Quilt3Config(registry_url="invalid-url")
        operation = TestOperation(invalid_config)

        result = operation.execute_safely()
        assert result.success is False
        assert result.error_type == "config"

    def test_operations_work_without_global_state_dependencies(self):
        """Operations should work without dependencies on global state."""
        from quilt_mcp.operations.base import Operation, SuccessResult
        from quilt_mcp.config.quilt3 import Quilt3Config

        class IsolatedOperation(Operation):
            def execute(self):
                # Should work using only injected configuration
                return SuccessResult(data={
                    "registry_url": self.config.registry_url,
                    "isolated": True
                })

        config = Quilt3Config(registry_url="s3://test-bucket")
        operation = IsolatedOperation(config)
        result = operation.execute()

        # Should work without any global quilt3 setup
        assert result.success is True
        assert result.data["registry_url"] == "s3://test-bucket"
        assert result.data["isolated"] is True


class TestOperationFrameworkIntegration:
    """Test operation framework components work together properly."""

    def test_complete_operation_workflow(self):
        """Test complete workflow from configuration to execution to result."""
        from quilt_mcp.operations.base import Operation, SuccessResult
        from quilt_mcp.config.quilt3 import Quilt3Config

        class CompleteWorkflowOperation(Operation):
            def execute(self):
                # Simulate operation that uses configuration
                return SuccessResult(
                    data={
                        "registry": self.config.registry_url,
                        "operation": "complete_workflow"
                    },
                    message="Workflow completed successfully"
                )

        # 1. Create configuration
        config = Quilt3Config(registry_url="s3://test-bucket")

        # 2. Create operation with configuration
        operation = CompleteWorkflowOperation(config)

        # 3. Execute operation safely
        result = operation.execute_safely(operation_id="test-workflow-123")

        # 4. Verify result format
        assert hasattr(result, 'success')
        assert hasattr(result, 'to_dict')
        assert result.success is True
        assert result.operation_id == "test-workflow-123"

        # 5. Serialize result
        serialized = result.to_dict()
        assert isinstance(serialized, dict)
        assert serialized["success"] is True
        assert serialized["operation_id"] == "test-workflow-123"

    def test_error_propagation_through_operation_stack(self):
        """Test that errors propagate correctly through the operation stack."""
        from quilt_mcp.operations.base import (
            Operation,
            NetworkError,
            AuthenticationError,
            ConfigurationError,
            AuthorizationError
        )
        from quilt_mcp.config.base import Configuration, ConfigValidationResult

        # Create valid configuration
        class ValidConfig(Configuration):
            def validate(self):
                return ConfigValidationResult.success_result()
            def to_dict(self):
                return {}
            @classmethod
            def from_dict(cls, data):
                return cls()

        config = ValidConfig()

        # Test error propagation for different error types
        error_tests = [
            (NetworkError("Network failed"), "network"),
            (AuthenticationError("Auth failed"), "auth"),
            (ConfigurationError("Config failed"), "config"),
            (AuthorizationError("Permission denied"), "authz"),
        ]

        for exception, expected_type in error_tests:
            class ErrorOperation(Operation):
                def execute(self):
                    raise exception

            operation = ErrorOperation(config)
            result = operation.execute_safely()

            assert result.success is False
            assert result.error_type == expected_type
            assert str(exception) in result.message

    def test_operation_framework_performance_characteristics(self):
        """Test that operation framework meets performance requirements."""
        from quilt_mcp.operations.base import Operation, SuccessResult
        from quilt_mcp.config.base import Configuration, ConfigValidationResult
        import time

        # Create test configuration
        class TestConfig(Configuration):
            def validate(self):
                return ConfigValidationResult.success_result()
            def to_dict(self):
                return {}
            @classmethod
            def from_dict(cls, data):
                return cls()

        class PerformanceTestOperation(Operation):
            def execute(self):
                return SuccessResult(data={"test": "performance"})

        config = TestConfig()
        operation = PerformanceTestOperation(config)

        # Measure execution time
        start_time = time.time()
        result = operation.execute_safely()
        end_time = time.time()

        execution_time = end_time - start_time

        # Should complete quickly (framework overhead should be minimal)
        assert execution_time < 0.1  # 100ms should be more than enough for framework overhead
        assert result.success is True

        # Test serialization performance
        start_time = time.time()
        serialized = result.to_dict()
        end_time = time.time()

        serialization_time = end_time - start_time

        # Serialization should be very fast
        assert serialization_time < 0.01  # 10ms should be more than enough
        assert isinstance(serialized, dict)