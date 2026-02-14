from __future__ import annotations

from quilt_mcp.search.tools import search_suggest as mod
from quilt_mcp.search.tools.search_suggest import SearchSuggestionEngine


def test_suggest_auto_populates_categories_and_total_count():
    engine = SearchSuggestionEngine()
    result = engine.suggest("csv files", context="team/pkg", suggestion_types=["auto"], limit=5)

    assert result["partial_query"] == "csv files"
    assert result["context"] == "team/pkg"
    assert "query_completions" in result["suggestions"]
    assert "context_suggestions" in result["suggestions"]
    assert result["total_suggestions"] == sum(len(v) for v in result["suggestions"].values())


def test_related_queries_falls_back_when_parser_raises(monkeypatch):
    engine = SearchSuggestionEngine()

    class ExplodingParser:
        def parse(self, _partial: str):
            raise RuntimeError("boom")

    monkeypatch.setattr(engine, "parser", ExplodingParser())
    related = engine._generate_related_queries("whatever", limit=5)
    assert isinstance(related, list)


def test_file_type_suggestions_handles_regex_and_partial_matches():
    engine = SearchSuggestionEngine()
    suggestions = engine._generate_file_type_suggestions("need csv and json files", limit=10)

    file_types = {s["file_type"] for s in suggestions}
    assert "csv" in file_types
    assert "json" in file_types


def test_context_suggestions_bucket_and_package_paths():
    engine = SearchSuggestionEngine()

    package_suggestions = engine._generate_context_suggestions("data", "org/pkg", limit=3)
    bucket_suggestions = engine._generate_context_suggestions("data", "my-bucket", limit=3)

    assert package_suggestions[0]["context_type"] == "packageEntry"
    assert bucket_suggestions[0]["context_type"] == "bucket"


def test_completion_confidence_exact_and_empty_partial():
    engine = SearchSuggestionEngine()
    assert engine._calculate_completion_confidence("csv files", "CSV files") == 1.0
    assert engine._calculate_completion_confidence("", "CSV files") == 0.1


def test_domain_relevance_boosts_for_overlap_and_domain():
    engine = SearchSuggestionEngine()
    score = engine._calculate_domain_relevance("genomics rna-seq", "RNA-seq data", "genomics")
    assert score > 0.5


def test_search_suggest_global_engine_and_error_path(monkeypatch):
    # reset singleton
    monkeypatch.setattr(mod, "_suggestion_engine", None)
    first = mod.get_suggestion_engine()
    second = mod.get_suggestion_engine()
    assert first is second

    class BrokenEngine:
        def suggest(self, *_args, **_kwargs):
            raise RuntimeError("failure")

    monkeypatch.setattr(mod, "get_suggestion_engine", lambda: BrokenEngine())
    result = mod.search_suggest("abc")
    assert result["success"] is False
    assert "failed" in result["error"].lower()
