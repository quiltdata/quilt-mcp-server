"""Tests for resource access response models."""

import pytest
from datetime import datetime, timezone
from quilt_mcp.tools.responses import (
    GetResourceSuccess,
    GetResourceError,
    ResourceMetadata,
)


class TestGetResourceSuccess:
    """Test GetResourceSuccess model."""

    def test_create_success_response(self):
        """Test creating a valid success response."""
        response = GetResourceSuccess(
            uri="auth://status",
            resource_name="Auth Status",
            data={"authenticated": True, "catalog_url": "https://example.com"},
            timestamp=datetime.now(timezone.utc),
            mime_type="application/json",
        )

        assert response.success is True
        assert response.uri == "auth://status"
        assert response.resource_name == "Auth Status"
        assert response.data["authenticated"] is True
        assert response.mime_type == "application/json"
        assert isinstance(response.timestamp, datetime)

    def test_dict_like_access(self):
        """Test dict-like access compatibility."""
        response = GetResourceSuccess(
            uri="auth://status",
            resource_name="Auth Status",
            data={"key": "value"},
        )

        # Dict-like access (from DictAccessibleModel)
        assert response["uri"] == "auth://status"
        assert response["data"]["key"] == "value"
        assert "resource_name" in response

    def test_model_dump_serialization(self):
        """Test model serialization to dict."""
        response = GetResourceSuccess(
            uri="auth://status",
            resource_name="Auth Status",
            data={"test": "data"},
        )

        dumped = response.model_dump()
        assert dumped["success"] is True
        assert dumped["uri"] == "auth://status"
        assert "timestamp" in dumped
        assert isinstance(dumped, dict)

    def test_default_mime_type(self):
        """Test default mime_type is application/json."""
        response = GetResourceSuccess(
            uri="auth://status",
            resource_name="Test",
            data={},
        )

        assert response.mime_type == "application/json"


class TestGetResourceError:
    """Test GetResourceError model."""

    def test_create_error_response(self):
        """Test creating a valid error response."""
        response = GetResourceError(
            error="InvalidURI",
            cause="Resource URI not recognized",
            suggested_actions=["Check URI format", "Call discovery mode"],
            valid_uris=["auth://status", "auth://catalog/info"],
        )

        assert response.success is False
        assert response.error == "InvalidURI"
        assert response.cause == "Resource URI not recognized"
        assert len(response.suggested_actions) == 2
        assert len(response.valid_uris) == 2

    def test_optional_valid_uris(self):
        """Test valid_uris is optional."""
        response = GetResourceError(
            error="ResourceExecutionError",
            cause="Service failed",
            suggested_actions=["Retry operation"],
        )

        assert response.valid_uris is None

    def test_dict_like_access(self):
        """Test dict-like access for error response."""
        response = GetResourceError(
            error="InvalidURI",
            cause="Test error",
            suggested_actions=["Action 1"],
        )

        assert response["error"] == "InvalidURI"
        assert response["success"] is False
        assert "suggested_actions" in response


class TestResourceMetadata:
    """Test ResourceMetadata model."""

    def test_create_static_resource_metadata(self):
        """Test metadata for static (non-template) resource."""
        metadata = ResourceMetadata(
            uri="auth://status",
            name="Auth Status",
            description="Check authentication status",
            is_template=False,
            template_variables=[],
            requires_admin=False,
            category="auth",
        )

        assert metadata.uri == "auth://status"
        assert metadata.is_template is False
        assert len(metadata.template_variables) == 0
        assert metadata.requires_admin is False
        assert metadata.category == "auth"

    def test_create_template_resource_metadata(self):
        """Test metadata for template resource."""
        metadata = ResourceMetadata(
            uri="metadata://templates/{template}",
            name="Metadata Template",
            description="Get specific metadata template",
            is_template=True,
            template_variables=["template"],
            requires_admin=False,
            category="metadata",
        )

        assert metadata.is_template is True
        assert metadata.template_variables == ["template"]
        assert "{template}" in metadata.uri

    def test_admin_resource_metadata(self):
        """Test metadata for admin-only resource."""
        metadata = ResourceMetadata(
            uri="admin://users",
            name="Admin Users List",
            description="List all users (requires admin)",
            is_template=False,
            template_variables=[],
            requires_admin=True,
            category="admin",
        )

        assert metadata.requires_admin is True
        assert metadata.category == "admin"

    def test_default_template_variables(self):
        """Test default empty list for template_variables."""
        metadata = ResourceMetadata(
            uri="auth://status",
            name="Test",
            description="Test resource",
            is_template=False,
            requires_admin=False,
            category="auth",
        )

        assert metadata.template_variables == []
