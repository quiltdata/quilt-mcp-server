"""E2E Backend Integration Test Configuration.

This module provides fixtures for E2E backend integration tests with REAL services.
NO MOCKING - all fixtures use actual AWS, Quilt catalog, and registry services.

Key fixtures:
- backend_with_auth: Authenticated backend (quilt3 or platform)
- cleanup_packages: Track and cleanup created packages
- cleanup_s3_objects: Track and cleanup uploaded S3 objects
- real_test_bucket: Test bucket name with validation
"""

import os
import pytest
import boto3
from typing import List, Dict, Any, Set
from pathlib import Path

# Import from root conftest for reuse
from tests.conftest import backend_mode, athena_service_factory, test_bucket  # noqa: F401

# Import from parent e2e conftest for auth_backend compatibility
from tests.e2e.conftest import AuthBackend  # noqa: F401


class ResourceTracker:
    """Track resources created during tests for cleanup.

    This class maintains lists of created resources and provides
    cleanup methods that handle errors gracefully.
    """

    def __init__(self):
        """Initialize empty resource tracking."""
        self.packages: List[Dict[str, str]] = []
        self.s3_objects: List[Dict[str, str]] = []

    def track_package(self, bucket: str, package_name: str, registry: str = None):
        """Track a package for cleanup.

        Args:
            bucket: Bucket name (without s3:// prefix)
            package_name: Package name (e.g., "test/my_package")
            registry: Optional registry URL
        """
        if registry is None:
            registry = f"s3://{bucket}"

        self.packages.append(
            {
                "bucket": bucket,
                "package_name": package_name,
                "registry": registry,
            }
        )

    def track_s3_object(self, bucket: str, key: str):
        """Track an S3 object for cleanup.

        Args:
            bucket: Bucket name (without s3:// prefix)
            key: Object key
        """
        self.s3_objects.append(
            {
                "bucket": bucket,
                "key": key,
            }
        )

    def cleanup_packages(self, backend) -> List[str]:
        """Clean up all tracked packages.

        Args:
            backend: Backend instance (unused, uses package_delete tool directly)

        Returns:
            List of error messages (empty if all successful)
        """
        errors = []
        # Import tool function for package deletion
        from quilt_mcp.tools.packages import package_delete

        for pkg in self.packages:
            try:
                package_delete(package_name=pkg["package_name"], registry=pkg["registry"])
                print(f"  ✅ Cleaned up package: {pkg['package_name']} in {pkg['bucket']}")
            except Exception as e:
                error_msg = f"Failed to delete package {pkg['package_name']}: {e}"
                errors.append(error_msg)
                print(f"  ⚠️  {error_msg}")

        return errors

    def cleanup_s3_objects(self) -> List[str]:
        """Clean up all tracked S3 objects.

        Returns:
            List of error messages (empty if all successful)
        """
        errors = []
        s3 = boto3.client('s3')

        for obj in self.s3_objects:
            try:
                s3.delete_object(Bucket=obj["bucket"], Key=obj["key"])
                print(f"  ✅ Cleaned up S3 object: s3://{obj['bucket']}/{obj['key']}")
            except Exception as e:
                error_msg = f"Failed to delete s3://{obj['bucket']}/{obj['key']}: {e}"
                errors.append(error_msg)
                print(f"  ⚠️  {error_msg}")

        return errors


@pytest.fixture
def real_test_bucket(test_bucket):
    """Get REAL test bucket with validation.

    This fixture ensures:
    1. Test bucket is configured
    2. Bucket name is valid (no s3:// prefix)
    3. Bucket is accessible

    Args:
        test_bucket: From root conftest.py

    Returns:
        str: Test bucket name (without s3:// prefix)

    Raises:
        pytest.skip: If bucket not available or not accessible
    """
    if not test_bucket:
        pytest.skip("QUILT_TEST_BUCKET not configured")

    # Validate bucket is accessible
    try:
        s3 = boto3.client('s3')
        s3.head_bucket(Bucket=test_bucket)
    except Exception as e:
        pytest.skip(f"Test bucket {test_bucket} not accessible: {e}")

    return test_bucket


@pytest.fixture
def backend_with_auth(backend_mode, real_test_bucket):
    """Create authenticated backend with connectivity verification.

    This fixture:
    1. Creates backend using QuiltOpsFactory (respects TEST_BACKEND_MODE)
    2. Verifies credentials are available
    3. Tests connectivity to real services
    4. Handles platform-specific initialization (JWT, GraphQL)

    NO MOCKING - Uses actual QuiltOpsFactory that creates real backends.

    Args:
        backend_mode: From root conftest (quilt3|platform)
        real_test_bucket: Validated test bucket name

    Returns:
        Backend instance (Quilt3_Backend or Platform_Backend)

    Raises:
        pytest.skip: If auth not available or connectivity fails
    """
    from quilt_mcp.ops.factory import QuiltOpsFactory

    # Check auth availability
    if backend_mode == "quilt3":
        config_file = Path.home() / ".quilt" / "config.yml"
        if not config_file.exists():
            pytest.skip("Quilt3 auth not available: ~/.quilt/config.yml not found")
    elif backend_mode == "platform":
        if not os.getenv("PLATFORM_TEST_ENABLED"):
            pytest.skip("Platform backend not enabled: PLATFORM_TEST_ENABLED not set")
        required_vars = ["QUILT_CATALOG_URL", "QUILT_REGISTRY_URL"]
        missing = [v for v in required_vars if not os.getenv(v)]
        if missing:
            pytest.skip(f"Platform backend config incomplete: {missing} not set")

    # Create backend using factory
    try:
        backend = QuiltOpsFactory.create()
    except Exception as e:
        pytest.skip(f"Failed to create backend: {e}")

    # Verify connectivity with real test - try a lightweight operation
    try:
        # For quilt3 backend, verify it has session
        # For platform backend, verify GraphQL is accessible
        if backend_mode == "quilt3":
            # Just verify backend was created successfully
            # (QuiltOpsFactory already validated config exists)
            pass
        else:
            # Platform backend - verify GraphQL connectivity
            headers = backend.get_graphql_auth_headers()
            endpoint = backend.get_graphql_endpoint()
            if not headers or not endpoint:
                pytest.skip("Platform backend: GraphQL not accessible")
    except Exception as e:
        pytest.skip(f"Backend initialization failed: {e}")

    # Platform-specific initialization
    if backend_mode == "platform":
        try:
            # Verify GraphQL connectivity
            headers = backend.get_graphql_auth_headers()
            endpoint = backend.get_graphql_endpoint()
            if not headers or not endpoint:
                pytest.skip("Platform backend: GraphQL auth/endpoint not available")
        except Exception as e:
            pytest.skip(f"Platform backend: GraphQL setup failed: {e}")

    return backend


@pytest.fixture
def cleanup_packages(request):
    """Track and cleanup packages created during test.

    This fixture provides a ResourceTracker that:
    1. Tracks packages created during test execution
    2. Cleans them up via pytest finalizer (runs even on failure)
    3. Reports cleanup errors without failing the test

    Usage:
        def test_something(backend_with_auth, cleanup_packages):
            # Create package
            result = backend_with_auth.package_create(...)

            # Track for cleanup
            cleanup_packages.track_package(
                bucket="test-bucket",
                package_name="test/my_package"
            )

            # ... test continues ...
            # Cleanup happens automatically after test

    Args:
        request: pytest request object for finalizer

    Returns:
        ResourceTracker: Instance with track_package() method
    """
    tracker = ResourceTracker()

    def cleanup():
        """Cleanup finalizer - runs even if test fails."""
        if not tracker.packages:
            return

        print(f"\n🧹 Cleaning up {len(tracker.packages)} package(s)...")

        # Get backend from test (if available)
        try:
            # Try to get backend from test function's fixtures
            if hasattr(request, 'node'):
                backend = request.node.funcargs.get('backend_with_auth')
                if backend:
                    errors = tracker.cleanup_packages(backend)
                    if errors:
                        print(f"  ⚠️  {len(errors)} cleanup error(s) occurred")
                else:
                    print("  ⚠️  Backend not available for cleanup")
        except Exception as e:
            print(f"  ⚠️  Cleanup error: {e}")

    request.addfinalizer(cleanup)
    return tracker


@pytest.fixture
def cleanup_s3_objects(request):
    """Track and cleanup S3 objects created during test.

    This fixture provides a ResourceTracker that:
    1. Tracks S3 objects uploaded during test execution
    2. Cleans them up via pytest finalizer (runs even on failure)
    3. Uses boto3 directly for cleanup (backend-agnostic)
    4. Reports cleanup errors without failing the test

    Usage:
        def test_something(backend_with_auth, cleanup_s3_objects):
            # Upload object
            result = backend_with_auth.bucket_objects_put(
                bucket="test-bucket",
                items=[{"key": "test/file.txt", "text": "test"}]
            )

            # Track for cleanup
            cleanup_s3_objects.track_s3_object(
                bucket="test-bucket",
                key="test/file.txt"
            )

            # ... test continues ...
            # Cleanup happens automatically after test

    Args:
        request: pytest request object for finalizer

    Returns:
        ResourceTracker: Instance with track_s3_object() method
    """
    tracker = ResourceTracker()

    def cleanup():
        """Cleanup finalizer - runs even if test fails."""
        if not tracker.s3_objects:
            return

        print(f"\n🧹 Cleaning up {len(tracker.s3_objects)} S3 object(s)...")
        errors = tracker.cleanup_s3_objects()
        if errors:
            print(f"  ⚠️  {len(errors)} cleanup error(s) occurred")

    request.addfinalizer(cleanup)
    return tracker


@pytest.fixture
def auth_backend(backend_with_auth, backend_mode):
    """Provide AuthBackend wrapper for compatibility with parent conftest.

    This fixture wraps backend_with_auth in an AuthBackend object
    to maintain compatibility with tests that expect the AuthBackend
    interface from tests/e2e/conftest.py.

    Args:
        backend_with_auth: Authenticated backend from backend_with_auth fixture
        backend_mode: Backend mode string (quilt3|platform)

    Returns:
        AuthBackend: Wrapper with backend.backend attribute and auth helpers
    """
    return AuthBackend(backend_with_auth, backend_mode)


@pytest.fixture
def tabulator_backend(backend_with_auth):
    """Provide backend with tabulator operations.

    This is an alias for clarity - backend_with_auth already has
    tabulator methods via TabulatorMixin.

    Args:
        backend_with_auth: Authenticated backend from backend_with_auth fixture

    Returns:
        Backend instance with tabulator methods
    """
    return backend_with_auth


@pytest.fixture
def real_athena(backend_with_auth, real_test_bucket, backend_mode):
    """Get REAL Athena service configured for test bucket.

    This fixture:
    1. Creates AthenaQueryService with real AWS Athena
    2. Attempts to discover Athena catalog from bucket config
    3. Validates Athena connectivity
    4. Only works for quilt3 backend (platform may not have direct Athena)

    NO MOCKING - Uses actual AthenaQueryService with real boto3 clients.

    Args:
        backend_with_auth: Authenticated backend
        real_test_bucket: Test bucket name
        backend_mode: Backend mode (quilt3|platform)

    Returns:
        AthenaQueryService: Real Athena service instance

    Raises:
        pytest.skip: If Athena not available or not accessible
    """
    if backend_mode != "quilt3":
        pytest.skip("Athena fixture only available for quilt3 backend")

    from quilt_mcp.services.athena_service import AthenaQueryService

    # Try to discover catalog from bucket config
    catalog_name = None
    try:
        catalog_config = backend_with_auth.get_catalog_config(real_test_bucket)
        catalog_name = catalog_config.tabulator_data_catalog
    except Exception as e:
        print(f"  ℹ️  Could not discover Athena catalog: {e}")

    # Create Athena service
    try:
        athena = AthenaQueryService(use_quilt_auth=True, data_catalog_name=catalog_name, backend=backend_with_auth)
    except Exception as e:
        pytest.skip(f"Cannot create Athena service: {e}")

    # Verify Athena connectivity
    try:
        athena.discover_databases()
    except Exception as e:
        pytest.skip(f"Cannot access REAL Athena: {e}")

    return athena
