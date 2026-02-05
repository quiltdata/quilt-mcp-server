import pytest
from unittest.mock import Mock

from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

pytestmark = pytest.mark.usefixtures(
    "test_env",
    "clean_auth",
    "cached_athena_service_constructor",
)


@pytest.fixture
def mock_backend():
    """Provide mocked backend for functional tests."""
    return Mock(spec=Quilt3_Backend)


@pytest.fixture
def requires_catalog(mock_backend):
    """Provide a mocked backend instead of real catalog access."""
    return mock_backend


@pytest.fixture(scope="session")
def test_bucket() -> str:
    """Provide a placeholder bucket name for mocked tests."""
    return "test-bucket"


@pytest.fixture(scope="session")
def test_registry(test_bucket: str) -> str:
    """Provide a placeholder registry URI for mocked tests."""
    return f"s3://{test_bucket}"
