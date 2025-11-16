"""Tests for Elasticsearch query escaping functionality."""

import pytest
from quilt_mcp.search.backends.elasticsearch import escape_elasticsearch_query


class TestElasticsearchQueryEscaping:
    """Test suite for Elasticsearch special character escaping."""

    def test_escape_forward_slash(self):
        """Test that forward slashes are properly escaped."""
        assert escape_elasticsearch_query("prefix/suffix") == r"prefix\/suffix"
        assert escape_elasticsearch_query("team/dataset") == r"team\/dataset"

    def test_escape_multiple_slashes(self):
        """Test escaping multiple forward slashes in a path."""
        assert escape_elasticsearch_query("data/2024/results.csv") == r"data\/2024\/results.csv"

    def test_escape_hyphen(self):
        """Test that hyphens are properly escaped."""
        assert escape_elasticsearch_query("file-name") == r"file\-name"

    def test_escape_greater_than(self):
        """Test that greater than signs are properly escaped."""
        assert escape_elasticsearch_query("size>100") == r"size\>100"

    def test_escape_colon(self):
        """Test that colons are properly escaped."""
        assert escape_elasticsearch_query("field:value") == r"field\:value"

    def test_escape_plus(self):
        """Test that plus signs are properly escaped."""
        assert escape_elasticsearch_query("gene+protein") == r"gene\+protein"

    def test_escape_asterisk(self):
        """Test that asterisks are NOT escaped (they're wildcards)."""
        assert escape_elasticsearch_query("file*.txt") == "file*.txt"

    def test_escape_question_mark(self):
        """Test that question marks are NOT escaped (they're wildcards)."""
        assert escape_elasticsearch_query("file?.txt") == "file?.txt"

    def test_escape_parentheses(self):
        """Test that parentheses are properly escaped."""
        assert escape_elasticsearch_query("term (with parens)") == r"term \(with parens\)"

    def test_escape_brackets(self):
        """Test that brackets are properly escaped."""
        assert escape_elasticsearch_query("array[0]") == r"array\[0\]"
        assert escape_elasticsearch_query("set{a,b}") == r"set\{a,b\}"

    def test_escape_quotes(self):
        """Test that quotes are properly escaped."""
        assert escape_elasticsearch_query('text "in quotes"') == r'text \"in quotes\"'

    def test_escape_backslash(self):
        """Test that backslashes are properly escaped."""
        assert escape_elasticsearch_query(r"path\to\file") == r"path\\to\\file"

    def test_escape_complex_query(self):
        """Test escaping a complex query with multiple special characters."""
        input_query = "team/dataset:value>100"
        expected = r"team\/dataset\:value\>100"
        assert escape_elasticsearch_query(input_query) == expected

    def test_preserve_spaces(self):
        """Test that spaces are not escaped."""
        assert escape_elasticsearch_query("name AND status") == r"name AND status"

    def test_empty_string(self):
        """Test that empty strings are handled correctly."""
        assert escape_elasticsearch_query("") == ""

    def test_no_special_chars(self):
        """Test that strings without special characters are unchanged."""
        assert escape_elasticsearch_query("simplequery") == "simplequery"

    def test_real_world_package_name(self):
        """Test escaping real-world package names with slashes."""
        assert escape_elasticsearch_query("quilt/demo") == r"quilt\/demo"
        assert escape_elasticsearch_query("team/analysis-v2") == r"team\/analysis\-v2"

    def test_real_world_file_paths(self):
        """Test escaping real-world file paths."""
        assert escape_elasticsearch_query("s3://bucket/path/to/file.csv") == r"s3\:\/\/bucket\/path\/to\/file.csv"
