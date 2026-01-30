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
        required_fields = {
            'path', 'size', 'type', 'modified_date', 'download_url'
        }
        
        assert required_fields.issubset(field_names), (
            f"Missing required fields: {required_fields - field_names}"
        )

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
            'download_url': Optional[str]
        }
        
        for field_name, expected_type in expected_types.items():
            assert field_name in field_types, f"Field {field_name} missing"
            assert field_types[field_name] == expected_type, (
                f"Field {field_name} has type {field_types[field_name]}, "
                f"expected {expected_type}"
            )

    def test_content_info_creation_with_all_fields(self):
        """Test creating Content_Info with all fields provided."""
        from quilt_mcp.domain.content_info import Content_Info
        
        content_info = Content_Info(
            path="data/analysis/results.csv",
            size=1024768,
            type="file",
            modified_date="2024-01-15T10:30:00Z",
            download_url="https://example.com/download/results.csv"
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
            path="data/analysis/",
            size=None,
            type="directory",
            modified_date="2024-01-15T10:30:00Z",
            download_url=None
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
            path="data/unknown_file.dat",
            size=None,
            type="file",
            modified_date=None,
            download_url=None
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
                download_url="https://example.com/download/file.txt"
            )

    def test_content_info_requires_type(self):
        """Test that Content_Info requires type field."""
        from quilt_mcp.domain.content_info import Content_Info
        
        with pytest.raises(TypeError, match="missing.*required.*argument.*type"):
            Content_Info(
                path="data/file.txt",
                size=1024,
                modified_date="2024-01-15T10:30:00Z",
                download_url="https://example.com/download/file.txt"
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
                download_url="https://example.com/download/file.txt"
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
                download_url="https://example.com/download/file.txt"
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
                download_url="https://example.com/download/file.txt"
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
                download_url="https://example.com/download/file.txt"
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
            download_url=None
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
            download_url="https://example.com/download/file.txt"
        )
        
        assert content_info.modified_date is None

    def test_content_info_allows_none_download_url(self):
        """Test that Content_Info allows None for optional download_url field."""
        from quilt_mcp.domain.content_info import Content_Info
        
        # This should NOT raise an error - download_url is optional
        content_info = Content_Info(
            path="data/file.txt",
            size=1024,
            type="file",
            modified_date="2024-01-15T10:30:00Z",
            download_url=None
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
                download_url="https://example.com/download/file.txt"
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
            download_url="https://example.com/download/empty_file.txt"
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
                download_url="https://example.com/download/test"
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
                download_url="https://example.com/download/test"
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
            download_url="https://example.com/download/results.csv"
        )
        
        # Convert to dict using dataclasses.asdict()
        result_dict = asdict(content_info)
        
        # Verify it's a plain dict
        assert isinstance(result_dict, dict)
        assert type(result_dict) == dict  # Exact type check
        
        # Verify all fields are present
        expected_keys = {
            'path', 'size', 'type', 'modified_date', 'download_url'
        }
        assert set(result_dict.keys()) == expected_keys

    def test_content_info_asdict_preserves_values(self):
        """Test that asdict() preserves all field values correctly."""
        from quilt_mcp.domain.content_info import Content_Info
        
        original_data = {
            'path': "data/analysis/results.csv",
            'size': 1024768,
            'type': "file",
            'modified_date': "2024-01-15T10:30:00Z",
            'download_url': "https://example.com/download/results.csv"
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
            path="data/directory/",
            size=None,
            type="directory",
            modified_date=None,
            download_url=None
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
            download_url="https://example.com/download/results.csv"
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
            download_url="https://example.com/download/partial_info.txt"
        )
        
        result_dict = asdict(content_info)
        
        # Verify mixed values are preserved correctly
        assert result_dict['path'] == "data/partial_info.txt"
        assert result_dict['size'] == 2048
        assert result_dict['type'] == "file"
        assert result_dict['modified_date'] is None
        assert result_dict['download_url'] == "https://example.com/download/partial_info.txt"


class TestContentInfoValidationEdgeCases:
    """Test edge cases and validation scenarios for Content_Info."""

    def test_content_info_with_nested_path(self):
        """Test Content_Info with deeply nested file paths."""
        from quilt_mcp.domain.content_info import Content_Info
        
        nested_path = "data/experiments/2024/january/analysis/results/final/output.csv"
        
        content_info = Content_Info(
            path=nested_path,
            size=4096,
            type="file",
            modified_date="2024-01-15T10:30:00Z",
            download_url="https://example.com/download/output.csv"
        )
        
        assert content_info.path == nested_path

    def test_content_info_with_special_characters_in_path(self):
        """Test Content_Info with special characters in file path."""
        from quilt_mcp.domain.content_info import Content_Info
        
        special_path = "data/files with spaces/file-name_with.special@chars#2024.txt"
        
        content_info = Content_Info(
            path=special_path,
            size=1024,
            type="file",
            modified_date="2024-01-15T10:30:00Z",
            download_url="https://example.com/download/special-file.txt"
        )
        
        assert content_info.path == special_path

    def test_content_info_with_unicode_path(self):
        """Test Content_Info with Unicode characters in path."""
        from quilt_mcp.domain.content_info import Content_Info
        
        unicode_path = "données/fichiers/résultats_été_2024.csv"
        
        content_info = Content_Info(
            path=unicode_path,
            size=2048,
            type="file",
            modified_date="2024-01-15T10:30:00Z",
            download_url="https://example.com/download/unicode-file.csv"
        )
        
        assert content_info.path == unicode_path

    def test_content_info_with_large_file_size(self):
        """Test Content_Info with large file sizes."""
        from quilt_mcp.domain.content_info import Content_Info
        
        large_size = 1024 * 1024 * 1024 * 5  # 5 GB
        
        content_info = Content_Info(
            path="data/large_dataset.parquet",
            size=large_size,
            type="file",
            modified_date="2024-01-15T10:30:00Z",
            download_url="https://example.com/download/large_dataset.parquet"
        )
        
        assert content_info.size == large_size

    def test_content_info_with_zero_size(self):
        """Test Content_Info with zero-byte files."""
        from quilt_mcp.domain.content_info import Content_Info
        
        content_info = Content_Info(
            path="data/empty_file.txt",
            size=0,
            type="file",
            modified_date="2024-01-15T10:30:00Z",
            download_url="https://example.com/download/empty_file.txt"
        )
        
        assert content_info.size == 0

    def test_content_info_with_different_date_formats(self):
        """Test Content_Info accepts different ISO date formats."""
        from quilt_mcp.domain.content_info import Content_Info
        
        # Test various ISO 8601 formats
        date_formats = [
            "2024-01-15T10:30:00Z",
            "2024-01-15T10:30:00.123Z",
            "2024-01-15T10:30:00+00:00",
            "2024-01-15T10:30:00.123456Z"
        ]
        
        for date_format in date_formats:
            content_info = Content_Info(
                path="data/test_file.txt",
                size=1024,
                type="file",
                modified_date=date_format,
                download_url="https://example.com/download/test_file.txt"
            )
            
            assert content_info.modified_date == date_format

    def test_content_info_with_different_url_schemes(self):
        """Test Content_Info with different URL schemes for download_url."""
        from quilt_mcp.domain.content_info import Content_Info
        
        url_schemes = [
            "https://example.com/file.txt",
            "http://example.com/file.txt",
            "s3://bucket/path/file.txt",
            "file:///local/path/file.txt",
            "ftp://ftp.example.com/file.txt"
        ]
        
        for url in url_schemes:
            content_info = Content_Info(
                path="data/test_file.txt",
                size=1024,
                type="file",
                modified_date="2024-01-15T10:30:00Z",
                download_url=url
            )
            
            assert content_info.download_url == url


class TestContentInfoTypeValidation:
    """Test validation of content type field values."""

    def test_content_info_with_file_type(self):
        """Test Content_Info with 'file' type."""
        from quilt_mcp.domain.content_info import Content_Info
        
        content_info = Content_Info(
            path="data/document.pdf",
            size=1024,
            type="file",
            modified_date="2024-01-15T10:30:00Z",
            download_url="https://example.com/download/document.pdf"
        )
        
        assert content_info.type == "file"

    def test_content_info_with_directory_type(self):
        """Test Content_Info with 'directory' type."""
        from quilt_mcp.domain.content_info import Content_Info
        
        content_info = Content_Info(
            path="data/subdirectory/",
            size=None,
            type="directory",
            modified_date="2024-01-15T10:30:00Z",
            download_url=None
        )
        
        assert content_info.type == "directory"

    def test_content_info_with_custom_type(self):
        """Test Content_Info with custom type values."""
        from quilt_mcp.domain.content_info import Content_Info
        
        # The design doesn't restrict type values, so custom types should be allowed
        custom_types = ["symlink", "binary", "text", "image", "archive"]
        
        for custom_type in custom_types:
            content_info = Content_Info(
                path=f"data/test_{custom_type}.dat",
                size=1024,
                type=custom_type,
                modified_date="2024-01-15T10:30:00Z",
                download_url=f"https://example.com/download/test_{custom_type}.dat"
            )
            
            assert content_info.type == custom_type


class TestContentInfoEquality:
    """Test equality and comparison behavior of Content_Info."""

    def test_content_info_equality_same_values(self):
        """Test that Content_Info instances with same values are equal."""
        from quilt_mcp.domain.content_info import Content_Info
        
        content_info1 = Content_Info(
            path="data/test_file.txt",
            size=1024,
            type="file",
            modified_date="2024-01-15T10:30:00Z",
            download_url="https://example.com/download/test_file.txt"
        )
        
        content_info2 = Content_Info(
            path="data/test_file.txt",
            size=1024,
            type="file",
            modified_date="2024-01-15T10:30:00Z",
            download_url="https://example.com/download/test_file.txt"
        )
        
        assert content_info1 == content_info2

    def test_content_info_inequality_different_values(self):
        """Test that Content_Info instances with different values are not equal."""
        from quilt_mcp.domain.content_info import Content_Info
        
        content_info1 = Content_Info(
            path="data/test_file1.txt",
            size=1024,
            type="file",
            modified_date="2024-01-15T10:30:00Z",
            download_url="https://example.com/download/test_file1.txt"
        )
        
        content_info2 = Content_Info(
            path="data/test_file2.txt",
            size=1024,
            type="file",
            modified_date="2024-01-15T10:30:00Z",
            download_url="https://example.com/download/test_file2.txt"
        )
        
        assert content_info1 != content_info2

    def test_content_info_equality_with_none_values(self):
        """Test equality with None values in optional fields."""
        from quilt_mcp.domain.content_info import Content_Info
        
        content_info1 = Content_Info(
            path="data/directory/",
            size=None,
            type="directory",
            modified_date=None,
            download_url=None
        )
        
        content_info2 = Content_Info(
            path="data/directory/",
            size=None,
            type="directory",
            modified_date=None,
            download_url=None
        )
        
        assert content_info1 == content_info2

    def test_content_info_hash_consistency(self):
        """Test that Content_Info instances can be used as dict keys (hashable)."""
        from quilt_mcp.domain.content_info import Content_Info
        
        content_info = Content_Info(
            path="data/test_file.txt",
            size=1024,
            type="file",
            modified_date="2024-01-15T10:30:00Z",
            download_url="https://example.com/download/test_file.txt"
        )
        
        # Should be able to use as dict key
        test_dict = {content_info: "test_value"}
        assert test_dict[content_info] == "test_value"


class TestContentInfoRepr:
    """Test string representation of Content_Info."""

    def test_content_info_repr_contains_key_fields(self):
        """Test that Content_Info repr contains key identifying fields."""
        from quilt_mcp.domain.content_info import Content_Info
        
        content_info = Content_Info(
            path="data/important_file.csv",
            size=2048,
            type="file",
            modified_date="2024-01-15T10:30:00Z",
            download_url="https://example.com/download/important_file.csv"
        )
        
        repr_str = repr(content_info)
        
        # Should contain the class name and key fields
        assert "Content_Info" in repr_str
        assert "data/important_file.csv" in repr_str

    def test_content_info_str_readable(self):
        """Test that Content_Info str representation is human readable."""
        from quilt_mcp.domain.content_info import Content_Info
        
        content_info = Content_Info(
            path="data/important_file.csv",
            size=2048,
            type="file",
            modified_date="2024-01-15T10:30:00Z",
            download_url="https://example.com/download/important_file.csv"
        )
        
        str_repr = str(content_info)
        
        # Should be readable and contain key information
        assert isinstance(str_repr, str)
        assert len(str_repr) > 0


class TestContentInfoBackendAgnostic:
    """Test that Content_Info is truly backend-agnostic as per Requirement 1."""

    def test_content_info_no_backend_specific_fields(self):
        """Test that Content_Info contains no backend-specific fields."""
        from quilt_mcp.domain.content_info import Content_Info
        
        # Get all field names
        field_names = {field.name for field in fields(Content_Info)}
        
        # Should not contain any quilt3-specific or Platform-specific fields
        backend_specific_fields = {
            'quilt3_object', 'package_instance', 'session', 'client',
            'graphql_response', 'jwt_token', 'platform_id', 'api_endpoint'
        }
        
        # Verify no backend-specific fields are present
        assert not backend_specific_fields.intersection(field_names), (
            f"Found backend-specific fields: {backend_specific_fields.intersection(field_names)}"
        )

    def test_content_info_represents_quilt_concepts(self):
        """Test that Content_Info represents pure Quilt concepts."""
        from quilt_mcp.domain.content_info import Content_Info
        
        # Should be able to represent any content regardless of backend
        content_scenarios = [
            # File from quilt3 backend
            {
                'path': 'data/analysis.csv',
                'size': 1024,
                'type': 'file',
                'modified_date': '2024-01-15T10:30:00Z',
                'download_url': 'https://s3.amazonaws.com/bucket/file.csv'
            },
            # Directory from Platform backend
            {
                'path': 'data/experiments/',
                'size': None,
                'type': 'directory',
                'modified_date': '2024-01-15T10:30:00Z',
                'download_url': None
            },
            # Content with minimal information
            {
                'path': 'unknown/file.dat',
                'size': None,
                'type': 'file',
                'modified_date': None,
                'download_url': None
            }
        ]
        
        for scenario in content_scenarios:
            content_info = Content_Info(**scenario)
            
            # Should successfully create Content_Info for any scenario
            assert content_info.path == scenario['path']
            assert content_info.type == scenario['type']
            
            # Should be convertible to dict for MCP responses
            result_dict = asdict(content_info)
            assert isinstance(result_dict, dict)