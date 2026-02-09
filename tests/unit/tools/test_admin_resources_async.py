"""Unit tests for admin:// resource async/await fix.

These tests verify that admin resources correctly await async governance service
functions instead of returning unawaited coroutines.

Regression tests for: spec/a18-mcp-test/30-async-await-bug-diagnosis.md
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_admin_users_resource_awaits_async_function():
    """Verify admin://users directly awaits admin_users_list (not using asyncio.to_thread)."""
    # Import the resource registration function
    from quilt_mcp.tools.resources import register_resources

    # Mock FastMCP
    mock_mcp = MagicMock()
    registered_resources = {}

    def capture_resource(uri, **kwargs):
        def decorator(func):
            registered_resources[uri] = func
            return func

        return decorator

    mock_mcp.resource = capture_resource

    # Mock the governance service to return expected data
    mock_result = {"users": [{"name": "test_user", "email": "test@example.com", "roles": ["user"]}], "total": 1}

    with (
        patch(
            "quilt_mcp.services.governance_service.admin_users_list", new_callable=AsyncMock
        ) as mock_admin_users_list,
        patch("quilt_mcp.context.factory.RequestContextFactory") as mock_context_factory,
    ):
        # Setup mocks
        mock_admin_users_list.return_value = mock_result
        mock_context = MagicMock()
        mock_context_factory.return_value.create_context.return_value = mock_context

        # Register resources
        register_resources(mock_mcp)

        # Get the registered resource function
        admin_users_resource = registered_resources.get("admin://users")
        assert admin_users_resource is not None, "admin://users resource not registered"

        # Call the resource function
        result = await admin_users_resource()

        # Verify the result is properly serialized JSON (not a coroutine string)
        assert isinstance(result, str), "Result should be a JSON string"
        assert "<coroutine object" not in result, "Result should NOT contain unawaited coroutine"

        # Parse and verify the JSON content
        parsed = json.loads(result)
        assert parsed == mock_result, "Result should match the mocked data"

        # Verify admin_users_list was properly awaited (called exactly once)
        mock_admin_users_list.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_roles_resource_awaits_async_function():
    """Verify admin://roles directly awaits admin_roles_list."""
    from quilt_mcp.tools.resources import register_resources

    mock_mcp = MagicMock()
    registered_resources = {}

    def capture_resource(uri, **kwargs):
        def decorator(func):
            registered_resources[uri] = func
            return func

        return decorator

    mock_mcp.resource = capture_resource

    mock_result = {"roles": [{"name": "admin", "id": "role-1"}, {"name": "user", "id": "role-2"}], "total": 2}

    with (
        patch(
            "quilt_mcp.services.governance_service.admin_roles_list", new_callable=AsyncMock
        ) as mock_admin_roles_list,
        patch("quilt_mcp.context.factory.RequestContextFactory") as mock_context_factory,
    ):
        mock_admin_roles_list.return_value = mock_result
        mock_context = MagicMock()
        mock_context_factory.return_value.create_context.return_value = mock_context

        register_resources(mock_mcp)

        admin_roles_resource = registered_resources.get("admin://roles")
        assert admin_roles_resource is not None

        result = await admin_roles_resource()

        assert isinstance(result, str)
        assert "<coroutine object" not in result

        parsed = json.loads(result)
        assert parsed == mock_result

        mock_admin_roles_list.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_sso_config_resource_awaits_async_function():
    """Verify admin://config/sso directly awaits admin_sso_config_get."""
    from quilt_mcp.tools.resources import register_resources

    mock_mcp = MagicMock()
    registered_resources = {}

    def capture_resource(uri, **kwargs):
        def decorator(func):
            registered_resources[uri] = func
            return func

        return decorator

    mock_mcp.resource = capture_resource

    mock_result = {"sso_enabled": True, "provider": "okta", "domain": "example.okta.com"}

    with (
        patch(
            "quilt_mcp.services.governance_service.admin_sso_config_get", new_callable=AsyncMock
        ) as mock_sso_config_get,
        patch("quilt_mcp.context.factory.RequestContextFactory") as mock_context_factory,
    ):
        mock_sso_config_get.return_value = mock_result
        mock_context = MagicMock()
        mock_context_factory.return_value.create_context.return_value = mock_context

        register_resources(mock_mcp)

        sso_config_resource = registered_resources.get("admin://config/sso")
        assert sso_config_resource is not None

        result = await sso_config_resource()

        assert isinstance(result, str)
        assert "<coroutine object" not in result

        parsed = json.loads(result)
        assert parsed == mock_result

        mock_sso_config_get.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_tabulator_config_resource_awaits_async_function():
    """Verify admin://config/tabulator directly awaits admin_tabulator_open_query_get."""
    from quilt_mcp.tools.resources import register_resources

    mock_mcp = MagicMock()
    registered_resources = {}

    def capture_resource(uri, **kwargs):
        def decorator(func):
            registered_resources[uri] = func
            return func

        return decorator

    mock_mcp.resource = capture_resource

    mock_result = {"open_query_enabled": False, "max_rows": 1000}

    with (
        patch(
            "quilt_mcp.services.governance_service.admin_tabulator_open_query_get", new_callable=AsyncMock
        ) as mock_tabulator_config_get,
        patch("quilt_mcp.context.factory.RequestContextFactory") as mock_context_factory,
    ):
        mock_tabulator_config_get.return_value = mock_result
        mock_context = MagicMock()
        mock_context_factory.return_value.create_context.return_value = mock_context

        register_resources(mock_mcp)

        tabulator_config_resource = registered_resources.get("admin://config/tabulator")
        assert tabulator_config_resource is not None

        result = await tabulator_config_resource()

        assert isinstance(result, str)
        assert "<coroutine object" not in result

        parsed = json.loads(result)
        assert parsed == mock_result

        mock_tabulator_config_get.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_users_resource_handles_authorization_errors():
    """Verify admin://users provides helpful error messages for auth failures."""
    from quilt_mcp.tools.resources import register_resources

    mock_mcp = MagicMock()
    registered_resources = {}

    def capture_resource(uri, **kwargs):
        def decorator(func):
            registered_resources[uri] = func
            return func

        return decorator

    mock_mcp.resource = capture_resource

    with (
        patch(
            "quilt_mcp.services.governance_service.admin_users_list", new_callable=AsyncMock
        ) as mock_admin_users_list,
        patch("quilt_mcp.context.factory.RequestContextFactory") as mock_context_factory,
    ):
        # Simulate an authorization error
        mock_admin_users_list.side_effect = Exception("Unauthorized: 403 Forbidden")
        mock_context = MagicMock()
        mock_context_factory.return_value.create_context.return_value = mock_context

        register_resources(mock_mcp)

        admin_users_resource = registered_resources.get("admin://users")
        result = await admin_users_resource()

        # Should return a helpful error message (not raise exception)
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["error"] == "Unauthorized"
        assert "admin privileges" in parsed["message"]


@pytest.mark.asyncio
async def test_comparison_auth_resource_uses_asyncio_to_thread():
    """Verify auth://status correctly uses asyncio.to_thread for sync functions.

    This test serves as a comparison to show that asyncio.to_thread is the
    RIGHT approach for synchronous functions (like auth_status), but was
    WRONG for async functions (like admin_users_list).
    """
    from quilt_mcp.tools.resources import register_resources

    mock_mcp = MagicMock()
    registered_resources = {}

    def capture_resource(uri, **kwargs):
        def decorator(func):
            registered_resources[uri] = func
            return func

        return decorator

    mock_mcp.resource = capture_resource

    mock_result = {"authenticated": True, "catalog": "test-catalog"}

    with patch("quilt_mcp.services.auth_metadata.auth_status", return_value=mock_result) as mock_auth_status:
        register_resources(mock_mcp)

        auth_status_resource = registered_resources.get("auth://status")
        assert auth_status_resource is not None

        result = await auth_status_resource()

        # Verify it properly serializes (auth_status is SYNC, so asyncio.to_thread is correct)
        assert isinstance(result, str)
        assert "<coroutine object" not in result

        parsed = json.loads(result)
        assert parsed == mock_result

        # Verify auth_status was called (not awaited, since it's sync)
        mock_auth_status.assert_called_once()
