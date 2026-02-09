"""Unit tests for quilt_mcp.testing.config module.

Tests configuration loading, filtering, selector parsing, and response truncation.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch, mock_open

import pytest
import yaml

from quilt_mcp.testing.config import (
    load_test_config,
    filter_tests_by_idempotence,
    parse_selector,
    validate_selector_names,
    filter_by_selector,
    truncate_response,
)


class TestLoadTestConfig:
    """Tests for load_test_config function."""

    def test_load_valid_config(self, tmp_path: Path):
        """Load valid YAML configuration with required environment variables."""
        config_data = {
            "environment": {"QUILT_TEST_BUCKET": "test-bucket"},
            "test_tools": {"bucket_list": {"args": {}, "effect": "none"}},
        }
        config_path = tmp_path / "test-config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        # Clear environment to test setting
        with patch.dict(os.environ, {"QUILT_TEST_BUCKET": ""}, clear=False):
            # Remove the key to simulate it not being set
            if "QUILT_TEST_BUCKET" in os.environ:
                del os.environ["QUILT_TEST_BUCKET"]

            with patch('builtins.print') as mock_print:
                config = load_test_config(config_path)

            assert config["environment"]["QUILT_TEST_BUCKET"] == "test-bucket"
            assert "bucket_list" in config["test_tools"]
            assert os.environ.get("QUILT_TEST_BUCKET") == "test-bucket"
            mock_print.assert_called_once()
            assert "Set QUILT_TEST_BUCKET=test-bucket" in mock_print.call_args[0][0]

    def test_load_config_with_existing_env_var(self, tmp_path: Path):
        """Don't override existing environment variable."""
        config_data = {"environment": {"QUILT_TEST_BUCKET": "config-bucket"}}
        config_path = tmp_path / "test-config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        # Set environment variable first
        with patch.dict(os.environ, {"QUILT_TEST_BUCKET": "existing-bucket"}, clear=False):
            with patch('builtins.print') as mock_print:
                config = load_test_config(config_path)

            # Config should have config value, but env should keep existing
            assert config["environment"]["QUILT_TEST_BUCKET"] == "config-bucket"
            assert os.environ.get("QUILT_TEST_BUCKET") == "existing-bucket"
            # Should not print info message
            assert not any("Set QUILT_TEST_BUCKET" in str(call) for call in mock_print.call_args_list)

    def test_load_config_missing_bucket(self, tmp_path: Path):
        """Exit with error if QUILT_TEST_BUCKET missing."""
        config_data = {"environment": {}}
        config_path = tmp_path / "test-config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        with patch('builtins.print') as mock_print:
            with pytest.raises(SystemExit) as exc_info:
                load_test_config(config_path)

        assert exc_info.value.code == 1
        calls = [str(call) for call in mock_print.call_args_list]
        assert any("QUILT_TEST_BUCKET must be set" in call for call in calls)

    def test_load_config_file_not_found(self, tmp_path: Path):
        """Exit with error if config file doesn't exist."""
        config_path = tmp_path / "nonexistent.yaml"

        with patch('builtins.print') as mock_print:
            with pytest.raises(SystemExit) as exc_info:
                load_test_config(config_path)

        assert exc_info.value.code == 1
        calls = [str(call) for call in mock_print.call_args_list]
        assert any("Test config not found" in call for call in calls)

    def test_load_config_invalid_yaml(self, tmp_path: Path):
        """Exit with error if YAML is malformed."""
        config_path = tmp_path / "invalid.yaml"
        with open(config_path, 'w') as f:
            f.write("invalid: yaml: content: [unclosed")

        with patch('builtins.print') as mock_print:
            with pytest.raises(SystemExit) as exc_info:
                load_test_config(config_path)

        assert exc_info.value.code == 1
        calls = [str(call) for call in mock_print.call_args_list]
        assert any("Invalid YAML config" in call for call in calls)


class TestFilterTestsByIdempotence:
    """Tests for filter_tests_by_idempotence function."""

    def test_filter_idempotent_only(self):
        """Filter to keep only read-only tools."""
        config = {
            "test_tools": {
                "bucket_list": {"effect": "none"},
                "bucket_create": {"effect": "create"},
                "user_list": {"effect": "none-context-required"},
                "package_update": {"effect": "update"},
            },
            "test_resources": {"quilt://bucket/package": {}},
        }

        filtered_config, stats = filter_tests_by_idempotence(config, idempotent_only=True)

        assert len(filtered_config["test_tools"]) == 2
        assert "bucket_list" in filtered_config["test_tools"]
        assert "user_list" in filtered_config["test_tools"]
        assert "bucket_create" not in filtered_config["test_tools"]
        assert "package_update" not in filtered_config["test_tools"]

        assert stats["total_tools"] == 4
        assert stats["total_resources"] == 1
        assert stats["selected_tools"] == 2
        assert stats["effect_counts"]["none"] == 1
        assert stats["effect_counts"]["create"] == 1
        assert stats["effect_counts"]["update"] == 1
        assert stats["effect_counts"]["none-context-required"] == 1

    def test_filter_all_tools(self):
        """Keep all tools when idempotent_only=False."""
        config = {
            "test_tools": {
                "bucket_list": {"effect": "none"},
                "bucket_create": {"effect": "create"},
            },
            "test_resources": {},
        }

        filtered_config, stats = filter_tests_by_idempotence(config, idempotent_only=False)

        assert len(filtered_config["test_tools"]) == 2
        assert "bucket_list" in filtered_config["test_tools"]
        assert "bucket_create" in filtered_config["test_tools"]
        assert stats["selected_tools"] == 2

    def test_filter_empty_config(self):
        """Handle empty configuration."""
        config = {"test_tools": {}, "test_resources": {}}

        filtered_config, stats = filter_tests_by_idempotence(config, idempotent_only=True)

        assert len(filtered_config["test_tools"]) == 0
        assert stats["total_tools"] == 0
        assert stats["selected_tools"] == 0

    def test_filter_default_effect(self):
        """Tools without explicit effect default to 'none'."""
        config = {
            "test_tools": {
                "bucket_list": {},  # No effect specified
                "bucket_create": {"effect": "create"},
            },
            "test_resources": {},
        }

        filtered_config, stats = filter_tests_by_idempotence(config, idempotent_only=True)

        assert len(filtered_config["test_tools"]) == 1
        assert "bucket_list" in filtered_config["test_tools"]
        assert stats["effect_counts"]["none"] == 1


class TestParseSelector:
    """Tests for parse_selector function."""

    def test_parse_all_selector(self):
        """Parse 'all' selector."""
        selection_type, names = parse_selector("all", "tools")
        assert selection_type == "all"
        assert names is None

    def test_parse_none_selector(self):
        """Parse 'none' selector."""
        selection_type, names = parse_selector("none", "tools")
        assert selection_type == "none"
        assert names is None

    def test_parse_none_selector_as_default(self):
        """Parse None as 'all' selector."""
        selection_type, names = parse_selector(None, "tools")
        assert selection_type == "all"
        assert names is None

    def test_parse_specific_single(self):
        """Parse single name selector."""
        selection_type, names = parse_selector("bucket_list", "tools")
        assert selection_type == "specific"
        assert names == ["bucket_list"]

    def test_parse_specific_multiple(self):
        """Parse multiple names selector."""
        selection_type, names = parse_selector("bucket_list,package_list,user_list", "tools")
        assert selection_type == "specific"
        assert names == ["bucket_list", "package_list", "user_list"]

    def test_parse_specific_with_spaces(self):
        """Parse selector with spaces around commas."""
        selection_type, names = parse_selector("bucket_list, package_list", "tools")
        assert selection_type == "specific"
        assert names == ["bucket_list", "package_list"]

    def test_parse_empty_selector_raises(self):
        """Empty selector string raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            parse_selector("", "tools")
        assert "Empty selector for tools" in str(exc_info.value)

    def test_parse_selector_with_empty_names(self):
        """Selector with empty names raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            parse_selector("bucket_list,,package_list", "tools")
        assert "contains empty names" in str(exc_info.value)
        assert "positions [1]" in str(exc_info.value)

    def test_parse_selector_whitespace_only(self):
        """Selector with whitespace-only names raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            parse_selector("bucket_list,  ,package_list", "tools")
        assert "contains empty names" in str(exc_info.value)


class TestValidateSelectorNames:
    """Tests for validate_selector_names function."""

    def test_validate_all_selector_no_validation(self):
        """'all' selector doesn't validate names."""
        available = {"bucket_list": {}, "package_list": {}}
        # Should not raise
        validate_selector_names("all", None, available, "tools")

    def test_validate_none_selector_no_validation(self):
        """'none' selector doesn't validate names."""
        available = {"bucket_list": {}, "package_list": {}}
        # Should not raise
        validate_selector_names("none", None, available, "tools")

    def test_validate_valid_names(self):
        """Valid selector names pass validation."""
        available = {"bucket_list": {}, "package_list": {}, "user_list": {}}
        names = ["bucket_list", "package_list"]
        # Should not raise
        validate_selector_names("specific", names, available, "tools")

    def test_validate_invalid_names(self):
        """Invalid selector names raise ValueError."""
        available = {"bucket_list": {}, "package_list": {}}
        names = ["bucket_list", "invalid_tool", "another_invalid"]

        with pytest.raises(ValueError) as exc_info:
            validate_selector_names("specific", names, available, "tools")

        error_msg = str(exc_info.value)
        assert "Invalid tools names" in error_msg
        assert "invalid_tool" in error_msg
        assert "another_invalid" in error_msg
        assert "Available tools (2):" in error_msg

    def test_validate_shows_available_names(self):
        """Error message shows available names."""
        available = {f"tool_{i:02d}": {} for i in range(15)}  # Use zero-padded numbers for predictable sorting
        names = ["nonexistent"]

        with pytest.raises(ValueError) as exc_info:
            validate_selector_names("specific", names, available, "tools")

        error_msg = str(exc_info.value)
        assert "Available tools (15):" in error_msg
        # Should show first 10 (now tool_00 to tool_09 due to sorting)
        assert "tool_00" in error_msg
        assert "tool_09" in error_msg
        # Should indicate more
        assert "(5 more)" in error_msg


class TestFilterBySelector:
    """Tests for filter_by_selector function."""

    def test_filter_all(self):
        """'all' selector returns all items."""
        items = {"a": 1, "b": 2, "c": 3}
        result = filter_by_selector(items, "all", None)
        assert result == items

    def test_filter_none(self):
        """'none' selector returns empty dict."""
        items = {"a": 1, "b": 2, "c": 3}
        result = filter_by_selector(items, "none", None)
        assert result == {}

    def test_filter_specific(self):
        """'specific' selector returns only specified items."""
        items = {"a": 1, "b": 2, "c": 3, "d": 4}
        names = ["a", "c"]
        result = filter_by_selector(items, "specific", names)
        assert result == {"a": 1, "c": 3}

    def test_filter_specific_nonexistent(self):
        """'specific' selector ignores nonexistent names."""
        items = {"a": 1, "b": 2}
        names = ["a", "c", "d"]
        result = filter_by_selector(items, "specific", names)
        assert result == {"a": 1}

    def test_filter_specific_empty_names(self):
        """'specific' selector with empty names returns empty dict."""
        items = {"a": 1, "b": 2}
        result = filter_by_selector(items, "specific", [])
        assert result == {}


class TestTruncateResponse:
    """Tests for truncate_response function."""

    def test_truncate_primitive_types(self):
        """Primitive types pass through unchanged."""
        assert truncate_response("hello") == "hello"
        assert truncate_response(42) == 42
        assert truncate_response(3.14) == 3.14
        assert truncate_response(True) is True
        assert truncate_response(None) is None

    def test_truncate_non_serializable_primitive(self):
        """Non-serializable primitives convert to string."""

        class CustomObject:
            pass

        obj = CustomObject()
        result = truncate_response(obj)
        assert isinstance(result, str)

    def test_truncate_long_string(self):
        """Long strings are truncated."""
        long_string = "a" * 2000
        response = {"key": long_string}
        result = truncate_response(response, max_size=1000)
        assert len(result["key"]) < len(long_string)
        assert "truncated" in result["key"]
        assert "2000 total chars" in result["key"]

    def test_truncate_short_string(self):
        """Short strings pass through unchanged."""
        response = {"key": "short"}
        result = truncate_response(response)
        assert result == response

    def test_truncate_long_array(self):
        """Long arrays are truncated."""
        long_array = [f"item_{i}" for i in range(100)]
        response = {"results": long_array}
        result = truncate_response(response)
        assert len(result["results"]) == 4  # 3 items + truncation marker
        assert result["results"][0] == "item_0"
        assert result["results"][1] == "item_1"
        assert result["results"][2] == "item_2"
        assert "_truncated" in result["results"][3]
        assert "97 more items" in result["results"][3]["_truncated"]

    def test_truncate_short_array(self):
        """Short arrays pass through unchanged."""
        response = {"results": ["a", "b", "c"]}
        result = truncate_response(response)
        assert result == response

    def test_truncate_nested_dict(self):
        """Nested dicts are recursively truncated."""
        response = {"outer": {"inner": {"data": "x" * 2000}}}
        result = truncate_response(response, max_size=1000)
        assert "truncated" in result["outer"]["inner"]["data"]

    def test_truncate_mixed_types(self):
        """Mixed types are handled correctly."""
        response = {
            "string": "hello",
            "number": 42,
            "array": ["a", "b"],
            "nested": {"key": "value"},
            "long_string": "x" * 2000,
        }
        result = truncate_response(response, max_size=1000)
        assert result["string"] == "hello"
        assert result["number"] == 42
        assert result["array"] == ["a", "b"]
        assert result["nested"] == {"key": "value"}
        assert "truncated" in result["long_string"]

    def test_truncate_non_serializable_values(self):
        """Non-serializable values convert to string."""

        class CustomObject:
            pass

        response = {"object": CustomObject(), "normal": "value"}
        result = truncate_response(response)
        assert isinstance(result["object"], str)
        assert result["normal"] == "value"

    def test_truncate_exception_handling(self):
        """Exceptions during truncation are handled gracefully."""

        class BadObject:
            def __str__(self):
                raise RuntimeError("Cannot convert")

        response = {"bad": BadObject()}
        result = truncate_response(response)
        assert "non-serializable" in result["bad"]

    def test_truncate_non_dict_response(self):
        """Non-dict responses are handled."""
        assert truncate_response("plain string") == "plain string"
        assert truncate_response(123) == 123
        assert truncate_response([1, 2, 3]) == "[1, 2, 3]"
