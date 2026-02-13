from __future__ import annotations

import base64
import json
import types
from pathlib import Path

import boto3
import pytest

from quilt_mcp.utils import common


def _jwt(payload: dict) -> str:
    def enc(obj):
        raw = json.dumps(obj).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")

    return f"{enc({'alg':'none','typ':'JWT'})}.{enc(payload)}."


def test_runtime_boto3_session_paths(monkeypatch):
    runtime_module = types.SimpleNamespace(get_runtime_auth=lambda: None)
    monkeypatch.setitem(__import__("sys").modules, "quilt_mcp.context.runtime_context", runtime_module)
    assert common._runtime_boto3_session() is None

    session = boto3.Session()
    runtime_module2 = types.SimpleNamespace(get_runtime_auth=lambda: types.SimpleNamespace(extras={"boto3_session": session}))
    monkeypatch.setitem(__import__("sys").modules, "quilt_mcp.context.runtime_context", runtime_module2)
    assert common._runtime_boto3_session() is session

    runtime_module3 = types.SimpleNamespace(
        get_runtime_auth=lambda: types.SimpleNamespace(
            extras={
                "aws_credentials": {
                    "access_key_id": "a",
                    "secret_access_key": "b",
                    "session_token": "c",
                    "region": "us-west-2",
                }
            }
        )
    )
    monkeypatch.setitem(__import__("sys").modules, "quilt_mcp.context.runtime_context", runtime_module3)
    created = common._runtime_boto3_session()
    assert isinstance(created, boto3.Session)


def test_s3_and_sts_client_priority(monkeypatch):
    runtime_session = types.SimpleNamespace(client=lambda name: f"runtime-{name}")
    monkeypatch.setattr(common, "_runtime_boto3_session", lambda: runtime_session)
    assert common.get_s3_client() == "runtime-s3"
    assert common.get_sts_client() == "runtime-sts"

    monkeypatch.setattr(common, "_runtime_boto3_session", lambda: None)
    jwt_module = types.SimpleNamespace(
        JWTAuthService=lambda: types.SimpleNamespace(get_boto3_session=lambda: types.SimpleNamespace(client=lambda n: f"jwt-{n}"))
    )
    monkeypatch.setitem(__import__("sys").modules, "quilt_mcp.services.jwt_auth_service", jwt_module)
    assert common.get_s3_client() == "jwt-s3"
    assert common.get_sts_client() == "jwt-sts"

    # Force JWT path failure to exercise quilt3 fallback.
    class BadJWT:
        def __init__(self):
            raise RuntimeError("bad jwt")

    monkeypatch.setitem(
        __import__("sys").modules,
        "quilt_mcp.services.jwt_auth_service",
        types.SimpleNamespace(JWTAuthService=BadJWT),
    )
    quilt3_module = types.SimpleNamespace(
        logged_in=lambda: True,
        get_boto3_session=lambda: types.SimpleNamespace(client=lambda n: f"quilt3-{n}"),
    )
    monkeypatch.setitem(__import__("sys").modules, "quilt3", quilt3_module)
    assert common.get_s3_client() == "quilt3-s3"
    assert common.get_sts_client() == "quilt3-sts"

    # Final fallback to boto3.client
    quilt3_module2 = types.SimpleNamespace(logged_in=lambda: False)
    monkeypatch.setitem(__import__("sys").modules, "quilt3", quilt3_module2)
    monkeypatch.setattr(common.boto3, "client", lambda name: f"default-{name}")
    assert common.get_s3_client() == "default-s3"
    assert common.get_sts_client() == "default-sts"


def test_get_jwt_from_auth_config(monkeypatch, tmp_path):
    home = tmp_path / "home"
    auth_dir = home / ".quilt"
    auth_dir.mkdir(parents=True)
    auth_file = auth_dir / "auth.json"
    auth_file.write_text(
        json.dumps({"tokens": {"https://registry.example.com": {"token": "abc.def.ghi"}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(common.pathlib.Path, "home", lambda: home)

    assert common.get_jwt_from_auth_config("https://registry.example.com") == "abc.def.ghi"
    assert common.get_jwt_from_auth_config("https://missing.example.com") is None

    auth_file.write_text("{", encoding="utf-8")
    assert common.get_jwt_from_auth_config("https://registry.example.com") is None

    auth_file.unlink()
    assert common.get_jwt_from_auth_config("https://registry.example.com") is None


def test_extract_jwt_claims_unsafe():
    token = _jwt({"sub": "u1", "exp": 123})
    claims = common.extract_jwt_claims_unsafe(token)
    assert claims["sub"] == "u1"
    assert claims["exp"] == 123

    with pytest.raises(ValueError, match="Malformed JWT token"):
        common.extract_jwt_claims_unsafe("not-a-jwt")

    bad_payload = "a." + base64.urlsafe_b64encode(b'"not-json-object"').decode("utf-8").rstrip("=") + ".c"
    with pytest.raises(ValueError, match="JWT payload must be a JSON object"):
        common.extract_jwt_claims_unsafe(bad_payload)
