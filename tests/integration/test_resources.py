#!/usr/bin/env python3
"""
Integration tests for MCP Resources.

These tests validate that resources can be read and return valid data
in real-world scenarios without mocking.

Note: Currently only testing async-compatible resources (admin, tabulator)
as other resources have sync/async mismatch issues that need to be
fixed separately.
"""

import pytest


@pytest.mark.integration
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
        # Should have items list (may be empty)
        assert "items" in result.content
        assert isinstance(result.content["items"], list)
        # Should have metadata
        assert "metadata" in result.content
        assert "total_count" in result.content["metadata"]
        assert result.content["metadata"]["total_count"] >= 0

    @pytest.mark.anyio
    async def test_admin_roles_resource(self):
        """Test that admin roles resource returns valid data."""
        from quilt_mcp.resources.admin import AdminRolesResource

        resource = AdminRolesResource()
        result = await resource.read("admin://roles")

        assert result.uri == "admin://roles"
        assert isinstance(result.content, dict)
        # Should have items list
        assert "items" in result.content
        assert isinstance(result.content["items"], list)
        # Should have at least some standard roles
        assert len(result.content["items"]) > 0

    @pytest.mark.anyio
    async def test_admin_config_resource(self):
        """Test that admin config resource returns valid data."""
        from quilt_mcp.resources.admin import AdminConfigResource

        resource = AdminConfigResource()
        result = await resource.read("admin://config")

        assert result.uri == "admin://config"
        assert isinstance(result.content, dict)
        # Should have config sections like sso, tabulator
        assert len(result.content) > 0


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
        # Should have items (may be empty if not configured)
        assert "items" in result.content
        assert isinstance(result.content["items"], list)
        # Check metadata
        assert "metadata" in result.content
        assert "total_count" in result.content["metadata"]
        assert result.content["metadata"]["total_count"] >= 0

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
        # Extract params from URI
        params = tables_resource.extract_params(tables_uri)
        tables_result = await tables_resource.read(tables_uri, params)

        assert tables_result.uri == tables_uri
        assert isinstance(tables_result.content, dict)
        assert "items" in tables_result.content
        assert isinstance(tables_result.content["items"], list)
