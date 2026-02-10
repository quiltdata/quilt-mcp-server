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

# Test package configuration (can reference any package in any bucket)
# These are used for basic connectivity checks only
KNOWN_TEST_PACKAGE = os.getenv("QUILT_TEST_PACKAGE", "test/raw")
KNOWN_TEST_ENTRY = os.getenv("QUILT_TEST_ENTRY", "README.md")


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
        from quilt_mcp.context.runtime_context import clear_runtime_auth, update_runtime_metadata

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
        from quilt_mcp.context.runtime_context import clear_runtime_auth, update_runtime_metadata

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
    from quilt_mcp.context.runtime_context import RuntimeAuthState, push_runtime_context, reset_runtime_context

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

        # Use real JWT from environment if available, otherwise try quilt3 session, otherwise generate test JWT
        access_token = os.getenv("PLATFORM_TEST_JWT_TOKEN")
        if not access_token:
            # Try to get JWT from quilt3 session (if authenticated)
            try:
                import quilt3

                quilt_session = quilt3.session.get_session()
                if hasattr(quilt_session, "headers") and "Authorization" in quilt_session.headers:
                    auth_header = quilt_session.headers["Authorization"]
                    if auth_header.startswith("Bearer "):
                        access_token = auth_header[7:]  # Strip "Bearer " prefix
                        print(f"✅ Using JWT from quilt3 session")
            except Exception as e:
                print(f"⚠️  Could not get JWT from quilt3 session: {e}")

        if not access_token:
            # Generate test JWT for mocked platform tests (only if no real token available)
            import jwt as pyjwt
            import time
            import uuid

            # Get JWT secret from environment or use default test secret
            jwt_secret = os.getenv("PLATFORM_TEST_JWT_SECRET", "test-secret-for-jwt-generation")

            claims = {
                "id": "test-user-platform",
                "uuid": str(uuid.uuid4()),
                "exp": int(time.time()) + 3600,
            }
            access_token = pyjwt.encode(claims, jwt_secret, algorithm="HS256")
            print(f"⚠️  Using generated test JWT (may not work with real servers)")

        # Decode JWT to get claims (works for both real and generated tokens)
        import jwt as pyjwt

        claims = pyjwt.decode(access_token, options={"verify_signature": False})

        token_handle = push_runtime_context(
            environment="web",
            auth=RuntimeAuthState(
                scheme="Bearer",
                access_token=access_token,
                claims=claims,
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


# ============================================================================
# Docker Infrastructure (Shared by stateless and e2e tests)
# ============================================================================
#
# These fixtures provide Docker container infrastructure for testing the
# containerized MCP server. They are shared between:
#
# 1. tests/stateless/ - Validates deployment constraints (security, resources, JWT)
# 2. tests/e2e/ - Validates functional correctness (MCP protocol, backend-agnostic)
#
# Key fixtures:
# - docker_client: Docker client for container management
# - docker_image_name: Image name to test (from TEST_DOCKER_IMAGE env var)
# - build_docker_image: Builds the Docker image once per session
# - stateless_container: Starts container with production-like constraints
# - container_url: HTTP endpoint URL for making requests to the container
# - get_container_filesystem_writes: Helper to detect filesystem changes
#
# See: spec/a18-valid-jwts/08-test-organization.md
# ============================================================================


def make_test_jwt(
    *,
    secret: str,
    subject: str = "stateless-user",
    expires_in: int = 600,
    extra_claims: Dict[str, Any] | None = None,
) -> str:
    """Generate a catalog-format JWT for testing.

    Args:
        secret: HS256 shared secret for signing
        subject: User ID (goes in 'id' claim)
        expires_in: Expiration time in seconds from now
        extra_claims: Additional claims to include

    Returns:
        Signed JWT token string
    """
    import jwt
    import time
    import uuid

    payload: Dict[str, Any] = {
        "id": subject,
        "uuid": str(uuid.uuid4()),
        "exp": int(time.time()) + expires_in,
    }

    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture(scope="session")
def docker_client():
    """Provide Docker client for container management.

    Used by both stateless tests (to verify deployment constraints)
    and e2e tests (to test MCP protocol functionality).
    """
    import docker

    return docker.from_env()


@pytest.fixture(scope="session")
def docker_image_name() -> str:
    """Get the Docker image name to test.

    Defaults to 'quilt-mcp-server:test' but can be overridden with
    TEST_DOCKER_IMAGE environment variable.
    """
    return os.getenv("TEST_DOCKER_IMAGE", "quilt-mcp-server:test")


@pytest.fixture(scope="session")
def build_docker_image(docker_client, docker_image_name: str) -> str:
    """Build the Docker image for testing.

    This fixture builds the image once per session and returns the image name.
    Both stateless and e2e tests use this same image.
    """
    print(f"\n🔨 Building Docker image: {docker_image_name}")

    # Get project root (parent directory of tests/)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Build image
    image, build_logs = docker_client.images.build(
        path=project_root,
        tag=docker_image_name,
        rm=True,
        forcerm=True,
    )

    # Print build summary
    print(f"✅ Built image: {image.short_id}")
    return docker_image_name


@pytest.fixture
def stateless_container(
    docker_client,
    build_docker_image: str,
):
    """
    Start a container with stateless deployment constraints.

    This fixture creates a container with:
    - Read-only root filesystem
    - Tmpfs mounts for temporary storage
    - Security constraints (no-new-privileges, cap-drop=ALL)
    - Resource limits (512M memory, 1.0 CPU)
    - JWT-only authentication mode

    Function-scoped: Each test gets a fresh container to ensure isolation.

    Used by both stateless tests (to verify constraints) and e2e tests
    (to test MCP protocol functionality).
    """
    from typing import Generator
    from docker.models.containers import Container

    container: Container | None = None

    try:
        # Container configuration matching production constraints
        container = docker_client.containers.run(
            image=build_docker_image,
            detach=True,
            remove=False,  # Don't auto-remove so we can inspect it
            read_only=True,  # Read-only root filesystem
            security_opt=["no-new-privileges:true"],  # Prevent privilege escalation
            cap_drop=["ALL"],  # Drop all capabilities
            tmpfs={
                "/tmp": "size=100M,mode=1777",  # noqa: S108
                # "/app/.cache": "size=50M,mode=700",  # Not needed with QUILT_DISABLE_CACHE=true
                "/run": "size=10M,mode=755",
            },
            mem_limit="512m",  # Memory limit
            memswap_limit="512m",  # No swap
            cpu_quota=100000,  # 1.0 CPU (100000/100000)
            cpu_period=100000,
            environment={
                "QUILT_MULTIUSER_MODE": "true",  # Enable multiuser mode
                "QUILT_CATALOG_URL": "http://test-catalog.example.com",  # Required for multiuser
                "QUILT_REGISTRY_URL": "http://test-registry.example.com",  # Required for multiuser
                "QUILT_DISABLE_CACHE": "true",  # Disable caching
                "HOME": "/tmp",  # Redirect home directory  # noqa: S108
                "LOG_LEVEL": "DEBUG",  # Verbose logging
                "FASTMCP_TRANSPORT": "http",
                "FASTMCP_HOST": "0.0.0.0",  # noqa: S104
                "FASTMCP_PORT": "8000",
            },
            ports={"8000/tcp": None},  # Random host port
        )

        # Wait for container to be healthy
        print(f"🚀 Started container: {container.short_id}")
        import time
        import httpx

        # Wait for HTTP server to be ready (up to 10 seconds)
        container.reload()
        ports = container.ports
        if "8000/tcp" not in ports or not ports["8000/tcp"]:
            raise RuntimeError("Container port 8000 not exposed")

        host_port = ports["8000/tcp"][0]["HostPort"]
        url = f"http://localhost:{host_port}"

        for attempt in range(20):  # 20 attempts * 0.5s = 10s max
            time.sleep(0.5)
            container.reload()

            if container.status != "running":
                logs = container.logs().decode("utf-8")
                raise RuntimeError(f"Container failed to start: {logs}")

            try:
                response = httpx.get(f"{url}/", timeout=2.0)
                if response.status_code == 200:
                    print(f"✅ Container running and healthy: {container.short_id}")
                    break
            except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError):
                # Server not ready yet, continue waiting
                continue
        else:
            logs = container.logs().decode("utf-8")
            raise RuntimeError(f"Container did not become healthy after 10s: {logs}")

        yield container

    finally:
        if container:
            try:
                print(f"\n🧹 Cleaning up container: {container.short_id}")
                container.stop(timeout=5)
                container.remove(force=True)
                print("✅ Container cleaned up")
            except Exception as e:
                print(f"⚠️  Error cleaning up container: {e}")


@pytest.fixture
def container_url(stateless_container) -> str:
    """Get the HTTP URL for the container's MCP server.

    This fixture is used by both stateless tests (to verify deployment)
    and e2e tests (to test MCP protocol functionality).

    E2E tests are completely backend-agnostic - they only use this URL
    to make HTTP requests and don't know or care what backend is running.

    Function-scoped to match stateless_container fixture.
    """
    stateless_container.reload()
    ports = stateless_container.ports

    if "8000/tcp" not in ports or not ports["8000/tcp"]:
        raise RuntimeError("Container port 8000 not exposed")

    host_port = ports["8000/tcp"][0]["HostPort"]
    return f"http://localhost:{host_port}"


def get_container_filesystem_writes(container) -> list[str]:
    """
    Get list of files written outside tmpfs directories.

    Uses `docker diff` to detect filesystem changes.
    Used by stateless tests to verify read-only filesystem enforcement.
    """
    import subprocess

    result = subprocess.run(
        ["docker", "diff", container.id],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return []

    # Parse docker diff output (format: "A /path/to/file" or "C /path/to/file")
    changes = []
    tmpfs_paths = {"/tmp", "/run"}  # noqa: S108

    for line in result.stdout.strip().split("\n"):
        if not line:
            continue

        parts = line.split(None, 1)
        if len(parts) != 2:
            continue

        change_type, path = parts

        # Ignore changes in tmpfs directories
        if any(path.startswith(tmpfs_path) for tmpfs_path in tmpfs_paths):
            continue

        changes.append(path)

    return changes
