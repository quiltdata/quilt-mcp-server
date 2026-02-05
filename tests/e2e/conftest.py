import pytest

pytestmark = pytest.mark.usefixtures(
    "test_env",
    "clean_auth",
    "cached_athena_service_constructor",
    "backend_mode",
    "requires_catalog",
    "test_bucket",
    "test_registry",
)
