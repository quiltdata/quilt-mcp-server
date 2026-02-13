"""Additional unit tests for search tool wrappers and GraphQL helpers."""

import asyncio
from unittest.mock import Mock, patch

import pytest
import requests

from quilt_mcp.tools import search


def test_extract_page_title_and_snippet_uses_meta_description():
    html = """
    <html>
      <head>
        <title>  Quilt   Docs  </title>
        <meta name="description" content="  Helpful docs summary.  ">
      </head>
      <body><p>Paragraph fallback.</p></body>
    </html>
    """
    response = Mock()
    response.text = html
    response.raise_for_status.return_value = None

    with patch("quilt_mcp.tools.search.requests.get", return_value=response):
        title, snippet = search._extract_page_title_and_snippet("https://docs.quilt.bio/x")

    assert title == "Quilt Docs"
    assert snippet == "Helpful docs summary."


def test_extract_page_title_and_snippet_falls_back_to_paragraph():
    html = "<html><head><title>T</title></head><body><p>First <b>paragraph</b> text.</p></body></html>"
    response = Mock()
    response.text = html
    response.raise_for_status.return_value = None

    with patch("quilt_mcp.tools.search.requests.get", return_value=response):
        title, snippet = search._extract_page_title_and_snippet("https://docs.quilt.bio/y")

    assert title == "T"
    assert snippet == "First paragraph text."


def test_parse_docs_sitemap_xml_skips_entries_without_loc():
    xml_text = "<urlset><url><lastmod>2026-01-01</lastmod></url></urlset>"
    is_index, entries = search._parse_docs_sitemap_xml(xml_text)
    assert is_index is False
    assert entries == []


def test_search_catalog_count_only_normalizes_bucket_and_defaults_backend():
    engine = Mock()
    engine.search = Mock(return_value=None)

    async def _search(**kwargs):
        return {"total_results": 7}

    engine.search.side_effect = _search

    with patch("quilt_mcp.tools.search.UnifiedSearchEngine", return_value=engine):
        result = search.search_catalog(
            query="csv",
            scope="file",
            bucket="s3://bucket-a/path",
            backend="",
            count_only=True,
        )

    assert result["success"] is True
    assert result["total_count"] == 7
    assert result["bucket"] == "bucket-a"


def test_search_catalog_success_returns_serialized_success_model():
    engine = Mock()

    async def _search(**kwargs):
        return {
            "success": True,
            "query": kwargs["query"],
            "scope": kwargs["scope"],
            "bucket": kwargs["bucket"],
            "results": [
                {"id": "1", "type": "file", "title": "README.md", "score": 0.9, "backend": "elasticsearch"},
            ],
            "total_results": 1,
            "query_time_ms": 12.3,
        }

    engine.search.side_effect = _search
    with patch("quilt_mcp.tools.search.UnifiedSearchEngine", return_value=engine):
        result = search.search_catalog(query="README", scope="file", bucket="my-bucket")

    assert result["success"] is True
    assert result["total_results"] == 1
    assert result["results"][0]["title"] == "README.md"


def test_search_catalog_returns_error_dict_for_unsuccessful_result():
    engine = Mock()

    async def _search(**kwargs):
        return {
            "success": False,
            "query": kwargs["query"],
            "scope": kwargs["scope"],
            "bucket": kwargs["bucket"],
            "error": "backend unavailable",
        }

    engine.search.side_effect = _search
    with patch("quilt_mcp.tools.search.UnifiedSearchEngine", return_value=engine):
        result = search.search_catalog(query="x", scope="global", bucket="")

    assert result["success"] is False
    assert "backend unavailable" in result["error"]


def test_search_catalog_maps_timeout_and_os_errors():
    engine = Mock()

    async def _timeout(**_kwargs):
        raise asyncio.TimeoutError("timed out")

    async def _oserror(**_kwargs):
        raise OSError("disk io")

    engine.search.side_effect = _timeout
    with patch("quilt_mcp.tools.search.UnifiedSearchEngine", return_value=engine):
        with pytest.raises(RuntimeError, match="Search timeout"):
            search.search_catalog(query="x", count_only=True)

    engine.search.side_effect = _oserror
    with patch("quilt_mcp.tools.search.UnifiedSearchEngine", return_value=engine):
        with pytest.raises(RuntimeError, match="Search I/O error"):
            search.search_catalog(query="x", count_only=True)


def test_search_suggest_default_types_and_error_fallback():
    with patch("quilt_mcp.tools.search._search_suggest", return_value={"success": True}) as mock_suggest:
        result = search.search_suggest(partial_query="csv")
    assert result["success"] is True
    assert mock_suggest.call_args.kwargs["suggestion_types"] == ["auto"]

    with patch("quilt_mcp.tools.search._search_suggest", side_effect=ValueError("bad")):
        error_result = search.search_suggest(partial_query="csv")
    assert error_result["success"] is False
    assert "Search suggestions failed" in error_result["error"]


def test_search_explain_success_and_error_paths():
    with patch(
        "quilt_mcp.tools.search._search_explain",
        return_value={
            "backend_selection": {"selected_backends": ["elasticsearch"]},
            "query_analysis": {"detected_type": "metadata"},
        },
    ):
        ok = search.search_explain(query="foo")
    assert ok.success is True
    assert ok.backends_selected == ["elasticsearch"]

    with patch("quilt_mcp.tools.search._search_explain", side_effect=RuntimeError("boom")):
        err = search.search_explain(query="foo")
    assert err.success is False
    assert "Search explanation failed" in err.error


def test_search_docs_quilt_bio_rejects_empty_alphanumeric_query():
    result = search.search_docs_quilt_bio(query="!!!")
    assert result["success"] is False
    assert "at least one alphanumeric term" in result["error"]


def test_search_docs_quilt_bio_skips_non_docs_domain_and_snippet_fetch_failures(monkeypatch):
    sitemap = """<urlset>
      <url><loc>https://example.com/nope</loc></url>
      <url><loc>https://docs.quilt.bio/path/auth</loc></url>
    </urlset>"""

    class _R:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    monkeypatch.setattr(search.requests, "get", lambda *_args, **_kwargs: _R(sitemap))

    def _raise(_url: str):
        raise requests.RequestException("no page")

    monkeypatch.setattr(search, "_extract_page_title_and_snippet", _raise)
    result = search.search_docs_quilt_bio(query="auth")

    assert result["success"] is True
    assert len(result["results"]) == 1
    assert result["results"][0]["url"] == "https://docs.quilt.bio/path/auth"


def test_search_graphql_and_search_objects_graphql_paths():
    with patch("quilt_mcp.tools.search._get_quilt_ops", return_value=None):
        unavailable = search.search_graphql(query="query { x }")
    assert unavailable.success is False

    ops = Mock()
    ops.execute_graphql_query.return_value = {"errors": [{"message": "bad"}]}
    with patch("quilt_mcp.tools.search._get_quilt_ops", return_value=ops):
        gql_error = search.search_graphql(query="query { x }")
    assert gql_error.success is False
    assert "GraphQL errors" in gql_error.error

    ops.execute_graphql_query.side_effect = Exception("boom")
    with patch("quilt_mcp.tools.search._get_quilt_ops", return_value=ops):
        gql_exception = search.search_graphql(query="query { x }")
    assert gql_exception.success is False
    assert "GraphQL request failed" in gql_exception.error

    with patch(
        "quilt_mcp.tools.search.search_graphql",
        return_value={"success": False, "error": "oops"},
    ):
        failed = search.search_objects_graphql(bucket="s3://bucket-x/path")
    assert failed["success"] is False
    assert failed["bucket"] == "bucket-x"

    with patch(
        "quilt_mcp.tools.search.search_graphql",
        return_value={
            "success": True,
            "data": {
                "objects": {
                    "edges": [
                        {"node": {"key": "a.csv", "size": 1, "updated": "t", "contentType": "text/csv", "extension": "csv"}},
                        "not-a-dict",
                    ],
                    "pageInfo": {"endCursor": "cur", "hasNextPage": True},
                }
            },
        },
    ):
        ok = search.search_objects_graphql(bucket="bucket-x", first=5000, after="")
    assert ok["success"] is True
    assert ok["objects"][0]["key"] == "a.csv"
    assert ok["page_info"]["has_next_page"] is True
