"""Tests for resource registry structure and validation."""

import pytest
from typing import get_type_hints
from quilt_mcp.tools.resource_access import (
    ResourceDefinition,
    validate_registry,
)


class TestResourceDefinitionType:
    """Test ResourceDefinition TypedDict structure."""

    def test_resource_definition_fields(self):
        """Test ResourceDefinition has all required fields."""
        # Get type hints from ResourceDefinition
        hints = get_type_hints(ResourceDefinition)

        required_fields = {
            "uri",
            "name",
            "description",
            "service_function",
            "is_async",
            "is_template",
            "template_variables",
            "requires_admin",
            "category",
            "parameter_mapping",
        }

        assert set(hints.keys()) == required_fields


class TestRegistryValidation:
    """Test registry validation function."""

    def test_valid_static_resource(self):
        """Test validation passes for valid static resource."""
        def mock_service():
            return {"test": "data"}

        registry = {
            "auth://status": {
                "uri": "auth://status",
                "name": "Auth Status",
                "description": "Test resource",
                "service_function": mock_service,
                "is_async": False,
                "is_template": False,
                "template_variables": [],
                "requires_admin": False,
                "category": "auth",
                "parameter_mapping": {},
            }
        }

        # Should not raise
        validate_registry(registry)

    def test_uri_mismatch_raises_error(self):
        """Test validation fails when key doesn't match uri."""
        def mock_service():
            return {}

        registry = {
            "auth://wrong": {
                "uri": "auth://correct",
                "name": "Test",
                "description": "Test",
                "service_function": mock_service,
                "is_async": False,
                "is_template": False,
                "template_variables": [],
                "requires_admin": False,
                "category": "auth",
                "parameter_mapping": {},
            }
        }

        with pytest.raises(ValueError, match="URI mismatch"):
            validate_registry(registry)

    def test_non_callable_service_function_raises_error(self):
        """Test validation fails for non-callable service function."""
        registry = {
            "auth://status": {
                "uri": "auth://status",
                "name": "Test",
                "description": "Test",
                "service_function": "not_callable",  # Invalid
                "is_async": False,
                "is_template": False,
                "template_variables": [],
                "requires_admin": False,
                "category": "auth",
                "parameter_mapping": {},
            }
        }

        with pytest.raises(ValueError, match="not callable"):
            validate_registry(registry)

    def test_template_flag_inconsistent_with_uri(self):
        """Test validation fails when template flag doesn't match URI."""
        def mock_service():
            return {}

        # URI has braces but is_template is False
        registry = {
            "test://{var}": {
                "uri": "test://{var}",
                "name": "Test",
                "description": "Test",
                "service_function": mock_service,
                "is_async": False,
                "is_template": False,  # Inconsistent!
                "template_variables": ["var"],
                "requires_admin": False,
                "category": "test",
                "parameter_mapping": {"var": "var"},
            }
        }

        with pytest.raises(ValueError, match="Template flag inconsistent"):
            validate_registry(registry)

    def test_template_missing_variables_list(self):
        """Test validation fails when template has empty variables list."""
        def mock_service():
            return {}

        registry = {
            "test://{var}": {
                "uri": "test://{var}",
                "name": "Test",
                "description": "Test",
                "service_function": mock_service,
                "is_async": False,
                "is_template": True,
                "template_variables": [],  # Empty but should have ["var"]
                "requires_admin": False,
                "category": "test",
                "parameter_mapping": {},
            }
        }

        with pytest.raises(ValueError, match="missing variable list"):
            validate_registry(registry)

    def test_template_missing_parameter_mapping(self):
        """Test validation fails when template variable not in mapping."""
        def mock_service():
            return {}

        registry = {
            "test://{var}": {
                "uri": "test://{var}",
                "name": "Test",
                "description": "Test",
                "service_function": mock_service,
                "is_async": False,
                "is_template": True,
                "template_variables": ["var"],
                "requires_admin": False,
                "category": "test",
                "parameter_mapping": {},  # Missing "var"
            }
        }

        with pytest.raises(ValueError, match="not in parameter mapping"):
            validate_registry(registry)

    def test_valid_template_resource(self):
        """Test validation passes for valid template resource."""
        def mock_service(name: str):
            return {"name": name}

        registry = {
            "test://{var}": {
                "uri": "test://{var}",
                "name": "Test",
                "description": "Test resource",
                "service_function": mock_service,
                "is_async": False,
                "is_template": True,
                "template_variables": ["var"],
                "requires_admin": False,
                "category": "test",
                "parameter_mapping": {"var": "name"},
            }
        }

        # Should not raise
        validate_registry(registry)