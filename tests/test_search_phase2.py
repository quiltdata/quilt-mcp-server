"""Tests for Phase 2 unified search features."""

import pytest
from unittest.mock import Mock, patch

from quilt_mcp.search.tools.search_suggest import SearchSuggestionEngine, search_suggest
from quilt_mcp.search.tools.search_explain import SearchExplainer, search_explain
from quilt_mcp.search.backends.graphql import EnterpriseGraphQLBackend
from quilt_mcp.search.backends.base import BackendStatus


class TestSearchSuggestions:
    """Test cases for search suggestion functionality."""

    def test_query_completions(self):
        """Test basic query completion suggestions."""
        engine = SearchSuggestionEngine()

        result = engine.suggest("csv fil", limit=5)

        assert "suggestions" in result
        completions = result["suggestions"]["query_completions"]
        assert len(completions) > 0
        assert any("CSV files" in comp["completion"] for comp in completions)

    def test_file_type_suggestions(self):
        """Test file type-specific suggestions."""
        engine = SearchSuggestionEngine()

        result = engine.suggest("csv", suggestion_types=["files"], limit=5)

        file_suggestions = result["suggestions"]["file_type_suggestions"]
        assert len(file_suggestions) > 0
        assert any("csv" in sugg["file_type"] for sugg in file_suggestions)

    def test_domain_suggestions(self):
        """Test domain-specific suggestions."""
        engine = SearchSuggestionEngine()

        result = engine.suggest("genomics", suggestion_types=["domain"], limit=5)

        domain_suggestions = result["suggestions"]["domain_suggestions"]
        assert len(domain_suggestions) > 0
        assert any("genomics" in sugg["domain"] for sugg in domain_suggestions)

    def test_context_suggestions_package(self):
        """Test context-aware suggestions for package scope."""
        engine = SearchSuggestionEngine()

        result = engine.suggest("files", context="user/dataset", suggestion_types=["context"], limit=5)

        context_suggestions = result["suggestions"]["context_suggestions"]
        assert len(context_suggestions) > 0
        assert any("package" in sugg["context_type"] for sugg in context_suggestions)

    def test_context_suggestions_bucket(self):
        """Test context-aware suggestions for bucket scope."""
        engine = SearchSuggestionEngine()

        result = engine.suggest("data", context="my-bucket", suggestion_types=["context"], limit=5)

        context_suggestions = result["suggestions"]["context_suggestions"]
        assert len(context_suggestions) > 0
        assert any("bucket" in sugg["context_type"] for sugg in context_suggestions)


class TestSearchExplanations:
    """Test cases for search explanation functionality."""

    def test_basic_explanation(self):
        """Test basic query explanation."""
        explainer = SearchExplainer()

        result = explainer.explain("CSV files")

        assert "query_analysis" in result
        assert "backend_selection" in result
        assert result["query_analysis"]["detected_type"] == "file_search"

    def test_performance_estimation(self):
        """Test performance estimation in explanations."""
        explainer = SearchExplainer()

        result = explainer.explain("large genomics files", show_performance=True)

        assert "performance_estimate" in result
        perf = result["performance_estimate"]
        assert "complexity_assessment" in perf
        assert "estimated_time_ranges" in perf
        assert perf["complexity_assessment"] in ["simple", "moderate", "complex"]

    def test_alternative_suggestions(self):
        """Test alternative query suggestions."""
        explainer = SearchExplainer()

        result = explainer.explain("genomics data", show_alternatives=True)

        assert "alternative_queries" in result
        alternatives = result["alternative_queries"]
        assert len(alternatives) > 0
        assert all("alternative" in alt for alt in alternatives)

    def test_backend_reasoning(self):
        """Test backend selection reasoning."""
        explainer = SearchExplainer()

        result = explainer.explain("packages about genomics", show_backends=True)

        backend_selection = result["backend_selection"]
        assert "selected_backends" in backend_selection
        assert "selection_reasoning" in backend_selection
        assert "fallback_chain" in backend_selection

        # Should prefer GraphQL for package discovery
        assert "graphql" in backend_selection["selected_backends"]


class TestGraphQLBackend:
    """Test cases for Enterprise GraphQL backend."""

    @patch('quilt_mcp.search.backends.graphql.quilt3')
    def test_graphql_initialization(self, mock_quilt3):
        """Test GraphQL backend initialization."""
        mock_session = Mock()
        mock_session.post.return_value.status_code = 200
        mock_session.post.return_value.json.return_value = {"data": {"__schema": {"queryType": {"name": "Query"}}}}

        mock_quilt3.session.get_registry_url.return_value = "https://test-catalog.com"
        mock_quilt3.session.get_session.return_value = mock_session

        backend = EnterpriseGraphQLBackend()
        assert backend.status == BackendStatus.AVAILABLE

    @patch('quilt_mcp.search.backends.graphql.quilt3')
    def test_graphql_unavailable(self, mock_quilt3):
        """Test GraphQL backend when service is unavailable."""
        mock_quilt3.session.get_registry_url.return_value = None
        mock_quilt3.session.get_session.return_value = None

        # Mock the GraphQL endpoint function to return None
        with patch('quilt_mcp.tools.graphql._get_graphql_endpoint', return_value=(None, None)):
            backend = EnterpriseGraphQLBackend()
            assert backend.status == BackendStatus.UNAVAILABLE

    @patch('quilt_mcp.search.backends.graphql.quilt3')
    @pytest.mark.asyncio
    async def test_graphql_health_check(self, mock_quilt3):
        """Test GraphQL backend health checking."""
        mock_session = Mock()
        mock_session.post.return_value.status_code = 200

        mock_quilt3.session.get_registry_url.return_value = "https://test-catalog.com"
        mock_quilt3.session.get_session.return_value = mock_session

        backend = EnterpriseGraphQLBackend()
        is_healthy = await backend.health_check()

        assert is_healthy is True
        assert backend.status == BackendStatus.AVAILABLE


class TestIntegratedPhase2:
    """Test cases for integrated Phase 2 functionality."""

    def test_search_suggest_function(self):
        """Test the search_suggest tool function."""
        result = search_suggest("csv", limit=3)

        assert "suggestions" in result
        assert result["partial_query"] == "csv"
        assert result["total_suggestions"] > 0

    def test_search_explain_function(self):
        """Test the search_explain tool function."""
        result = search_explain("large files", show_performance=True)

        assert "query_analysis" in result
        assert "backend_selection" in result
        assert "performance_estimate" in result
        # "large files" gets detected as file_search, which is correct
        assert result["query_analysis"]["detected_type"] in ["file_search", "analytical_search"]

    @patch('quilt_mcp.search.tools.unified_search.get_search_engine')
    def test_enhanced_backend_registry(self, mock_get_engine):
        """Test that the enhanced search engine includes all backends."""
        from quilt_mcp.search.tools.unified_search import UnifiedSearchEngine

        # Create actual engine to test backend registration
        engine = UnifiedSearchEngine()

        # Should have all three backend types registered
        all_backends = list(engine.registry._backends.keys())
        assert len(all_backends) == 3  # elasticsearch, s3, graphql

        backend_names = [bt.value for bt in all_backends]
        assert "elasticsearch" in backend_names
        assert "s3" in backend_names
        assert "graphql" in backend_names
