from __future__ import annotations

import importlib

import pytest
import requests

search = importlib.import_module("quilt_mcp.tools.search")

TOP_LEVEL_SITEMAP = """<?xml version="1.0" encoding="utf-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://docs.quilt.bio/sitemap-pages.xml</loc></sitemap>
  <sitemap><loc>https://docs.quilt.bio/version-5.0.x/sitemap-pages.xml</loc></sitemap>
</sitemapindex>
"""

LATEST_PAGES = """<?xml version="1.0" encoding="utf-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://docs.quilt.bio/architecture</loc><lastmod>2025-08-18T16:05:31.208Z</lastmod></url>
  <url><loc>https://docs.quilt.bio/quilt-platform-catalog-user/query</loc><lastmod>2025-12-09T16:24:00.420Z</lastmod></url>
  <url><loc>https://docs.quilt.bio/quilt-platform-catalog-admin/tabulator</loc><lastmod>2025-12-11T16:44:26.386Z</lastmod></url>
  <url><loc>https://docs.quilt.bio/quilt-platform-catalog-admin/authentication</loc><lastmod>2025-12-11T16:44:26.386Z</lastmod></url>
</urlset>
"""

VERSIONED_PAGES = """<?xml version="1.0" encoding="utf-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://docs.quilt.bio/version-5.0.x/legacy/tabulator</loc><lastmod>2024-01-01T00:00:00.000Z</lastmod></url>
</urlset>
"""


class _MockResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status={self.status_code}")


def _mock_requests_get(url: str, timeout: float):  # noqa: ARG001
    mapping = {
        "https://docs.quilt.bio/sitemap.xml": _MockResponse(TOP_LEVEL_SITEMAP),
        "https://docs.quilt.bio/sitemap-pages.xml": _MockResponse(LATEST_PAGES),
        "https://docs.quilt.bio/version-5.0.x/sitemap-pages.xml": _MockResponse(VERSIONED_PAGES),
    }
    if url not in mapping:
        raise requests.RequestException(f"Unexpected URL: {url}")
    return mapping[url]


def test_search_docs_quilt_bio_returns_ranked_results(monkeypatch):
    monkeypatch.setattr(search.requests, "get", _mock_requests_get)
    monkeypatch.setattr(search, "_extract_page_title_and_snippet", lambda url: ("", ""))  # noqa: ARG005

    result = search.search_docs_quilt_bio(query="tabulator auth", limit=3)

    assert result["success"] is True
    assert result["total_matches"] >= 2
    assert len(result["results"]) <= 3
    assert result["results"][0]["url"].endswith("/tabulator")


def test_search_docs_quilt_bio_excludes_versioned_docs_by_default(monkeypatch):
    monkeypatch.setattr(search.requests, "get", _mock_requests_get)
    monkeypatch.setattr(search, "_extract_page_title_and_snippet", lambda url: ("", ""))  # noqa: ARG005

    result = search.search_docs_quilt_bio(query="legacy tabulator", limit=10)

    assert result["success"] is True
    assert all("/version-" not in item["url"] for item in result["results"])


def test_search_docs_quilt_bio_includes_versioned_docs_when_requested(monkeypatch):
    monkeypatch.setattr(search.requests, "get", _mock_requests_get)
    monkeypatch.setattr(search, "_extract_page_title_and_snippet", lambda url: ("", ""))  # noqa: ARG005

    result = search.search_docs_quilt_bio(query="legacy tabulator", limit=10, include_versioned_docs=True)

    assert result["success"] is True
    assert any("/version-" in item["url"] for item in result["results"])


def test_search_docs_quilt_bio_returns_error_when_sitemap_fails(monkeypatch):
    def _raise_request_error(url: str, timeout: float):  # noqa: ARG001
        raise requests.RequestException("network down")

    monkeypatch.setattr(search.requests, "get", _raise_request_error)

    result = search.search_docs_quilt_bio(query="auth")

    assert result["success"] is False
    assert "Failed to fetch docs sitemap" in result["error"]


def test_search_docs_quilt_bio_query_matching_is_case_insensitive(monkeypatch):
    monkeypatch.setattr(search.requests, "get", _mock_requests_get)
    monkeypatch.setattr(search, "_extract_page_title_and_snippet", lambda url: ("", ""))  # noqa: ARG005

    result = search.search_docs_quilt_bio(query="TaBuLaToR", limit=5)

    assert result["success"] is True
    assert any(item["url"].endswith("/tabulator") for item in result["results"])
