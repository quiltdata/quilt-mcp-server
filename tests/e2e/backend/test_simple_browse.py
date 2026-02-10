"""Simple test to browse existing test/mcp_create package."""

import pytest


@pytest.mark.e2e
def test_browse_existing_package(backend_with_auth):
    """Test browsing an existing package without creating it first.

    This tests whether browse_content works on existing packages
    (not newly created ones).
    """
    print("\n[Test] Browsing existing package: test/mcp_create@latest")

    result = backend_with_auth.browse_content(
        package_name="test/mcp_create", registry="s3://quilt-ernest-staging", path=""
    )

    print(f"✅ Browse succeeded! Found {len(result)} items")
    for item in result[:10]:
        print(f"  - {item.path} ({item.type})")

    assert len(result) > 0, "Should find at least one item in package"
