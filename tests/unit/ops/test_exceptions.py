"""Tests for QuiltOps custom exceptions - Test-Driven Development Implementation.

This test suite follows TDD principles by defining the expected behavior of custom exceptions
before implementation. Tests cover exception hierarchy, error context fields, and messages.
"""

from __future__ import annotations

import pytest
from typing import Any, Dict, Optional


class TestAuthenticationError:
    """Test AuthenticationError exception behavior."""

    def test_authentication_error_can_be_imported(self):
        """Test that AuthenticationError can be imported from ops module."""
        # This test will fail initially - that's the RED phase of TDD
        from quilt_mcp.ops.exceptions import AuthenticationError
        assert AuthenticationError is not None

    def test_authentication_error_is_exception(self):
        """Test that AuthenticationError inherits from Exception."""
        from quilt_mcp.ops.exceptions import AuthenticationError
        
        # Should be a subclass of Exception
        assert issubclass(AuthenticationError, Exception)

    def test_authentication_error_creation_with_message(self):
        """Test creating AuthenticationError with message."""
        from quilt_mcp.ops.exceptions import AuthenticationError
        
        error = AuthenticationError("Invalid JWT token")
        
        assert str(error) == "Invalid JWT token"
        assert error.args == ("Invalid JWT token",)

    def test_authentication_error_creation_with_context(self):
        """Test creating AuthenticationError with error context."""
        from quilt_mcp.ops.exceptions import AuthenticationError
        
        context = {
            "auth_method": "jwt",
            "error_code": "INVALID_TOKEN",
            "remediation": "Please provide a valid JWT token"
        }
        
        error = AuthenticationError("Authentication failed", context=context)
        
        assert str(error) == "Authentication failed"
        assert error.context == context

    def test_authentication_error_without_context(self):
        """Test creating AuthenticationError without context."""
        from quilt_mcp.ops.exceptions import AuthenticationError
        
        error = AuthenticationError("Authentication failed")
        
        assert str(error) == "Authentication failed"
        assert error.context == {}

    def test_authentication_error_context_access(self):
        """Test accessing context fields from AuthenticationError."""
        from quilt_mcp.ops.exceptions import AuthenticationError
        
        context = {
            "auth_method": "quilt3_session",
            "session_path": "/path/to/session",
            "error_details": "Session expired"
        }
        
        error = AuthenticationError("Session validation failed", context=context)
        
        assert error.context["auth_method"] == "quilt3_session"
        assert error.context["session_path"] == "/path/to/session"
        assert error.context["error_details"] == "Session expired"


class TestBackendError:
    """Test BackendError exception behavior."""

    def test_backend_error_can_be_imported(self):
        """Test that BackendError can be imported from ops module."""
        from quilt_mcp.ops.exceptions import BackendError
        assert BackendError is not None

    def test_backend_error_is_exception(self):
        """Test that BackendError inherits from Exception."""
        from quilt_mcp.ops.exceptions import BackendError
        
        # Should be a subclass of Exception
        assert issubclass(BackendError, Exception)

    def test_backend_error_creation_with_backend_type(self):
        """Test creating BackendError with backend type in context."""
        from quilt_mcp.ops.exceptions import BackendError
        
        context = {
            "backend_type": "quilt3",
            "operation": "search_packages",
            "error_details": "Network timeout"
        }
        
        error = BackendError("Backend operation failed", context=context)
        
        assert str(error) == "Backend operation failed"
        assert error.context["backend_type"] == "quilt3"
        assert error.context["operation"] == "search_packages"

    def test_backend_error_with_original_exception(self):
        """Test creating BackendError with original exception in context."""
        from quilt_mcp.ops.exceptions import BackendError
        
        original_error = ValueError("Invalid package name")
        context = {
            "backend_type": "platform",
            "original_exception": str(original_error),
            "operation": "get_package_info"
        }
        
        error = BackendError("Package lookup failed", context=context)
        
        assert error.context["original_exception"] == "Invalid package name"
        assert error.context["backend_type"] == "platform"

    def test_backend_error_without_context(self):
        """Test creating BackendError without context."""
        from quilt_mcp.ops.exceptions import BackendError
        
        error = BackendError("Unknown backend error")
        
        assert str(error) == "Unknown backend error"
        assert error.context == {}


class TestValidationError:
    """Test ValidationError exception behavior."""

    def test_validation_error_can_be_imported(self):
        """Test that ValidationError can be imported from ops module."""
        from quilt_mcp.ops.exceptions import ValidationError
        assert ValidationError is not None

    def test_validation_error_is_exception(self):
        """Test that ValidationError inherits from Exception."""
        from quilt_mcp.ops.exceptions import ValidationError
        
        # Should be a subclass of Exception
        assert issubclass(ValidationError, Exception)

    def test_validation_error_creation_with_field_info(self):
        """Test creating ValidationError with field validation info."""
        from quilt_mcp.ops.exceptions import ValidationError
        
        context = {
            "field_name": "package_name",
            "field_value": "invalid/name/with/too/many/slashes",
            "validation_rule": "Package name must have format 'user/package'",
            "error_type": "format_error"
        }
        
        error = ValidationError("Invalid package name format", context=context)
        
        assert str(error) == "Invalid package name format"
        assert error.context["field_name"] == "package_name"
        assert error.context["validation_rule"] == "Package name must have format 'user/package'"

    def test_validation_error_with_multiple_fields(self):
        """Test creating ValidationError with multiple field errors."""
        from quilt_mcp.ops.exceptions import ValidationError
        
        context = {
            "errors": [
                {"field": "name", "error": "Required field missing"},
                {"field": "registry", "error": "Invalid S3 URL format"}
            ],
            "validation_type": "package_info"
        }
        
        error = ValidationError("Multiple validation errors", context=context)
        
        assert len(error.context["errors"]) == 2
        assert error.context["validation_type"] == "package_info"

    def test_validation_error_without_context(self):
        """Test creating ValidationError without context."""
        from quilt_mcp.ops.exceptions import ValidationError
        
        error = ValidationError("Validation failed")
        
        assert str(error) == "Validation failed"
        assert error.context == {}


class TestExceptionHierarchy:
    """Test exception inheritance and hierarchy."""

    def test_all_exceptions_inherit_from_exception(self):
        """Test that all custom exceptions inherit from Exception."""
        from quilt_mcp.ops.exceptions import (
            AuthenticationError, BackendError, ValidationError
        )
        
        assert issubclass(AuthenticationError, Exception)
        assert issubclass(BackendError, Exception)
        assert issubclass(ValidationError, Exception)

    def test_exceptions_are_distinct_types(self):
        """Test that custom exceptions are distinct types."""
        from quilt_mcp.ops.exceptions import (
            AuthenticationError, BackendError, ValidationError
        )
        
        # Should not inherit from each other
        assert not issubclass(AuthenticationError, BackendError)
        assert not issubclass(AuthenticationError, ValidationError)
        assert not issubclass(BackendError, AuthenticationError)
        assert not issubclass(BackendError, ValidationError)
        assert not issubclass(ValidationError, AuthenticationError)
        assert not issubclass(ValidationError, BackendError)

    def test_exception_catching_specificity(self):
        """Test that exceptions can be caught specifically."""
        from quilt_mcp.ops.exceptions import (
            AuthenticationError, BackendError, ValidationError
        )
        
        # Test AuthenticationError catching
        try:
            raise AuthenticationError("Test auth error")
        except AuthenticationError as e:
            assert str(e) == "Test auth error"
        except Exception:
            pytest.fail("Should have caught AuthenticationError specifically")
        
        # Test BackendError catching
        try:
            raise BackendError("Test backend error")
        except BackendError as e:
            assert str(e) == "Test backend error"
        except Exception:
            pytest.fail("Should have caught BackendError specifically")
        
        # Test ValidationError catching
        try:
            raise ValidationError("Test validation error")
        except ValidationError as e:
            assert str(e) == "Test validation error"
        except Exception:
            pytest.fail("Should have caught ValidationError specifically")


class TestExceptionContextFields:
    """Test exception context field behavior."""

    def test_context_is_mutable(self):
        """Test that exception context can be modified after creation."""
        from quilt_mcp.ops.exceptions import BackendError
        
        error = BackendError("Test error")
        
        # Initially empty
        assert error.context == {}
        
        # Can be modified
        error.context["backend_type"] = "quilt3"
        error.context["operation"] = "test_operation"
        
        assert error.context["backend_type"] == "quilt3"
        assert error.context["operation"] == "test_operation"

    def test_context_preserves_original_data(self):
        """Test that context preserves original data types."""
        from quilt_mcp.ops.exceptions import ValidationError
        
        original_context = {
            "field_name": "test_field",
            "field_value": 42,
            "is_required": True,
            "allowed_values": ["a", "b", "c"],
            "nested_data": {"key": "value"}
        }
        
        error = ValidationError("Test error", context=original_context)
        
        # Should preserve all data types
        assert error.context["field_name"] == "test_field"
        assert error.context["field_value"] == 42
        assert error.context["is_required"] is True
        assert error.context["allowed_values"] == ["a", "b", "c"]
        assert error.context["nested_data"]["key"] == "value"

    def test_context_is_optional(self):
        """Test that context parameter is optional for all exceptions."""
        from quilt_mcp.ops.exceptions import (
            AuthenticationError, BackendError, ValidationError
        )
        
        # All should work without context
        auth_error = AuthenticationError("Auth error")
        backend_error = BackendError("Backend error")
        validation_error = ValidationError("Validation error")
        
        assert auth_error.context == {}
        assert backend_error.context == {}
        assert validation_error.context == {}


class TestExceptionMessages:
    """Test exception message formatting and content."""

    def test_exception_message_clarity(self):
        """Test that exception messages are clear and informative."""
        from quilt_mcp.ops.exceptions import AuthenticationError
        
        context = {
            "auth_method": "jwt",
            "error_code": "EXPIRED_TOKEN",
            "remediation": "Please refresh your authentication token"
        }
        
        error = AuthenticationError(
            "JWT token has expired and cannot be used for authentication",
            context=context
        )
        
        message = str(error)
        assert "JWT token has expired" in message
        assert "authentication" in message
        
        # Context should be accessible for detailed error reporting
        assert error.context["remediation"] == "Please refresh your authentication token"

    def test_exception_repr_includes_context(self):
        """Test that exception repr includes context information."""
        from quilt_mcp.ops.exceptions import BackendError
        
        context = {"backend_type": "quilt3", "operation": "search"}
        error = BackendError("Search failed", context=context)
        
        repr_str = repr(error)
        
        # Should include class name and basic info
        assert "BackendError" in repr_str
        assert "Search failed" in repr_str

    def test_exception_str_is_message_only(self):
        """Test that str(exception) returns only the message."""
        from quilt_mcp.ops.exceptions import ValidationError
        
        context = {"field": "name", "error": "too long"}
        error = ValidationError("Field validation failed", context=context)
        
        # str() should return only the message
        assert str(error) == "Field validation failed"
        
        # Context should be separate
        assert error.context["field"] == "name"


class TestExceptionUsagePatterns:
    """Test common exception usage patterns."""

    def test_chaining_exceptions(self):
        """Test exception chaining with original exceptions."""
        from quilt_mcp.ops.exceptions import BackendError
        
        try:
            # Simulate original exception
            raise ValueError("Invalid input parameter")
        except ValueError as original:
            context = {
                "backend_type": "quilt3",
                "original_exception": str(original),
                "operation": "package_search"
            }
            
            backend_error = BackendError(
                "Package search failed due to invalid parameters",
                context=context
            )
            
            assert backend_error.context["original_exception"] == "Invalid input parameter"
            assert backend_error.context["backend_type"] == "quilt3"

    def test_error_context_for_debugging(self):
        """Test that error context provides sufficient debugging information."""
        from quilt_mcp.ops.exceptions import AuthenticationError
        
        context = {
            "auth_method": "quilt3_session",
            "session_file": "/home/user/.quilt/session.json",
            "error_details": "Session file not found",
            "timestamp": "2024-01-15T10:30:00Z",
            "remediation_steps": [
                "Run 'quilt3 login' to create a new session",
                "Check file permissions on session directory",
                "Verify network connectivity to Quilt registry"
            ]
        }
        
        error = AuthenticationError("Quilt3 session validation failed", context=context)
        
        # Should have comprehensive debugging info
        assert error.context["auth_method"] == "quilt3_session"
        assert error.context["session_file"] == "/home/user/.quilt/session.json"
        assert error.context["error_details"] == "Session file not found"
        assert len(error.context["remediation_steps"]) == 3

    def test_error_context_serialization(self):
        """Test that error context can be serialized for logging."""
        import json
        from quilt_mcp.ops.exceptions import ValidationError
        
        context = {
            "validation_errors": [
                {"field": "name", "error": "required"},
                {"field": "tags", "error": "must be list"}
            ],
            "input_data": {"name": "", "tags": "invalid"},
            "validation_timestamp": "2024-01-15T10:30:00Z"
        }
        
        error = ValidationError("Input validation failed", context=context)
        
        # Context should be JSON serializable for logging
        serialized = json.dumps(error.context)
        deserialized = json.loads(serialized)
        
        assert deserialized["validation_errors"][0]["field"] == "name"
        assert deserialized["input_data"]["name"] == ""
        assert deserialized["validation_timestamp"] == "2024-01-15T10:30:00Z"