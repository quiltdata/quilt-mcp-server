from __future__ import annotations

from quilt_mcp.search.core.query_parser import QueryAnalysis, QueryParser, QueryType, SearchScope, parse_query


def test_parse_defaults_to_file_search_when_no_patterns_match():
    parser = QueryParser()
    analysis = parser.parse("nonsense tokens only")

    assert analysis.query_type == QueryType.FILE_SEARCH
    assert analysis.scope == SearchScope.GLOBAL
    assert analysis.filters == {}
    assert analysis.suggested_backends == ["elasticsearch", "graphql", "s3"]


def test_parse_detects_analytical_query_and_extracts_size_date_filters():
    parser = QueryParser()
    analysis = parser.parse("largest csv files larger than 10MB from last 2 weeks", scope="bucket", bucket="bkt")

    assert analysis.query_type == QueryType.ANALYTICAL_SEARCH
    assert analysis.scope == SearchScope.BUCKET
    assert analysis.bucket == "bkt"
    assert analysis.filters["size_min"] == 10 * 1024 * 1024
    assert analysis.filters["created_after"] == "now-14d"
    assert "csv" in analysis.file_extensions


def test_parse_extracts_multiple_extensions_and_since_date():
    parser = QueryParser()
    analysis = parser.parse("find csv and json files since 2024-01-01")

    assert sorted(analysis.file_extensions) == ["csv", "json"]
    assert analysis.date_filters["created_after"] == "2024-01-01"
    assert analysis.filters["created_after"] == "2024-01-01"


def test_parse_created_in_sets_date_range():
    parser = QueryParser()
    analysis = parser.parse("packages created in 2025")

    assert analysis.date_filters["created_after"] == "2025-01-01"
    assert analysis.date_filters["created_before"] == "2025-12-31"


def test_extract_keywords_handles_hyphenated_terms_and_deduplicates():
    parser = QueryParser()
    keywords = parser._extract_keywords("find RNA-seq RNA-seq data in packages")

    assert "rna-seq" in keywords
    assert keywords.count("rna-seq") == 1


def test_normalize_size_unknown_unit_falls_back_to_bytes():
    parser = QueryParser()
    assert parser._normalize_size("3", "xb") == 3


def test_suggest_backends_for_metadata_and_confidence_cap():
    parser = QueryParser()
    backends = parser._suggest_backends(QueryType.METADATA_SEARCH, {})
    confidence = parser._calculate_confidence(
        QueryType.FILE_SEARCH,
        keywords=["a", "b", "c", "d", "e", "f"],
        filters={"x": 1, "y": 2, "z": 3},
    )

    assert backends == ["graphql", "elasticsearch", "s3"]
    assert confidence == 1.0


def test_parse_query_convenience_function():
    analysis = parse_query("csv files", scope="package", bucket="s3://bucket")

    assert analysis.scope == SearchScope.PACKAGE
    assert analysis.bucket == "s3://bucket"


def test_query_analysis_post_init_sets_defaults_from_none():
    analysis = QueryAnalysis(query_type=QueryType.FILE_SEARCH, scope=SearchScope.GLOBAL)
    assert analysis.filters == {}
    assert analysis.keywords == []
    assert analysis.file_extensions == []
    assert analysis.size_filters == {}
    assert analysis.date_filters == {}
    assert analysis.suggested_backends == []


def test_size_filter_range_and_smaller_than_paths():
    parser = QueryParser()
    range_filters = parser._extract_size_filters("files between 1mb and 2mb")
    smaller_filters = parser._extract_size_filters("files smaller than 5kb")

    assert range_filters["size_min"] == 1024 * 1024
    assert range_filters["size_max"] == 2 * 1024 * 1024
    assert smaller_filters["size_max"] == 5 * 1024
