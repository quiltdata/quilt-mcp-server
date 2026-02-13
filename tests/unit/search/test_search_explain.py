from __future__ import annotations

from quilt_mcp.search.tools import search_explain as mod
from quilt_mcp.search.tools.search_explain import SearchExplainer


def test_explain_includes_optional_sections_and_query_analysis():
    explainer = SearchExplainer()
    result = explainer.explain(
        "largest csv files in global scope",
        show_backends=True,
        show_performance=True,
        show_alternatives=True,
    )

    assert result["query"] == "largest csv files in global scope"
    assert "query_analysis" in result
    assert "backend_selection" in result
    assert "performance_estimate" in result
    assert "alternative_queries" in result
    assert "optimization_suggestions" in result


def test_backend_selection_handles_unknown_backend_name():
    explainer = SearchExplainer()
    analysis = mod.parse_query("csv files")
    analysis.suggested_backends = ["nonexistent"]

    selection = explainer._explain_backend_selection(analysis)
    assert selection["selection_reasoning"]["nonexistent"]["expected_speed"] == "Unknown"


def test_estimate_performance_handles_unknown_backend_and_scalability_notes():
    explainer = SearchExplainer()
    analysis = mod.parse_query("one two three four five six csv files in global")
    analysis.suggested_backends = ["unknown"]
    analysis.filters = {"size_min": 10}

    perf = explainer._estimate_performance(analysis)
    assert perf["estimated_time_ranges"]["unknown"]["typical_ms"] == 1000
    assert any("many keywords" in note.lower() for note in perf["scalability_notes"])
    assert any("filters will improve performance" in note.lower() for note in perf["scalability_notes"])


def test_suggest_alternatives_for_global_without_filters():
    explainer = SearchExplainer()
    analysis = mod.parse_query("genomics data files")
    analysis.filters = {}
    alternatives = explainer._suggest_alternatives(analysis)

    assert len(alternatives) >= 1
    assert any("faster" in alt["expected_benefit"].lower() or "relevant" in alt["expected_benefit"].lower() for alt in alternatives)


def test_helper_methods_cover_reasoning_and_fallbacks():
    explainer = SearchExplainer()
    analysis = mod.parse_query("csv")

    complexity = explainer._assess_query_complexity(analysis)
    base_time = explainer._get_base_time_estimate(mod.BackendType.ELASTICSEARCH)
    reason = explainer._get_selection_reason(mod.QueryType.FILE_SEARCH, mod.BackendType.ELASTICSEARCH)
    fallback = explainer._build_fallback_chain(mod.QueryType.CONTENT_SEARCH)

    assert complexity in {"simple", "moderate", "complex"}
    assert base_time == 100
    assert "text search" in reason.lower()
    assert fallback == ["elasticsearch"]


def test_search_explain_wrapper_error_path(monkeypatch):
    class BrokenExplainer:
        def explain(self, *_args, **_kwargs):
            raise RuntimeError("kaboom")

    monkeypatch.setattr(mod, "get_explainer", lambda: BrokenExplainer())
    result = mod.search_explain("csv")
    assert result["success"] is False
    assert "failed" in result["error"].lower()
