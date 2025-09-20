"""Integration test fixtures."""

from functools import lru_cache
from typing import Callable

import pytest

from quilt_mcp.services.athena_service import AthenaQueryService


@lru_cache(maxsize=2)
def _cached_athena_service(use_quilt_auth: bool) -> AthenaQueryService:
    """Cache Athena service instances by auth mode."""

    return AthenaQueryService(use_quilt_auth=use_quilt_auth)


@pytest.fixture(scope="session")
def athena_service_factory() -> Callable[[bool], AthenaQueryService]:
    """Return a factory that reuses cached Athena service instances."""

    def factory(use_quilt_auth: bool = True) -> AthenaQueryService:
        return _cached_athena_service(bool(use_quilt_auth))

    return factory


@pytest.fixture(scope="session")
def athena_service_quilt(athena_service_factory) -> AthenaQueryService:
    """Session-scoped Athena service using quilt authentication."""

    return athena_service_factory(True)


@pytest.fixture(scope="session")
def athena_service_builtin(athena_service_factory) -> AthenaQueryService:
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
