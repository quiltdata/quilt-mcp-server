"""Test configuration for pytest."""

import sys
import os
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


@pytest.fixture(scope="session")
def test_bucket() -> str:
    """Provide test bucket S3 URI for tests that require write access.

    This fixture is ONLY for tests. Production code should never import this.
    Tests requiring a bucket should explicitly declare this dependency.

    Returns:
        S3 URI of test bucket (e.g., "s3://my-test-bucket")

    Raises:
        pytest.skip: If QUILT_TEST_BUCKET environment variable not set
    """
    if not QUILT_TEST_BUCKET:
        pytest.skip("QUILT_TEST_BUCKET environment variable not set")
    return QUILT_TEST_BUCKET


@pytest.fixture(scope="session")
def test_bucket_name() -> str:
    """Provide test bucket name (without s3:// prefix).

    This fixture is ONLY for tests. Production code should never import this.

    Returns:
        Bucket name without s3:// prefix (e.g., "my-test-bucket")

    Raises:
        pytest.skip: If QUILT_TEST_BUCKET environment variable not set
    """
    if not QUILT_TEST_BUCKET:
        pytest.skip("QUILT_TEST_BUCKET environment variable not set")
    return QUILT_TEST_BUCKET.replace("s3://", "")


# ============================================================================
# Pytest Configuration
# ============================================================================


@pytest.fixture(scope="session")
def anyio_backend():
    """Configure anyio to use asyncio backend only (AsyncMock doesn't support trio)."""
    return "asyncio"


def pytest_configure(config):
    """Configure pytest and set up AWS session if needed."""
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
