"""Unit tests for helper functions in packages.py.

Tests the internal helper functions used by package tools, particularly
the _should_include_object function which filters S3 objects based on
characters and patterns.
"""

import pytest

from quilt_mcp.tools.packages import _should_include_object


class TestShouldIncludeObject:
    """Test _should_include_object function for character and pattern filtering."""

    # UTF-8 Support Tests
    def test_allows_utf8_accented_characters(self):
        """Should allow accented Latin characters (UTF-8)."""
        # Common accented characters
        assert _should_include_object("café.txt", None, None) is True
        assert _should_include_object("naïve.csv", None, None) is True
        assert _should_include_object("résumé.pdf", None, None) is True
        assert _should_include_object("Zürich.json", None, None) is True
        assert _should_include_object("señor.parquet", None, None) is True

    def test_allows_utf8_non_latin_scripts(self):
        """Should allow non-Latin scripts (UTF-8)."""
        # Japanese
        assert _should_include_object("日本語.txt", None, None) is True
        assert _should_include_object("data_日本.csv", None, None) is True

        # Chinese
        assert _should_include_object("中文.json", None, None) is True

        # Korean
        assert _should_include_object("한국어.parquet", None, None) is True

        # Arabic
        assert _should_include_object("العربية.txt", None, None) is True

        # Cyrillic
        assert _should_include_object("Москва.csv", None, None) is True

    def test_allows_utf8_emojis(self):
        """Should allow emoji characters (UTF-8)."""
        assert _should_include_object("data_📊.csv", None, None) is True
        assert _should_include_object("report_✅.json", None, None) is True
        assert _should_include_object("🔥_metrics.parquet", None, None) is True

    def test_allows_utf8_mixed_scripts(self):
        """Should allow mixed scripts and characters."""
        assert _should_include_object("data_2024_日本_café.csv", None, None) is True
        assert _should_include_object("report_année_2024_📊.json", None, None) is True

    # Invalid S3 Character Tests
    def test_blocks_invalid_s3_characters(self):
        """Should block characters that cause issues in S3 keys."""
        # Backslash
        assert _should_include_object("path\\file.txt", None, None) is False

        # Opening brace
        assert _should_include_object("file{test}.txt", None, None) is False

        # Closing brace
        assert _should_include_object("file}test.txt", None, None) is False

        # Caret
        assert _should_include_object("file^test.txt", None, None) is False

        # Percent
        assert _should_include_object("file%test.txt", None, None) is False

        # Backtick
        assert _should_include_object("file`test.txt", None, None) is False

        # Square brackets
        assert _should_include_object("file]test.txt", None, None) is False
        assert _should_include_object('file"test.txt', None, None) is False

        # Angle brackets
        assert _should_include_object("file>test.txt", None, None) is False
        assert _should_include_object("file<test.txt", None, None) is False

        # Tilde, hash, pipe
        assert _should_include_object("file~test.txt", None, None) is False
        assert _should_include_object("file#test.txt", None, None) is False
        assert _should_include_object("file|test.txt", None, None) is False

    def test_blocks_multiple_invalid_characters(self):
        """Should block keys with multiple invalid characters."""
        assert _should_include_object("path\\to{file}.txt", None, None) is False
        assert _should_include_object("file^%test.txt", None, None) is False

    # Non-printable Character Tests
    def test_blocks_control_characters(self):
        """Should block control characters (non-printable)."""
        # Null byte
        assert _should_include_object("file\x00test.txt", None, None) is False

        # Bell character
        assert _should_include_object("file\x07test.txt", None, None) is False

        # Backspace
        assert _should_include_object("file\x08test.txt", None, None) is False

        # Form feed
        assert _should_include_object("file\x0ctest.txt", None, None) is False

        # Escape
        assert _should_include_object("file\x1btest.txt", None, None) is False

    def test_blocks_delete_character(self):
        """Should block DEL character (127)."""
        assert _should_include_object("file\x7ftest.txt", None, None) is False

    def test_allows_space_characters(self):
        """Should allow space characters (printable whitespace)."""
        # Space is the only whitespace character considered "printable" by Python
        assert _should_include_object("file test.txt", None, None) is True
        assert _should_include_object("my file name.csv", None, None) is True

    def test_blocks_non_printable_whitespace(self):
        """Should block non-printable whitespace characters."""
        # Tab (not considered printable by Python)
        assert _should_include_object("file\ttest.txt", None, None) is False

        # Vertical tab
        assert _should_include_object("file\x0btest.txt", None, None) is False

    # Valid S3 Key Tests
    def test_allows_standard_ascii_filenames(self):
        """Should allow standard ASCII filenames."""
        assert _should_include_object("file.txt", None, None) is True
        assert _should_include_object("data_2024.csv", None, None) is True
        assert _should_include_object("report-final.json", None, None) is True
        assert _should_include_object("path/to/file.parquet", None, None) is True

    def test_allows_numbers_and_underscores(self):
        """Should allow numbers and underscores."""
        assert _should_include_object("file_123_test.txt", None, None) is True
        assert _should_include_object("2024_data.csv", None, None) is True

    def test_allows_hyphens_and_dots(self):
        """Should allow hyphens and dots."""
        assert _should_include_object("my-file.test.txt", None, None) is True
        assert _should_include_object("file-v2.0.1.json", None, None) is True

    def test_allows_parentheses_and_plus(self):
        """Should allow parentheses and plus signs (valid S3 chars)."""
        assert _should_include_object("file(1).txt", None, None) is True
        assert _should_include_object("data+backup.csv", None, None) is True

    def test_allows_equals_and_at_signs(self):
        """Should allow equals and at signs (valid S3 chars)."""
        assert _should_include_object("file=test.txt", None, None) is True
        assert _should_include_object("user@domain.csv", None, None) is True

    # Include Pattern Tests
    def test_include_patterns_csv_only(self):
        """Should filter by include patterns."""
        # CSV only
        assert _should_include_object("data.csv", ["*.csv"], None) is True
        assert _should_include_object("data.json", ["*.csv"], None) is False

    def test_include_patterns_multiple(self):
        """Should match any of multiple include patterns."""
        patterns = ["*.csv", "*.json"]
        assert _should_include_object("data.csv", patterns, None) is True
        assert _should_include_object("data.json", patterns, None) is True
        assert _should_include_object("data.parquet", patterns, None) is False

    def test_include_patterns_with_path(self):
        """Should match include patterns with paths."""
        patterns = ["data/*.csv"]
        assert _should_include_object("data/file.csv", patterns, None) is True
        assert _should_include_object("other/file.csv", patterns, None) is False

    # Exclude Pattern Tests
    def test_exclude_patterns_tmp_files(self):
        """Should exclude files matching exclude patterns."""
        assert _should_include_object("data.csv", None, ["*.tmp"]) is True
        assert _should_include_object("data.tmp", None, ["*.tmp"]) is False

    def test_exclude_patterns_multiple(self):
        """Should exclude files matching any exclude pattern."""
        patterns = ["*.tmp", "*.log"]
        assert _should_include_object("data.csv", None, patterns) is True
        assert _should_include_object("data.tmp", None, patterns) is False
        assert _should_include_object("data.log", None, patterns) is False

    def test_exclude_patterns_with_path(self):
        """Should exclude paths matching patterns."""
        patterns = ["temp/*"]
        assert _should_include_object("data/file.csv", None, patterns) is True
        assert _should_include_object("temp/file.csv", None, patterns) is False

    # Combined Pattern Tests
    def test_include_and_exclude_patterns(self):
        """Should apply both include and exclude patterns."""
        include = ["*.csv"]
        exclude = ["*_backup.csv"]

        # Matches include, not excluded
        assert _should_include_object("data.csv", include, exclude) is True

        # Matches include but also excluded
        assert _should_include_object("data_backup.csv", include, exclude) is False

        # Doesn't match include
        assert _should_include_object("data.json", include, exclude) is False

    def test_exclude_takes_priority_over_include(self):
        """Exclude patterns should take priority over include patterns."""
        include = ["data/*"]
        exclude = ["data/temp/*"]

        assert _should_include_object("data/file.csv", include, exclude) is True
        assert _should_include_object("data/temp/file.csv", include, exclude) is False

    # Invalid Characters Take Priority Tests
    def test_invalid_chars_block_even_with_include_pattern(self):
        """Invalid characters should block even if include pattern matches."""
        include = ["*.csv"]
        assert _should_include_object("data.csv", include, None) is True
        assert _should_include_object("data{test}.csv", include, None) is False

    def test_non_printable_blocks_even_with_include_pattern(self):
        """Non-printable characters should block even if include pattern matches."""
        include = ["*.csv"]
        assert _should_include_object("data.csv", include, None) is True
        assert _should_include_object("data\x00.csv", include, None) is False

    def test_invalid_chars_block_before_pattern_checking(self):
        """Invalid characters should be checked before pattern matching."""
        # This ensures efficiency - no point checking patterns if chars are invalid
        include = ["data/*"]
        assert _should_include_object("data/file^.csv", include, None) is False

    # Edge Cases
    def test_empty_string_key(self):
        """Should handle empty string key."""
        # Empty string is printable, has no invalid chars
        assert _should_include_object("", None, None) is True

    def test_very_long_utf8_key(self):
        """Should handle very long UTF-8 keys."""
        long_key = "データ" * 100 + ".csv"
        assert _should_include_object(long_key, None, None) is True

    def test_key_with_only_emojis(self):
        """Should handle keys that are only emojis."""
        assert _should_include_object("📊📈📉.csv", None, None) is True

    def test_newline_in_key_is_not_printable(self):
        """Newlines should be considered non-printable and blocked."""
        assert _should_include_object("file\ntest.txt", None, None) is False

    def test_carriage_return_is_not_printable(self):
        """Carriage returns should be considered non-printable and blocked."""
        assert _should_include_object("file\rtest.txt", None, None) is False

    # Real-world Filename Tests
    def test_real_world_scientific_filenames(self):
        """Should handle real-world scientific data filenames."""
        assert _should_include_object("experiment_2024-01-15_résultats.csv", None, None) is True
        assert _should_include_object("données_françaises.parquet", None, None) is True
        assert _should_include_object("测试数据_2024.json", None, None) is True

    def test_real_world_multilingual_reports(self):
        """Should handle multilingual report filenames."""
        assert _should_include_object("Q4_Report_日本_2024.pdf", None, None) is True
        assert _should_include_object("Informe_Español_2024.docx", None, None) is True
        assert _should_include_object("Bericht_Zürich_2024.xlsx", None, None) is True
