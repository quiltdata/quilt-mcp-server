"""Tests for Auth_Status domain object.

This test suite validates the Auth_Status dataclass that represents authentication
status information in a backend-agnostic way.
"""

import pytest
from quilt_mcp.domain import Auth_Status


class TestAuthStatusCreation:
    """Test Auth_Status dataclass creation and basic functionality."""

    def test_auth_status_can_be_imported(self):
        """Test that Auth_Status can be imported from domain module."""
        from quilt_mcp.domain import Auth_Status
        assert Auth_Status is not None

    def test_authenticated_status_creation(self):
        """Test creating an authenticated Auth_Status."""
        auth_status = Auth_Status(
            is_authenticated=True,
            logged_in_url="https://catalog.example.com",
            catalog_name="my-catalog",
            registry_url="s3://my-registry-bucket"
        )
        
        assert auth_status.is_authenticated is True
        assert auth_status.logged_in_url == "https://catalog.example.com"
        assert auth_status.catalog_name == "my-catalog"
        assert auth_status.registry_url == "s3://my-registry-bucket"

    def test_unauthenticated_status_creation(self):
        """Test creating an unauthenticated Auth_Status."""
        auth_status = Auth_Status(
            is_authenticated=False,
            logged_in_url=None,
            catalog_name=None,
            registry_url=None
        )
        
        assert auth_status.is_authenticated is False
        assert auth_status.logged_in_url is None
        assert auth_status.catalog_name is None
        assert auth_status.registry_url is None

    def test_partial_authentication_info(self):
        """Test creating Auth_Status with partial authentication info."""
        auth_status = Auth_Status(
            is_authenticated=True,
            logged_in_url="https://catalog.example.com",
            catalog_name=None,  # Catalog name might not always be available
            registry_url="s3://my-registry-bucket"
        )
        
        assert auth_status.is_authenticated is True
        assert auth_status.logged_in_url == "https://catalog.example.com"
        assert auth_status.catalog_name is None
        assert auth_status.registry_url == "s3://my-registry-bucket"


class TestAuthStatusImmutability:
    """Test that Auth_Status is immutable (frozen dataclass)."""

    def test_auth_status_is_frozen(self):
        """Test that Auth_Status fields cannot be modified after creation."""
        auth_status = Auth_Status(
            is_authenticated=True,
            logged_in_url="https://catalog.example.com",
            catalog_name="my-catalog",
            registry_url="s3://my-registry-bucket"
        )
        
        # Should not be able to modify any field
        with pytest.raises(AttributeError):
            auth_status.is_authenticated = False
        
        with pytest.raises(AttributeError):
            auth_status.logged_in_url = "https://other-catalog.com"
        
        with pytest.raises(AttributeError):
            auth_status.catalog_name = "other-catalog"
        
        with pytest.raises(AttributeError):
            auth_status.registry_url = "s3://other-registry"

    def test_auth_status_is_hashable(self):
        """Test that Auth_Status can be used as dictionary key or in sets."""
        auth_status1 = Auth_Status(
            is_authenticated=True,
            logged_in_url="https://catalog.example.com",
            catalog_name="my-catalog",
            registry_url="s3://my-registry-bucket"
        )
        
        auth_status2 = Auth_Status(
            is_authenticated=True,
            logged_in_url="https://catalog.example.com",
            catalog_name="my-catalog",
            registry_url="s3://my-registry-bucket"
        )
        
        # Should be able to hash
        hash1 = hash(auth_status1)
        hash2 = hash(auth_status2)
        
        # Same content should have same hash
        assert hash1 == hash2
        
        # Should be able to use in set
        status_set = {auth_status1, auth_status2}
        assert len(status_set) == 1  # Same content, so only one item
        
        # Should be able to use as dict key
        status_dict = {auth_status1: "authenticated"}
        assert status_dict[auth_status2] == "authenticated"


class TestAuthStatusEquality:
    """Test Auth_Status equality comparison."""

    def test_identical_auth_status_are_equal(self):
        """Test that Auth_Status objects with identical data are equal."""
        auth_status1 = Auth_Status(
            is_authenticated=True,
            logged_in_url="https://catalog.example.com",
            catalog_name="my-catalog",
            registry_url="s3://my-registry-bucket"
        )
        
        auth_status2 = Auth_Status(
            is_authenticated=True,
            logged_in_url="https://catalog.example.com",
            catalog_name="my-catalog",
            registry_url="s3://my-registry-bucket"
        )
        
        assert auth_status1 == auth_status2
        assert not (auth_status1 != auth_status2)

    def test_different_auth_status_are_not_equal(self):
        """Test that Auth_Status objects with different data are not equal."""
        auth_status1 = Auth_Status(
            is_authenticated=True,
            logged_in_url="https://catalog.example.com",
            catalog_name="my-catalog",
            registry_url="s3://my-registry-bucket"
        )
        
        auth_status2 = Auth_Status(
            is_authenticated=False,
            logged_in_url=None,
            catalog_name=None,
            registry_url=None
        )
        
        assert auth_status1 != auth_status2
        assert not (auth_status1 == auth_status2)

    def test_auth_status_with_none_values_equality(self):
        """Test equality with None values."""
        auth_status1 = Auth_Status(
            is_authenticated=True,
            logged_in_url="https://catalog.example.com",
            catalog_name=None,
            registry_url="s3://my-registry-bucket"
        )
        
        auth_status2 = Auth_Status(
            is_authenticated=True,
            logged_in_url="https://catalog.example.com",
            catalog_name=None,
            registry_url="s3://my-registry-bucket"
        )
        
        assert auth_status1 == auth_status2


class TestAuthStatusStringRepresentation:
    """Test Auth_Status string representation."""

    def test_auth_status_str_representation(self):
        """Test that Auth_Status has a readable string representation."""
        auth_status = Auth_Status(
            is_authenticated=True,
            logged_in_url="https://catalog.example.com",
            catalog_name="my-catalog",
            registry_url="s3://my-registry-bucket"
        )
        
        str_repr = str(auth_status)
        
        # Should contain the class name and key information
        assert "Auth_Status" in str_repr
        assert "is_authenticated=True" in str_repr
        assert "https://catalog.example.com" in str_repr
        assert "my-catalog" in str_repr
        assert "s3://my-registry-bucket" in str_repr

    def test_unauthenticated_status_str_representation(self):
        """Test string representation of unauthenticated status."""
        auth_status = Auth_Status(
            is_authenticated=False,
            logged_in_url=None,
            catalog_name=None,
            registry_url=None
        )
        
        str_repr = str(auth_status)
        
        assert "Auth_Status" in str_repr
        assert "is_authenticated=False" in str_repr
        assert "None" in str_repr


class TestAuthStatusUsagePatterns:
    """Test common usage patterns for Auth_Status."""

    def test_auth_status_boolean_check(self):
        """Test using Auth_Status for boolean authentication checks."""
        authenticated_status = Auth_Status(
            is_authenticated=True,
            logged_in_url="https://catalog.example.com",
            catalog_name="my-catalog",
            registry_url="s3://my-registry-bucket"
        )
        
        unauthenticated_status = Auth_Status(
            is_authenticated=False,
            logged_in_url=None,
            catalog_name=None,
            registry_url=None
        )
        
        # Should be able to check authentication status
        if authenticated_status.is_authenticated:
            assert authenticated_status.logged_in_url is not None
        
        if not unauthenticated_status.is_authenticated:
            assert unauthenticated_status.logged_in_url is None

    def test_auth_status_conditional_access(self):
        """Test conditional access to optional fields."""
        auth_status = Auth_Status(
            is_authenticated=True,
            logged_in_url="https://catalog.example.com",
            catalog_name=None,  # Might not be available
            registry_url="s3://my-registry-bucket"
        )
        
        # Should handle optional fields gracefully
        catalog_display = auth_status.catalog_name or "Unknown Catalog"
        assert catalog_display == "Unknown Catalog"
        
        # Should have required fields when authenticated
        if auth_status.is_authenticated:
            assert auth_status.logged_in_url is not None
            assert auth_status.registry_url is not None

    def test_auth_status_in_collections(self):
        """Test using Auth_Status in collections."""
        statuses = [
            Auth_Status(True, "https://catalog1.com", "cat1", "s3://reg1"),
            Auth_Status(True, "https://catalog2.com", "cat2", "s3://reg2"),
            Auth_Status(False, None, None, None),
        ]
        
        # Should be able to filter authenticated statuses
        authenticated_statuses = [s for s in statuses if s.is_authenticated]
        assert len(authenticated_statuses) == 2
        
        # Should be able to get unique catalogs
        catalog_urls = {s.logged_in_url for s in authenticated_statuses}
        assert len(catalog_urls) == 2
        assert "https://catalog1.com" in catalog_urls
        assert "https://catalog2.com" in catalog_urls


class TestAuthStatusTypeHints:
    """Test Auth_Status type hints and annotations."""

    def test_auth_status_has_correct_type_annotations(self):
        """Test that Auth_Status has correct type annotations."""
        import inspect
        from typing import get_type_hints
        
        # Get type hints for Auth_Status
        type_hints = get_type_hints(Auth_Status)
        
        # Check that all fields have correct types
        assert type_hints['is_authenticated'] == bool
        
        # Optional fields should be Union[type, None] or Optional[type]
        # In Python 3.10+, Optional[str] is represented as str | None
        logged_in_url_type = type_hints['logged_in_url']
        catalog_name_type = type_hints['catalog_name']
        registry_url_type = type_hints['registry_url']
        
        # These should be optional string types (Union[str, None] or str | None)
        assert hasattr(logged_in_url_type, '__args__')  # Union type
        assert str in logged_in_url_type.__args__
        assert type(None) in logged_in_url_type.__args__
        
        assert hasattr(catalog_name_type, '__args__')
        assert str in catalog_name_type.__args__
        assert type(None) in catalog_name_type.__args__
        
        assert hasattr(registry_url_type, '__args__')
        assert str in registry_url_type.__args__
        assert type(None) in registry_url_type.__args__

    def test_auth_status_dataclass_properties(self):
        """Test that Auth_Status has correct dataclass properties."""
        import dataclasses
        
        # Should be a dataclass
        assert dataclasses.is_dataclass(Auth_Status)
        
        # Should be frozen
        fields = dataclasses.fields(Auth_Status)
        
        # Check that all expected fields exist
        field_names = {f.name for f in fields}
        expected_fields = {'is_authenticated', 'logged_in_url', 'catalog_name', 'registry_url'}
        assert field_names == expected_fields
        
        # Check field types
        field_types = {f.name: f.type for f in fields}
        assert field_types['is_authenticated'] == bool