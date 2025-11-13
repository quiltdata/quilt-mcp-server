"""Tests for resource registry structure and validation."""

import pytest
from typing import get_type_hints
from quilt_mcp.tools.resource_access import (
    ResourceDefinition,
    validate_registry,
    RESOURCE_REGISTRY,
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


class TestResourceRegistry:
    """Test RESOURCE_REGISTRY structure and content."""

    def test_registry_exists(self):
        """Test RESOURCE_REGISTRY is defined."""
        assert RESOURCE_REGISTRY is not None
        assert isinstance(RESOURCE_REGISTRY, dict)

    def test_registry_has_phase1_resources(self):
        """Test registry contains Phase 1 resources."""
        expected_uris = [
            "auth://status",
            "auth://catalog/info",
            "admin://users",
            "permissions://discover",
            "metadata://templates/{template}",
        ]

        for uri in expected_uris:
            assert uri in RESOURCE_REGISTRY, f"Missing resource: {uri}"

    def test_registry_validates_successfully(self):
        """Test registry passes validation checks."""
        # Should not raise
        validate_registry(RESOURCE_REGISTRY)

    def test_static_resources_correctly_marked(self):
        """Test static resources have is_template=False."""
        static_uris = [
            "auth://status",
            "auth://catalog/info",
            "admin://users",
            "permissions://discover",
        ]

        for uri in static_uris:
            assert RESOURCE_REGISTRY[uri]["is_template"] is False
            assert len(RESOURCE_REGISTRY[uri]["template_variables"]) == 0

    def test_template_resource_correctly_marked(self):
        """Test template resource has is_template=True."""
        uri = "metadata://templates/{template}"

        assert RESOURCE_REGISTRY[uri]["is_template"] is True
        assert "template" in RESOURCE_REGISTRY[uri]["template_variables"]
        assert "template" in RESOURCE_REGISTRY[uri]["parameter_mapping"]

    def test_admin_resource_requires_admin(self):
        """Test admin resource has requires_admin=True."""
        assert RESOURCE_REGISTRY["admin://users"]["requires_admin"] is True

    def test_non_admin_resources_accessible(self):
        """Test non-admin resources have requires_admin=False."""
        non_admin_uris = [
            "auth://status",
            "auth://catalog/info",
            "permissions://discover",
            "metadata://templates/{template}",
        ]

        for uri in non_admin_uris:
            assert RESOURCE_REGISTRY[uri]["requires_admin"] is False

    def test_categories_assigned(self):
        """Test all resources have valid categories."""
        category_map = {
            "auth://status": "auth",
            "auth://catalog/info": "auth",
            "admin://users": "admin",
            "permissions://discover": "permissions",
            "metadata://templates/{template}": "metadata",
        }

        for uri, expected_category in category_map.items():
            assert RESOURCE_REGISTRY[uri]["category"] == expected_category

    def test_service_functions_callable(self):
        """Test all service functions are callable."""
        for uri, defn in RESOURCE_REGISTRY.items():
            assert callable(defn["service_function"]), \
                f"Service function not callable: {uri}"

    def test_async_flags_accurate(self):
        """Test async flags match actual service functions."""
        # admin_users_list is async, others are sync
        assert RESOURCE_REGISTRY["admin://users"]["is_async"] is True

        sync_uris = [
            "auth://status",
            "auth://catalog/info",
            "permissions://discover",
            "metadata://templates/{template}",
        ]

        for uri in sync_uris:
            assert RESOURCE_REGISTRY[uri]["is_async"] is False