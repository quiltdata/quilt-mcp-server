from types import SimpleNamespace
from unittest.mock import Mock, patch

from quilt_mcp.config import set_test_mode_config
from quilt_mcp.tools.packages import package_create


def _mock_create_result(top_hash: str = "test_top_hash") -> SimpleNamespace:
    return SimpleNamespace(
        success=True,
        top_hash=top_hash,
        file_count=2,
        catalog_url="https://example.invalid/catalog/pkg",
    )


@patch("quilt_mcp.tools.package_crud._authorize_package")
@patch("quilt_mcp.tools.package_crud.QuiltOpsFactory.create")
def test_package_create_copy_false(mock_factory_create, mock_authorize):
    set_test_mode_config(multiuser_mode=False)
    mock_authorize.return_value = (SimpleNamespace(auth_type="iam"), None)
    mock_backend = Mock()
    mock_backend.create_package_revision.return_value = _mock_create_result()
    mock_factory_create.return_value = mock_backend

    result = package_create(
        package_name="team/pkg",
        s3_uris=[
            "s3://bucket-a/dir/file1.csv",
            "s3://bucket-b/file2.json",
        ],
        registry="s3://target-bucket",
        copy=False,
        flatten=True,
    )

    assert result.success is True
    assert result.top_hash == "test_top_hash"
    mock_backend.create_package_revision.assert_called_once_with(
        package_name="team/pkg",
        s3_uris=["s3://bucket-a/dir/file1.csv", "s3://bucket-b/file2.json"],
        metadata={},
        registry="s3://target-bucket",
        message="Created via package_create tool",
        auto_organize=False,
        copy=False,
    )


@patch("quilt_mcp.tools.package_crud._authorize_package")
@patch("quilt_mcp.tools.package_crud.QuiltOpsFactory.create")
def test_package_create_copy_true(mock_factory_create, mock_authorize):
    set_test_mode_config(multiuser_mode=False)
    mock_authorize.return_value = (SimpleNamespace(auth_type="iam"), None)
    mock_backend = Mock()
    mock_backend.create_package_revision.return_value = _mock_create_result()
    mock_factory_create.return_value = mock_backend

    result = package_create(
        package_name="team/pkg",
        s3_uris=[
            "s3://target-bucket/path/file1.csv",
            "s3://other-bucket/file2.json",
        ],
        registry="s3://target-bucket",
        copy=True,
        flatten=True,
    )

    assert result.success is True
    assert result.top_hash == "test_top_hash"
    mock_backend.create_package_revision.assert_called_once_with(
        package_name="team/pkg",
        s3_uris=["s3://target-bucket/path/file1.csv", "s3://other-bucket/file2.json"],
        metadata={},
        registry="s3://target-bucket",
        message="Created via package_create tool",
        auto_organize=False,
        copy=True,
    )
