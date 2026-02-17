"""Functional tests for package operation tool wiring."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from quilt_mcp.tools.packages import package_delete


def test_package_delete_platform_backend_wiring():
    """Verify package_delete routes through backend abstraction in func layer."""
    mock_backend = Mock()
    mock_backend.delete_package.return_value = True

    with (
        patch(
            "quilt_mcp.tools.package_crud._authorize_package", return_value=(SimpleNamespace(auth_type="jwt"), None)
        ),
        patch("quilt_mcp.tools.package_crud.QuiltOpsFactory.create", return_value=mock_backend),
    ):
        result = package_delete(package_name="team/data", registry="registry-bucket")

    assert result.success is True
    mock_backend.delete_package.assert_called_once_with(name="team/data", bucket="s3://registry-bucket")
