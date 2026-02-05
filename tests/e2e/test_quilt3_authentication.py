"""Integration test to verify quilt3 authentication is working.

This test explicitly verifies that quilt3 login is working and will be skipped
when authentication is not configured. It should be run before other functional
tests to catch auth issues early.
"""

from __future__ import annotations

import pytest

from quilt_mcp.backends.quilt3_backend import Quilt3_Backend


pytestmark = pytest.mark.usefixtures("requires_catalog")


def test_quilt3_authentication_is_configured():
    """Verify that quilt3 is authenticated before running functional tests.

    This test requires quilt3 login and will be skipped when unavailable.
    """
    backend = Quilt3_Backend()
    auth_status = backend.get_auth_status()

    # Fail explicitly with helpful message, don't skip
    assert auth_status.is_authenticated, (
        "quilt3 is not authenticated. Run 'quilt3 login' before running functional tests.\n"
        f"Auth status: is_authenticated={auth_status.is_authenticated}, "
        f"catalog_name={auth_status.catalog_name}, "
        f"logged_in_url={auth_status.logged_in_url}"
    )

    # Verify we got meaningful auth details
    assert auth_status.catalog_name is not None, "Authentication succeeded but catalog_name is None"
    assert auth_status.logged_in_url is not None, "Authentication succeeded but logged_in_url is None"

    print(f"\n✓ Authenticated to {auth_status.catalog_name}")
    print(f"  URL: {auth_status.logged_in_url}")
    if auth_status.registry_url:
        print(f"  Registry: {auth_status.registry_url}")


def test_quilt3_backend_can_get_auth_status():
    """Verify that get_auth_status() works without errors."""
    backend = Quilt3_Backend()

    # This should not raise an exception
    auth_status = backend.get_auth_status()

    # Verify the auth_status object has expected attributes
    assert hasattr(auth_status, 'is_authenticated')
    assert hasattr(auth_status, 'catalog_name')
    assert hasattr(auth_status, 'logged_in_url')
    assert hasattr(auth_status, 'registry_url')

    # The type should be correct
    assert isinstance(auth_status.is_authenticated, bool)
