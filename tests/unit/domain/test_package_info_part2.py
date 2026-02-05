"""Tests for Package_Info domain object validation - Test-Driven Development Implementation.

This test suite follows TDD principles by defining the expected behavior of Package_Info
before implementation. Tests cover validation, required fields, and dataclasses.asdict() compatibility.
"""

from __future__ import annotations

import pytest
from dataclasses import asdict, fields
from datetime import datetime
from typing import Any, Dict, List, Optional


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
            top_hash="abc123def456",
        )

        package_info2 = Package_Info(
            name="user/test-package",
            description="Test package",
            tags=["test"],
            modified_date="2024-01-15T10:30:00Z",
            registry="s3://test-registry",
            bucket="test-bucket",
            top_hash="abc123def456",
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
            top_hash="abc123def456",
        )

        package_info2 = Package_Info(
            name="user/test-package2",
            description="Test package",
            tags=["test"],
            modified_date="2024-01-15T10:30:00Z",
            registry="s3://test-registry",
            bucket="test-bucket",
            top_hash="abc123def456",
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
            top_hash="abc123def456",
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
            top_hash="abc123def456",
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
            top_hash="abc123def456",
        )

        str_repr = str(package_info)

        # Should be readable and contain key information
        assert isinstance(str_repr, str)
        assert len(str_repr) > 0
