from types import SimpleNamespace
from unittest.mock import Mock, patch

from quilt_mcp.tools.packages import package_delete


def test_package_delete_uses_quiltops_backend_success():
    mock_backend = Mock()
    mock_backend.delete_package.return_value = True

    with (
        patch("quilt_mcp.tools.package_crud._authorize_package", return_value=(SimpleNamespace(auth_type="jwt"), None)),
        patch("quilt_mcp.tools.package_crud.QuiltOpsFactory.create", return_value=mock_backend),
    ):
        result = package_delete(package_name="team/data", registry="test-bucket")

    assert result.success is True
    mock_backend.delete_package.assert_called_once_with(name="team/data", bucket="s3://test-bucket")


def test_package_delete_returns_error_when_backend_reports_failure():
    mock_backend = Mock()
    mock_backend.delete_package.return_value = False

    with (
        patch("quilt_mcp.tools.package_crud._authorize_package", return_value=(SimpleNamespace(auth_type="jwt"), None)),
        patch("quilt_mcp.tools.package_crud.QuiltOpsFactory.create", return_value=mock_backend),
    ):
        result = package_delete(package_name="team/data", registry="s3://test-bucket")

    assert result.success is False
    assert "Failed to delete package" in result.error


def test_package_delete_returns_error_when_backend_raises():
    mock_backend = Mock()
    mock_backend.delete_package.side_effect = RuntimeError("boom")

    with (
        patch("quilt_mcp.tools.package_crud._authorize_package", return_value=(SimpleNamespace(auth_type="jwt"), None)),
        patch("quilt_mcp.tools.package_crud.QuiltOpsFactory.create", return_value=mock_backend),
    ):
        result = package_delete(package_name="team/data", registry="s3://test-bucket")

    assert result.success is False
    assert "boom" in result.error
