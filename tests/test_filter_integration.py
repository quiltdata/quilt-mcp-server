"""Integration tests for natural language filter parameter in PackageCreateFromS3Params.

Tests the model_validator that automatically parses the filter parameter
and populates include_patterns and exclude_patterns.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from quilt_mcp.models.inputs import PackageCreateFromS3Params
from quilt_mcp.services.filter_parser import FilterPatterns


@pytest.fixture
def mock_parse_filter():
    """Mock the parse_file_filter function."""
    with patch("quilt_mcp.services.filter_parser.parse_file_filter") as mock:
        yield mock


class TestFilterParameterValidation:
    """Test filter parameter validation in PackageCreateFromS3Params."""

    def test_no_filter_no_patterns(self):
        """Test creating params without filter or patterns."""
        params = PackageCreateFromS3Params(
            source_bucket="test-bucket",
            package_name="team/dataset",
        )
        assert params.filter is None
        assert params.include_patterns is None
        assert params.exclude_patterns is None

    def test_filter_parsed_when_no_patterns(self, mock_parse_filter):
        """Test filter is parsed when no explicit patterns provided."""
        mock_parse_filter.return_value = FilterPatterns(
            include=["*.csv", "*.json"],
            exclude=["*.tmp"],
        )

        params = PackageCreateFromS3Params(
            source_bucket="test-bucket",
            package_name="team/dataset",
            filter="include CSV and JSON files but exclude temp files",
        )

        # Verify parse_file_filter was called
        mock_parse_filter.assert_called_once_with(
            "include CSV and JSON files but exclude temp files"
        )

        # Verify patterns were populated
        assert params.include_patterns == ["*.csv", "*.json"]
        assert params.exclude_patterns == ["*.tmp"]

    def test_filter_ignored_when_include_patterns_set(self, mock_parse_filter):
        """Test filter is ignored when include_patterns explicitly set."""
        params = PackageCreateFromS3Params(
            source_bucket="test-bucket",
            package_name="team/dataset",
            filter="include CSV and JSON files",
            include_patterns=["*.parquet"],  # Explicit pattern overrides
        )

        # Parser should not be called
        mock_parse_filter.assert_not_called()

        # Explicit patterns should be used
        assert params.include_patterns == ["*.parquet"]

    def test_filter_ignored_when_exclude_patterns_set(self, mock_parse_filter):
        """Test filter is ignored when exclude_patterns explicitly set."""
        params = PackageCreateFromS3Params(
            source_bucket="test-bucket",
            package_name="team/dataset",
            filter="exclude temp files",
            exclude_patterns=["*.log"],  # Explicit pattern overrides
        )

        # Parser should not be called
        mock_parse_filter.assert_not_called()

        # Explicit patterns should be used
        assert params.exclude_patterns == ["*.log"]

    def test_filter_ignored_when_both_patterns_set(self, mock_parse_filter):
        """Test filter is ignored when both patterns explicitly set."""
        params = PackageCreateFromS3Params(
            source_bucket="test-bucket",
            package_name="team/dataset",
            filter="some filter description",
            include_patterns=["*.csv"],
            exclude_patterns=["*.tmp"],
        )

        # Parser should not be called
        mock_parse_filter.assert_not_called()

        # Explicit patterns should be used
        assert params.include_patterns == ["*.csv"]
        assert params.exclude_patterns == ["*.tmp"]

    def test_filter_parsing_error_raises_valueerror(self, mock_parse_filter):
        """Test that parsing errors are raised as ValueError with context."""
        mock_parse_filter.side_effect = Exception("API Error")

        with pytest.raises(ValueError) as exc_info:
            PackageCreateFromS3Params(
                source_bucket="test-bucket",
                package_name="team/dataset",
                filter="invalid filter",
            )

        # Error should include the filter text for debugging
        assert "invalid filter" in str(exc_info.value)
        assert "Failed to parse" in str(exc_info.value)

    def test_empty_filter_not_parsed(self, mock_parse_filter):
        """Test empty filter string is not parsed."""
        params = PackageCreateFromS3Params(
            source_bucket="test-bucket",
            package_name="team/dataset",
            filter="",
        )

        # Parser should not be called for empty string
        mock_parse_filter.assert_not_called()
        assert params.include_patterns is None
        assert params.exclude_patterns is None

    def test_filter_with_include_only(self, mock_parse_filter):
        """Test filter that produces only include patterns."""
        mock_parse_filter.return_value = FilterPatterns(
            include=["*.csv", "*.json"],
            exclude=[],
        )

        params = PackageCreateFromS3Params(
            source_bucket="test-bucket",
            package_name="team/dataset",
            filter="only CSV and JSON files",
        )

        assert params.include_patterns == ["*.csv", "*.json"]
        # exclude_patterns remains None when empty list returned
        # (validator only sets non-empty lists)
        assert params.exclude_patterns is None or params.exclude_patterns == []

    def test_filter_with_exclude_only(self, mock_parse_filter):
        """Test filter that produces only exclude patterns."""
        mock_parse_filter.return_value = FilterPatterns(
            include=[],
            exclude=["*.tmp", "*.log"],
        )

        params = PackageCreateFromS3Params(
            source_bucket="test-bucket",
            package_name="team/dataset",
            filter="exclude temp and log files",
        )

        # include_patterns remains None when empty list returned
        # (validator only sets non-empty lists)
        assert params.include_patterns is None or params.include_patterns == []
        assert params.exclude_patterns == ["*.tmp", "*.log"]


class TestFilterWithPresets:
    """Test interaction between filter parameter and presets."""

    def test_preset_and_filter(self, mock_parse_filter):
        """Test that filter works alongside preset."""
        mock_parse_filter.return_value = FilterPatterns(
            include=["*.csv"],
            exclude=["*.tmp"],
        )

        params = PackageCreateFromS3Params(
            source_bucket="test-bucket",
            package_name="team/dataset",
            preset="simple",
            filter="CSV files excluding temp",
        )

        # Both preset and filter should be applied
        assert params.include_patterns == ["*.csv"]
        assert params.exclude_patterns == ["*.tmp"]

    def test_preset_patterns_overridden_by_filter(self, mock_parse_filter):
        """Test that filter overrides preset patterns when no explicit patterns."""
        mock_parse_filter.return_value = FilterPatterns(
            include=["*.json"],  # Different from preset
            exclude=[],
        )

        # filtered-csv preset has include_patterns=["*.csv"]
        params = PackageCreateFromS3Params(
            source_bucket="test-bucket",
            package_name="team/dataset",
            preset="filtered-csv",
            filter="only JSON files",
        )

        # Filter should override preset patterns
        assert params.include_patterns == ["*.json"]

    def test_explicit_patterns_override_both_preset_and_filter(self, mock_parse_filter):
        """Test explicit patterns take precedence over both preset and filter."""
        params = PackageCreateFromS3Params(
            source_bucket="test-bucket",
            package_name="team/dataset",
            preset="filtered-csv",
            filter="only JSON files",
            include_patterns=["*.parquet"],  # Explicit wins
        )

        # Parser should not be called
        mock_parse_filter.assert_not_called()

        # Explicit pattern should be used
        assert params.include_patterns == ["*.parquet"]


class TestFilterExamples:
    """Test realistic filter examples that users might provide."""

    def test_csv_and_json_exclude_temp(self, mock_parse_filter):
        """Test: 'include CSV and JSON files but exclude temp files'"""
        mock_parse_filter.return_value = FilterPatterns(
            include=["*.csv", "*.json"],
            exclude=["*.tmp", "*temp*", "temp/*"],
        )

        params = PackageCreateFromS3Params(
            source_bucket="test-bucket",
            package_name="team/dataset",
            filter="include CSV and JSON files but exclude temp files",
        )

        assert "*.csv" in params.include_patterns
        assert "*.json" in params.include_patterns
        assert any("tmp" in p or "temp" in p for p in params.exclude_patterns)

    def test_parquet_in_data_folder(self, mock_parse_filter):
        """Test: 'only parquet files in the data folder'"""
        mock_parse_filter.return_value = FilterPatterns(
            include=["data/*.parquet", "data/**/*.parquet"],
            exclude=[],
        )

        params = PackageCreateFromS3Params(
            source_bucket="test-bucket",
            package_name="team/dataset",
            filter="only parquet files in the data folder",
        )

        assert any("data" in p and "parquet" in p for p in params.include_patterns)

    def test_images_except_thumbnails(self, mock_parse_filter):
        """Test: 'all images except thumbnails'"""
        mock_parse_filter.return_value = FilterPatterns(
            include=["*.jpg", "*.jpeg", "*.png", "*.gif", "*.bmp", "*.svg"],
            exclude=["*thumb*", "*thumbnail*", "thumbs/*", "thumbnails/*"],
        )

        params = PackageCreateFromS3Params(
            source_bucket="test-bucket",
            package_name="team/dataset",
            filter="all images except thumbnails",
        )

        # Should have multiple image extensions
        assert len(params.include_patterns) >= 4
        # Should exclude thumbnails
        assert any("thumb" in p.lower() for p in params.exclude_patterns)

    def test_python_excluding_tests(self, mock_parse_filter):
        """Test: 'Python files excluding tests and __pycache__'"""
        mock_parse_filter.return_value = FilterPatterns(
            include=["*.py"],
            exclude=["test_*.py", "*_test.py", "tests/*", "__pycache__/*", "*.pyc"],
        )

        params = PackageCreateFromS3Params(
            source_bucket="test-bucket",
            package_name="team/dataset",
            filter="Python files excluding tests and __pycache__",
        )

        assert "*.py" in params.include_patterns
        assert any("test" in p.lower() for p in params.exclude_patterns)
        assert any("pycache" in p.lower() for p in params.exclude_patterns)


class TestValidatorOrder:
    """Test that validators run in the correct order."""

    def test_preset_then_filter(self, mock_parse_filter):
        """Test that preset is applied before filter parsing."""
        mock_parse_filter.return_value = FilterPatterns(
            include=["*.csv"],
            exclude=["*.tmp"],
        )

        params = PackageCreateFromS3Params(
            source_bucket="test-bucket",
            package_name="team/dataset",
            preset="simple",
            filter="CSV files only",
            description="",  # Will be set by preset
        )

        # Preset's description should be applied
        # Filter should be parsed and patterns set
        assert params.include_patterns == ["*.csv"]
        assert params.exclude_patterns == ["*.tmp"]


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set - skipping live API test",
)
class TestLiveIntegration:
    """Integration tests with actual Claude API calls."""

    def test_live_csv_json_filter(self):
        """Test real API call for CSV/JSON filter."""
        params = PackageCreateFromS3Params(
            source_bucket="test-bucket",
            package_name="team/dataset",
            filter="include CSV and JSON files but exclude temp files",
        )

        # Should have reasonable patterns from Claude
        assert params.include_patterns is not None
        assert params.exclude_patterns is not None
        assert any("csv" in p.lower() for p in params.include_patterns)
        assert any("json" in p.lower() for p in params.include_patterns)
        assert any(
            "tmp" in p.lower() or "temp" in p.lower()
            for p in params.exclude_patterns
        )

    def test_live_image_filter(self):
        """Test real API call for image filter."""
        params = PackageCreateFromS3Params(
            source_bucket="test-bucket",
            package_name="team/dataset",
            filter="all images except thumbnails",
        )

        # Should have image extensions
        assert params.include_patterns is not None
        assert len(params.include_patterns) > 0
        assert any(
            ext in p.lower()
            for p in params.include_patterns
            for ext in ["jpg", "jpeg", "png", "gif"]
        )

        # Should exclude thumbnails
        assert params.exclude_patterns is not None
        assert any("thumb" in p.lower() for p in params.exclude_patterns)
