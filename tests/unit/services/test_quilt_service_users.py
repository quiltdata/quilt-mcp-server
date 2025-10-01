"""Tests for QuiltService user management operations (Phase 2.1).

This module tests user listing and retrieval operations, ensuring proper
error handling when admin modules are unavailable or users don't exist.
"""

from unittest.mock import Mock, patch, MagicMock
import pytest

from quilt_mcp.services.quilt_service import QuiltService
from quilt_mcp.services.exceptions import (
    AdminNotAvailableError,
    UserNotFoundError,
    UserAlreadyExistsError,
)


class TestUserListing:
    """Test list_users() method."""

    def test_list_users_returns_typed_list(self):
        """Test that list_users() returns a properly typed list of user dicts."""
        service = QuiltService()

        # Mock the admin module's list function to return list of dicts
        mock_users_module = Mock()
        mock_users_module.list.return_value = [
            {"name": "alice", "email": "alice@example.com", "role": "user"},
            {"name": "bob", "email": "bob@example.com", "role": "admin"},
        ]

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            users = service.list_users()

            assert isinstance(users, list)
            assert len(users) > 0
            # Verify each user is a dict with expected structure
            for user in users:
                assert isinstance(user, dict)
                assert "name" in user
                assert "email" in user

    def test_list_users_raises_admin_not_available(self):
        """Test that list_users() raises AdminNotAvailableError when admin unavailable."""
        service = QuiltService()

        # Mock is_admin_available to return False
        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service.list_users()

            # Verify error message is descriptive
            assert "Admin operations not available" in str(exc_info.value)

    def test_list_users_with_admin_available_calls_admin_module(self):
        """Test that list_users() properly calls the admin users module."""
        service = QuiltService()

        # Mock the admin module's list function
        mock_users_module = Mock()
        mock_users_module.list.return_value = [
            {"name": "alice", "email": "alice@example.com", "role": "user"},
            {"name": "bob", "email": "bob@example.com", "role": "admin"},
        ]

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            users = service.list_users()

            # Verify the admin module was called
            mock_users_module.list.assert_called_once()
            # Verify we got the expected results
            assert len(users) == 2
            assert users[0]["name"] == "alice"
            assert users[1]["name"] == "bob"


class TestUserRetrieval:
    """Test get_user() method."""

    def test_get_user_returns_typed_dict(self):
        """Test that get_user() returns a properly typed user dict."""
        service = QuiltService()

        # Mock the admin module's get function to return a dict
        mock_users_module = Mock()
        mock_users_module.get.return_value = {
            "name": "alice",
            "email": "alice@example.com",
            "role": "user",
            "active": True,
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            user = service.get_user("alice")

            assert isinstance(user, dict)
            assert "name" in user
            assert user["name"] == "alice"
            assert "email" in user

    def test_get_user_raises_admin_not_available(self):
        """Test that get_user() raises AdminNotAvailableError when admin unavailable."""
        service = QuiltService()

        # Mock is_admin_available to return False
        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service.get_user("alice")

            # Verify error message is descriptive
            assert "Admin operations not available" in str(exc_info.value)

    def test_get_user_raises_user_not_found(self):
        """Test that get_user() raises UserNotFoundError when user doesn't exist."""
        service = QuiltService()

        # Mock the admin module to raise UserNotFoundError from quilt3.admin
        mock_users_module = Mock()

        # Create a mock exception that matches quilt3.admin.exceptions.UserNotFoundError
        class MockQuilt3UserNotFoundError(Exception):
            pass

        mock_users_module.get.side_effect = MockQuilt3UserNotFoundError("User 'nonexistent' not found")

        # Mock the exception mapping to include our mock exception
        mock_exceptions = {
            'UserNotFoundError': MockQuilt3UserNotFoundError,
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            with patch.object(service, '_get_admin_exceptions', return_value=mock_exceptions):
                with pytest.raises(UserNotFoundError) as exc_info:
                    service.get_user("nonexistent")

                # Verify error message includes the username
                assert "nonexistent" in str(exc_info.value)

    def test_get_user_with_admin_available_calls_admin_module(self):
        """Test that get_user() properly calls the admin users module."""
        service = QuiltService()

        # Mock the admin module's get function
        mock_users_module = Mock()
        mock_users_module.get.return_value = {
            "name": "alice",
            "email": "alice@example.com",
            "role": "user",
            "active": True,
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            user = service.get_user("alice")

            # Verify the admin module was called with correct username
            mock_users_module.get.assert_called_once_with("alice")
            # Verify we got the expected result
            assert user["name"] == "alice"
            assert user["email"] == "alice@example.com"
            assert user["active"] is True


class TestUsersAdminModuleHelper:
    """Test _get_users_admin_module() helper method."""

    def test_get_users_admin_module_returns_module_when_available(self):
        """Test that _get_users_admin_module() returns the module when available."""
        service = QuiltService()

        # Mock admin availability
        with patch.object(service, 'is_admin_available', return_value=True):
            # Mock the actual import
            mock_users_module = Mock()
            with patch('quilt3.admin.users', mock_users_module):
                result = service._get_users_admin_module()

                # Verify we got the mocked module
                assert result is mock_users_module

    def test_get_users_admin_module_raises_when_unavailable(self):
        """Test that _get_users_admin_module() raises AdminNotAvailableError when unavailable."""
        service = QuiltService()

        # Mock admin availability
        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service._get_users_admin_module()

            # Verify error message is descriptive
            assert "Admin operations not available" in str(exc_info.value)


class TestUserCreation:
    """Test create_user() method."""

    def test_create_user_returns_user_dict(self):
        """Test that create_user() returns created user details."""
        service = QuiltService()

        # Mock the admin module's create function
        mock_users_module = Mock()
        mock_users_module.create.return_value = {
            "name": "newuser",
            "email": "newuser@example.com",
            "role": "user",
            "active": True,
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            user = service.create_user(
                name="newuser",
                email="newuser@example.com",
                role="user",
                extra_roles=None,
            )

            # Verify the admin module was called with correct parameters
            mock_users_module.create.assert_called_once_with(
                name="newuser",
                email="newuser@example.com",
                role="user",
                extra_roles=None,
            )
            # Verify we got the expected result
            assert user["name"] == "newuser"
            assert user["email"] == "newuser@example.com"
            assert user["role"] == "user"

    def test_create_user_with_extra_roles(self):
        """Test that create_user() properly handles extra_roles parameter."""
        service = QuiltService()

        # Mock the admin module's create function
        mock_users_module = Mock()
        mock_users_module.create.return_value = {
            "name": "adminuser",
            "email": "admin@example.com",
            "role": "admin",
            "extra_roles": ["viewer", "editor"],
            "active": True,
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            user = service.create_user(
                name="adminuser",
                email="admin@example.com",
                role="admin",
                extra_roles=["viewer", "editor"],
            )

            # Verify the admin module was called with extra_roles
            mock_users_module.create.assert_called_once_with(
                name="adminuser",
                email="admin@example.com",
                role="admin",
                extra_roles=["viewer", "editor"],
            )
            assert user["name"] == "adminuser"
            assert user["extra_roles"] == ["viewer", "editor"]

    def test_create_user_raises_admin_not_available(self):
        """Test that create_user() raises AdminNotAvailableError when admin unavailable."""
        service = QuiltService()

        # Mock is_admin_available to return False
        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service.create_user(
                    name="newuser",
                    email="newuser@example.com",
                    role="user",
                    extra_roles=None,
                )

            # Verify error message is descriptive
            assert "Admin operations not available" in str(exc_info.value)

    def test_create_user_raises_user_already_exists(self):
        """Test that create_user() raises UserAlreadyExistsError for duplicate users."""
        service = QuiltService()

        # Mock the admin module to raise an error for duplicate user
        mock_users_module = Mock()

        # Create a mock exception that matches quilt3.admin behavior
        class MockQuilt3AdminError(Exception):
            pass

        mock_users_module.create.side_effect = MockQuilt3AdminError("User 'duplicate' already exists")

        # Mock the exception mapping
        mock_exceptions = {
            'Quilt3AdminError': MockQuilt3AdminError,
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            with patch.object(service, '_get_admin_exceptions', return_value=mock_exceptions):
                with pytest.raises(UserAlreadyExistsError) as exc_info:
                    service.create_user(
                        name="duplicate",
                        email="duplicate@example.com",
                        role="user",
                        extra_roles=None,
                    )

                # Verify error message includes the username
                assert "duplicate" in str(exc_info.value)


class TestUserDeletion:
    """Test delete_user() method."""

    def test_delete_user_completes_successfully(self):
        """Test that delete_user() completes without error."""
        service = QuiltService()

        # Mock the admin module's delete function
        mock_users_module = Mock()
        mock_users_module.delete.return_value = None

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            # Should complete without raising an exception
            result = service.delete_user("usertoremove")

            # Verify the admin module was called with correct username
            mock_users_module.delete.assert_called_once_with("usertoremove")
            # Verify function returns None (no return value)
            assert result is None

    def test_delete_user_raises_admin_not_available(self):
        """Test that delete_user() raises AdminNotAvailableError when admin unavailable."""
        service = QuiltService()

        # Mock is_admin_available to return False
        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service.delete_user("someuser")

            # Verify error message is descriptive
            assert "Admin operations not available" in str(exc_info.value)

    def test_delete_user_raises_user_not_found(self):
        """Test that delete_user() raises UserNotFoundError when user doesn't exist."""
        service = QuiltService()

        # Mock the admin module to raise UserNotFoundError
        mock_users_module = Mock()

        # Create a mock exception that matches quilt3.admin.exceptions.UserNotFoundError
        class MockQuilt3UserNotFoundError(Exception):
            pass

        mock_users_module.delete.side_effect = MockQuilt3UserNotFoundError("User 'nonexistent' not found")

        # Mock the exception mapping to include our mock exception
        mock_exceptions = {
            'UserNotFoundError': MockQuilt3UserNotFoundError,
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            with patch.object(service, '_get_admin_exceptions', return_value=mock_exceptions):
                with pytest.raises(UserNotFoundError) as exc_info:
                    service.delete_user("nonexistent")

                # Verify error message includes the username
                assert "nonexistent" in str(exc_info.value)
