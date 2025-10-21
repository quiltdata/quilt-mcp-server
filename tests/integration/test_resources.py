#!/usr/bin/env python3
"""
Integration tests for MCP Resources.

These tests validate that resources can be read and return valid data
in real-world scenarios without mocking.
"""

import pytest


@pytest.mark.integration
class TestAuthResources:
    """Integration tests for auth resources."""

    @pytest.mark.anyio
    async def test_auth_status_resource(self):
        """Test that auth status resource returns valid data."""
        from quilt_mcp.resources.auth import AuthStatusResource

        resource = AuthStatusResource()
        result = await resource.read("auth://status")

        assert result.uri == "auth://status"
        assert isinstance(result.content, dict)
        assert "status" in result.content

    @pytest.mark.anyio
    async def test_catalog_info_resource(self):
        """Test that catalog info resource returns valid data."""
        from quilt_mcp.resources.auth import CatalogInfoResource

        resource = CatalogInfoResource()
        result = await resource.read("auth://catalog/info")

        assert result.uri == "auth://catalog/info"
        assert isinstance(result.content, dict)
        assert "status" in result.content

    @pytest.mark.anyio
    async def test_catalog_name_resource(self):
        """Test that catalog name resource returns valid data."""
        from quilt_mcp.resources.auth import CatalogNameResource

        resource = CatalogNameResource()
        result = await resource.read("auth://catalog/name")

        assert result.uri == "auth://catalog/name"
        assert isinstance(result.content, dict)
        assert "status" in result.content

    @pytest.mark.anyio
    async def test_filesystem_status_resource(self):
        """Test that filesystem status resource returns valid data."""
        from quilt_mcp.resources.auth import FilesystemStatusResource

        resource = FilesystemStatusResource()
        result = await resource.read("auth://filesystem/status")

        assert result.uri == "auth://filesystem/status"
        assert isinstance(result.content, dict)
        assert "home_writable" in result.content
        assert "temp_writable" in result.content


@pytest.mark.integration
class TestPermissionsResources:
    """Integration tests for permissions resources."""

    @pytest.mark.anyio
    async def test_permissions_discover_resource(self):
        """Test that permissions discover resource returns valid data."""
        from quilt_mcp.resources.permissions import PermissionsDiscoverResource

        resource = PermissionsDiscoverResource()
        result = await resource.read("permissions://discover")

        assert result.uri == "permissions://discover"
        assert isinstance(result.content, dict)

    @pytest.mark.anyio
    async def test_bucket_recommendations_resource(self):
        """Test that bucket recommendations resource returns valid data."""
        from quilt_mcp.resources.permissions import BucketRecommendationsResource

        resource = BucketRecommendationsResource()
        result = await resource.read("permissions://recommendations")

        assert result.uri == "permissions://recommendations"
        assert isinstance(result.content, dict)

    @pytest.mark.anyio
    async def test_bucket_access_resource(self):
        """Test that bucket access resource returns valid data for a known bucket."""
        from quilt_mcp.resources.permissions import BucketAccessResource

        resource = BucketAccessResource()
        # Use a common test bucket
        test_uri = "permissions://buckets/quilt-example/access"
        params = resource.extract_params(test_uri)
        result = await resource.read(test_uri, params)

        assert result.uri == test_uri
        assert isinstance(result.content, dict)


@pytest.mark.integration
class TestAthenaResources:
    """Integration tests for Athena resources."""

    @pytest.mark.anyio
    async def test_athena_databases_resource(self):
        """Test that Athena databases resource returns valid data."""
        from quilt_mcp.resources.athena import AthenaDatabasesResource

        resource = AthenaDatabasesResource()
        result = await resource.read("athena://databases")

        assert result.uri == "athena://databases"
        assert isinstance(result.content, dict)
        assert "items" in result.content
        assert isinstance(result.content["items"], list)

    @pytest.mark.anyio
    async def test_athena_workgroups_resource(self):
        """Test that Athena workgroups resource returns valid data."""
        from quilt_mcp.resources.athena import AthenaWorkgroupsResource

        resource = AthenaWorkgroupsResource()
        result = await resource.read("athena://workgroups")

        assert result.uri == "athena://workgroups"
        assert isinstance(result.content, dict)
        assert "items" in result.content
        assert isinstance(result.content["items"], list)

    @pytest.mark.anyio
    async def test_athena_query_history_resource(self):
        """Test that Athena query history resource returns valid data."""
        from quilt_mcp.resources.athena import AthenaQueryHistoryResource

        resource = AthenaQueryHistoryResource()
        result = await resource.read("athena://queries/history")

        assert result.uri == "athena://queries/history"
        # Content is now a Pydantic model, check it has the expected structure
        from quilt_mcp.models import AthenaQueryHistorySuccess
        assert hasattr(result.content, 'success') or isinstance(result.content, (dict, AthenaQueryHistorySuccess))


@pytest.mark.integration
class TestMetadataResources:
    """Integration tests for metadata resources."""

    @pytest.mark.anyio
    async def test_metadata_templates_resource(self):
        """Test that metadata templates resource returns valid data."""
        from quilt_mcp.resources.metadata import MetadataTemplatesResource

        resource = MetadataTemplatesResource()
        result = await resource.read("metadata://templates")

        assert result.uri == "metadata://templates"
        assert isinstance(result.content, dict)
        # Content has "available_templates" key, not "templates"
        assert "available_templates" in result.content or "templates" in result.content
        # Should have multiple templates
        assert len(result.content) > 0

    @pytest.mark.anyio
    async def test_metadata_examples_resource(self):
        """Test that metadata examples resource returns valid data."""
        from quilt_mcp.resources.metadata import MetadataExamplesResource

        resource = MetadataExamplesResource()
        result = await resource.read("metadata://examples")

        assert result.uri == "metadata://examples"
        assert isinstance(result.content, dict)
        # Should have content about metadata usage
        assert len(result.content) > 0

    @pytest.mark.anyio
    async def test_metadata_troubleshooting_resource(self):
        """Test that metadata troubleshooting resource returns valid data."""
        from quilt_mcp.resources.metadata import MetadataTroubleshootingResource

        resource = MetadataTroubleshootingResource()
        result = await resource.read("metadata://troubleshooting")

        assert result.uri == "metadata://troubleshooting"
        assert isinstance(result.content, dict)

    @pytest.mark.anyio
    async def test_metadata_template_resource(self):
        """Test that metadata template resource returns valid data."""
        from quilt_mcp.resources.metadata import MetadataTemplateResource

        resource = MetadataTemplateResource()
        test_uri = "metadata://templates/standard"
        params = resource.extract_params(test_uri)
        result = await resource.read(test_uri, params)

        assert result.uri == test_uri
        assert isinstance(result.content, dict)
        # Should have template data (may be nested or direct)
        assert len(result.content) > 0


@pytest.mark.integration
class TestWorkflowResources:
    """Integration tests for workflow resources."""

    @pytest.mark.anyio
    async def test_workflows_resource(self):
        """Test that workflows resource returns valid data."""
        from quilt_mcp.resources.workflow import WorkflowsResource

        resource = WorkflowsResource()
        result = await resource.read("workflow://workflows")

        assert result.uri == "workflow://workflows"
        assert isinstance(result.content, dict)
        assert "items" in result.content
        assert isinstance(result.content["items"], list)


@pytest.mark.integration
class TestTabulatorResources:
    """Integration tests for Tabulator resources."""

    @pytest.mark.anyio
    async def test_tabulator_buckets_resource(self):
        """Test that Tabulator buckets resource returns valid data."""
        from quilt_mcp.resources.tabulator import TabulatorBucketsResource

        resource = TabulatorBucketsResource()
        result = await resource.read("tabulator://buckets")

        assert result.uri == "tabulator://buckets"
        assert isinstance(result.content, dict)
        assert "items" in result.content
        assert isinstance(result.content["items"], list)

    @pytest.mark.admin
    @pytest.mark.anyio
    async def test_tabulator_tables_resource(self):
        """Test that Tabulator tables resource works for a bucket."""
        from quilt_mcp.resources.tabulator import TabulatorBucketsResource, TabulatorTablesResource

        # First get a bucket name
        buckets_resource = TabulatorBucketsResource()
        buckets_result = await buckets_resource.read("tabulator://buckets")

        if len(buckets_result.content["items"]) == 0:
            pytest.skip("No Tabulator buckets configured")

        # Get first bucket name - items may be strings or dicts
        first_bucket = buckets_result.content["items"][0]
        if isinstance(first_bucket, str):
            bucket_name = first_bucket
        else:
            bucket_name = first_bucket.get("name", first_bucket.get("bucket"))

        # Now test tables for that bucket
        tables_resource = TabulatorTablesResource()
        tables_uri = f"tabulator://buckets/{bucket_name}/tables"
        params = tables_resource.extract_params(tables_uri)
        tables_result = await tables_resource.read(tables_uri, params)

        assert tables_result.uri == tables_uri
        assert isinstance(tables_result.content, dict)
        assert "items" in tables_result.content
        assert isinstance(tables_result.content["items"], list)


@pytest.mark.integration
@pytest.mark.admin
class TestAdminResources:
    """Integration tests for admin resources."""

    @pytest.mark.anyio
    async def test_admin_users_resource(self):
        """Test that admin users resource returns valid data."""
        from quilt_mcp.resources.admin import AdminUsersResource

        resource = AdminUsersResource()
        result = await resource.read("admin://users")

        assert result.uri == "admin://users"
        assert isinstance(result.content, dict)
        assert "items" in result.content
        assert isinstance(result.content["items"], list)

    @pytest.mark.anyio
    async def test_admin_roles_resource(self):
        """Test that admin roles resource returns valid data."""
        from quilt_mcp.resources.admin import AdminRolesResource

        resource = AdminRolesResource()
        result = await resource.read("admin://roles")

        assert result.uri == "admin://roles"
        assert isinstance(result.content, dict)
        assert "items" in result.content
        assert isinstance(result.content["items"], list)
        assert len(result.content["items"]) > 0

    @pytest.mark.anyio
    async def test_admin_config_resource(self):
        """Test that admin config resource returns valid data."""
        from quilt_mcp.resources.admin import AdminConfigResource

        resource = AdminConfigResource()
        result = await resource.read("admin://config")

        assert result.uri == "admin://config"
        assert isinstance(result.content, dict)
        assert len(result.content) > 0
