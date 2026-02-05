"""Tests for Content_Info domain object validation - Test-Driven Development Implementation.

This test suite follows TDD principles by defining the expected behavior of Content_Info
before implementation. Tests cover validation, required fields, and dataclasses.asdict() compatibility.
"""

from __future__ import annotations

import pytest
from dataclasses import asdict, fields
from typing import Any, Dict, Optional


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
            download_url="https://example.com/download/output.csv",
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
            download_url="https://example.com/download/special-file.txt",
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
            download_url="https://example.com/download/unicode-file.csv",
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
            download_url="https://example.com/download/large_dataset.parquet",
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
            download_url="https://example.com/download/empty_file.txt",
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
            "2024-01-15T10:30:00.123456Z",
        ]

        for date_format in date_formats:
            content_info = Content_Info(
                path="data/test_file.txt",
                size=1024,
                type="file",
                modified_date=date_format,
                download_url="https://example.com/download/test_file.txt",
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
            "ftp://ftp.example.com/file.txt",
        ]

        for url in url_schemes:
            content_info = Content_Info(
                path="data/test_file.txt",
                size=1024,
                type="file",
                modified_date="2024-01-15T10:30:00Z",
                download_url=url,
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
            download_url="https://example.com/download/document.pdf",
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
            download_url=None,
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
                download_url=f"https://example.com/download/test_{custom_type}.dat",
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
            download_url="https://example.com/download/test_file.txt",
        )

        content_info2 = Content_Info(
            path="data/test_file.txt",
            size=1024,
            type="file",
            modified_date="2024-01-15T10:30:00Z",
            download_url="https://example.com/download/test_file.txt",
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
            download_url="https://example.com/download/test_file1.txt",
        )

        content_info2 = Content_Info(
            path="data/test_file2.txt",
            size=1024,
            type="file",
            modified_date="2024-01-15T10:30:00Z",
            download_url="https://example.com/download/test_file2.txt",
        )

        assert content_info1 != content_info2

    def test_content_info_equality_with_none_values(self):
        """Test equality with None values in optional fields."""
        from quilt_mcp.domain.content_info import Content_Info

        content_info1 = Content_Info(
            path="data/directory/", size=None, type="directory", modified_date=None, download_url=None
        )

        content_info2 = Content_Info(
            path="data/directory/", size=None, type="directory", modified_date=None, download_url=None
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
            download_url="https://example.com/download/test_file.txt",
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
            download_url="https://example.com/download/important_file.csv",
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
            download_url="https://example.com/download/important_file.csv",
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
            'quilt3_object',
            'package_instance',
            'session',
            'client',
            'graphql_response',
            'jwt_token',
            'platform_id',
            'api_endpoint',
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
                'download_url': 'https://s3.amazonaws.com/bucket/file.csv',
            },
            # Directory from Platform backend
            {
                'path': 'data/experiments/',
                'size': None,
                'type': 'directory',
                'modified_date': '2024-01-15T10:30:00Z',
                'download_url': None,
            },
            # Content with minimal information
            {'path': 'unknown/file.dat', 'size': None, 'type': 'file', 'modified_date': None, 'download_url': None},
        ]

        for scenario in content_scenarios:
            content_info = Content_Info(**scenario)

            # Should successfully create Content_Info for any scenario
            assert content_info.path == scenario['path']
            assert content_info.type == scenario['type']

            # Should be convertible to dict for MCP responses
            result_dict = asdict(content_info)
            assert isinstance(result_dict, dict)
