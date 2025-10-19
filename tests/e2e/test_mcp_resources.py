#!/usr/bin/env python3
"""
End-to-end tests for MCP Resources.

These tests validate the complete resource workflow from registration
to reading through the MCP server protocol.

Note: Currently focused on async-compatible resources (admin, tabulator)
as other resources have sync/async mismatch issues to be fixed separately.
"""

import pytest


@pytest.mark.e2e
@pytest.mark.slow
class TestMCPResourcesWorkflow:
    """E2E tests for complete MCP resources workflow."""

    @pytest.mark.anyio
    async def test_resource_registration_and_discovery(self):
        """
        Test complete resource workflow:
        1. Register all resources
        2. Discover available resources
        3. Read sample resources from working categories
        4. Validate response format

        This exercises:
        - Resource registration
        - Resource discovery via registry
        - Resource reading
        - Response format validation
        """
        from quilt_mcp.resources import get_registry, register_all_resources

        # 1. Register all resources
        register_all_resources()
        registry = get_registry()

        # 2. Discover available resources
        resources = registry.list_resources()
        assert len(resources) > 0, "No resources registered"

        print(f"\nFound {len(resources)} registered resources")

        # Verify we have resources from each category
        categories = set()
        for resource in resources:
            # Extract category from URI (e.g., "auth://status" -> "auth")
            uri = resource["uri"]
            if "://" in uri:
                category = uri.split("://")[0]
                categories.add(category)

        print(f"Found categories: {categories}")
        # Should have at least these working categories
        expected_categories = {"admin", "tabulator"}
        assert expected_categories.issubset(
            categories
        ), f"Missing categories: {expected_categories - categories}"

        # 3. Read sample resources from working categories
        sample_uris = {
            "admin://users": "admin users list",
            "admin://roles": "admin roles list",
            "tabulator://buckets": "tabulator buckets",
        }

        for uri, description in sample_uris.items():
            print(f"Testing {description} ({uri})...")
            result = await registry.read_resource(uri)

            assert result is not None, f"Failed to read {uri}"
            assert result.uri == uri, f"URI mismatch for {uri}"
            assert isinstance(result.content, dict), f"Content not dict for {uri}"

            # Validate that content has some data
            assert len(result.content) > 0, f"Empty content for {uri}"

    @pytest.mark.anyio
    async def test_parameterized_resources(self):
        """
        Test parameterized resource workflow:
        1. List available buckets
        2. Read tables for a specific bucket
        3. Validate parameter extraction

        This exercises:
        - Parameterized resource URIs
        - Parameter extraction
        - Bucket-specific data
        """
        from quilt_mcp.resources import get_registry, register_all_resources

        # Register all resources
        register_all_resources()
        registry = get_registry()

        # 1. List available buckets
        buckets_result = await registry.read_resource("tabulator://buckets")

        assert "items" in buckets_result.content
        bucket_list = buckets_result.content["items"]

        print(f"\nFound {len(bucket_list)} tabulator buckets")

        if len(bucket_list) == 0:
            pytest.skip("No buckets configured for parameterized resource test")

        # 2. Read tables for first bucket
        first_bucket = bucket_list[0]
        if isinstance(first_bucket, str):
            bucket_name = first_bucket
        else:
            bucket_name = first_bucket.get("name", first_bucket.get("bucket"))

        tables_uri = f"tabulator://buckets/{bucket_name}/tables"

        print(f"Reading tables for bucket: {bucket_name}")
        tables_result = await registry.read_resource(tables_uri)

        assert tables_result is not None
        assert tables_result.uri == tables_uri
        assert isinstance(tables_result.content, dict)
        assert "items" in tables_result.content

    @pytest.mark.anyio
    async def test_resource_error_handling(self):
        """
        Test resource error handling:
        1. Try to read non-existent resource
        2. Validate error responses

        This exercises:
        - Resource not found handling
        - Error response format
        """
        from quilt_mcp.resources import get_registry, register_all_resources

        register_all_resources()
        registry = get_registry()

        # 1. Try to read non-existent resource
        with pytest.raises((ValueError, KeyError, RuntimeError)):  # Should raise an error
            await registry.read_resource("nonexistent://resource")

    @pytest.mark.anyio
    async def test_admin_workflow(self):
        """
        Test complete admin resource workflow:
        1. List users
        2. List roles
        3. Get config

        This validates the complete admin discovery workflow.
        """
        from quilt_mcp.resources import get_registry, register_all_resources

        register_all_resources()
        registry = get_registry()

        # 1. List users
        users = await registry.read_resource("admin://users")
        assert isinstance(users.content, dict)
        assert "items" in users.content
        user_count = len(users.content["items"])
        print(f"\nFound {user_count} users")

        # 2. List roles
        roles = await registry.read_resource("admin://roles")
        assert isinstance(roles.content, dict)
        assert "items" in roles.content
        role_count = len(roles.content["items"])
        assert role_count > 0  # Should have at least some standard roles
        print(f"Found {role_count} roles")

        # 3. Get config
        config = await registry.read_resource("admin://config")
        assert isinstance(config.content, dict)
        assert len(config.content) > 0
        print(f"Config has {len(config.content)} sections")

    @pytest.mark.anyio
    async def test_tabulator_workflow(self):
        """
        Test tabulator resources workflow:
        1. List buckets
        2. List tables for a bucket (if available)
        3. Validate response formats

        This validates tabulator resource functionality.
        """
        from quilt_mcp.resources import get_registry, register_all_resources

        register_all_resources()
        registry = get_registry()

        # 1. List buckets
        buckets = await registry.read_resource("tabulator://buckets")
        assert isinstance(buckets.content, dict)
        assert "items" in buckets.content
        bucket_count = len(buckets.content["items"])
        print(f"\nFound {bucket_count} tabulator buckets")

        # 2. If buckets exist, try to read tables
        if bucket_count > 0:
            first_bucket = buckets.content["items"][0]
            if isinstance(first_bucket, str):
                bucket_name = first_bucket
            else:
                bucket_name = first_bucket.get("name", first_bucket.get("bucket"))

            tables_uri = f"tabulator://buckets/{bucket_name}/tables"
            tables = await registry.read_resource(tables_uri)

            assert isinstance(tables.content, dict)
            assert "items" in tables.content
            table_count = len(tables.content["items"])
            print(f"Found {table_count} tables in bucket '{bucket_name}'")
