"""Test configuration for pytest."""

import sys
import os
import boto3
import pytest
import tempfile
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Callable, Dict, Any

from tests.jwt_helpers import get_sample_catalog_claims, get_sample_catalog_token

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


@pytest.fixture(scope="session")
def test_env():
    """Configure test environment defaults (opt-in)."""
    # Ensure unit tests run in local mode (not multiuser mode)
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
    # This must be done before any imports that create boto3 clients
    if os.getenv("AWS_PROFILE"):
        boto3.setup_default_session(profile_name=os.getenv("AWS_PROFILE"))

    # Set default Athena workgroup to skip discovery in tests
    if not os.getenv("ATHENA_WORKGROUP"):
        os.environ["ATHENA_WORKGROUP"] = "primary"

    yield


@pytest.fixture
def clean_auth():
    """Ensure runtime auth state doesn't leak between tests (opt-in)."""
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
def backend_mode(request, monkeypatch, clean_auth, test_env):
    """Run selected functional tests against quilt3 and/or platform backends."""
    del clean_auth  # dependency for fixture ordering
    del test_env

    from quilt_mcp.config import reset_mode_config, set_test_mode_config
    from quilt_mcp.runtime_context import RuntimeAuthState, push_runtime_context, reset_runtime_context

    mode = request.param
    token_handle = None

    if mode == "platform":
        if not _is_truthy_env(os.getenv("PLATFORM_TEST_ENABLED")):
            pytest.skip("Platform functional tests disabled - set PLATFORM_TEST_ENABLED=true")

        quilt_catalog_url = os.getenv("QUILT_CATALOG_URL")
        quilt_registry_url = os.getenv("QUILT_REGISTRY_URL")
        if not quilt_catalog_url or not quilt_registry_url:
            pytest.skip("Platform functional tests require QUILT_CATALOG_URL and QUILT_REGISTRY_URL to be set")

        monkeypatch.setenv("QUILT_MULTIUSER_MODE", "true")
        monkeypatch.setenv("QUILT_CATALOG_URL", quilt_catalog_url)
        monkeypatch.setenv("QUILT_REGISTRY_URL", quilt_registry_url)
        monkeypatch.setenv("MCP_JWT_SECRET", os.getenv("PLATFORM_TEST_JWT_SECRET", "test-secret"))

        token_handle = push_runtime_context(
            environment="web",
            auth=RuntimeAuthState(
                scheme="Bearer",
                access_token=get_sample_catalog_token(),
                claims=get_sample_catalog_claims(),
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


@pytest.fixture(scope="session")
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


@pytest.fixture
def requires_admin():
    """Skip tests unless admin functionality is available."""
    try:
        from quilt_mcp.services import governance_service as governance

        if not getattr(governance, "ADMIN_AVAILABLE", False):
            pytest.skip("Admin functionality not available")
    except Exception as exc:
        pytest.skip(f"Admin check failed: {exc}")


@pytest.fixture
def requires_catalog(quilt3_backend):
    """Skip tests unless quilt3 catalog authentication is available."""
    return quilt3_backend


@pytest.fixture
def requires_search(requires_catalog):
    """Skip tests unless search backend is available."""
    try:
        from quilt_mcp.search.utils.backend_status import get_search_backend_status

        status = get_search_backend_status()
        if not status.get("available"):
            pytest.skip(f"Search backend unavailable: {status.get('status')}")
    except Exception as exc:
        pytest.skip(f"Search backend check failed: {exc}")


@pytest.fixture(scope="session")
def requires_docker():
    """Skip tests unless Docker CLI and daemon are available."""
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI not available")
    try:
        import subprocess

        subprocess.run(["docker", "info"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as exc:
        pytest.skip(f"Docker daemon unavailable: {exc}")


# ============================================================================
# Quilt3 Backend Fixture
# ============================================================================


@pytest.fixture(scope="session")
def quilt3_backend():
    """Provide initialized Quilt3_Backend for functional tests.

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
                pytest.skip("Quilt3 not authenticated - skipping functional tests")
        except Exception as e:
            pytest.skip(f"Failed to verify auth status: {e}")

        return backend
    except ImportError as e:
        pytest.skip(f"Failed to import Quilt3_Backend: {e}")
    except Exception as e:
        pytest.skip(f"Failed to initialize Quilt3_Backend: {e}")


@pytest.fixture(scope="session")
def platform_backend():
    """Provide initialized Platform_Backend for functional tests.

    Returns:
        Platform_Backend: Initialized backend instance

    Raises:
        pytest.skip: If platform backend initialization fails or auth is unavailable
    """
    try:
        from quilt_mcp.backends.platform_backend import Platform_Backend

        backend = Platform_Backend()

        try:
            auth_status = backend.get_auth_status()
            if not auth_status.is_authenticated:
                pytest.skip("Platform backend not authenticated - skipping functional tests")
        except Exception as e:
            pytest.skip(f"Failed to verify platform auth status: {e}")

        return backend
    except ImportError as e:
        pytest.skip(f"Failed to import Platform_Backend: {e}")
    except Exception as e:
        pytest.skip(f"Failed to initialize Platform_Backend: {e}")
