"""Tests for Package_Info domain object validation - Test-Driven Development Implementation.

This test suite follows TDD principles by defining the expected behavior of Package_Info
before implementation. Tests cover validation, required fields, and dataclasses.asdict() compatibility.
"""

from __future__ import annotations

import pytest
from dataclasses import asdict, fields
from datetime import datetime
from typing import Any, Dict, List, Optional


class TestPackageInfoValidation:
    """Test Package_Info validation and field requirements."""

    def test_package_info_can_be_imported(self):
        """Test that Package_Info can be imported from domain module."""
        # This test will fail initially - that's the RED phase of TDD
        from quilt_mcp.domain.package_info import Package_Info
        assert Package_Info is not None

    def test_package_info_is_dataclass(self):
        """Test that Package_Info is implemented as a dataclass."""
        from quilt_mcp.domain.package_info import Package_Info
        
        # Verify it's a dataclass
        assert hasattr(Package_Info, '__dataclass_fields__')
        assert hasattr(Package_Info, '__dataclass_params__')

    def test_package_info_has_required_fields(self):
        """Test that Package_Info has all required fields as specified in design."""
        from quilt_mcp.domain.package_info import Package_Info
        
        # Get dataclass fields
        field_names = {field.name for field in fields(Package_Info)}
        
        # Verify all required fields are present
        required_fields = {
            'name', 'description', 'tags', 'modified_date', 
            'registry', 'bucket', 'top_hash'
        }
        
        assert required_fields.issubset(field_names), (
            f"Missing required fields: {required_fields - field_names}"
        )

    def test_package_info_field_types(self):
        """Test that Package_Info fields have correct type annotations."""
        from quilt_mcp.domain.package_info import Package_Info
        
        field_types = {field.name: field.type for field in fields(Package_Info)}
        
        # Verify field types match design specification
        expected_types = {
            'name': str,
            'description': Optional[str],
            'tags': List[str],
            'modified_date': str,
            'registry': str,
            'bucket': str,
            'top_hash': str
        }
        
        for field_name, expected_type in expected_types.items():
            assert field_name in field_types, f"Field {field_name} missing"
            assert field_types[field_name] == expected_type, (
                f"Field {field_name} has type {field_types[field_name]}, "
                f"expected {expected_type}"
            )

    def test_package_info_creation_with_all_fields(self):
        """Test creating Package_Info with all fields provided."""
        from quilt_mcp.domain.package_info import Package_Info
        
        package_info = Package_Info(
            name="user/test-package",
            description="A test package for validation",
            tags=["test", "validation", "sample"],
            modified_date="2024-01-15T10:30:00Z",
            registry="s3://test-registry",
            bucket="test-bucket",
            top_hash="abc123def456"
        )
        
        assert package_info.name == "user/test-package"
        assert package_info.description == "A test package for validation"
        assert package_info.tags == ["test", "validation", "sample"]
        assert package_info.modified_date == "2024-01-15T10:30:00Z"
        assert package_info.registry == "s3://test-registry"
        assert package_info.bucket == "test-bucket"
        assert package_info.top_hash == "abc123def456"

    def test_package_info_creation_with_none_description(self):
        """Test creating Package_Info with None description (optional field)."""
        from quilt_mcp.domain.package_info import Package_Info
        
        package_info = Package_Info(
            name="user/test-package",
            description=None,
            tags=["test"],
            modified_date="2024-01-15T10:30:00Z",
            registry="s3://test-registry",
            bucket="test-bucket",
            top_hash="abc123def456"
        )
        
        assert package_info.description is None

    def test_package_info_creation_with_empty_tags(self):
        """Test creating Package_Info with empty tags list."""
        from quilt_mcp.domain.package_info import Package_Info
        
        package_info = Package_Info(
            name="user/test-package",
            description="Test package",
            tags=[],
            modified_date="2024-01-15T10:30:00Z",
            registry="s3://test-registry",
            bucket="test-bucket",
            top_hash="abc123def456"
        )
        
        assert package_info.tags == []


class TestPackageInfoRequiredFieldValidation:
    """Test validation of required fields in Package_Info."""

    def test_package_info_requires_name(self):
        """Test that Package_Info requires name field."""
        from quilt_mcp.domain.package_info import Package_Info
        
        # This should raise TypeError for missing required argument
        with pytest.raises(TypeError, match="missing.*required.*argument.*name"):
            Package_Info(
                description="Test package",
                tags=["test"],
                modified_date="2024-01-15T10:30:00Z",
                registry="s3://test-registry",
                bucket="test-bucket",
                top_hash="abc123def456"
            )

    def test_package_info_requires_tags(self):
        """Test that Package_Info requires tags field."""
        from quilt_mcp.domain.package_info import Package_Info
        
        with pytest.raises(TypeError, match="missing.*required.*argument.*tags"):
            Package_Info(
                name="user/test-package",
                description="Test package",
                modified_date="2024-01-15T10:30:00Z",
                registry="s3://test-registry",
                bucket="test-bucket",
                top_hash="abc123def456"
            )

    def test_package_info_requires_modified_date(self):
        """Test that Package_Info requires modified_date field."""
        from quilt_mcp.domain.package_info import Package_Info
        
        with pytest.raises(TypeError, match="missing.*required.*argument.*modified_date"):
            Package_Info(
                name="user/test-package",
                description="Test package",
                tags=["test"],
                registry="s3://test-registry",
                bucket="test-bucket",
                top_hash="abc123def456"
            )

    def test_package_info_requires_registry(self):
        """Test that Package_Info requires registry field."""
        from quilt_mcp.domain.package_info import Package_Info
        
        with pytest.raises(TypeError, match="missing.*required.*argument.*registry"):
            Package_Info(
                name="user/test-package",
                description="Test package",
                tags=["test"],
                modified_date="2024-01-15T10:30:00Z",
                bucket="test-bucket",
                top_hash="abc123def456"
            )

    def test_package_info_requires_bucket(self):
        """Test that Package_Info requires bucket field."""
        from quilt_mcp.domain.package_info import Package_Info
        
        with pytest.raises(TypeError, match="missing.*required.*argument.*bucket"):
            Package_Info(
                name="user/test-package",
                description="Test package",
                tags=["test"],
                modified_date="2024-01-15T10:30:00Z",
                registry="s3://test-registry",
                top_hash="abc123def456"
            )

    def test_package_info_requires_top_hash(self):
        """Test that Package_Info requires top_hash field."""
        from quilt_mcp.domain.package_info import Package_Info
        
        with pytest.raises(TypeError, match="missing.*required.*argument.*top_hash"):
            Package_Info(
                name="user/test-package",
                description="Test package",
                tags=["test"],
                modified_date="2024-01-15T10:30:00Z",
                registry="s3://test-registry",
                bucket="test-bucket"
            )

    def test_package_info_allows_none_description(self):
        """Test that Package_Info allows None for optional description field."""
        from quilt_mcp.domain.package_info import Package_Info
        
        # This should NOT raise an error - description is optional
        package_info = Package_Info(
            name="user/test-package",
            description=None,
            tags=["test"],
            modified_date="2024-01-15T10:30:00Z",
            registry="s3://test-registry",
            bucket="test-bucket",
            top_hash="abc123def456"
        )
        
        assert package_info.description is None


class TestPackageInfoDataclassAsdict:
    """Test dataclasses.asdict() compatibility for MCP response formatting."""

    def test_package_info_asdict_conversion(self):
        """Test that Package_Info can be converted to dict using dataclasses.asdict()."""
        from quilt_mcp.domain.package_info import Package_Info
        
        package_info = Package_Info(
            name="user/test-package",
            description="A test package for validation",
            tags=["test", "validation", "sample"],
            modified_date="2024-01-15T10:30:00Z",
            registry="s3://test-registry",
            bucket="test-bucket",
            top_hash="abc123def456"
        )
        
        # Convert to dict using dataclasses.asdict()
        result_dict = asdict(package_info)
        
        # Verify it's a plain dict
        assert isinstance(result_dict, dict)
        assert type(result_dict) == dict  # Exact type check
        
        # Verify all fields are present
        expected_keys = {
            'name', 'description', 'tags', 'modified_date',
            'registry', 'bucket', 'top_hash'
        }
        assert set(result_dict.keys()) == expected_keys

    def test_package_info_asdict_preserves_values(self):
        """Test that asdict() preserves all field values correctly."""
        from quilt_mcp.domain.package_info import Package_Info
        
        original_data = {
            'name': "user/test-package",
            'description': "A test package for validation",
            'tags': ["test", "validation", "sample"],
            'modified_date': "2024-01-15T10:30:00Z",
            'registry': "s3://test-registry",
            'bucket': "test-bucket",
            'top_hash': "abc123def456"
        }
        
        package_info = Package_Info(**original_data)
        result_dict = asdict(package_info)
        
        # Verify all values are preserved
        for key, expected_value in original_data.items():
            assert result_dict[key] == expected_value

    def test_package_info_asdict_with_none_description(self):
        """Test that asdict() handles None description correctly."""
        from quilt_mcp.domain.package_info import Package_Info
        
        package_info = Package_Info(
            name="user/test-package",
            description=None,
            tags=["test"],
            modified_date="2024-01-15T10:30:00Z",
            registry="s3://test-registry",
            bucket="test-bucket",
            top_hash="abc123def456"
        )
        
        result_dict = asdict(package_info)
        
        # Verify None is preserved
        assert result_dict['description'] is None

    def test_package_info_asdict_with_empty_tags(self):
        """Test that asdict() handles empty tags list correctly."""
        from quilt_mcp.domain.package_info import Package_Info
        
        package_info = Package_Info(
            name="user/test-package",
            description="Test package",
            tags=[],
            modified_date="2024-01-15T10:30:00Z",
            registry="s3://test-registry",
            bucket="test-bucket",
            top_hash="abc123def456"
        )
        
        result_dict = asdict(package_info)
        
        # Verify empty list is preserved
        assert result_dict['tags'] == []

    def test_package_info_asdict_json_serializable(self):
        """Test that asdict() result is JSON serializable for MCP responses."""
        import json
        from quilt_mcp.domain.package_info import Package_Info
        
        package_info = Package_Info(
            name="user/test-package",
            description="A test package for validation",
            tags=["test", "validation", "sample"],
            modified_date="2024-01-15T10:30:00Z",
            registry="s3://test-registry",
            bucket="test-bucket",
            top_hash="abc123def456"
        )
        
        result_dict = asdict(package_info)
        
        # Should be able to serialize to JSON without errors
        json_str = json.dumps(result_dict)
        assert isinstance(json_str, str)
        
        # Should be able to deserialize back
        deserialized = json.loads(json_str)
        assert deserialized == result_dict


class TestPackageInfoValidationEdgeCases:
    """Test edge cases and validation scenarios for Package_Info."""

    def test_package_info_with_special_characters_in_name(self):
        """Test Package_Info with special characters in package name."""
        from quilt_mcp.domain.package_info import Package_Info
        
        package_info = Package_Info(
            name="user/test-package_with-special.chars",
            description="Test package",
            tags=["test"],
            modified_date="2024-01-15T10:30:00Z",
            registry="s3://test-registry",
            bucket="test-bucket",
            top_hash="abc123def456"
        )
        
        assert package_info.name == "user/test-package_with-special.chars"

    def test_package_info_with_unicode_description(self):
        """Test Package_Info with Unicode characters in description."""
        from quilt_mcp.domain.package_info import Package_Info
        
        unicode_description = "Test package with émojis 🚀 and ñoñó characters"
        
        package_info = Package_Info(
            name="user/test-package",
            description=unicode_description,
            tags=["test", "unicode"],
            modified_date="2024-01-15T10:30:00Z",
            registry="s3://test-registry",
            bucket="test-bucket",
            top_hash="abc123def456"
        )
        
        assert package_info.description == unicode_description

    def test_package_info_with_many_tags(self):
        """Test Package_Info with a large number of tags."""
        from quilt_mcp.domain.package_info import Package_Info
        
        many_tags = [f"tag{i}" for i in range(100)]
        
        package_info = Package_Info(
            name="user/test-package",
            description="Test package with many tags",
            tags=many_tags,
            modified_date="2024-01-15T10:30:00Z",
            registry="s3://test-registry",
            bucket="test-bucket",
            top_hash="abc123def456"
        )
        
        assert len(package_info.tags) == 100
        assert package_info.tags == many_tags

    def test_package_info_with_long_hash(self):
        """Test Package_Info with long hash values."""
        from quilt_mcp.domain.package_info import Package_Info
        
        long_hash = "a" * 64  # SHA-256 length
        
        package_info = Package_Info(
            name="user/test-package",
            description="Test package",
            tags=["test"],
            modified_date="2024-01-15T10:30:00Z",
            registry="s3://test-registry",
            bucket="test-bucket",
            top_hash=long_hash
        )
        
        assert package_info.top_hash == long_hash

    def test_package_info_with_different_date_formats(self):
        """Test Package_Info accepts different ISO date formats."""
        from quilt_mcp.domain.package_info import Package_Info
        
        # Test various ISO 8601 formats
        date_formats = [
            "2024-01-15T10:30:00Z",
            "2024-01-15T10:30:00.123Z",
            "2024-01-15T10:30:00+00:00",
            "2024-01-15T10:30:00.123456Z"
        ]
        
        for date_format in date_formats:
            package_info = Package_Info(
                name="user/test-package",
                description="Test package",
                tags=["test"],
                modified_date=date_format,
                registry="s3://test-registry",
                bucket="test-bucket",
                top_hash="abc123def456"
            )
            
            assert package_info.modified_date == date_format


class TestPackageInfoEquality:
    """Test equality and comparison behavior of Package_Info."""

    def test_package_info_equality_same_values(self):
        """Test that Package_Info instances with same values are equal."""
        from quilt_mcp.domain.package_info import Package_Info
        
        package_info1 = Package_Info(
            name="user/test-package",
            description="Test package",
            tags=["test"],
            modified_date="2024-01-15T10:30:00Z",
            registry="s3://test-registry",
            bucket="test-bucket",
            top_hash="abc123def456"
        )
        
        package_info2 = Package_Info(
            name="user/test-package",
            description="Test package",
            tags=["test"],
            modified_date="2024-01-15T10:30:00Z",
            registry="s3://test-registry",
            bucket="test-bucket",
            top_hash="abc123def456"
        )
        
        assert package_info1 == package_info2

    def test_package_info_inequality_different_values(self):
        """Test that Package_Info instances with different values are not equal."""
        from quilt_mcp.domain.package_info import Package_Info
        
        package_info1 = Package_Info(
            name="user/test-package1",
            description="Test package",
            tags=["test"],
            modified_date="2024-01-15T10:30:00Z",
            registry="s3://test-registry",
            bucket="test-bucket",
            top_hash="abc123def456"
        )
        
        package_info2 = Package_Info(
            name="user/test-package2",
            description="Test package",
            tags=["test"],
            modified_date="2024-01-15T10:30:00Z",
            registry="s3://test-registry",
            bucket="test-bucket",
            top_hash="abc123def456"
        )
        
        assert package_info1 != package_info2

    def test_package_info_hash_consistency(self):
        """Test that Package_Info instances can be used as dict keys (hashable)."""
        from quilt_mcp.domain.package_info import Package_Info
        
        package_info = Package_Info(
            name="user/test-package",
            description="Test package",
            tags=["test"],
            modified_date="2024-01-15T10:30:00Z",
            registry="s3://test-registry",
            bucket="test-bucket",
            top_hash="abc123def456"
        )
        
        # Should be able to use as dict key
        test_dict = {package_info: "test_value"}
        assert test_dict[package_info] == "test_value"


class TestPackageInfoRepr:
    """Test string representation of Package_Info."""

    def test_package_info_repr_contains_key_fields(self):
        """Test that Package_Info repr contains key identifying fields."""
        from quilt_mcp.domain.package_info import Package_Info
        
        package_info = Package_Info(
            name="user/test-package",
            description="Test package",
            tags=["test"],
            modified_date="2024-01-15T10:30:00Z",
            registry="s3://test-registry",
            bucket="test-bucket",
            top_hash="abc123def456"
        )
        
        repr_str = repr(package_info)
        
        # Should contain the class name and key fields
        assert "Package_Info" in repr_str
        assert "user/test-package" in repr_str

    def test_package_info_str_readable(self):
        """Test that Package_Info str representation is human readable."""
        from quilt_mcp.domain.package_info import Package_Info
        
        package_info = Package_Info(
            name="user/test-package",
            description="Test package",
            tags=["test"],
            modified_date="2024-01-15T10:30:00Z",
            registry="s3://test-registry",
            bucket="test-bucket",
            top_hash="abc123def456"
        )
        
        str_repr = str(package_info)
        
        # Should be readable and contain key information
        assert isinstance(str_repr, str)
        assert len(str_repr) > 0