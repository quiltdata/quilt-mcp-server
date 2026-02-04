"""Test configuration for pytest."""

import sys
import os
import base64
import json
import boto3
import pytest
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Callable, Dict, Any

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    # Load from .env file in the project root
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"Loaded environment from {env_path}")
except ImportError:
    # python-dotenv not available, try manual loading
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key, value)
        print(f"Manually loaded environment from {env_path}")

# Add the app directory to Python path so quilt_mcp module can be imported
app_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app")
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

# Removed unused README test framework imports


# ============================================================================
# Test-Only Configuration (NEVER used in production code)
# ============================================================================
# This configuration is ONLY for running the test suite
# Production code should NEVER import from this file
# ============================================================================

QUILT_TEST_BUCKET = os.getenv("QUILT_TEST_BUCKET", "")


def _generate_test_jwt() -> str:
    """Generate a lightweight unsigned JWT for platform integration tests."""
    header = {"alg": "none", "typ": "JWT"}
    payload = {
        "id": "test-user",
        "uuid": "test-uuid",
        "sub": "test-user",
        "email": "test-user@example.com",
        "exp": 9999999999,
    }

    def _encode(value: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(value).encode("utf-8")).decode("utf-8").rstrip("=")

    return f"{_encode(header)}.{_encode(payload)}."


def _is_truthy_env(value: str | None) -> bool:
    """Parse a permissive true/false environment variable value."""
    if value is None:
        return False
    return value.lower() in {"1", "true", "yes", "on"}


def _backend_mode_params() -> list[str]:
    """Resolve backend parametrization mode for test runs."""
    requested_mode = os.getenv("TEST_BACKEND_MODE", "both").strip().lower()
    if requested_mode in {"quilt3", "local", "single-user"}:
        return ["quilt3"]
    if requested_mode in {"platform", "graphql", "multiuser"}:
        return ["platform"]
    return ["quilt3", "platform"]


@pytest.fixture(scope="session")
def test_bucket() -> str:
    """Provide test bucket name (without s3:// prefix) for bucket operations.

    This fixture is ONLY for tests. Production code should never import this.
    Tests requiring a bucket should explicitly declare this dependency.

    IMPORTANT: Returns bucket NAME only (e.g., "my-test-bucket")
    For S3 URI format, use test_registry fixture instead.

    Returns:
        Bucket name without s3:// prefix (e.g., "my-test-bucket")

    Raises:
        pytest.fail: If QUILT_TEST_BUCKET environment variable not set
    """
    if not QUILT_TEST_BUCKET:
        pytest.fail("QUILT_TEST_BUCKET environment variable not set")
    # Remove s3:// prefix if present (for backward compatibility)
    return QUILT_TEST_BUCKET.replace("s3://", "")


@pytest.fixture(scope="session")
def test_bucket_name() -> str:
    """Provide test bucket name (without s3:// prefix).

    This fixture is ONLY for tests. Production code should never import this.
    Alias for test_bucket fixture for clarity in some contexts.

    Returns:
        Bucket name without s3:// prefix (e.g., "my-test-bucket")

    Raises:
        pytest.fail: If QUILT_TEST_BUCKET environment variable not set
    """
    if not QUILT_TEST_BUCKET:
        pytest.fail("QUILT_TEST_BUCKET environment variable not set")
    return QUILT_TEST_BUCKET.replace("s3://", "")


@pytest.fixture(scope="session")
def test_registry() -> str:
    """Provide test bucket as S3 URI for registry parameters.

    This fixture is ONLY for tests that pass registry parameter.
    Use this when the test needs to pass a registry to package functions.

    Returns:
        S3 URI of test bucket (e.g., "s3://my-test-bucket")

    Raises:
        pytest.fail: If QUILT_TEST_BUCKET environment variable not set
    """
    if not QUILT_TEST_BUCKET:
        pytest.fail("QUILT_TEST_BUCKET environment variable not set")
    # Remove s3:// prefix if present, then add it back
    bucket_name = QUILT_TEST_BUCKET.replace("s3://", "")
    return f"s3://{bucket_name}"


# ============================================================================
# Pytest Configuration
# ============================================================================


@pytest.fixture(scope="session")
def anyio_backend():
    """Configure anyio to use asyncio backend only (AsyncMock doesn't support trio)."""
    return "asyncio"


def pytest_configure(config):
    """Configure pytest and set up AWS session if needed."""
    # CRITICAL: Ensure tests use IAM credentials, not JWT authentication
    # Clear any existing runtime auth context to prevent JWT fallback
    try:
        from quilt_mcp.runtime_context import clear_runtime_auth

        clear_runtime_auth()
    except ImportError:
        pass

    # Explicitly ensure unit tests run in local mode (not multiuser mode)
    # This forces tests to use local AWS credentials (AWS_PROFILE or default)
    os.environ["QUILT_MULTIUSER_MODE"] = "false"

    # Remove JWT secrets to prevent development fallback behavior
    os.environ.pop("MCP_JWT_SECRET", None)
    os.environ.pop("MCP_JWT_SECRET_SSM_PARAMETER", None)

    # Reset ModeConfig singleton to pick up test environment variables
    try:
        from quilt_mcp.config import reset_mode_config

        reset_mode_config()
    except ImportError:
        pass

    # Configure boto3 default session to use AWS_PROFILE if set
    # This must be done very early before any imports that create boto3 clients
    if os.getenv("AWS_PROFILE"):
        boto3.setup_default_session(profile_name=os.getenv("AWS_PROFILE"))

    # Set default Athena workgroup to skip discovery in tests
    if not os.getenv("ATHENA_WORKGROUP"):
        os.environ["ATHENA_WORKGROUP"] = "primary"

    # Add custom markers
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow: mark test as slow-running test")


@pytest.fixture(autouse=True)
def reset_runtime_auth_state():
    """Ensure runtime auth state doesn't leak between tests."""
    try:
        from quilt_mcp.runtime_context import clear_runtime_auth, update_runtime_metadata

        clear_runtime_auth()
        update_runtime_metadata(jwt_assumed_session=None, jwt_assumed_expiration=None)
    except Exception:
        pass

    # Reset ModeConfig singleton to ensure test environment variables are used
    try:
        from quilt_mcp.config import reset_mode_config

        reset_mode_config()
    except Exception:
        pass

    yield

    try:
        from quilt_mcp.runtime_context import clear_runtime_auth, update_runtime_metadata

        clear_runtime_auth()
        update_runtime_metadata(jwt_assumed_session=None, jwt_assumed_expiration=None)
    except Exception:
        pass

    # Reset ModeConfig singleton after test
    try:
        from quilt_mcp.config import reset_mode_config

        reset_mode_config()
    except Exception:
        pass


@pytest.fixture(params=_backend_mode_params())
def backend_mode(request, monkeypatch, reset_runtime_auth_state):
    """Run selected integration tests against quilt3 and/or platform backends."""
    del reset_runtime_auth_state  # dependency for fixture ordering

    from quilt_mcp.config import reset_mode_config, set_test_mode_config
    from quilt_mcp.runtime_context import RuntimeAuthState, push_runtime_context, reset_runtime_context

    mode = request.param
    token_handle = None

    if mode == "platform":
        if not _is_truthy_env(os.getenv("PLATFORM_TEST_ENABLED")):
            pytest.skip("Platform integration tests disabled - set PLATFORM_TEST_ENABLED=true")

        monkeypatch.setenv("QUILT_MULTIUSER_MODE", "true")
        monkeypatch.setenv("QUILT_CATALOG_URL", os.getenv("PLATFORM_CATALOG_URL", "https://test.quiltdata.com"))
        monkeypatch.setenv("QUILT_REGISTRY_URL", os.getenv("PLATFORM_REGISTRY_URL", "https://registry.test.com"))
        monkeypatch.setenv("MCP_JWT_SECRET", os.getenv("PLATFORM_TEST_JWT_SECRET", "test-secret"))

        token_handle = push_runtime_context(
            environment="web",
            auth=RuntimeAuthState(
                scheme="Bearer",
                access_token=_generate_test_jwt(),
                claims={"id": "test-user", "uuid": "test-uuid", "sub": "test-user", "exp": 9999999999},
            ),
        )

    set_test_mode_config(multiuser_mode=(mode == "platform"))
    try:
        yield mode
    finally:
        if token_handle is not None:
            reset_runtime_context(token_handle)
        reset_mode_config()


# Cached Athena service fixtures for better performance across all tests


@lru_cache(maxsize=2)
def _cached_athena_service(use_quilt_auth: bool):
    """Cache Athena service instances by auth mode."""
    from quilt_mcp.services.athena_service import AthenaQueryService

    return AthenaQueryService(use_quilt_auth=use_quilt_auth)


@pytest.fixture(scope="session")
def athena_service_factory() -> Callable:
    """Return a factory that reuses cached Athena service instances."""

    def factory(use_quilt_auth: bool = True):
        return _cached_athena_service(bool(use_quilt_auth))

    return factory


@pytest.fixture(scope="session")
def athena_service_quilt(athena_service_factory):
    """Session-scoped Athena service using quilt authentication."""
    return athena_service_factory(True)


@pytest.fixture(scope="session")
def athena_service_builtin(athena_service_factory):
    """Session-scoped Athena service using default AWS credentials."""
    return athena_service_factory(False)


@pytest.fixture(scope="session")
def athena_service_cache_controller():
    """Expose cache control so suites can clear cached services if needed."""
    return _cached_athena_service.cache_clear


@pytest.fixture(scope="session", autouse=True)
def cached_athena_service_constructor(athena_service_factory):
    """Patch athena_glue module to reuse cached service instances in tests."""
    from quilt_mcp.tools import athena_glue

    original_constructor = athena_glue.AthenaQueryService

    def cached_constructor(*args, **kwargs):
        # Fallback to original constructor when extra kwargs are provided
        extra_kwargs = {k: v for k, v in kwargs.items() if k != "use_quilt_auth"}
        if extra_kwargs or len(args) > 1:
            return original_constructor(*args, **kwargs)

        use_quilt_auth = kwargs.get("use_quilt_auth") if kwargs else None
        if args:
            use_quilt_auth = args[0]
        if use_quilt_auth is None:
            use_quilt_auth = True

        return athena_service_factory(use_quilt_auth=use_quilt_auth)

    athena_glue.AthenaQueryService = cached_constructor
    try:
        yield
    finally:
        athena_glue.AthenaQueryService = original_constructor


# ============================================================================
# Quilt3 Backend Fixture
# ============================================================================


@pytest.fixture(scope="session")
def quilt3_backend():
    """Provide initialized Quilt3_Backend for integration tests.

    This fixture creates a session-scoped Quilt3_Backend instance that uses
    the current quilt3 session and AWS credentials from the environment.

    Returns:
        Quilt3_Backend: Initialized backend instance

    Raises:
        pytest.skip: If quilt3 is not authenticated or backend initialization fails
    """
    try:
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        backend = Quilt3_Backend()

        # Verify auth status is available
        try:
            auth_status = backend.get_auth_status()
            if not auth_status.is_authenticated:
                pytest.skip("Quilt3 not authenticated - skipping integration tests")
        except Exception as e:
            pytest.skip(f"Failed to verify auth status: {e}")

        return backend
    except ImportError as e:
        pytest.skip(f"Failed to import Quilt3_Backend: {e}")
    except Exception as e:
        pytest.skip(f"Failed to initialize Quilt3_Backend: {e}")
