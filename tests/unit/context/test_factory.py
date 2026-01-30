"""Unit tests for RequestContextFactory."""

from __future__ import annotations

import gc
import uuid
import weakref

import pytest

from quilt_mcp.context.exceptions import ServiceInitializationError, TenantValidationError
from quilt_mcp.context.factory import RequestContextFactory
from quilt_mcp.runtime_context import RuntimeAuthState, push_runtime_context, reset_runtime_context
from quilt_mcp.services.auth_service import reset_auth_service
from quilt_mcp.services.iam_auth_service import IAMAuthService
from quilt_mcp.services.jwt_auth_service import JWTAuthService


def test_factory_auto_mode_reads_env(monkeypatch):
    monkeypatch.setenv("QUILT_MULTITENANT_MODE", "true")
    factory = RequestContextFactory()
    assert factory.mode == "multitenant"

    monkeypatch.setenv("QUILT_MULTITENANT_MODE", "false")
    factory = RequestContextFactory()
    assert factory.mode == "single-user"


def test_factory_explicit_mode_overrides_env(monkeypatch):
    monkeypatch.setenv("QUILT_MULTITENANT_MODE", "false")
    factory = RequestContextFactory(mode="multitenant")
    assert factory.mode == "multitenant"


def test_factory_create_context_uses_jwt_auth(monkeypatch):
    auth_state = RuntimeAuthState(scheme="Bearer", access_token="token", claims={"sub": "user-1"})
    token_handle = push_runtime_context(environment="web-service", auth=auth_state)
    try:
        factory = RequestContextFactory(mode="single-user")
        context = factory.create_context()
    finally:
        reset_runtime_context(token_handle)

    assert isinstance(context.auth_service, JWTAuthService)


def test_factory_create_context_uses_iam_auth(monkeypatch):
    factory = RequestContextFactory(mode="single-user")
    context = factory.create_context()
    assert isinstance(context.auth_service, IAMAuthService)


def test_factory_create_context_requires_tenant_in_multitenant_mode():
    factory = RequestContextFactory(mode="multitenant")
    with pytest.raises(TenantValidationError):
        factory.create_context()


def test_factory_create_context_sets_default_tenant_in_single_user_mode():
    factory = RequestContextFactory(mode="single-user")
    context = factory.create_context()
    assert context.tenant_id == "default"


def test_factory_create_context_generates_request_id():
    factory = RequestContextFactory(mode="single-user")
    context = factory.create_context()
    assert context.request_id
    uuid.UUID(context.request_id)


def test_factory_create_context_requires_auth_when_jwt_mode_enabled(monkeypatch):
    monkeypatch.setenv("MCP_REQUIRE_JWT", "true")
    reset_auth_service()
    factory = RequestContextFactory(mode="single-user")
    with pytest.raises(ServiceInitializationError):
        factory.create_context()


def test_factory_creates_fresh_auth_service_instances(monkeypatch):
    monkeypatch.delenv("MCP_REQUIRE_JWT", raising=False)
    reset_auth_service()
    factory = RequestContextFactory(mode="single-user")
    context_a = factory.create_context()
    context_b = factory.create_context()
    assert context_a.auth_service is not context_b.auth_service


def test_factory_service_creation_errors_are_wrapped(monkeypatch):
    factory = RequestContextFactory(mode="single-user")

    def _boom():
        raise RuntimeError("nope")

    monkeypatch.setattr(factory, "_create_auth_service", _boom)

    with pytest.raises(ServiceInitializationError) as excinfo:
        factory.create_context()

    assert excinfo.value.service_name == "AuthService"
    assert "nope" in excinfo.value.reason


def test_factory_service_instances_are_gc_eligible(monkeypatch):
    factory = RequestContextFactory(mode="single-user")

    class _Sentinel:
        def get_user_identity(self):
            return {}

    monkeypatch.setattr(factory, "_create_auth_service", lambda: _Sentinel())

    context = factory.create_context()
    ref = weakref.ref(context.auth_service)
    del context
    gc.collect()

    assert ref() is None
