"""Search suggestion tool for query completion and recommendations.

This tool provides intelligent search suggestions based on context,
popular queries, and available data.
"""

import re
from typing import Dict, List, Any, Optional

from ..core.query_parser import QueryParser, QueryType


class SearchSuggestionEngine:
    """Engine for generating search suggestions and query completions."""

    def __init__(self):
        self.parser = QueryParser()

        # Common query patterns and completions
        self.query_patterns = {
            "file_search": [
                "CSV files",
                "JSON files",
                "parquet files",
                "README files",
                "configuration files",
                "data files",
                "log files",
                "image files",
            ],
            "package_discovery": [
                "packages about genomics",
                "packages containing RNA-seq data",
                "packages created last month",
                "packages by author",
                "packages with large files",
                "machine learning packages",
                "analytics packages",
            ],
            "analytical": [
                "largest files",
                "files larger than 100MB",
                "count of files by type",
                "total size of packages",
                "files created last week",
                "most recent packages",
            ],
            "content_search": [
                "files containing 'keyword'",
                "text files with specific content",
                "documents mentioning topic",
            ],
        }

        # Domain-specific suggestions
        self.domain_suggestions = {
            "genomics": [
                "BAM files",
                "VCF files",
                "FASTQ files",
                "GFF files",
                "RNA-seq data",
            ],
            "ml": ["model files", "training data", "test datasets", "feature files"],
            "analytics": ["dashboard data", "reports", "metrics", "KPI data"],
            "imaging": ["TIFF files", "microscopy data", "image analysis results"],
        }

        # File type suggestions
        self.file_type_suggestions = {
            "csv": ["CSV files", "CSV data files", "CSV reports"],
            "json": ["JSON files", "JSON configuration", "JSON metadata"],
            "parquet": ["parquet files", "parquet datasets", "columnar data"],
            "txt": ["text files", "log files", "documentation"],
            "pdf": ["PDF documents", "PDF reports", "documentation"],
            "xlsx": ["Excel files", "spreadsheet data", "Excel reports"],
        }

    def suggest(
        self,
        partial_query: str,
        context: str = "",
        suggestion_types: List[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Generate search suggestions for partial query.

        Args:
            partial_query: Incomplete query to complete
            context: Current context (package/bucket name)
            suggestion_types: Types of suggestions (queries, packages, files, metadata)
            limit: Maximum suggestions to return

        Returns:
            Dictionary with categorized suggestions
        """
        if suggestion_types is None:
            suggestion_types = ["auto"]
        partial_lower = partial_query.lower().strip()
        suggestions = {
            "query_completions": [],
            "related_queries": [],
            "domain_suggestions": [],
            "file_type_suggestions": [],
            "context_suggestions": [],
        }

        # Generate query completions
        if "auto" in suggestion_types or "queries" in suggestion_types:
            suggestions["query_completions"] = self._generate_query_completions(partial_lower, limit)

        # Generate related queries based on detected intent
        if "auto" in suggestion_types or "related" in suggestion_types:
            suggestions["related_queries"] = self._generate_related_queries(partial_lower, limit)

        # Generate domain-specific suggestions
        if "auto" in suggestion_types or "domain" in suggestion_types:
            suggestions["domain_suggestions"] = self._generate_domain_suggestions(partial_lower, limit)

        # Generate file type suggestions
        if "auto" in suggestion_types or "files" in suggestion_types:
            suggestions["file_type_suggestions"] = self._generate_file_type_suggestions(partial_lower, limit)

        # Generate context-aware suggestions
        if context and ("auto" in suggestion_types or "context" in suggestion_types):
            suggestions["context_suggestions"] = self._generate_context_suggestions(partial_lower, context, limit)

        return {
            "partial_query": partial_query,
            "context": context,
            "suggestions": suggestions,
            "total_suggestions": sum(len(s) for s in suggestions.values()),
        }

    def _generate_query_completions(self, partial: str, limit: int) -> List[Dict[str, Any]]:
        """Generate direct query completions."""
        completions = []

        # Look through all query patterns for matches
        for category, patterns in self.query_patterns.items():
            for pattern in patterns:
                if partial in pattern.lower():
                    completions.append(
                        {
                            "completion": pattern,
                            "category": category,
                            "confidence": self._calculate_completion_confidence(partial, pattern),
                        }
                    )

        # Sort by confidence and limit
        completions.sort(key=lambda x: x["confidence"], reverse=True)
        return completions[:limit]

    def _generate_related_queries(self, partial: str, limit: int) -> List[Dict[str, Any]]:
        """Generate related query suggestions."""
        # Analyze partial query to understand intent
        try:
            analysis = self.parser.parse(partial)
            query_type = analysis.query_type
        except Exception:
            query_type = QueryType.FILE_SEARCH

        # Get suggestions for the detected query type
        related_patterns = self.query_patterns.get(query_type.value.replace("_search", ""), [])

        related = []
        for pattern in related_patterns[:limit]:
            if pattern.lower() != partial:  # Don't suggest the same query
                related.append(
                    {
                        "query": pattern,
                        "type": query_type.value,
                        "reason": f"Similar {query_type.value.replace('_', ' ')} query",
                    }
                )

        return related

    def _generate_domain_suggestions(self, partial: str, limit: int) -> List[Dict[str, Any]]:
        """Generate domain-specific suggestions."""
        suggestions = []

        for domain, domain_queries in self.domain_suggestions.items():
            if domain in partial or any(keyword in partial for keyword in domain_queries):
                for suggestion in domain_queries[: limit // len(self.domain_suggestions)]:
                    suggestions.append(
                        {
                            "suggestion": suggestion,
                            "domain": domain,
                            "relevance": self._calculate_domain_relevance(partial, suggestion, domain),
                        }
                    )

        # Sort by relevance
        suggestions.sort(key=lambda x: x["relevance"], reverse=True)
        return suggestions[:limit]

    def _generate_file_type_suggestions(self, partial: str, limit: int) -> List[Dict[str, Any]]:
        """Generate file type-specific suggestions."""
        suggestions = []

        # Look for file extensions in the partial query
        file_ext_matches = re.findall(r"\b([a-z]{2,5})\b", partial)

        for ext in file_ext_matches:
            if ext in self.file_type_suggestions:
                for suggestion in self.file_type_suggestions[ext]:
                    suggestions.append({"suggestion": suggestion, "file_type": ext, "relevance": 0.8})

        # Also suggest based on partial matches
        for file_type, type_suggestions in self.file_type_suggestions.items():
            if file_type in partial:
                for suggestion in type_suggestions:
                    if suggestion not in [s["suggestion"] for s in suggestions]:
                        suggestions.append(
                            {
                                "suggestion": suggestion,
                                "file_type": file_type,
                                "relevance": 0.6,
                            }
                        )

        return suggestions[:limit]

    def _generate_context_suggestions(self, partial: str, context: str, limit: int) -> List[Dict[str, Any]]:
        """Generate context-aware suggestions."""
        suggestions = []

        if "/" in context:  # Package context
            suggestions.extend(
                [
                    {
                        "suggestion": f"files in {context}",
                        "context_type": "package",
                        "relevance": 0.9,
                    },
                    {
                        "suggestion": f"README files in {context}",
                        "context_type": "package",
                        "relevance": 0.8,
                    },
                    {
                        "suggestion": f"data files in {context}",
                        "context_type": "package",
                        "relevance": 0.7,
                    },
                ]
            )
        else:  # Bucket context
            suggestions.extend(
                [
                    {
                        "suggestion": f"files in bucket {context}",
                        "context_type": "bucket",
                        "relevance": 0.9,
                    },
                    {
                        "suggestion": f"packages in {context}",
                        "context_type": "bucket",
                        "relevance": 0.8,
                    },
                ]
            )

        return suggestions[:limit]

    def _calculate_completion_confidence(self, partial: str, pattern: str) -> float:
        """Calculate confidence score for query completion."""
        if partial == pattern.lower():
            return 1.0

        # Calculate based on how much of the pattern matches
        words_partial = set(partial.split())
        words_pattern = set(pattern.lower().split())

        if not words_partial:
            return 0.1

        overlap = len(words_partial.intersection(words_pattern))
        return min(overlap / len(words_partial), 1.0)

    def _calculate_domain_relevance(self, partial: str, suggestion: str, domain: str) -> float:
        """Calculate relevance score for domain suggestions."""
        base_score = 0.5

        # Boost if domain is mentioned in partial
        if domain in partial:
            base_score += 0.3

        # Boost if suggestion words appear in partial
        suggestion_words = set(suggestion.lower().split())
        partial_words = set(partial.split())

        overlap = len(suggestion_words.intersection(partial_words))
        if overlap > 0:
            base_score += overlap * 0.1

        return min(base_score, 1.0)


# Global suggestion engine instance
_suggestion_engine = None


def get_suggestion_engine() -> SearchSuggestionEngine:
    """Get or create the global suggestion engine instance."""
    global _suggestion_engine
    if _suggestion_engine is None:
        _suggestion_engine = SearchSuggestionEngine()
    return _suggestion_engine


def search_suggest(
    partial_query: str,
    context: str = "",
    suggestion_types: List[str] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """
    Provide intelligent search suggestions and query completion.

    Args:
        partial_query: Incomplete query to complete
        context: Current context (package/bucket name)
        suggestion_types: Types of suggestions (queries, packages, files, metadata)
        limit: Maximum suggestions to return

    Returns:
        List of suggested completions with explanations

    Examples:
        search_suggest("CSV fil")  # → "CSV files", "CSV files in packages", etc.
        search_suggest("genomics", context="user/dataset")
    """
    if suggestion_types is None:
        suggestion_types = ["auto"]
    try:
        engine = get_suggestion_engine()
        return engine.suggest(partial_query, context, suggestion_types, limit)
    except Exception as e:
        return {
            "success": False,
            "error": f"Search suggestions failed: {e}",
            "partial_query": partial_query,
            "context": context,
        }
