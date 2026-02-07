"""Tests for QuiltOps concrete workflow methods.

This module tests the concrete workflow methods in the QuiltOps base class
using mocked backend primitives. It focuses on:
- Validation logic
- Transformation logic
- Orchestration logic
- Error handling in workflows

Backend primitives are mocked to isolate testing to the base class logic.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from quilt_mcp.ops.quilt_ops import QuiltOps
from quilt_mcp.ops.exceptions import ValidationError, BackendError, NotFoundError
from quilt_mcp.domain import Package_Info, Content_Info, Package_Creation_Result, Auth_Status, Catalog_Config


# =========================================================================
# Test Fixtures
# =========================================================================


class MockQuiltOps(QuiltOps):
    """Concrete implementation of QuiltOps for testing.

    Implements all abstract methods as mocks so we can test
    the concrete workflow methods in isolation.
    """

    def __init__(self):
        # Create mocks for all backend primitives
        self._mock_create_empty_package = Mock(return_value=Mock())
        self._mock_add_file_to_package = Mock()
        self._mock_set_package_metadata = Mock()
        self._mock_push_package = Mock(return_value="test-hash-123")
        self._mock_get_package = Mock(return_value=Mock())
        self._mock_get_package_entries = Mock(return_value={})
        self._mock_get_package_metadata = Mock(return_value={})
        self._mock_search_packages = Mock(return_value=[])
        self._mock_diff_packages = Mock(return_value={"added": [], "deleted": [], "modified": []})
        self._mock_browse_package_content = Mock(return_value=[])
        self._mock_get_file_url = Mock(return_value="https://example.com/file.txt")
        self._mock_get_session_info = Mock(return_value={"is_authenticated": True, "catalog_url": None})
        self._mock_get_catalog_config = Mock(
            return_value=Catalog_Config(
                region="us-east-1",
                api_gateway_endpoint="https://test-api.execute-api.us-east-1.amazonaws.com",
                registry_url="s3://test-registry",
                analytics_bucket="test-analytics-bucket",
                stack_prefix="test-stack",
                tabulator_data_catalog="AwsDataCatalog",
            )
        )
        self._mock_list_buckets = Mock(return_value=[])
        self._mock_get_boto3_session = Mock(return_value=Mock())
        self._mock_backend_get_auth_status = Mock(
            return_value=Auth_Status(
                is_authenticated=True,
                logged_in_url="https://test-catalog.quiltdata.com",
                catalog_name="test-catalog",
                registry_url=None,  # Will be enriched by Template Method
            )
        )

    # Implement backend primitive abstract methods by delegating to mocks
    def _backend_create_empty_package(self):
        return self._mock_create_empty_package()

    def _backend_add_file_to_package(self, package, logical_key, s3_uri):
        return self._mock_add_file_to_package(package, logical_key, s3_uri)

    def _backend_set_package_metadata(self, package, metadata):
        return self._mock_set_package_metadata(package, metadata)

    def _backend_push_package(self, package, package_name, registry, message, copy):
        return self._mock_push_package(package, package_name, registry, message, copy)

    def _backend_get_package(self, package_name, registry, top_hash=None):
        return self._mock_get_package(package_name, registry, top_hash)

    def _backend_get_package_entries(self, package):
        return self._mock_get_package_entries(package)

    def _backend_get_package_metadata(self, package):
        return self._mock_get_package_metadata(package)

    def _backend_search_packages(self, query, registry):
        return self._mock_search_packages(query, registry)

    def _backend_diff_packages(self, pkg1, pkg2):
        return self._mock_diff_packages(pkg1, pkg2)

    def _backend_browse_package_content(self, package, path):
        return self._mock_browse_package_content(package, path)

    def _backend_get_file_url(self, package_name, registry, path, top_hash=None):
        return self._mock_get_file_url(package_name, registry, path, top_hash)

    def _backend_get_session_info(self):
        return self._mock_get_session_info()

    def _backend_get_catalog_config(self, catalog_url):
        return self._mock_get_catalog_config(catalog_url)

    def _backend_list_buckets(self):
        return self._mock_list_buckets()

    def _backend_get_boto3_session(self):
        return self._mock_get_boto3_session()

    def _backend_get_auth_status(self):
        return self._mock_backend_get_auth_status()

    # Transformation abstract methods
    def _transform_search_result_to_package_info(self, result, registry):
        from quilt_mcp.domain import Package_Info

        bucket = result.get("bucket", registry.replace("s3://", "").split("/")[0])
        return Package_Info(
            name=result.get("name", ""),
            description=result.get("comment"),
            tags=[],
            modified_date=result.get("modified", ""),
            registry=registry,
            bucket=bucket,
            top_hash=result.get("top_hash", ""),
        )

    def _transform_content_entry_to_content_info(self, entry):
        from quilt_mcp.domain import Content_Info

        return Content_Info(
            path=entry.get("path", ""),
            size=entry.get("size"),
            type=entry.get("type", "file"),
            modified_date=entry.get("modified_date"),
            download_url=entry.get("download_url"),
        )

    # Properties required by base class
    @property
    def admin(self):
        return Mock()

    # High-level abstract methods (not tested here - just stub them)
    # Note: get_auth_status() is now a concrete Template Method in QuiltOps base class
    # We implement the _backend_get_auth_status() primitive instead

    def get_package_info(self, package_name, registry):
        return Mock()

    def list_buckets(self):
        return []

    def get_content_url(self, package_name, registry, path):
        return "http://example.com"

    def get_catalog_config(self, catalog_url):
        # Return the mocked catalog config
        return self._mock_get_catalog_config(catalog_url)

    def configure_catalog(self, catalog_url):
        pass

    def get_registry_url(self):
        return None

    def get_graphql_endpoint(self):
        return "http://graphql"

    def get_graphql_auth_headers(self):
        return {}

    def execute_graphql_query(self, query, variables=None):
        return {}

    def list_tabulator_tables(self, bucket):
        return []

    def get_tabulator_table(self, bucket, table_name):
        return {}

    def create_tabulator_table(self, bucket, table_name, config=None):
        return {}

    def update_tabulator_table(self, bucket, table_name, config):
        return {}

    def rename_tabulator_table(self, bucket, old_name, new_name):
        return {}

    def delete_tabulator_table(self, bucket, table_name):
        return {}

    def get_open_query_status(self):
        return {}

    def set_open_query(self, enabled):
        return {}

    def get_boto3_client(self, service_name, region_name=None):
        return Mock()

    def diff_packages(self, package1_name, package1_registry, package2_name, package2_registry):
        return {"added": [], "deleted": [], "modified": []}


@pytest.fixture
def ops():
    """Fixture providing MockQuiltOps instance."""
    return MockQuiltOps()


# =========================================================================
# Validation Method Tests
# =========================================================================


class TestValidationMethods:
    """Test validation methods in QuiltOps base class."""

    def test_validate_package_name_success(self, ops):
        """Test valid package name passes validation."""
        # Should not raise
        ops._validate_package_name("user/package")
        ops._validate_package_name("myuser/mypackage")
        ops._validate_package_name("a/b")

    def test_validate_package_name_empty_string(self, ops):
        """Test empty package name raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ops._validate_package_name("")
        assert "non-empty string" in str(exc_info.value)

    def test_validate_package_name_none(self, ops):
        """Test None package name raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ops._validate_package_name(None)
        assert "non-empty string" in str(exc_info.value)

    def test_validate_package_name_no_slash(self, ops):
        """Test package name without slash raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ops._validate_package_name("invalid-package")
        assert "user/package" in str(exc_info.value)

    def test_validate_package_name_multiple_slashes(self, ops):
        """Test package name with multiple slashes raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ops._validate_package_name("user/package/extra")
        assert "user/package" in str(exc_info.value)

    def test_validate_s3_uri_success(self, ops):
        """Test valid S3 URI passes validation."""
        ops._validate_s3_uri("s3://bucket/key")
        ops._validate_s3_uri("s3://my-bucket/path/to/file.txt")

    def test_validate_s3_uri_invalid_scheme(self, ops):
        """Test S3 URI without s3:// raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ops._validate_s3_uri("http://bucket/key")
        assert "s3://" in str(exc_info.value)

    def test_validate_s3_uri_with_index(self, ops):
        """Test S3 URI validation includes index in error message."""
        with pytest.raises(ValidationError) as exc_info:
            ops._validate_s3_uri("invalid-uri", index=3)
        assert "index 3" in str(exc_info.value)

    def test_validate_s3_uri_missing_key(self, ops):
        """Test S3 URI without key raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ops._validate_s3_uri("s3://bucket")
        assert "bucket and key" in str(exc_info.value)

    def test_validate_s3_uri_empty_key(self, ops):
        """Test S3 URI with empty key raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ops._validate_s3_uri("s3://bucket/")
        assert "bucket and key" in str(exc_info.value)

    def test_validate_s3_uris_success(self, ops):
        """Test valid S3 URI list passes validation."""
        ops._validate_s3_uris(["s3://bucket/key1", "s3://bucket/key2"])

    def test_validate_s3_uris_empty_list(self, ops):
        """Test empty URI list raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ops._validate_s3_uris([])
        assert "non-empty list" in str(exc_info.value)

    def test_validate_s3_uris_none(self, ops):
        """Test None URI list raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ops._validate_s3_uris(None)
        assert "non-empty list" in str(exc_info.value)

    def test_validate_s3_uris_validates_each_uri(self, ops):
        """Test that each URI in list is validated."""
        with pytest.raises(ValidationError) as exc_info:
            ops._validate_s3_uris(["s3://bucket/key1", "invalid-uri", "s3://bucket/key3"])
        assert "index 1" in str(exc_info.value)

    def test_validate_registry_success(self, ops):
        """Test valid registry passes validation."""
        ops._validate_registry("s3://my-registry")
        ops._validate_registry("s3://registry/prefix")

    def test_validate_registry_invalid_scheme(self, ops):
        """Test registry without s3:// raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ops._validate_registry("my-registry")
        assert "s3://" in str(exc_info.value)

    def test_validate_registry_empty(self, ops):
        """Test empty registry raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ops._validate_registry("")
        assert "non-empty string" in str(exc_info.value)

    def test_validate_package_creation_inputs_success(self, ops):
        """Test valid package creation inputs pass validation."""
        ops._validate_package_creation_inputs("user/package", ["s3://bucket/file.txt"])

    def test_validate_package_creation_inputs_invalid_name(self, ops):
        """Test invalid package name fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            ops._validate_package_creation_inputs("invalid", ["s3://bucket/file.txt"])
        assert "user/package" in str(exc_info.value)

    def test_validate_package_creation_inputs_invalid_uris(self, ops):
        """Test invalid URIs fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            ops._validate_package_creation_inputs("user/package", ["not-s3"])
        assert "s3://" in str(exc_info.value)

    def test_validate_package_update_inputs_success(self, ops):
        """Test valid package update inputs pass validation."""
        ops._validate_package_update_inputs("user/package", ["s3://bucket/file.txt"], "s3://registry")

    def test_validate_package_update_inputs_invalid_name(self, ops):
        """Test invalid package name fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            ops._validate_package_update_inputs("invalid", ["s3://bucket/file.txt"], "s3://registry")
        assert "user/package" in str(exc_info.value)

    def test_validate_package_update_inputs_invalid_registry(self, ops):
        """Test invalid registry fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            ops._validate_package_update_inputs("user/package", ["s3://bucket/file.txt"], "not-s3")
        assert "s3://" in str(exc_info.value)

    def test_validate_package_update_inputs_no_valid_uris(self, ops):
        """Test update validation requires at least one potentially valid URI."""
        with pytest.raises(ValidationError) as exc_info:
            ops._validate_package_update_inputs("user/package", ["not-s3", "http://invalid"], "s3://registry")
        assert "No potentially valid S3 URIs" in str(exc_info.value)

    def test_validate_package_update_inputs_allows_some_invalid(self, ops):
        """Test update validation allows some invalid URIs if at least one is valid."""
        # Should not raise - update is permissive and will skip invalid URIs
        ops._validate_package_update_inputs(
            "user/package", ["not-s3", "s3://bucket/valid.txt", "http://invalid"], "s3://registry"
        )


# =========================================================================
# Transformation Method Tests
# =========================================================================


class TestTransformationMethods:
    """Test transformation methods in QuiltOps base class."""

    def test_extract_logical_key_auto_organize_true(self, ops):
        """Test logical key extraction preserves folder structure."""
        assert ops._extract_logical_key("s3://bucket/path/to/file.txt", auto_organize=True) == "path/to/file.txt"
        assert ops._extract_logical_key("s3://bucket/file.txt", auto_organize=True) == "file.txt"
        assert (
            ops._extract_logical_key("s3://my-bucket/data/nested/file.csv", auto_organize=True)
            == "data/nested/file.csv"
        )

    def test_extract_logical_key_auto_organize_false(self, ops):
        """Test logical key extraction flattens to filename."""
        assert ops._extract_logical_key("s3://bucket/path/to/file.txt", auto_organize=False) == "file.txt"
        assert ops._extract_logical_key("s3://bucket/file.txt", auto_organize=False) == "file.txt"
        assert ops._extract_logical_key("s3://my-bucket/data/nested/file.csv", auto_organize=False) == "file.csv"

    def test_extract_bucket_from_registry_s3_uri(self, ops):
        """Test bucket extraction from S3 URI registry."""
        assert ops._extract_bucket_from_registry("s3://my-bucket") == "my-bucket"
        assert ops._extract_bucket_from_registry("s3://my-bucket/prefix") == "my-bucket"
        assert ops._extract_bucket_from_registry("s3://registry-123/path/to/prefix") == "registry-123"

    def test_extract_bucket_from_registry_http_url(self, ops):
        """Test bucket extraction from HTTP URL."""
        assert ops._extract_bucket_from_registry("https://catalog.example.com") == "catalog.example.com"
        assert ops._extract_bucket_from_registry("http://example.org/path") == "example.org"

    def test_extract_bucket_from_registry_plain_string(self, ops):
        """Test bucket extraction from plain string."""
        assert ops._extract_bucket_from_registry("my-bucket") == "my-bucket"
        assert ops._extract_bucket_from_registry("bucket-name/prefix") == "bucket-name"

    def test_extract_bucket_from_registry_empty(self, ops):
        """Test bucket extraction from empty string."""
        assert ops._extract_bucket_from_registry("") == ""

    def test_build_catalog_url_success(self, ops):
        """Test catalog URL building."""
        url = ops._build_catalog_url("user/package", "s3://my-bucket")
        assert url is not None
        assert "my-bucket" in url
        assert "user/package" in url

    def test_build_catalog_url_with_prefix(self, ops):
        """Test catalog URL with registry prefix."""
        url = ops._build_catalog_url("user/package", "s3://my-bucket/prefix")
        assert url is not None
        assert "my-bucket" in url
        assert "user/package" in url

    def test_is_valid_s3_uri_for_update_valid(self, ops):
        """Test valid URIs pass update validation check."""
        assert ops._is_valid_s3_uri_for_update("s3://bucket/key") is True
        assert ops._is_valid_s3_uri_for_update("s3://bucket/path/to/file.txt") is True

    def test_is_valid_s3_uri_for_update_invalid_scheme(self, ops):
        """Test invalid scheme fails update validation check."""
        assert ops._is_valid_s3_uri_for_update("http://bucket/key") is False
        assert ops._is_valid_s3_uri_for_update("not-s3-uri") is False

    def test_is_valid_s3_uri_for_update_no_key(self, ops):
        """Test URI without key fails update validation check."""
        assert ops._is_valid_s3_uri_for_update("s3://bucket") is False
        assert ops._is_valid_s3_uri_for_update("s3://bucket/") is False

    def test_is_valid_s3_uri_for_update_directory(self, ops):
        """Test directory URI fails update validation check."""
        assert ops._is_valid_s3_uri_for_update("s3://bucket/path/") is False


# =========================================================================
# create_package_revision Workflow Tests
# =========================================================================


class TestCreatePackageRevision:
    """Test create_package_revision workflow orchestration."""

    def test_successful_creation(self, ops):
        """Test successful package creation workflow."""
        result = ops.create_package_revision(
            package_name="user/mypackage",
            s3_uris=["s3://bucket/file1.txt", "s3://bucket/file2.txt"],
            registry="s3://test-registry",
            metadata={"description": "Test package"},
            message="Initial commit",
            auto_organize=True,
            copy="none",
        )

        # Verify result structure
        assert isinstance(result, Package_Creation_Result)
        assert result.package_name == "user/mypackage"
        assert result.top_hash == "test-hash-123"
        assert result.registry == "s3://test-registry"
        assert result.file_count == 2
        assert result.success is True
        assert result.catalog_url is not None

        # Verify backend primitives were called in correct order
        ops._mock_create_empty_package.assert_called_once()
        assert ops._mock_add_file_to_package.call_count == 2
        ops._mock_set_package_metadata.assert_called_once_with(
            ops._mock_create_empty_package.return_value, {"description": "Test package"}
        )
        ops._mock_push_package.assert_called_once()

    def test_validation_error_prevents_backend_calls(self, ops):
        """Test validation errors prevent backend primitive calls."""
        with pytest.raises(ValidationError):
            ops.create_package_revision(
                package_name="invalid-name",  # No slash
                s3_uris=["s3://bucket/file.txt"],
                registry="s3://test-registry",
            )

        # Verify no backend primitives were called
        ops._mock_create_empty_package.assert_not_called()
        ops._mock_add_file_to_package.assert_not_called()
        ops._mock_push_package.assert_not_called()

    def test_invalid_s3_uris_validation(self, ops):
        """Test invalid S3 URIs raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ops.create_package_revision(
                package_name="user/package", s3_uris=["not-s3-uri"], registry="s3://test-registry"
            )
        assert "s3://" in str(exc_info.value)

    def test_auto_organize_true_preserves_structure(self, ops):
        """Test auto_organize=True preserves folder structure."""
        ops.create_package_revision(
            package_name="user/package",
            s3_uris=["s3://bucket/path/to/file.txt"],
            registry="s3://test-registry",
            auto_organize=True,
        )

        # Check logical key passed to add_file primitive
        call_args = ops._mock_add_file_to_package.call_args[0]
        logical_key = call_args[1]
        assert logical_key == "path/to/file.txt"

    def test_auto_organize_false_flattens_keys(self, ops):
        """Test auto_organize=False flattens to filenames."""
        ops.create_package_revision(
            package_name="user/package",
            s3_uris=["s3://bucket/path/to/file.txt"],
            registry="s3://test-registry",
            auto_organize=False,
        )

        # Check logical key passed to add_file primitive
        call_args = ops._mock_add_file_to_package.call_args[0]
        logical_key = call_args[1]
        assert logical_key == "file.txt"

    def test_copy_behavior_passed_to_push(self, ops):
        """Test copy parameter is passed to push primitive."""
        ops.create_package_revision(
            package_name="user/package", s3_uris=["s3://bucket/file.txt"], registry="s3://test-registry", copy=True
        )

        # Check copy parameter passed to push
        call_args = ops._mock_push_package.call_args[0]
        copy_param = call_args[4]
        assert copy_param is True

    def test_copy_none_passed_as_false(self, ops):
        """Test copy=False is passed as False to push primitive."""
        ops.create_package_revision(
            package_name="user/package", s3_uris=["s3://bucket/file.txt"], registry="s3://test-registry", copy=False
        )

        # Check copy parameter passed to push
        call_args = ops._mock_push_package.call_args[0]
        copy_param = call_args[4]
        assert copy_param is False

    def test_metadata_set_when_provided(self, ops):
        """Test metadata is set when provided."""
        metadata = {"key": "value", "description": "test"}
        ops.create_package_revision(
            package_name="user/package",
            s3_uris=["s3://bucket/file.txt"],
            registry="s3://test-registry",
            metadata=metadata,
        )

        ops._mock_set_package_metadata.assert_called_once()
        call_args = ops._mock_set_package_metadata.call_args[0]
        assert call_args[1] == metadata

    def test_no_metadata_when_none(self, ops):
        """Test metadata is not set when None."""
        ops.create_package_revision(
            package_name="user/package", s3_uris=["s3://bucket/file.txt"], registry="s3://test-registry", metadata=None
        )

        # Metadata primitive should NOT be called when metadata is None (see line 1152: if metadata:)
        ops._mock_set_package_metadata.assert_not_called()

    def test_backend_error_wrapped_in_backend_error(self, ops):
        """Test backend primitive exceptions are wrapped in BackendError."""
        ops._mock_push_package.side_effect = Exception("Push failed")

        with pytest.raises(BackendError) as exc_info:
            ops.create_package_revision(
                package_name="user/package", s3_uris=["s3://bucket/file.txt"], registry="s3://test-registry"
            )

        assert "Package creation failed:" in str(exc_info.value)
        assert "Push failed" in str(exc_info.value)

    def test_failed_push_returns_failed_result(self, ops):
        """Test that None/empty top_hash indicates failure."""
        ops._mock_push_package.return_value = None

        result = ops.create_package_revision(
            package_name="user/package", s3_uris=["s3://bucket/file.txt"], registry="s3://test-registry"
        )

        assert result.success is False
        assert result.top_hash is None or result.top_hash == ""


# =========================================================================
# update_package_revision Workflow Tests
# =========================================================================


class TestUpdatePackageRevision:
    """Test update_package_revision workflow orchestration."""

    def test_successful_update(self, ops):
        """Test successful package update workflow."""
        # Mock existing package with entries
        ops._mock_get_package_entries.return_value = {
            "existing.txt": {"physicalKey": "s3://bucket/existing.txt", "size": 100, "hash": "abc123"}
        }
        ops._mock_get_package_metadata.return_value = {"description": "Original"}

        result = ops.update_package_revision(
            package_name="user/mypackage",
            s3_uris=["s3://bucket/new.txt"],
            registry="s3://test-registry",
            metadata={"description": "Updated"},
            message="Update commit",
            auto_organize=True,
            copy="none",
        )

        # Verify result
        assert isinstance(result, Package_Creation_Result)
        assert result.success is True
        assert result.file_count == 1  # Only new files counted

        # Verify workflow steps (get_package gets called with 3 args: name, registry, top_hash=None)
        ops._mock_get_package.assert_called_once()
        assert ops._mock_get_package.call_args[0][0] == "user/mypackage"
        assert ops._mock_get_package.call_args[0][1] == "s3://test-registry"
        ops._mock_get_package_entries.assert_called_once()
        ops._mock_get_package_metadata.assert_called_once()
        ops._mock_create_empty_package.assert_called_once()

        # Should add existing file + new file
        assert ops._mock_add_file_to_package.call_count == 2

        # Metadata should be merged
        ops._mock_set_package_metadata.assert_called_once()
        merged_meta = ops._mock_set_package_metadata.call_args[0][1]
        assert merged_meta["description"] == "Updated"  # New overwrites old

        ops._mock_push_package.assert_called_once()

    def test_preserves_existing_files(self, ops):
        """Test update preserves existing package files."""
        ops._mock_get_package_entries.return_value = {
            "file1.txt": {"physicalKey": "s3://bucket/file1.txt"},
            "file2.txt": {"physicalKey": "s3://bucket/file2.txt"},
        }
        ops._mock_get_package_metadata.return_value = {}

        ops.update_package_revision(
            package_name="user/package", s3_uris=["s3://bucket/new.txt"], registry="s3://test-registry"
        )

        # Should add 2 existing + 1 new = 3 total
        assert ops._mock_add_file_to_package.call_count == 3

    def test_metadata_merging(self, ops):
        """Test metadata from update merges with existing metadata."""
        ops._mock_get_package_entries.return_value = {}
        ops._mock_get_package_metadata.return_value = {"original": "value", "shared": "old_value"}

        ops.update_package_revision(
            package_name="user/package",
            s3_uris=["s3://bucket/file.txt"],
            registry="s3://test-registry",
            metadata={"new": "value", "shared": "new_value"},
        )

        # Check merged metadata
        merged = ops._mock_set_package_metadata.call_args[0][1]
        assert merged["original"] == "value"  # Preserved
        assert merged["new"] == "value"  # Added
        assert merged["shared"] == "new_value"  # Updated

    def test_skips_invalid_uris(self, ops):
        """Test update skips invalid URIs rather than failing."""
        ops._mock_get_package_entries.return_value = {}
        ops._mock_get_package_metadata.return_value = {}

        result = ops.update_package_revision(
            package_name="user/package",
            s3_uris=[
                "s3://bucket/valid1.txt",
                "not-s3-uri",  # Should be skipped
                "s3://bucket",  # No key, should be skipped
                "s3://bucket/valid2.txt",
            ],
            registry="s3://test-registry",
        )

        # Only 2 valid files should be added
        assert result.file_count == 2

    def test_validation_errors_prevent_backend_calls(self, ops):
        """Test validation errors prevent backend primitive calls."""
        with pytest.raises(ValidationError):
            ops.update_package_revision(
                package_name="invalid-name",  # No slash
                s3_uris=["s3://bucket/file.txt"],
                registry="s3://test-registry",
            )

        # No backend primitives should be called
        ops._mock_get_package.assert_not_called()
        ops._mock_create_empty_package.assert_not_called()

    def test_backend_error_wrapped(self, ops):
        """Test backend primitive exceptions are wrapped in BackendError."""
        ops._mock_get_package.side_effect = Exception("Package not found")

        with pytest.raises(BackendError) as exc_info:
            ops.update_package_revision(
                package_name="user/package", s3_uris=["s3://bucket/file.txt"], registry="s3://test-registry"
            )

        assert "Package update failed:" in str(exc_info.value)
        assert "Package not found" in str(exc_info.value)


# =========================================================================
# search_packages Workflow Tests
# =========================================================================


class TestSearchPackages:
    """Test search_packages workflow orchestration."""

    def test_successful_search(self, ops):
        """Test successful package search."""
        # Mock backend search result
        ops._mock_search_packages.return_value = [
            {
                "name": "user/package1",
                "bucket": "test-registry",
                "top_hash": "hash123",
                "modified": "2024-01-01T00:00:00Z",
                "comment": "Test package",
                "meta": {"key": "value"},
            }
        ]

        results = ops.search_packages("test query", "s3://test-registry")

        # Verify backend primitive was called
        ops._mock_search_packages.assert_called_once_with("test query", "s3://test-registry")

        # Verify results transformed to domain objects
        assert len(results) == 1
        assert isinstance(results[0], Package_Info)
        assert results[0].name == "user/package1"

    def test_validation_invalid_registry(self, ops):
        """Test invalid registry raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ops.search_packages("test query", "not-s3-uri")

        assert "s3://" in str(exc_info.value)
        ops._mock_search_packages.assert_not_called()

    def test_empty_query_allowed(self, ops):
        """Test empty query is allowed (returns all packages)."""
        ops._mock_search_packages.return_value = []

        results = ops.search_packages("", "s3://test-registry")

        ops._mock_search_packages.assert_called_once_with("", "s3://test-registry")
        assert results == []

    def test_backend_error_wrapped(self, ops):
        """Test backend exceptions are wrapped in BackendError."""
        ops._mock_search_packages.side_effect = Exception("Search failed")

        with pytest.raises(BackendError) as exc_info:
            ops.search_packages("test", "s3://test-registry")

        assert "Package search failed:" in str(exc_info.value)


# =========================================================================
# browse_content Workflow Tests
# =========================================================================


class TestBrowseContent:
    """Test browse_content workflow orchestration."""

    def test_successful_browse(self, ops):
        """Test successful content browsing."""
        # Mock backend browse result
        ops._mock_browse_package_content.return_value = [
            {"path": "file1.txt", "type": "file"},
            {"path": "folder/", "type": "directory"},
        ]

        results = ops.browse_content("user/package", "s3://test-registry", "")

        # Verify backend primitive called
        ops._mock_browse_package_content.assert_called_once()

        # Verify results transformed to domain objects
        assert len(results) == 2
        assert all(isinstance(r, Content_Info) for r in results)

    def test_validation_invalid_package_name(self, ops):
        """Test invalid package name raises ValidationError."""
        with pytest.raises(ValidationError):
            ops.browse_content("invalid", "s3://test-registry", "")

        ops._mock_get_package.assert_not_called()

    def test_validation_invalid_registry(self, ops):
        """Test invalid registry raises ValidationError."""
        with pytest.raises(ValidationError):
            ops.browse_content("user/package", "not-s3", "")

        ops._mock_get_package.assert_not_called()

    def test_path_parameter_passed_to_backend(self, ops):
        """Test path parameter is passed to backend primitive."""
        ops._mock_browse_package_content.return_value = []

        ops.browse_content("user/package", "s3://test-registry", "subfolder/")

        # Check path was passed to browse primitive
        call_args = ops._mock_browse_package_content.call_args[0]
        path = call_args[1]
        assert path == "subfolder/"

    def test_backend_error_wrapped(self, ops):
        """Test backend exceptions are wrapped in BackendError."""
        ops._mock_get_package.side_effect = Exception("Package not found")

        with pytest.raises(BackendError) as exc_info:
            ops.browse_content("user/package", "s3://test-registry", "")

        assert "Browse content failed:" in str(exc_info.value)


# =========================================================================
# Error Handling Tests
# =========================================================================


class TestErrorHandling:
    """Test error handling across workflows."""

    def test_validation_error_not_wrapped(self, ops):
        """Test ValidationError is not wrapped, just re-raised."""
        with pytest.raises(ValidationError) as exc_info:
            ops.create_package_revision(
                package_name="invalid", s3_uris=["s3://bucket/file.txt"], registry="s3://test-registry"
            )

        # Should be original ValidationError, not BackendError
        assert isinstance(exc_info.value, ValidationError)
        assert "user/package" in str(exc_info.value)

    def test_not_found_error_not_wrapped(self, ops):
        """Test NotFoundError is re-raised without wrapping."""
        ops._mock_get_package.side_effect = NotFoundError("Package not found", {})

        with pytest.raises(NotFoundError):
            ops.update_package_revision(
                package_name="user/package", s3_uris=["s3://bucket/file.txt"], registry="s3://test-registry"
            )

    def test_generic_exception_wrapped_in_backend_error(self, ops):
        """Test generic exceptions are wrapped in BackendError."""
        ops._mock_push_package.side_effect = RuntimeError("Unexpected error")

        with pytest.raises(BackendError) as exc_info:
            ops.create_package_revision(
                package_name="user/package", s3_uris=["s3://bucket/file.txt"], registry="s3://test-registry"
            )

        assert "Package creation failed:" in str(exc_info.value)
        assert "Unexpected error" in str(exc_info.value)

    def test_error_context_included(self, ops):
        """Test error context includes relevant information."""
        ops._mock_push_package.side_effect = Exception("Push failed")

        with pytest.raises(BackendError) as exc_info:
            ops.create_package_revision(
                package_name="user/mypackage",
                s3_uris=["s3://bucket/file1.txt", "s3://bucket/file2.txt"],
                registry="s3://test-registry",
            )

        error = exc_info.value
        # Backend error should include context about the operation
        assert error.context.get("package_name") == "user/mypackage"
        assert error.context.get("registry") == "s3://test-registry"
