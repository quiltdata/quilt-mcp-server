"""Stateless tests for permissions tools ensuring AWS session uses JWT credentials."""

import datetime as _dt
from unittest.mock import patch, MagicMock

import pytest

from quilt_mcp.runtime import request_context
from quilt_mcp.tools.permissions import permissions
from quilt_mcp.services.permission_discovery import BucketInfo, PermissionLevel


@pytest.fixture(autouse=True)
def reset_singleton(monkeypatch):
    from quilt_mcp.tools import permissions as permissions_module

    monkeypatch.setattr(permissions_module, "_permission_discovery", None)


def test_permissions_access_check_uses_jwt_credentials(monkeypatch):
    # Prepare fake JWT token and mock auth service to return AWS credentials
    token_value = "test.jwt.token"

    fake_auth_result = MagicMock()
    fake_session = MagicMock()

    fake_auth_service = MagicMock()
    fake_auth_service.authenticate_header.return_value = fake_auth_result
    fake_auth_service.build_boto3_session.return_value = fake_session

    monkeypatch.setattr(
        "quilt_mcp.tools.permissions._get_bearer_auth_service",
        lambda: fake_auth_service,
    )

    # Fake AWS session should be used when AWSPermissionDiscovery is instantiated
    fake_permission_discovery = MagicMock()
    fake_permission_discovery.discover_bucket_permissions.return_value = BucketInfo(
        name="bucket",
        region="us-east-1",
        permission_level=PermissionLevel.FULL_ACCESS,
        can_read=True,
        can_write=True,
        can_list=True,
        last_checked=_dt.datetime.now(_dt.timezone.utc),
        error_message=None,
    )
    fake_permission_discovery.test_bucket_operations.return_value = {"read": True, "write": True, "list": True}

    with patch(
        "quilt_mcp.tools.permissions.AWSPermissionDiscovery",
        return_value=fake_permission_discovery,
    ) as mock_pd:
        with request_context(token_value, metadata={"path": "/permissions"}):
            result = permissions(action="access_check", params={"bucket_name": "bucket"})
            builder = mock_pd.call_args.kwargs["aws_session_builder"]
            built_session = builder()

    assert result["success"] is True
    fake_auth_service.authenticate_header.assert_called_once_with(f"Bearer {token_value}")
    fake_auth_service.build_boto3_session.assert_called_once_with(fake_auth_result)

    # Ensure AWSPermissionDiscovery was created with the session builder
    assert "aws_session_builder" in mock_pd.call_args.kwargs
    assert built_session is fake_session

