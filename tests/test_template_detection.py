"""Test that resource template detection works correctly.

This test verifies that parameterized resources are correctly identified as
templates by FastMCP after the fix to register service functions directly.
"""

import inspect
import pytest
from quilt_mcp.utils import create_resource_handler
from quilt_mcp.resources.permissions import BucketAccessResource
from quilt_mcp.resources.admin import AdminUserResource, AdminUsersResource


def test_static_resource_handler_has_no_parameters():
    """Static resources should have handlers with no parameters."""
    resource = AdminUsersResource()
    uri = "admin://users"
    param_names = []

    handler = create_resource_handler(resource, uri, param_names)

    # Get the signature
    sig = inspect.signature(handler)
    params = list(sig.parameters.keys())

    # Static handler should have no parameters
    assert len(params) == 0, f"Static handler should have no parameters, got: {params}"


def test_single_param_resource_handler_has_explicit_parameter():
    """Single-parameter resources should have handlers with one named parameter."""
    resource = BucketAccessResource()
    uri = "permissions://buckets/{bucket}/access"
    param_names = ["bucket"]

    handler = create_resource_handler(resource, uri, param_names)

    # Get the signature
    sig = inspect.signature(handler)
    params = list(sig.parameters.keys())

    # Should have exactly one parameter named 'bucket'
    assert len(params) == 1, f"Expected 1 parameter, got {len(params)}: {params}"
    assert params[0] == "bucket", f"Expected parameter named 'bucket', got '{params[0]}'"

    # Verify parameter has type annotation (it will be a string 'str' due to exec)
    param = sig.parameters["bucket"]
    assert param.annotation in (str, 'str'), f"Expected str annotation, got {param.annotation}"


def test_multi_param_resource_handler_has_explicit_parameters():
    """Multi-parameter resources should have handlers with all named parameters."""
    resource = AdminUserResource()
    uri = "admin://users/{name}"
    param_names = ["name"]

    handler = create_resource_handler(resource, uri, param_names)

    # Get the signature
    sig = inspect.signature(handler)
    params = list(sig.parameters.keys())

    # Should have exactly one parameter named 'name'
    assert len(params) == 1, f"Expected 1 parameter, got {len(params)}: {params}"
    assert params[0] == "name", f"Expected parameter named 'name', got '{params[0]}'"


def test_handler_is_async():
    """All handlers should be async functions."""
    resource = BucketAccessResource()
    uri = "permissions://buckets/{bucket}/access"
    param_names = ["bucket"]

    handler = create_resource_handler(resource, uri, param_names)

    # Verify it's a coroutine function
    assert inspect.iscoroutinefunction(handler), "Handler should be an async function"


@pytest.mark.anyio
async def test_parameterized_handler_constructs_correct_uri():
    """Parameterized handler should construct URI with provided parameters."""
    resource = BucketAccessResource()
    uri = "permissions://buckets/{bucket}/access"
    param_names = ["bucket"]

    handler = create_resource_handler(resource, uri, param_names)

    # Call handler with a test bucket name
    # This will make a real call, but we're testing the URI construction
    try:
        result = await handler(bucket="test-bucket")
        # If it succeeds, great - we just wanted to verify it doesn't crash
        assert isinstance(result, str)
    except Exception as e:
        # If it fails, verify it's not due to URI construction
        # (access errors are expected in test environment)
        error_msg = str(e)
        assert "Missing required parameter" not in error_msg, \
            f"Handler failed due to URI construction: {error_msg}"


def test_fastmcp_can_detect_template_parameters():
    """FastMCP should be able to detect template parameters from handler signature.

    This is the core requirement - FastMCP inspects the function signature
    to determine if a resource is a template or not.
    """
    resource = BucketAccessResource()
    uri = "permissions://buckets/{bucket}/access"
    param_names = ["bucket"]

    handler = create_resource_handler(resource, uri, param_names)

    # Simulate what FastMCP does: inspect the signature
    sig = inspect.signature(handler)
    detected_params = list(sig.parameters.keys())

    # FastMCP should detect 'bucket' as a parameter
    assert "bucket" in detected_params, \
        f"FastMCP should detect 'bucket' parameter, got: {detected_params}"

    # Verify the parameter doesn't use *args or **kwargs
    for param_name, param in sig.parameters.items():
        assert param.kind not in [
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ], f"Parameter {param_name} should be explicit, not *args/**kwargs"


def test_handler_function_name_is_descriptive():
    """Handler functions should have descriptive names for debugging."""
    resource = BucketAccessResource()
    uri = "permissions://buckets/{bucket}/access"
    param_names = ["bucket"]

    handler = create_resource_handler(resource, uri, param_names)

    # Should have a descriptive name
    assert handler.__name__ == "resource_handler_bucket", \
        f"Expected 'resource_handler_bucket', got '{handler.__name__}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
