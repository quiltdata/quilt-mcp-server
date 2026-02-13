from __future__ import annotations

from types import SimpleNamespace

import pytest

from quilt_mcp.search.backends.base import BackendResponse, BackendStatus, BackendType, SearchResult
from quilt_mcp.search.tools.unified_search import UnifiedSearchEngine


class StubBackend:
    backend_type = BackendType.ELASTICSEARCH
    status = BackendStatus.AVAILABLE

    async def search(self, _query, _scope, _bucket, _filters, _limit):
        results = [
            SearchResult(
                id="1",
                type="file",
                title="a.csv",
                logical_key="a.csv",
                size=10,
                score=0.1,
                backend="elasticsearch",
            ),
            SearchResult(
                id="2",
                type="file",
                title="b.txt",
                logical_key="b.txt",
                size=9999,
                score=0.9,
                backend="elasticsearch",
            ),
        ]
        return BackendResponse(
            backend_type=BackendType.ELASTICSEARCH,
            status=BackendStatus.AVAILABLE,
            results=results,
            query_time_ms=12.0,
        )


@pytest.mark.asyncio
async def test_search_success_with_explanation_and_filters(monkeypatch):
    monkeypatch.setattr(UnifiedSearchEngine, "_initialize_backends", lambda self: None)
    engine = UnifiedSearchEngine()
    stub = StubBackend()
    monkeypatch.setattr(engine.registry, "_select_primary_backend", lambda: stub)
    monkeypatch.setattr(engine.registry, "get_backend_statuses", lambda: {"elasticsearch": "available"})
    monkeypatch.setattr("quilt_mcp.search.utils.get_search_backend_status", lambda: {"ok": True})

    response = await engine.search(
        query="find csv files larger than 5b",
        backend="auto",
        include_metadata=True,
        explain_query=True,
    )

    assert response["success"] is True
    assert response["backend_used"] == "elasticsearch"
    # post-filter should keep csv and remove txt
    assert len(response["results"]) == 1
    assert response["results"][0]["name"] == "a.csv"
    assert response["explanation"]["execution_summary"]["success"] is True
    assert response["backend_info"] == {"ok": True}


@pytest.mark.asyncio
async def test_search_returns_authentication_required_error(monkeypatch):
    monkeypatch.setattr(UnifiedSearchEngine, "_initialize_backends", lambda self: None)
    engine = UnifiedSearchEngine()

    # no selected backend + auth error marker present
    monkeypatch.setattr(engine.registry, "_select_primary_backend", lambda: None)
    engine.registry._backends = {BackendType.ELASTICSEARCH: SimpleNamespace(_auth_error=True)}
    monkeypatch.setattr(engine.registry, "get_backend_statuses", lambda: {"elasticsearch": "unavailable"})

    response = await engine.search("csv")
    assert response["success"] is False
    assert response["error_category"] == "authentication"
    assert response["backend_used"] is None


@pytest.mark.asyncio
async def test_search_returns_not_available_error(monkeypatch):
    monkeypatch.setattr(UnifiedSearchEngine, "_initialize_backends", lambda self: None)
    engine = UnifiedSearchEngine()

    monkeypatch.setattr(engine.registry, "_select_primary_backend", lambda: None)
    engine.registry._backends = {BackendType.ELASTICSEARCH: SimpleNamespace()}
    monkeypatch.setattr(engine.registry, "get_backend_statuses", lambda: {"elasticsearch": "unavailable"})

    response = await engine.search("csv")
    assert response["success"] is False
    assert response["error_category"] == "not_applicable"
    assert response["backend_used"] is None


def test_process_backend_results_and_post_filters():
    engine = UnifiedSearchEngine.__new__(UnifiedSearchEngine)

    response = BackendResponse(
        backend_type=BackendType.ELASTICSEARCH,
        status=BackendStatus.AVAILABLE,
        results=[
            SearchResult(
                id="r1",
                type="file",
                title="f1.csv",
                logical_key="folder/f1.csv",
                score=0.1,
                size=5,
                backend="es",
            ),
            SearchResult(
                id="r2",
                type="package",
                title="pkg",
                package_name="team/pkg",
                score=0.9,
                size=500,
                backend="es",
            ),
        ],
    )
    processed = engine._process_backend_results(response, limit=10)
    assert processed[0]["name"] == "team/pkg"

    filtered = engine._apply_post_filters(
        processed,
        {"file_extensions": ["csv"], "size_min": 1, "size_max": 100},
    )
    # package kept, csv file kept
    assert len(filtered) == 2


def test_generate_explanation_for_error_backend():
    engine = UnifiedSearchEngine.__new__(UnifiedSearchEngine)
    analysis = SimpleNamespace(query_type=SimpleNamespace(value="file_search"), confidence=0.7, keywords=["csv"], filters={})
    backend_response = BackendResponse(
        backend_type=BackendType.ELASTICSEARCH,
        status=BackendStatus.ERROR,
        results=[],
        query_time_ms=1.0,
        error_message="boom",
    )
    selected_backend = SimpleNamespace(backend_type=SimpleNamespace(value="elasticsearch"))

    explanation = engine._generate_explanation(analysis, backend_response, selected_backend)
    assert explanation["execution_summary"]["success"] is False
    assert explanation["execution_summary"]["error"] == "boom"
