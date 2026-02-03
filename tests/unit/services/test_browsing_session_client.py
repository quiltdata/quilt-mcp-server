"""Unit tests for BrowsingSessionClient."""

from __future__ import annotations

import time

import pytest

from quilt_mcp.services.browsing_session_client import BrowsingSessionClient


class _Response:
    def __init__(self, status_code: int, payload: dict | None = None, headers: dict | None = None, url: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}
        self.url = url

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload

    @property
    def ok(self):
        return 200 <= self.status_code < 300


class _Session:
    def __init__(self, post_responses, get_responses):
        self.headers = {}
        self.post_calls = []
        self.get_calls = []
        self._post_responses = list(post_responses)
        self._get_responses = list(get_responses)

    def post(self, url, json, timeout):
        self.post_calls.append({"url": url, "json": json, "timeout": timeout})
        return self._post_responses.pop(0)

    def get(self, url, allow_redirects, timeout):
        self.get_calls.append({"url": url, "allow_redirects": allow_redirects, "timeout": timeout})
        return self._get_responses.pop(0)


def _session_response(session_id: str, expires: str):
    return _Response(
        200,
        payload={
            "data": {
                "browsingSessionCreate": {
                    "__typename": "BrowsingSession",
                    "id": session_id,
                    "expires": expires,
                }
            }
        },
    )


def test_browsing_session_cache_reuse(monkeypatch):
    BrowsingSessionClient._cache = {}
    session = _Session(
        post_responses=[_session_response("session-1", "2099-01-01T00:00:00Z")],
        get_responses=[
            _Response(302, headers={"Location": "https://signed-url-1"}),
            _Response(302, headers={"Location": "https://signed-url-2"}),
        ],
    )

    client = BrowsingSessionClient(
        catalog_url="https://catalog.example.com",
        graphql_endpoint="https://registry.example.com/graphql",
        access_token="token",
        session=session,
        ttl_seconds=180,
    )

    url1 = client.get_presigned_url(scope="s3://bucket#package=team/pkg&hash=abc", path="file.txt")
    url2 = client.get_presigned_url(scope="s3://bucket#package=team/pkg&hash=abc", path="file2.txt")

    assert url1 == "https://signed-url-1"
    assert url2 == "https://signed-url-2"
    assert len(session.post_calls) == 1


def test_browsing_session_refreshes_after_expiry(monkeypatch):
    BrowsingSessionClient._cache = {}
    now = 1_700_000_000
    monkeypatch.setattr(time, "time", lambda: now)

    session = _Session(
        post_responses=[
            _session_response("session-1", "1970-01-01T00:00:01Z"),
            _session_response("session-2", "2099-01-01T00:00:00Z"),
        ],
        get_responses=[
            _Response(302, headers={"Location": "https://signed-url-1"}),
            _Response(302, headers={"Location": "https://signed-url-2"}),
        ],
    )

    client = BrowsingSessionClient(
        catalog_url="https://catalog.example.com",
        graphql_endpoint="https://registry.example.com/graphql",
        access_token="token",
        session=session,
        ttl_seconds=180,
    )

    url1 = client.get_presigned_url(scope="s3://bucket#package=team/pkg&hash=abc", path="file.txt")
    url2 = client.get_presigned_url(scope="s3://bucket#package=team/pkg&hash=abc", path="file.txt")

    assert url1 == "https://signed-url-1"
    assert url2 == "https://signed-url-2"
    assert len(session.post_calls) == 2
