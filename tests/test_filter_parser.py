"""Tests for natural language filter parser service.

Tests the FilterParserService which uses Claude Haiku to convert natural
language filter descriptions into glob patterns for file filtering.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, Mock, patch

import pytest
from anthropic.types import Message, TextBlock, Usage

from quilt_mcp.services.filter_parser import (
    FilterParserService,
    FilterPatterns,
    get_default_parser,
    parse_file_filter,
)


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for testing."""
    with patch("quilt_mcp.services.filter_parser.Anthropic") as mock_anthropic:
        mock_client = Mock()
        mock_anthropic.return_value = mock_client
        yield mock_client


@pytest.fixture
def filter_parser(mock_anthropic_client):
    """Create FilterParserService with mocked Anthropic client."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        return FilterParserService()


class TestFilterPatterns:
    """Test FilterPatterns model."""

    def test_empty_patterns(self):
        """Test creating empty patterns."""
        patterns = FilterPatterns()
        assert patterns.include == []
        assert patterns.exclude == []

    def test_with_include_only(self):
        """Test patterns with include only."""
        patterns = FilterPatterns(include=["*.csv", "*.json"])
        assert patterns.include == ["*.csv", "*.json"]
        assert patterns.exclude == []

    def test_with_exclude_only(self):
        """Test patterns with exclude only."""
        patterns = FilterPatterns(exclude=["*.tmp", "*.log"])
        assert patterns.include == []
        assert patterns.exclude == ["*.tmp", "*.log"]

    def test_with_both(self):
        """Test patterns with both include and exclude."""
        patterns = FilterPatterns(
            include=["*.csv"], exclude=["*temp*", "test/*"]
        )
        assert patterns.include == ["*.csv"]
        assert patterns.exclude == ["*temp*", "test/*"]


class TestFilterParserService:
    """Test FilterParserService."""

    def test_init_with_api_key(self):
        """Test initializing with explicit API key."""
        parser = FilterParserService(api_key="my-key")
        assert parser._api_key == "my-key"

    def test_init_with_env_var(self):
        """Test initializing with API key from environment."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-key"}):
            parser = FilterParserService()
            assert parser._api_key == "env-key"

    def test_init_without_api_key(self):
        """Test initialization fails without API key."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="API key required"):
                FilterParserService()

    def test_parse_empty_filter(self, filter_parser):
        """Test parsing empty or whitespace-only filter."""
        result = filter_parser.parse_filter("")
        assert result.include == []
        assert result.exclude == []

        result = filter_parser.parse_filter("   ")
        assert result.include == []
        assert result.exclude == []

    def test_parse_csv_and_json(self, filter_parser, mock_anthropic_client):
        """Test parsing 'include CSV and JSON' filter."""
        # Mock Claude response
        mock_response = Message(
            id="msg_123",
            type="message",
            role="assistant",
            content=[
                TextBlock(
                    type="text",
                    text='{"include": ["*.csv", "*.json"], "exclude": []}',
                )
            ],
            model="claude-3-5-haiku-20241022",
            stop_reason="end_turn",
            usage=Usage(input_tokens=100, output_tokens=50),
        )
        mock_anthropic_client.messages.create.return_value = mock_response

        result = filter_parser.parse_filter("include CSV and JSON files")

        assert result.include == ["*.csv", "*.json"]
        assert result.exclude == []

        # Verify API was called correctly
        mock_anthropic_client.messages.create.assert_called_once()
        call_args = mock_anthropic_client.messages.create.call_args
        assert call_args.kwargs["model"] == "claude-3-5-haiku-20241022"
        assert call_args.kwargs["temperature"] == 0.0
        assert "include CSV and JSON files" in call_args.kwargs["messages"][0]["content"]

    def test_parse_exclude_temp_files(self, filter_parser, mock_anthropic_client):
        """Test parsing filter with exclusions."""
        mock_response = Message(
            id="msg_123",
            type="message",
            role="assistant",
            content=[
                TextBlock(
                    type="text",
                    text='{"include": ["*.csv"], "exclude": ["*.tmp", "*temp*", "temp/*"]}',
                )
            ],
            model="claude-3-5-haiku-20241022",
            stop_reason="end_turn",
            usage=Usage(input_tokens=100, output_tokens=50),
        )
        mock_anthropic_client.messages.create.return_value = mock_response

        result = filter_parser.parse_filter("CSV files but exclude temp files")

        assert result.include == ["*.csv"]
        assert result.exclude == ["*.tmp", "*temp*", "temp/*"]

    def test_parse_data_folder_only(self, filter_parser, mock_anthropic_client):
        """Test parsing filter for specific folder."""
        mock_response = Message(
            id="msg_123",
            type="message",
            role="assistant",
            content=[
                TextBlock(
                    type="text",
                    text='{"include": ["data/*.parquet", "data/**/*.parquet"], "exclude": []}',
                )
            ],
            model="claude-3-5-haiku-20241022",
            stop_reason="end_turn",
            usage=Usage(input_tokens=100, output_tokens=50),
        )
        mock_anthropic_client.messages.create.return_value = mock_response

        result = filter_parser.parse_filter("only parquet files in the data folder")

        assert "data/*.parquet" in result.include
        assert result.exclude == []

    def test_parse_images_except_thumbnails(self, filter_parser, mock_anthropic_client):
        """Test parsing complex filter with multiple extensions."""
        mock_response = Message(
            id="msg_123",
            type="message",
            role="assistant",
            content=[
                TextBlock(
                    type="text",
                    text='{"include": ["*.jpg", "*.jpeg", "*.png", "*.gif"], '
                    '"exclude": ["*thumb*", "*thumbnail*", "thumbs/*"]}',
                )
            ],
            model="claude-3-5-haiku-20241022",
            stop_reason="end_turn",
            usage=Usage(input_tokens=100, output_tokens=50),
        )
        mock_anthropic_client.messages.create.return_value = mock_response

        result = filter_parser.parse_filter("all images except thumbnails")

        assert len(result.include) >= 4
        assert "*.jpg" in result.include
        assert "*.png" in result.include
        assert "*thumb*" in result.exclude or "*thumbnail*" in result.exclude

    def test_parse_json_in_markdown(self, filter_parser, mock_anthropic_client):
        """Test parsing when Claude returns JSON in markdown code block."""
        mock_response = Message(
            id="msg_123",
            type="message",
            role="assistant",
            content=[
                TextBlock(
                    type="text",
                    text='```json\n{"include": ["*.py"], "exclude": ["test_*.py"]}\n```',
                )
            ],
            model="claude-3-5-haiku-20241022",
            stop_reason="end_turn",
            usage=Usage(input_tokens=100, output_tokens=50),
        )
        mock_anthropic_client.messages.create.return_value = mock_response

        result = filter_parser.parse_filter("Python files excluding tests")

        assert result.include == ["*.py"]
        assert result.exclude == ["test_*.py"]

    def test_parse_invalid_json(self, filter_parser, mock_anthropic_client):
        """Test error handling for invalid JSON response."""
        mock_response = Message(
            id="msg_123",
            type="message",
            role="assistant",
            content=[TextBlock(type="text", text="This is not JSON")],
            model="claude-3-5-haiku-20241022",
            stop_reason="end_turn",
            usage=Usage(input_tokens=100, output_tokens=50),
        )
        mock_anthropic_client.messages.create.return_value = mock_response

        with pytest.raises(ValueError, match="Invalid JSON response"):
            filter_parser.parse_filter("some filter")

    def test_parse_invalid_structure(self, filter_parser, mock_anthropic_client):
        """Test that JSON with wrong keys still creates valid (empty) patterns.

        Pydantic allows extra keys and provides defaults for missing ones,
        so this doesn't raise an error - it just returns empty patterns.
        """
        mock_response = Message(
            id="msg_123",
            type="message",
            role="assistant",
            content=[
                TextBlock(
                    type="text",
                    text='{"wrong": "structure", "missing": "keys"}',
                )
            ],
            model="claude-3-5-haiku-20241022",
            stop_reason="end_turn",
            usage=Usage(input_tokens=100, output_tokens=50),
        )
        mock_anthropic_client.messages.create.return_value = mock_response

        # This should succeed but return empty patterns (Pydantic uses defaults)
        result = filter_parser.parse_filter("some filter")
        assert result.include == []
        assert result.exclude == []

    def test_parse_empty_response(self, filter_parser, mock_anthropic_client):
        """Test error handling for empty response."""
        mock_response = Message(
            id="msg_123",
            type="message",
            role="assistant",
            content=[],
            model="claude-3-5-haiku-20241022",
            stop_reason="end_turn",
            usage=Usage(input_tokens=100, output_tokens=0),
        )
        mock_anthropic_client.messages.create.return_value = mock_response

        with pytest.raises(ValueError, match="Empty response"):
            filter_parser.parse_filter("some filter")

    def test_parse_api_error(self, filter_parser, mock_anthropic_client):
        """Test error handling for API failures."""
        mock_anthropic_client.messages.create.side_effect = Exception("API Error")

        with pytest.raises(ValueError, match="Failed to parse filter"):
            filter_parser.parse_filter("some filter")


class TestConvenienceFunctions:
    """Test convenience functions for filter parsing."""

    @patch("quilt_mcp.services.filter_parser.FilterParserService")
    def test_get_default_parser(self, mock_parser_class):
        """Test getting default parser singleton."""
        # Reset singleton
        import quilt_mcp.services.filter_parser as filter_module

        filter_module._default_parser = None

        mock_instance = Mock()
        mock_parser_class.return_value = mock_instance

        # First call creates instance
        parser1 = get_default_parser()
        assert parser1 is mock_instance
        mock_parser_class.assert_called_once()

        # Second call returns same instance
        parser2 = get_default_parser()
        assert parser2 is mock_instance
        assert mock_parser_class.call_count == 1  # Not called again

    @patch("quilt_mcp.services.filter_parser.get_default_parser")
    def test_parse_file_filter(self, mock_get_parser):
        """Test parse_file_filter convenience function."""
        mock_parser = Mock()
        mock_parser.parse_filter.return_value = FilterPatterns(
            include=["*.csv"], exclude=["*.tmp"]
        )
        mock_get_parser.return_value = mock_parser

        result = parse_file_filter("CSV files only")

        assert result.include == ["*.csv"]
        assert result.exclude == ["*.tmp"]
        mock_parser.parse_filter.assert_called_once_with("CSV files only")


class TestPromptBuilding:
    """Test prompt generation for Claude."""

    def test_prompt_includes_filter(self, filter_parser):
        """Test that prompt includes user's filter description."""
        prompt = filter_parser._build_prompt("include CSV files")
        assert "include CSV files" in prompt

    def test_prompt_has_examples(self, filter_parser):
        """Test that prompt includes helpful examples."""
        prompt = filter_parser._build_prompt("some filter")
        assert "Examples:" in prompt or "Example:" in prompt
        assert "*.csv" in prompt  # Should have file extension examples
        assert "include" in prompt.lower()
        assert "exclude" in prompt.lower()

    def test_prompt_has_rules(self, filter_parser):
        """Test that prompt includes parsing rules."""
        prompt = filter_parser._build_prompt("some filter")
        assert "Rules:" in prompt or "rule" in prompt.lower()
        assert "glob" in prompt.lower()

    def test_prompt_requests_json(self, filter_parser):
        """Test that prompt requests JSON format."""
        prompt = filter_parser._build_prompt("some filter")
        assert "JSON" in prompt or "json" in prompt
        assert "include" in prompt
        assert "exclude" in prompt


class TestIntegration:
    """Integration tests with PackageCreateFromS3Params (requires real parsing)."""

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set - skipping live API test",
    )
    def test_live_api_csv_json(self):
        """Test actual Claude API call for CSV/JSON filter."""
        parser = FilterParserService()
        result = parser.parse_filter("include CSV and JSON files but exclude temp files")

        # Verify we got reasonable patterns
        assert any("csv" in p.lower() for p in result.include)
        assert any("json" in p.lower() for p in result.include)
        assert any("tmp" in p.lower() or "temp" in p.lower() for p in result.exclude)

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set - skipping live API test",
    )
    def test_live_api_images(self):
        """Test actual Claude API call for image filter."""
        parser = FilterParserService()
        result = parser.parse_filter("all images except thumbnails")

        # Verify we got image extensions
        assert len(result.include) > 0
        assert any(
            ext in p.lower()
            for p in result.include
            for ext in ["jpg", "jpeg", "png", "gif"]
        )
        assert len(result.exclude) > 0
        assert any("thumb" in p.lower() for p in result.exclude)

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set - skipping live API test",
    )
    def test_live_api_python_files(self):
        """Test actual Claude API call for Python file filter."""
        parser = FilterParserService()
        result = parser.parse_filter(
            "Python files excluding tests and __pycache__"
        )

        # Verify we got Python patterns
        assert any("*.py" in p for p in result.include)
        assert any(
            test_pattern in p.lower()
            for p in result.exclude
            for test_pattern in ["test", "pycache", "pyc"]
        )
