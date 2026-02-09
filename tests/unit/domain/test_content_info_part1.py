"""Tests for Content_Info domain object validation - Test-Driven Development Implementation.

This test suite follows TDD principles by defining the expected behavior of Content_Info
before implementation. Tests cover validation, required fields, and dataclasses.asdict() compatibility.
"""

from __future__ import annotations

import pytest
from dataclasses import asdict, fields
from typing import Any, Dict, Optional


class TestContentInfoValidation:
    """Test Content_Info validation and field requirements."""

    def test_content_info_can_be_imported(self):
        """Test that Content_Info can be imported from domain module."""
        # This test will fail initially - that's the RED phase of TDD
        from quilt_mcp.domain.content_info import Content_Info

        assert Content_Info is not None

    def test_content_info_is_dataclass(self):
        """Test that Content_Info is implemented as a dataclass."""
        from quilt_mcp.domain.content_info import Content_Info

        # Verify it's a dataclass
        assert hasattr(Content_Info, '__dataclass_fields__')
        assert hasattr(Content_Info, '__dataclass_params__')

    def test_content_info_has_required_fields(self):
        """Test that Content_Info has all required fields as specified in design."""
        from quilt_mcp.domain.content_info import Content_Info

        # Get dataclass fields
        field_names = {field.name for field in fields(Content_Info)}

        # Verify all required fields are present
        required_fields = {'path', 'size', 'type', 'modified_date', 'download_url'}

        assert required_fields.issubset(field_names), f"Missing required fields: {required_fields - field_names}"

    def test_content_info_field_types(self):
        """Test that Content_Info fields have correct type annotations."""
        from quilt_mcp.domain.content_info import Content_Info

        field_types = {field.name: field.type for field in fields(Content_Info)}

        # Verify field types match design specification
        expected_types = {
            'path': str,
            'size': Optional[int],
            'type': str,
            'modified_date': Optional[str],
            'download_url': Optional[str],
        }

        for field_name, expected_type in expected_types.items():
            assert field_name in field_types, f"Field {field_name} missing"
            assert field_types[field_name] == expected_type, (
                f"Field {field_name} has type {field_types[field_name]}, expected {expected_type}"
            )

    def test_content_info_creation_with_all_fields(self):
        """Test creating Content_Info with all fields provided."""
        from quilt_mcp.domain.content_info import Content_Info

        content_info = Content_Info(
            path="data/analysis/results.csv",
            size=1024768,
            type="file",
            modified_date="2024-01-15T10:30:00Z",
            download_url="https://example.com/download/results.csv",
        )

        assert content_info.path == "data/analysis/results.csv"
        assert content_info.size == 1024768
        assert content_info.type == "file"
        assert content_info.modified_date == "2024-01-15T10:30:00Z"
        assert content_info.download_url == "https://example.com/download/results.csv"

    def test_content_info_creation_with_directory_type(self):
        """Test creating Content_Info for directory type."""
        from quilt_mcp.domain.content_info import Content_Info

        content_info = Content_Info(
            path="data/analysis/", size=None, type="directory", modified_date="2024-01-15T10:30:00Z", download_url=None
        )

        assert content_info.path == "data/analysis/"
        assert content_info.size is None
        assert content_info.type == "directory"
        assert content_info.modified_date == "2024-01-15T10:30:00Z"
        assert content_info.download_url is None

    def test_content_info_creation_with_optional_fields_none(self):
        """Test creating Content_Info with optional fields as None."""
        from quilt_mcp.domain.content_info import Content_Info

        content_info = Content_Info(
            path="data/unknown_file.dat", size=None, type="file", modified_date=None, download_url=None
        )

        assert content_info.path == "data/unknown_file.dat"
        assert content_info.size is None
        assert content_info.type == "file"
        assert content_info.modified_date is None
        assert content_info.download_url is None


class TestContentInfoRequiredFieldValidation:
    """Test validation of required fields in Content_Info."""

    def test_content_info_requires_path(self):
        """Test that Content_Info requires path field."""
        from quilt_mcp.domain.content_info import Content_Info

        # This should raise TypeError for missing required argument
        with pytest.raises(TypeError, match="missing.*required.*argument.*path"):
            Content_Info(
                size=1024,
                type="file",
                modified_date="2024-01-15T10:30:00Z",
                download_url="https://example.com/download/file.txt",
            )

    def test_content_info_requires_type(self):
        """Test that Content_Info requires type field."""
        from quilt_mcp.domain.content_info import Content_Info

        with pytest.raises(TypeError, match="missing.*required.*argument.*type"):
            Content_Info(
                path="data/file.txt",
                size=1024,
                modified_date="2024-01-15T10:30:00Z",
                download_url="https://example.com/download/file.txt",
            )

    def test_content_info_path_cannot_be_none(self):
        """Test that Content_Info path field cannot be None."""
        from quilt_mcp.domain.content_info import Content_Info

        # Even if we try to pass None explicitly, it should fail validation
        with pytest.raises((TypeError, ValueError)):
            Content_Info(
                path=None,
                size=1024,
                type="file",
                modified_date="2024-01-15T10:30:00Z",
                download_url="https://example.com/download/file.txt",
            )

    def test_content_info_type_cannot_be_none(self):
        """Test that Content_Info type field cannot be None."""
        from quilt_mcp.domain.content_info import Content_Info

        # Even if we try to pass None explicitly, it should fail validation
        with pytest.raises((TypeError, ValueError)):
            Content_Info(
                path="data/file.txt",
                size=1024,
                type=None,
                modified_date="2024-01-15T10:30:00Z",
                download_url="https://example.com/download/file.txt",
            )

    def test_content_info_path_cannot_be_empty_string(self):
        """Test that Content_Info path field cannot be empty string."""
        from quilt_mcp.domain.content_info import Content_Info

        # Empty path should fail validation
        with pytest.raises(ValueError, match="path.*cannot be empty"):
            Content_Info(
                path="",
                size=1024,
                type="file",
                modified_date="2024-01-15T10:30:00Z",
                download_url="https://example.com/download/file.txt",
            )

    def test_content_info_type_cannot_be_empty_string(self):
        """Test that Content_Info type field cannot be empty string."""
        from quilt_mcp.domain.content_info import Content_Info

        # Empty type should fail validation
        with pytest.raises(ValueError, match="type.*cannot be empty"):
            Content_Info(
                path="data/file.txt",
                size=1024,
                type="",
                modified_date="2024-01-15T10:30:00Z",
                download_url="https://example.com/download/file.txt",
            )

    def test_content_info_allows_none_size(self):
        """Test that Content_Info allows None for optional size field."""
        from quilt_mcp.domain.content_info import Content_Info

        # This should NOT raise an error - size is optional
        content_info = Content_Info(
            path="data/directory/",
            size=None,
            type="directory",
            modified_date="2024-01-15T10:30:00Z",
            download_url=None,
        )

        assert content_info.size is None

    def test_content_info_allows_none_modified_date(self):
        """Test that Content_Info allows None for optional modified_date field."""
        from quilt_mcp.domain.content_info import Content_Info

        # This should NOT raise an error - modified_date is optional
        content_info = Content_Info(
            path="data/file.txt",
            size=1024,
            type="file",
            modified_date=None,
            download_url="https://example.com/download/file.txt",
        )

        assert content_info.modified_date is None

    def test_content_info_allows_none_download_url(self):
        """Test that Content_Info allows None for optional download_url field."""
        from quilt_mcp.domain.content_info import Content_Info

        # This should NOT raise an error - download_url is optional
        content_info = Content_Info(
            path="data/file.txt", size=1024, type="file", modified_date="2024-01-15T10:30:00Z", download_url=None
        )

        assert content_info.download_url is None

    def test_content_info_size_must_be_non_negative(self):
        """Test that Content_Info size field must be non-negative when provided."""
        from quilt_mcp.domain.content_info import Content_Info

        # Negative size should fail validation
        with pytest.raises(ValueError, match="size.*cannot be negative"):
            Content_Info(
                path="data/file.txt",
                size=-1,
                type="file",
                modified_date="2024-01-15T10:30:00Z",
                download_url="https://example.com/download/file.txt",
            )

    def test_content_info_allows_zero_size(self):
        """Test that Content_Info allows zero size for empty files."""
        from quilt_mcp.domain.content_info import Content_Info

        # Zero size should be allowed (empty files)
        content_info = Content_Info(
            path="data/empty_file.txt",
            size=0,
            type="file",
            modified_date="2024-01-15T10:30:00Z",
            download_url="https://example.com/download/empty_file.txt",
        )

        assert content_info.size == 0

    def test_content_info_validates_type_values(self):
        """Test that Content_Info validates type field values."""
        from quilt_mcp.domain.content_info import Content_Info

        # Valid types should work
        valid_types = ["file", "directory"]

        for valid_type in valid_types:
            content_info = Content_Info(
                path=f"data/test_{valid_type}",
                size=1024 if valid_type == "file" else None,
                type=valid_type,
                modified_date="2024-01-15T10:30:00Z",
                download_url="https://example.com/download/test",
            )
            assert content_info.type == valid_type

    def test_content_info_allows_custom_type_values(self):
        """Test that Content_Info allows custom type values beyond file/directory."""
        from quilt_mcp.domain.content_info import Content_Info

        # Custom types should be allowed for extensibility
        custom_types = ["symlink", "binary", "text", "image", "archive"]

        for custom_type in custom_types:
            content_info = Content_Info(
                path=f"data/test_{custom_type}",
                size=1024,
                type=custom_type,
                modified_date="2024-01-15T10:30:00Z",
                download_url="https://example.com/download/test",
            )
            assert content_info.type == custom_type


class TestContentInfoDataclassAsdict:
    """Test dataclasses.asdict() compatibility for MCP response formatting."""

    def test_content_info_asdict_conversion(self):
        """Test that Content_Info can be converted to dict using dataclasses.asdict()."""
        from quilt_mcp.domain.content_info import Content_Info

        content_info = Content_Info(
            path="data/analysis/results.csv",
            size=1024768,
            type="file",
            modified_date="2024-01-15T10:30:00Z",
            download_url="https://example.com/download/results.csv",
        )

        # Convert to dict using dataclasses.asdict()
        result_dict = asdict(content_info)

        # Verify it's a plain dict
        assert isinstance(result_dict, dict)
        assert type(result_dict) is dict  # Exact type check

        # Verify all fields are present
        expected_keys = {'path', 'size', 'type', 'modified_date', 'download_url', 'meta'}
        assert set(result_dict.keys()) == expected_keys

    def test_content_info_asdict_preserves_values(self):
        """Test that asdict() preserves all field values correctly."""
        from quilt_mcp.domain.content_info import Content_Info

        original_data = {
            'path': "data/analysis/results.csv",
            'size': 1024768,
            'type': "file",
            'modified_date': "2024-01-15T10:30:00Z",
            'download_url': "https://example.com/download/results.csv",
        }

        content_info = Content_Info(**original_data)
        result_dict = asdict(content_info)

        # Verify all values are preserved
        for key, expected_value in original_data.items():
            assert result_dict[key] == expected_value

    def test_content_info_asdict_with_none_values(self):
        """Test that asdict() handles None values correctly."""
        from quilt_mcp.domain.content_info import Content_Info

        content_info = Content_Info(
            path="data/directory/", size=None, type="directory", modified_date=None, download_url=None
        )

        result_dict = asdict(content_info)

        # Verify None values are preserved
        assert result_dict['size'] is None
        assert result_dict['modified_date'] is None
        assert result_dict['download_url'] is None

    def test_content_info_asdict_json_serializable(self):
        """Test that asdict() result is JSON serializable for MCP responses."""
        import json
        from quilt_mcp.domain.content_info import Content_Info

        content_info = Content_Info(
            path="data/analysis/results.csv",
            size=1024768,
            type="file",
            modified_date="2024-01-15T10:30:00Z",
            download_url="https://example.com/download/results.csv",
        )

        result_dict = asdict(content_info)

        # Should be able to serialize to JSON without errors
        json_str = json.dumps(result_dict)
        assert isinstance(json_str, str)

        # Should be able to deserialize back
        deserialized = json.loads(json_str)
        assert deserialized == result_dict

    def test_content_info_asdict_with_mixed_none_values(self):
        """Test that asdict() handles mixed None and non-None values correctly."""
        from quilt_mcp.domain.content_info import Content_Info

        content_info = Content_Info(
            path="data/partial_info.txt",
            size=2048,
            type="file",
            modified_date=None,
            download_url="https://example.com/download/partial_info.txt",
        )

        result_dict = asdict(content_info)

        # Verify mixed values are preserved correctly
        assert result_dict['path'] == "data/partial_info.txt"
        assert result_dict['size'] == 2048
        assert result_dict['type'] == "file"
        assert result_dict['modified_date'] is None
        assert result_dict['download_url'] == "https://example.com/download/partial_info.txt"
