"""Query parser and classifier for unified search.

This module provides natural language query processing and intent detection
to route queries to appropriate search backends.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any, Union


class QueryType(Enum):
    """Types of search queries supported."""

    FILE_SEARCH = "file_search"  # "find CSV files"
    PACKAGE_DISCOVERY = "package_discovery"  # "packages about genomics"
    CONTENT_SEARCH = "content_search"  # "files containing 'RNA-seq'"
    METADATA_SEARCH = "metadata_search"  # "packages created in 2024"
    ANALYTICAL_SEARCH = "analytical_search"  # "largest files by size"
    CROSS_CATALOG = "cross_catalog"  # "compare across catalogs"


class SearchScope(Enum):
    """Search scope definitions."""

    GLOBAL = "global"  # Search everything accessible
    CATALOG = "catalog"  # Current catalog only
    PACKAGE = "package"  # Within specific package
    BUCKET = "bucket"  # Within specific bucket
    REGISTRY = "registry"  # Within specific registry


@dataclass
class QueryAnalysis:
    """Result of query analysis."""

    query_type: QueryType
    scope: SearchScope
    target: Optional[str] = None  # Specific package/bucket when scope is narrow
    filters: Dict[str, Any] = None
    keywords: List[str] = None
    file_extensions: List[str] = None
    size_filters: Dict[str, Union[str, int]] = None
    date_filters: Dict[str, str] = None
    confidence: float = 1.0
    suggested_backends: List[str] = None

    def __post_init__(self):
        if self.filters is None:
            self.filters = {}
        if self.keywords is None:
            self.keywords = []
        if self.file_extensions is None:
            self.file_extensions = []
        if self.size_filters is None:
            self.size_filters = {}
        if self.date_filters is None:
            self.date_filters = {}
        if self.suggested_backends is None:
            self.suggested_backends = []


class QueryParser:
    """Natural language query parser for search intent detection."""

    # Pattern definitions for query classification
    FILE_PATTERNS = [
        r"\b(?:find|search|locate|get)\s+.*?(?:files?|data)\b",
        r"\b(?:csv|json|parquet|txt|pdf|xlsx?)\s+files?\b",
        r"\bfiles?\s+(?:with|containing|matching)\b",
        r"\b(?:download|access)\s+.*?files?\b",
    ]

    PACKAGE_PATTERNS = [
        r"\bpackages?\s+(?:about|containing|with|for)\b",
        r"\b(?:find|search|list)\s+packages?\b",
        r"\bpackages?\s+(?:created|modified|updated)\b",
        r"\b(?:browse|explore)\s+packages?\b",
    ]

    CONTENT_PATTERNS = [
        r'\bfiles?\s+containing\s+["\'].*?["\']',
        r"\bcontent\s+(?:matching|with|containing)\b",
        r"\btext\s+search\b",
        r"\bfull.?text\s+search\b",
    ]

    METADATA_PATTERNS = [
        r"\bpackages?\s+(?:created|modified|updated)\s+(?:in|during|on)\b",
        r"\bmetadata\s+(?:search|query|filter)\b",
        r"\b(?:tags?|labels?|properties)\s+(?:matching|containing)\b",
        r"\bpackages?\s+(?:by|from)\s+(?:author|creator|user)\b",
    ]

    ANALYTICAL_PATTERNS = [
        r"\b(?:largest|smallest|biggest)\s+files?\b",
        r"\bfiles?\s+(?:larger|smaller|bigger)\s+than\b",
        r"\b(?:count|total|sum|average|mean)\s+(?:of|files?|size)\b",
        r"\b(?:analyze|analysis|statistics|stats)\b",
        r"\b(?:aggregate|group\s+by|summarize)\b",
    ]

    # File extension patterns - improved to catch more variations
    FILE_EXT_PATTERNS = [
        r"\*\.([a-z]{2,5})\b",  # *.csv
        r"\.([a-z]{2,5})\s+(?:files?|data)\b",  # .csv files
        r"\b([a-z]{2,5})\s+(?:files?|data)\b",  # csv files
        r"(?:files?\s+with\s+)?\.([a-z]{2,5})\s+(?:extension|format)\b",  # files with .csv extension
        r"\b([a-z]{2,5})\s+file\s+(?:type|format|extension)\b",  # csv file type
    ]

    # Size patterns
    SIZE_PATTERNS = {
        "larger_than": r"(?:larger|bigger|greater)\s+than\s+(\d+(?:\.\d+)?)\s*([kmgt]?b)",
        "smaller_than": r"(?:smaller|less)\s+than\s+(\d+(?:\.\d+)?)\s*([kmgt]?b)",
        "size_range": r"between\s+(\d+(?:\.\d+)?)\s*([kmgt]?b)\s+and\s+(\d+(?:\.\d+)?)\s*([kmgt]?b)",
    }

    # Date patterns
    DATE_PATTERNS = {
        "last_days": r"(?:last|past)\s+(\d+)\s+days?",
        "last_weeks": r"(?:last|past)\s+(\d+)\s+weeks?",
        "last_months": r"(?:last|past)\s+(\d+)\s+months?",
        "created_in": r"created\s+in\s+(\d{4})",
        "since_date": r"since\s+(\d{4}-\d{2}-\d{2})",
    }

    def __init__(self):
        """Initialize the query parser."""
        self.compiled_patterns = {
            QueryType.FILE_SEARCH: [re.compile(p, re.IGNORECASE) for p in self.FILE_PATTERNS],
            QueryType.PACKAGE_DISCOVERY: [re.compile(p, re.IGNORECASE) for p in self.PACKAGE_PATTERNS],
            QueryType.CONTENT_SEARCH: [re.compile(p, re.IGNORECASE) for p in self.CONTENT_PATTERNS],
            QueryType.METADATA_SEARCH: [re.compile(p, re.IGNORECASE) for p in self.METADATA_PATTERNS],
            QueryType.ANALYTICAL_SEARCH: [re.compile(p, re.IGNORECASE) for p in self.ANALYTICAL_PATTERNS],
        }

        self.size_patterns = {k: re.compile(v, re.IGNORECASE) for k, v in self.SIZE_PATTERNS.items()}
        self.date_patterns = {k: re.compile(v, re.IGNORECASE) for k, v in self.DATE_PATTERNS.items()}
        self.file_ext_patterns = [re.compile(p, re.IGNORECASE) for p in self.FILE_EXT_PATTERNS]

    def parse(self, query: str, scope: str = "global", target: str = "") -> QueryAnalysis:
        """Parse a natural language query and extract search intent.

        Args:
            query: Natural language search query
            scope: Search scope (global, catalog, package, bucket)
            target: Specific target when scope is narrow

        Returns:
            QueryAnalysis with detected intent and extracted parameters
        """
        query_lower = query.lower().strip()

        # Determine query type based on patterns
        query_type = self._classify_query_type(query_lower)

        # Parse scope
        search_scope = SearchScope(scope) if scope in [s.value for s in SearchScope] else SearchScope.GLOBAL

        # Extract filters and parameters
        keywords = self._extract_keywords(query_lower)
        file_extensions = self._extract_file_extensions(query_lower)
        size_filters = self._extract_size_filters(query_lower)
        date_filters = self._extract_date_filters(query_lower)

        # Build filters dictionary
        filters = {}
        if file_extensions:
            filters["file_extensions"] = file_extensions
        if size_filters:
            filters.update(size_filters)
        if date_filters:
            filters.update(date_filters)

        # Suggest optimal backends based on query type
        suggested_backends = self._suggest_backends(query_type, filters)

        return QueryAnalysis(
            query_type=query_type,
            scope=search_scope,
            target=target,
            filters=filters,
            keywords=keywords,
            file_extensions=file_extensions,
            size_filters=size_filters,
            date_filters=date_filters,
            confidence=self._calculate_confidence(query_type, keywords, filters),
            suggested_backends=suggested_backends,
        )

    def _classify_query_type(self, query: str) -> QueryType:
        """Classify the query type based on pattern matching."""
        type_scores = {}

        for query_type, patterns in self.compiled_patterns.items():
            score = 0
            for pattern in patterns:
                if pattern.search(query):  # Use search instead of findall for better matching
                    score += 1
            type_scores[query_type] = score

        # Special case: if "packages" is mentioned prominently, lean toward package discovery
        if "packages" in query.lower() and "package" in query.lower():
            type_scores[QueryType.PACKAGE_DISCOVERY] = type_scores.get(QueryType.PACKAGE_DISCOVERY, 0) + 2

        # Special case: analytical terms get priority
        analytical_terms = [
            "largest",
            "smallest",
            "count",
            "total",
            "analyze",
            "bigger",
            "larger",
            "smaller",
        ]
        if any(term in query.lower() for term in analytical_terms):
            type_scores[QueryType.ANALYTICAL_SEARCH] = type_scores.get(QueryType.ANALYTICAL_SEARCH, 0) + 2

        # Return the type with highest score, default to FILE_SEARCH
        if not type_scores or max(type_scores.values()) == 0:
            return QueryType.FILE_SEARCH

        return max(type_scores, key=type_scores.get)

    def _extract_keywords(self, query: str) -> List[str]:
        """Extract meaningful keywords from the query."""
        # Remove common stop words and extract meaningful terms
        stop_words = {
            "find",
            "search",
            "get",
            "show",
            "list",
            "files",
            "file",
            "data",
            "packages",
            "package",
            "with",
            "containing",
            "about",
            "for",
            "in",
            "the",
            "a",
            "an",
            "and",
            "or",
            "of",
            "to",
            "from",
            "that",
            "this",
            "all",
        }

        # Handle hyphenated terms like "RNA-seq"
        # First extract hyphenated terms
        hyphenated_terms = re.findall(r"\b\w+(?:-\w+)+\b", query.lower())

        # Then extract regular words
        words = re.findall(r"\b\w+\b", query.lower())

        # Combine and filter
        all_terms = hyphenated_terms + [word for word in words if word not in stop_words and len(word) > 2]

        # Remove duplicates while preserving order
        keywords = []
        for term in all_terms:
            if term not in keywords:
                keywords.append(term)

        return keywords

    def _extract_file_extensions(self, query: str) -> List[str]:
        """Extract file extensions mentioned in the query."""
        extensions = []

        # Try all file extension patterns
        for pattern in self.file_ext_patterns:
            matches = pattern.findall(query)
            if matches:
                extensions.extend(matches)

        # Also look for "CSV and JSON" patterns
        and_pattern = re.compile(r"\b([a-z]{2,5})\s+and\s+([a-z]{2,5})\s+(?:files?|data)\b", re.IGNORECASE)
        and_matches = and_pattern.findall(query)

        for match in and_matches:
            extensions.extend(match)

        # Clean and deduplicate extensions
        clean_extensions = []
        for ext in extensions:
            ext_clean = ext.lower().strip()
            if (
                len(ext_clean) <= 5
                and ext_clean not in ["data", "files", "file", "with", "extension", "format", "type"]
                and ext_clean not in clean_extensions
            ):
                clean_extensions.append(ext_clean)

        return clean_extensions

    def _extract_size_filters(self, query: str) -> Dict[str, Any]:
        """Extract size-based filters from the query."""
        size_filters = {}

        for filter_type, pattern in self.size_patterns.items():
            match = pattern.search(query)
            if match:
                if filter_type == "size_range":
                    # Handle range: between X and Y
                    min_size, min_unit, max_size, max_unit = match.groups()
                    size_filters["size_min"] = self._normalize_size(min_size, min_unit)
                    size_filters["size_max"] = self._normalize_size(max_size, max_unit)
                else:
                    # Handle single threshold
                    size_value, unit = match.groups()
                    normalized_size = self._normalize_size(size_value, unit)
                    if "larger" in filter_type:
                        size_filters["size_min"] = normalized_size
                    else:
                        size_filters["size_max"] = normalized_size

        return size_filters

    def _extract_date_filters(self, query: str) -> Dict[str, str]:
        """Extract date-based filters from the query."""
        date_filters = {}

        for filter_type, pattern in self.date_patterns.items():
            match = pattern.search(query)
            if match:
                if filter_type == "last_days":
                    days = int(match.group(1))
                    date_filters["created_after"] = f"now-{days}d"
                elif filter_type == "last_weeks":
                    weeks = int(match.group(1))
                    date_filters["created_after"] = f"now-{weeks * 7}d"
                elif filter_type == "last_months":
                    months = int(match.group(1))
                    date_filters["created_after"] = f"now-{months * 30}d"
                elif filter_type == "created_in":
                    year = match.group(1)
                    date_filters["created_after"] = f"{year}-01-01"
                    date_filters["created_before"] = f"{year}-12-31"
                elif filter_type == "since_date":
                    date = match.group(1)
                    date_filters["created_after"] = date

        return date_filters

    def _normalize_size(self, size_str: str, unit: str) -> int:
        """Convert size string to bytes."""
        size = float(size_str)
        unit = unit.lower()

        multipliers = {"b": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3, "tb": 1024**4}

        return int(size * multipliers.get(unit, 1))

    def _suggest_backends(self, query_type: QueryType, filters: Dict[str, Any]) -> List[str]:
        """Suggest optimal backends based on query type and filters."""
        if query_type == QueryType.FILE_SEARCH:
            return ["elasticsearch", "graphql", "s3"]
        elif query_type == QueryType.PACKAGE_DISCOVERY:
            return ["graphql", "elasticsearch", "s3"]
        elif query_type == QueryType.CONTENT_SEARCH:
            return ["elasticsearch", "graphql", "s3"]
        elif query_type == QueryType.METADATA_SEARCH:
            return ["graphql", "elasticsearch", "s3"]
        elif query_type == QueryType.ANALYTICAL_SEARCH:
            return ["elasticsearch", "graphql", "s3"]
        else:
            return ["elasticsearch", "graphql", "s3"]

    def _calculate_confidence(self, query_type: QueryType, keywords: List[str], filters: Dict[str, Any]) -> float:
        """Calculate confidence score for the query analysis."""
        base_confidence = 0.5

        # Boost confidence based on specific patterns found
        if keywords:
            base_confidence += min(len(keywords) * 0.1, 0.3)

        if filters:
            base_confidence += min(len(filters) * 0.1, 0.2)

        return min(base_confidence, 1.0)


def parse_query(query: str, scope: str = "global", target: str = "") -> QueryAnalysis:
    """Convenience function to parse a query.

    Args:
        query: Natural language search query
        scope: Search scope (global, catalog, package, bucket)
        target: Specific target when scope is narrow

    Returns:
        QueryAnalysis with detected intent and parameters
    """
    parser = QueryParser()
    return parser.parse(query, scope, target)
