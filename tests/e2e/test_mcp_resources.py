#!/usr/bin/env python3
"""
End-to-end tests for MCP Resources.

These tests validate the complete resource workflow from registration
to reading through the MCP server protocol.
"""

import pytest


@pytest.mark.e2e
@pytest.mark.slow
class TestMCPResourcesWorkflow:
    """E2E tests for complete MCP resources workflow."""

    @pytest.mark.admin
    @pytest.mark.anyio
    async def test_resource_registration_and_discovery(self):
        """
        Test complete resource workflow:
        1. Register all resources
        2. Discover available resources
        3. Read sample resources from all categories
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
        # Should have at least these categories
        expected_categories = {"auth", "permissions", "athena", "metadata", "workflow", "admin", "tabulator"}
        assert expected_categories.issubset(categories), f"Missing categories: {expected_categories - categories}"

        # 3. Read sample resources from each category (in parallel for performance)
        sample_uris = {
            "auth://status": "auth status",
            "metadata://templates": "metadata templates",
            "workflow://workflows": "workflows list",
            "tabulator://buckets": "tabulator buckets",
            "admin://users": "admin users",
            "permissions://discover": "permissions discover",
            "athena://databases": "athena databases",
        }

        # Read all resources in parallel
        import asyncio

        async def read_and_validate(uri: str, description: str):
            print(f"Testing {description} ({uri})...")
            try:
                result = await registry.read_resource(uri)

                assert result is not None, f"Failed to read {uri}"
                assert result.uri == uri, f"URI mismatch for {uri}"
                assert isinstance(result.content, dict), f"Content not dict for {uri}"

                # Validate that content has some data
                assert len(result.content) > 0, f"Empty content for {uri}"
                return result
            except Exception as e:
                # Some resources may fail due to auth or permissions
                # This is expected in e2e tests without full setup
                print(f"  Skipped {uri}: {e}")
                return None

        # Execute all reads in parallel (return_exceptions=True to not fail fast)
        results = await asyncio.gather(
            *[read_and_validate(uri, description) for uri, description in sample_uris.items()], return_exceptions=True
        )

        # Verify we successfully read at least some resources from each major category
        successful_reads = [r for r in results if r is not None and not isinstance(r, Exception)]
        assert len(successful_reads) >= 4, f"Expected at least 4 successful reads, got {len(successful_reads)}"

    @pytest.mark.anyio
    async def test_parameterized_resources(self):
        """
        Test parameterized resource workflow:
        1. List available templates
        2. Read a specific template
        3. Validate parameter extraction

        This exercises:
        - Parameterized resource URIs
        - Parameter extraction
        - Template-specific data
        """
        from quilt_mcp.resources import get_registry, register_all_resources

        register_all_resources()
        registry = get_registry()

        # 1. List available templates
        templates_result = await registry.read_resource("metadata://templates")

        # Handle both response formats
        if "available_templates" in templates_result.content:
            template_names = list(templates_result.content["available_templates"].keys())
        else:
            template_list = templates_result.content.get("templates", [])
            template_names = [t.get("name", t.get("id", "standard")) for t in template_list]

        assert len(template_names) > 0, "No templates found"

        print(f"\nFound {len(template_names)} metadata templates")

        # 2. Read first template
        template_name = template_names[0]
        template_uri = f"metadata://templates/{template_name}"

        print(f"Reading template: {template_uri}")
        template_result = await registry.read_resource(template_uri)

        assert template_result is not None
        assert template_result.uri == template_uri
        assert isinstance(template_result.content, dict)
        # Template content is the dict itself, not wrapped in a "template" key
        assert len(template_result.content) > 0

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

        # Try to read non-existent resource
        with pytest.raises((ValueError, KeyError, RuntimeError)):
            await registry.read_resource("nonexistent://resource")

    @pytest.mark.anyio
    async def test_auth_workflow(self):
        """
        Test complete auth resource workflow:
        1. Check auth status
        2. Get catalog info
        3. Check filesystem status

        This validates the complete authentication and catalog
        discovery workflow.
        """
        from quilt_mcp.resources import get_registry, register_all_resources

        register_all_resources()
        registry = get_registry()

        # 1. Check auth status
        auth_status = await registry.read_resource("auth://status")
        assert isinstance(auth_status.content, dict)
        assert "status" in auth_status.content
        print(f"\nAuth status: {auth_status.content['status']}")

        # 2. Get catalog info
        catalog_info = await registry.read_resource("auth://catalog/info")
        assert isinstance(catalog_info.content, dict)
        print(f"Catalog info status: {catalog_info.content.get('status')}")

        # 3. Check filesystem status
        fs_status = await registry.read_resource("auth://filesystem/status")
        assert isinstance(fs_status.content, dict)
        assert "home_writable" in fs_status.content
        assert "temp_writable" in fs_status.content
        print(
            f"Filesystem writable: home={fs_status.content['home_writable']}, temp={fs_status.content['temp_writable']}"
        )

    @pytest.mark.anyio
    async def test_metadata_workflow(self):
        """
        Test complete metadata resource workflow:
        1. List all templates
        2. Get a specific template
        3. Get examples
        4. Get troubleshooting info

        This validates the complete metadata discovery workflow.
        """
        from quilt_mcp.resources import get_registry, register_all_resources

        register_all_resources()
        registry = get_registry()

        # 1. List all templates
        templates = await registry.read_resource("metadata://templates")
        assert isinstance(templates.content, dict)

        # Handle both response formats
        if "available_templates" in templates.content:
            template_count = len(templates.content["available_templates"])
        else:
            assert "templates" in templates.content
            template_count = len(templates.content["templates"])

        assert template_count > 0
        print(f"\nFound {template_count} metadata templates")

        # 2. Get standard template
        standard_template = await registry.read_resource("metadata://templates/standard")
        assert isinstance(standard_template.content, dict)
        # Template content is the dict itself, not wrapped in a "template" key
        assert len(standard_template.content) > 0
        print("Successfully retrieved standard template")

        # 3. Get examples
        examples = await registry.read_resource("metadata://examples")
        assert isinstance(examples.content, dict)
        # Examples content has "metadata_usage_guide" key, not "examples"
        assert len(examples.content) > 0
        print("Successfully retrieved metadata examples")

        # 4. Get troubleshooting info
        troubleshooting = await registry.read_resource("metadata://troubleshooting")
        assert isinstance(troubleshooting.content, dict)
        print("Successfully retrieved troubleshooting info")

    @pytest.mark.anyio
    async def test_athena_workflow(self):
        """
        Test Athena resources workflow:
        1. List databases
        2. List workgroups
        3. Check query history

        This validates Athena resource functionality.
        """
        from quilt_mcp.resources import get_registry, register_all_resources

        register_all_resources()
        registry = get_registry()

        # 1. List databases
        databases = await registry.read_resource("athena://databases")
        assert isinstance(databases.content, dict)
        assert "items" in databases.content
        db_count = len(databases.content["items"])
        print(f"\nFound {db_count} Athena databases")

        # 2. List workgroups
        workgroups = await registry.read_resource("athena://workgroups")
        assert isinstance(workgroups.content, dict)
        assert "items" in workgroups.content
        wg_count = len(workgroups.content["items"])
        print(f"Found {wg_count} Athena workgroups")

        # 3. Check query history
        history = await registry.read_resource("athena://queries/history")
        assert isinstance(history.content, dict)
        print("Successfully retrieved query history")

    @pytest.mark.anyio
    async def test_workflow_and_tabulator_resources(self):
        """
        Test workflow and tabulator resources:
        1. List workflows
        2. List tabulator buckets
        3. Validate response formats

        This validates workflow and tabulator resource functionality.
        """
        from quilt_mcp.resources import get_registry, register_all_resources

        register_all_resources()
        registry = get_registry()

        # 1. List workflows
        workflows = await registry.read_resource("workflow://workflows")
        assert isinstance(workflows.content, dict)
        assert "items" in workflows.content
        workflow_count = len(workflows.content["items"])
        print(f"\nFound {workflow_count} workflows")

        # 2. List tabulator buckets
        buckets = await registry.read_resource("tabulator://buckets")
        assert isinstance(buckets.content, dict)
        assert "items" in buckets.content
        bucket_count = len(buckets.content["items"])
        print(f"Found {bucket_count} tabulator buckets")
