"""Search explanation tool for query execution analysis.

This tool provides detailed explanations of how queries are executed,
which backends are selected, and how results are ranked.
"""

from typing import Dict, List, Any, Optional

from ..core.query_parser import parse_query, QueryType, SearchScope
from ..backends.base import BackendType


class SearchExplainer:
    """Engine for generating search execution explanations."""

    def __init__(self):
        self.backend_characteristics = {
            BackendType.ELASTICSEARCH: {
                "strengths": [
                    "Fast full-text search",
                    "Complex query DSL",
                    "Relevance scoring",
                ],
                "weaknesses": ["Requires indexing", "May not have all data"],
                "best_for": [
                    "File content search",
                    "Package discovery",
                    "Text matching",
                ],
                "typical_speed": "< 200ms",
            },
            BackendType.GRAPHQL: {
                "strengths": [
                    "Rich metadata",
                    "Relationship queries",
                    "Structured results",
                ],
                "weaknesses": ["Slower than ES", "Limited text search"],
                "best_for": [
                    "Package relationships",
                    "Metadata queries",
                    "Complex filters",
                ],
                "typical_speed": "< 1s",
            },
            BackendType.S3: {
                "strengths": [
                    "Always available",
                    "No indexing required",
                    "Direct S3 access",
                ],
                "weaknesses": ["Slow for large buckets", "Limited query capabilities"],
                "best_for": [
                    "Fallback searches",
                    "Simple prefix matching",
                    "Basic enumeration",
                ],
                "typical_speed": "< 5s",
            },
        }

        self.optimization_suggestions = {
            QueryType.FILE_SEARCH: [
                "Use specific file extensions for faster results",
                "Include size filters to narrow results",
                "Specify bucket scope if you know the location",
            ],
            QueryType.PACKAGE_DISCOVERY: [
                "Use specific keywords related to your domain",
                "Include temporal filters (created last month, etc.)",
                "Use metadata filters for better targeting",
            ],
            QueryType.ANALYTICAL_SEARCH: [
                "Use Elasticsearch for complex aggregations",
                "Consider GraphQL for relationship analysis",
                "Combine with size/date filters for efficiency",
            ],
            QueryType.CONTENT_SEARCH: [
                "Use quoted strings for exact phrase matching",
                "Include file type filters to narrow scope",
                "Consider using regex patterns for complex matching",
            ],
        }

    def explain(
        self,
        query: str,
        show_backends: bool = True,
        show_performance: bool = True,
        show_alternatives: bool = False,
    ) -> Dict[str, Any]:
        """Explain how a search query would be executed.

        Args:
            query: Search query to explain
            show_backends: Include backend selection reasoning
            show_performance: Include performance estimates
            show_alternatives: Suggest alternative query formulations

        Returns:
            Detailed explanation of query execution plan
        """
        # Parse the query
        analysis = parse_query(query)

        explanation = {
            "query": query,
            "query_analysis": {
                "detected_type": analysis.query_type.value,
                "confidence": analysis.confidence,
                "scope": analysis.scope.value,
                "keywords": analysis.keywords,
                "file_extensions": analysis.file_extensions,
                "filters": analysis.filters,
            },
        }

        if show_backends:
            explanation["backend_selection"] = self._explain_backend_selection(analysis)

        if show_performance:
            explanation["performance_estimate"] = self._estimate_performance(analysis)

        if show_alternatives:
            explanation["alternative_queries"] = self._suggest_alternatives(analysis)

        # Add optimization suggestions
        explanation["optimization_suggestions"] = self.optimization_suggestions.get(analysis.query_type, [])

        return explanation

    def _explain_backend_selection(self, analysis) -> Dict[str, Any]:
        """Explain why specific backends were selected."""
        selected_backends = analysis.suggested_backends

        explanation = {
            "selected_backends": selected_backends,
            "selection_reasoning": {},
            "execution_order": selected_backends,
            "fallback_chain": self._build_fallback_chain(analysis.query_type),
        }

        # Explain each backend selection
        for backend_name in selected_backends:
            try:
                backend_type = BackendType(backend_name)
                characteristics = self.backend_characteristics[backend_type]

                explanation["selection_reasoning"][backend_name] = {
                    "why_selected": self._get_selection_reason(analysis.query_type, backend_type),
                    "strengths": characteristics["strengths"],
                    "best_for": characteristics["best_for"],
                    "expected_speed": characteristics["typical_speed"],
                }
            except (ValueError, KeyError):
                explanation["selection_reasoning"][backend_name] = {
                    "why_selected": "Unknown backend",
                    "strengths": [],
                    "best_for": [],
                    "expected_speed": "Unknown",
                }

        return explanation

    def _estimate_performance(self, analysis) -> Dict[str, Any]:
        """Estimate query performance characteristics."""
        query_complexity = self._assess_query_complexity(analysis)

        performance = {
            "complexity_assessment": query_complexity,
            "estimated_time_ranges": {},
            "resource_usage": {},
            "scalability_notes": [],
        }

        # Estimate time ranges for each backend
        for backend_name in analysis.suggested_backends:
            try:
                backend_type = BackendType(backend_name)
                base_time = self._get_base_time_estimate(backend_type)

                # Adjust based on complexity
                if query_complexity == "simple":
                    multiplier = 1.0
                elif query_complexity == "moderate":
                    multiplier = 2.0
                else:  # complex
                    multiplier = 4.0

                performance["estimated_time_ranges"][backend_name] = {
                    "min_ms": int(base_time * 0.5 * multiplier),
                    "max_ms": int(base_time * 2.0 * multiplier),
                    "typical_ms": int(base_time * multiplier),
                }
            except (ValueError, KeyError):
                performance["estimated_time_ranges"][backend_name] = {
                    "min_ms": 100,
                    "max_ms": 5000,
                    "typical_ms": 1000,
                }

        # Add scalability notes
        if len(analysis.keywords) > 5:
            performance["scalability_notes"].append("Many keywords may slow down text search")

        if analysis.filters:
            performance["scalability_notes"].append("Filters will improve performance by reducing result set")

        if analysis.scope == SearchScope.GLOBAL:
            performance["scalability_notes"].append("Global scope may be slower than targeted searches")

        return performance

    def _suggest_alternatives(self, analysis) -> List[Dict[str, Any]]:
        """Suggest alternative query formulations."""
        alternatives = []

        # Suggest more specific queries
        if analysis.scope == SearchScope.GLOBAL and not analysis.file_extensions:
            alternatives.append(
                {
                    "alternative": f"{' '.join(analysis.keywords)} files",
                    "improvement": "Add file type for faster results",
                    "expected_benefit": "2-5x faster execution",
                }
            )

        # Suggest adding filters
        if not analysis.filters:
            alternatives.append(
                {
                    "alternative": f"{' '.join(analysis.keywords)} created last week",
                    "improvement": "Add temporal filter",
                    "expected_benefit": "More relevant, recent results",
                }
            )

        # Suggest scope narrowing
        if analysis.scope == SearchScope.GLOBAL:
            alternatives.append(
                {
                    "alternative": "Search within specific package or bucket",
                    "improvement": "Narrow search scope",
                    "expected_benefit": "Faster execution, more targeted results",
                }
            )

        return alternatives

    def _assess_query_complexity(self, analysis) -> str:
        """Assess the complexity of a query."""
        complexity_score = 0

        # Add complexity for keywords
        complexity_score += len(analysis.keywords)

        # Add complexity for filters
        complexity_score += len(analysis.filters) * 2

        # Add complexity for scope
        if analysis.scope == SearchScope.GLOBAL:
            complexity_score += 3
        elif analysis.scope == SearchScope.CATALOG:
            complexity_score += 2

        if complexity_score <= 3:
            return "simple"
        elif complexity_score <= 8:
            return "moderate"
        else:
            return "complex"

    def _get_base_time_estimate(self, backend_type: BackendType) -> int:
        """Get base time estimate in milliseconds for backend."""
        estimates = {
            BackendType.ELASTICSEARCH: 100,
            BackendType.GRAPHQL: 500,
            BackendType.S3: 2000,
        }
        return estimates.get(backend_type, 1000)

    def _get_selection_reason(self, query_type: QueryType, backend_type: BackendType) -> str:
        """Get reason why backend was selected for query type."""
        reasons = {
            (
                QueryType.FILE_SEARCH,
                BackendType.ELASTICSEARCH,
            ): "Fast text search optimal for file discovery",
            (
                QueryType.FILE_SEARCH,
                BackendType.GRAPHQL,
            ): "Provides rich file metadata and package context",
            (
                QueryType.FILE_SEARCH,
                BackendType.S3,
            ): "Reliable fallback when search indices unavailable",
            (
                QueryType.PACKAGE_DISCOVERY,
                BackendType.GRAPHQL,
            ): "Excellent for package metadata and relationships",
            (
                QueryType.PACKAGE_DISCOVERY,
                BackendType.ELASTICSEARCH,
            ): "Good for package content search",
            (
                QueryType.PACKAGE_DISCOVERY,
                BackendType.S3,
            ): "Basic package enumeration fallback",
            (
                QueryType.ANALYTICAL_SEARCH,
                BackendType.ELASTICSEARCH,
            ): "Supports complex aggregations and analytics",
            (
                QueryType.ANALYTICAL_SEARCH,
                BackendType.GRAPHQL,
            ): "Good for metadata-based analytics",
            (
                QueryType.ANALYTICAL_SEARCH,
                BackendType.S3,
            ): "Limited analytics via client-side processing",
        }

        return reasons.get(
            (query_type, backend_type),
            "Selected as part of comprehensive search strategy",
        )

    def _build_fallback_chain(self, query_type: QueryType) -> List[str]:
        """Build fallback chain for query type."""
        chains = {
            QueryType.FILE_SEARCH: ["elasticsearch", "graphql", "s3"],
            QueryType.PACKAGE_DISCOVERY: ["graphql", "elasticsearch", "s3"],
            QueryType.ANALYTICAL_SEARCH: ["elasticsearch", "graphql", "s3"],
            QueryType.CONTENT_SEARCH: ["elasticsearch", "graphql", "s3"],
            QueryType.METADATA_SEARCH: ["graphql", "elasticsearch", "s3"],
        }

        return chains.get(query_type, ["elasticsearch", "graphql", "s3"])


# Global explainer instance
_explainer = None


def get_explainer() -> SearchExplainer:
    """Get or create the global explainer instance."""
    global _explainer
    if _explainer is None:
        _explainer = SearchExplainer()
    return _explainer


def search_explain(
    query: str,
    show_backends: bool = True,
    show_performance: bool = True,
    show_alternatives: bool = False,
) -> Dict[str, Any]:
    """
    Explain how a search query would be executed and optimized.

    Args:
        query: Search query to explain
        show_backends: Include backend selection reasoning
        show_performance: Include performance estimates
        show_alternatives: Suggest alternative query formulations

    Returns:
        Detailed explanation of query execution plan

    Examples:
        search_explain("large genomics files")
        search_explain("packages with RNA-seq data", show_alternatives=True)
    """
    try:
        explainer = get_explainer()
        return explainer.explain(query, show_backends, show_performance, show_alternatives)
    except Exception as e:
        return {
            "success": False,
            "error": f"Query explanation failed: {e}",
            "query": query,
        }
