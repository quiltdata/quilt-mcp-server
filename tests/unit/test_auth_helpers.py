from __future__ import annotations

import pytest

from quilt_mcp.runtime_context import RuntimeAuthState
from quilt_mcp.services.auth_service import JwtContext
from quilt_mcp.services.bearer_auth_service import AuthorizationDecision, JwtAuthResult
from quilt_mcp.tools import auth_helpers


class DummySession:
    def __init__(self) -> None:
        self.created: dict[str, object] = {}

    def client(self, service: str):
        handle = object()
        self.created[service] = handle
        return handle


def _make_jwt_context(session: DummySession) -> JwtContext:
    result = JwtAuthResult(
        token="token",
        claims={"permissions": ["s3:GetObject"]},
        permissions=["s3:GetObject"],
        buckets=["example-bucket"],
        roles=[],
    )
    state = RuntimeAuthState(scheme="jwt", extras={"jwt_auth_result": result, "boto3_session": session})
    return JwtContext(result=result, session=session, auth_state=state)


class DummyAuthService:
    def __init__(
        self,
        *,
        jwt_context: JwtContext | None = None,
        require_jwt: bool = False,
        iam_session: DummySession | None = None,
        decision: AuthorizationDecision | None = None,
    ) -> None:
        self._jwt_context = jwt_context
        self._require_jwt = require_jwt
        self._iam_session = iam_session or DummySession()
        self._decision = decision or AuthorizationDecision(allowed=True)

    def get_jwt_context(self) -> JwtContext | None:
        return self._jwt_context

    def authorize_jwt_tool(self, jwt_context: JwtContext, tool_name, tool_args):
        return self._decision

    def require_jwt(self) -> bool:
        return self._require_jwt

    def get_iam_session(self):
        return self._iam_session


@pytest.fixture
def patch_auth_service(monkeypatch):
    def apply(service: DummyAuthService):
        monkeypatch.setattr(auth_helpers, "get_auth_service", lambda: service)
        return service

    return apply


def test_check_s3_authorization_prefers_jwt_session(patch_auth_service):
    session = DummySession()
    jwt_context = _make_jwt_context(session)
    patch_auth_service(DummyAuthService(jwt_context=jwt_context))

    ctx = auth_helpers.check_s3_authorization("bucket_objects_list", {"bucket": "example"})

    assert ctx.authorized is True
    assert ctx.auth_type == "jwt"
    assert ctx.s3_client is session.created["s3"]


def test_check_s3_authorization_falls_back_to_iam(patch_auth_service):
    iam_session = DummySession()
    patch_auth_service(DummyAuthService(jwt_context=None, iam_session=iam_session))

    ctx = auth_helpers.check_s3_authorization("bucket_objects_list", {"bucket": "example"})

    assert ctx.authorized is True
    assert ctx.auth_type == "iam"
    assert ctx.s3_client is iam_session.created["s3"]


def test_check_s3_authorization_strict_mode_requires_jwt(patch_auth_service):
    patch_auth_service(DummyAuthService(jwt_context=None, require_jwt=True))

    ctx = auth_helpers.check_s3_authorization("bucket_objects_list", {"bucket": "example"})

    assert ctx.authorized is False
    assert ctx.strict is True
    error = ctx.error_response()
    assert error["strict_mode"] is True
    assert "JWT" in error["error"]
