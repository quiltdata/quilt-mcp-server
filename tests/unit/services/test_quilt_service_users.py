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


class TestSetUserEmail:
    """Test set_user_email() method."""

    def test_set_user_email_returns_updated_user(self):
        """Test that set_user_email() returns updated user details."""
        service = QuiltService()

        # Mock the admin module's set_email function
        mock_users_module = Mock()
        mock_users_module.set_email.return_value = {
            "name": "alice",
            "email": "newemail@example.com",
            "role": "user",
            "active": True,
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            user = service.set_user_email("alice", "newemail@example.com")

            # Verify the admin module was called with correct parameters
            mock_users_module.set_email.assert_called_once_with("alice", "newemail@example.com")
            # Verify we got the expected result
            assert user["name"] == "alice"
            assert user["email"] == "newemail@example.com"

    def test_set_user_email_raises_admin_not_available(self):
        """Test that set_user_email() raises AdminNotAvailableError when admin unavailable."""
        service = QuiltService()

        # Mock is_admin_available to return False
        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service.set_user_email("alice", "newemail@example.com")

            # Verify error message is descriptive
            assert "Admin operations not available" in str(exc_info.value)

    def test_set_user_email_raises_user_not_found(self):
        """Test that set_user_email() raises UserNotFoundError when user doesn't exist."""
        service = QuiltService()

        # Mock the admin module to raise UserNotFoundError
        mock_users_module = Mock()

        class MockQuilt3UserNotFoundError(Exception):
            pass

        mock_users_module.set_email.side_effect = MockQuilt3UserNotFoundError("User 'nonexistent' not found")

        mock_exceptions = {
            'UserNotFoundError': MockQuilt3UserNotFoundError,
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            with patch.object(service, '_get_admin_exceptions', return_value=mock_exceptions):
                with pytest.raises(UserNotFoundError) as exc_info:
                    service.set_user_email("nonexistent", "newemail@example.com")

                assert "nonexistent" in str(exc_info.value)


class TestSetUserRole:
    """Test set_user_role() method."""

    def test_set_user_role_returns_updated_user(self):
        """Test that set_user_role() returns updated user details."""
        service = QuiltService()

        # Mock the admin module's set_role function
        mock_users_module = Mock()
        mock_users_module.set_role.return_value = {
            "name": "alice",
            "email": "alice@example.com",
            "role": "admin",
            "extra_roles": ["viewer"],
            "active": True,
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            user = service.set_user_role("alice", "admin", ["viewer"], False)

            # Verify the admin module was called with correct parameters
            mock_users_module.set_role.assert_called_once_with("alice", "admin", ["viewer"], False)
            # Verify we got the expected result
            assert user["name"] == "alice"
            assert user["role"] == "admin"
            assert user["extra_roles"] == ["viewer"]

    def test_set_user_role_with_append_true(self):
        """Test that set_user_role() properly handles append=True parameter."""
        service = QuiltService()

        # Mock the admin module's set_role function
        mock_users_module = Mock()
        mock_users_module.set_role.return_value = {
            "name": "alice",
            "email": "alice@example.com",
            "role": "user",
            "extra_roles": ["viewer", "editor"],
            "active": True,
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            user = service.set_user_role("alice", "user", ["editor"], True)

            # Verify the admin module was called with append=True
            mock_users_module.set_role.assert_called_once_with("alice", "user", ["editor"], True)
            assert user["extra_roles"] == ["viewer", "editor"]

    def test_set_user_role_raises_admin_not_available(self):
        """Test that set_user_role() raises AdminNotAvailableError when admin unavailable."""
        service = QuiltService()

        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service.set_user_role("alice", "admin", None, False)

            assert "Admin operations not available" in str(exc_info.value)

    def test_set_user_role_raises_user_not_found(self):
        """Test that set_user_role() raises UserNotFoundError when user doesn't exist."""
        service = QuiltService()

        mock_users_module = Mock()

        class MockQuilt3UserNotFoundError(Exception):
            pass

        mock_users_module.set_role.side_effect = MockQuilt3UserNotFoundError("User 'nonexistent' not found")

        mock_exceptions = {
            'UserNotFoundError': MockQuilt3UserNotFoundError,
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            with patch.object(service, '_get_admin_exceptions', return_value=mock_exceptions):
                with pytest.raises(UserNotFoundError) as exc_info:
                    service.set_user_role("nonexistent", "admin", None, False)

                assert "nonexistent" in str(exc_info.value)


class TestSetUserActive:
    """Test set_user_active() method."""

    def test_set_user_active_true_returns_updated_user(self):
        """Test that set_user_active(True) returns updated user details."""
        service = QuiltService()

        # Mock the admin module's set_active function
        mock_users_module = Mock()
        mock_users_module.set_active.return_value = {
            "name": "alice",
            "email": "alice@example.com",
            "role": "user",
            "active": True,
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            user = service.set_user_active("alice", True)

            # Verify the admin module was called with correct parameters
            mock_users_module.set_active.assert_called_once_with("alice", True)
            # Verify we got the expected result
            assert user["name"] == "alice"
            assert user["active"] is True

    def test_set_user_active_false_returns_updated_user(self):
        """Test that set_user_active(False) returns updated user details."""
        service = QuiltService()

        # Mock the admin module's set_active function
        mock_users_module = Mock()
        mock_users_module.set_active.return_value = {
            "name": "bob",
            "email": "bob@example.com",
            "role": "user",
            "active": False,
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            user = service.set_user_active("bob", False)

            mock_users_module.set_active.assert_called_once_with("bob", False)
            assert user["name"] == "bob"
            assert user["active"] is False

    def test_set_user_active_raises_admin_not_available(self):
        """Test that set_user_active() raises AdminNotAvailableError when admin unavailable."""
        service = QuiltService()

        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service.set_user_active("alice", True)

            assert "Admin operations not available" in str(exc_info.value)

    def test_set_user_active_raises_user_not_found(self):
        """Test that set_user_active() raises UserNotFoundError when user doesn't exist."""
        service = QuiltService()

        mock_users_module = Mock()

        class MockQuilt3UserNotFoundError(Exception):
            pass

        mock_users_module.set_active.side_effect = MockQuilt3UserNotFoundError("User 'nonexistent' not found")

        mock_exceptions = {
            'UserNotFoundError': MockQuilt3UserNotFoundError,
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            with patch.object(service, '_get_admin_exceptions', return_value=mock_exceptions):
                with pytest.raises(UserNotFoundError) as exc_info:
                    service.set_user_active("nonexistent", True)

                assert "nonexistent" in str(exc_info.value)


class TestSetUserAdmin:
    """Test set_user_admin() method."""

    def test_set_user_admin_true_returns_updated_user(self):
        """Test that set_user_admin(True) returns updated user details."""
        service = QuiltService()

        # Mock the admin module's set_admin function
        mock_users_module = Mock()
        mock_users_module.set_admin.return_value = {
            "name": "alice",
            "email": "alice@example.com",
            "role": "admin",
            "admin": True,
            "active": True,
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            user = service.set_user_admin("alice", True)

            # Verify the admin module was called with correct parameters
            mock_users_module.set_admin.assert_called_once_with("alice", True)
            # Verify we got the expected result
            assert user["name"] == "alice"
            assert user["admin"] is True

    def test_set_user_admin_false_returns_updated_user(self):
        """Test that set_user_admin(False) returns updated user details."""
        service = QuiltService()

        # Mock the admin module's set_admin function
        mock_users_module = Mock()
        mock_users_module.set_admin.return_value = {
            "name": "bob",
            "email": "bob@example.com",
            "role": "user",
            "admin": False,
            "active": True,
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            user = service.set_user_admin("bob", False)

            mock_users_module.set_admin.assert_called_once_with("bob", False)
            assert user["name"] == "bob"
            assert user["admin"] is False

    def test_set_user_admin_raises_admin_not_available(self):
        """Test that set_user_admin() raises AdminNotAvailableError when admin unavailable."""
        service = QuiltService()

        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service.set_user_admin("alice", True)

            assert "Admin operations not available" in str(exc_info.value)

    def test_set_user_admin_raises_user_not_found(self):
        """Test that set_user_admin() raises UserNotFoundError when user doesn't exist."""
        service = QuiltService()

        mock_users_module = Mock()

        class MockQuilt3UserNotFoundError(Exception):
            pass

        mock_users_module.set_admin.side_effect = MockQuilt3UserNotFoundError("User 'nonexistent' not found")

        mock_exceptions = {
            'UserNotFoundError': MockQuilt3UserNotFoundError,
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            with patch.object(service, '_get_admin_exceptions', return_value=mock_exceptions):
                with pytest.raises(UserNotFoundError) as exc_info:
                    service.set_user_admin("nonexistent", True)

                assert "nonexistent" in str(exc_info.value)


class TestAddUserRoles:
    """Test add_user_roles() method."""

    def test_add_user_roles_returns_updated_user(self):
        """Test that add_user_roles() returns updated user details."""
        service = QuiltService()

        # Mock the admin module's add_roles function
        mock_users_module = Mock()
        mock_users_module.add_roles.return_value = {
            "name": "alice",
            "email": "alice@example.com",
            "role": "user",
            "extra_roles": ["viewer", "editor"],
            "active": True,
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            user = service.add_user_roles("alice", ["viewer", "editor"])

            # Verify the admin module was called with correct parameters
            mock_users_module.add_roles.assert_called_once_with("alice", ["viewer", "editor"])
            # Verify we got the expected result
            assert user["name"] == "alice"
            assert user["extra_roles"] == ["viewer", "editor"]

    def test_add_user_roles_with_single_role(self):
        """Test that add_user_roles() works with a single role."""
        service = QuiltService()

        mock_users_module = Mock()
        mock_users_module.add_roles.return_value = {
            "name": "bob",
            "email": "bob@example.com",
            "role": "user",
            "extra_roles": ["viewer"],
            "active": True,
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            user = service.add_user_roles("bob", ["viewer"])

            mock_users_module.add_roles.assert_called_once_with("bob", ["viewer"])
            assert "viewer" in user["extra_roles"]

    def test_add_user_roles_raises_admin_not_available(self):
        """Test that add_user_roles() raises AdminNotAvailableError when admin unavailable."""
        service = QuiltService()

        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service.add_user_roles("alice", ["viewer"])

            assert "Admin operations not available" in str(exc_info.value)

    def test_add_user_roles_raises_user_not_found(self):
        """Test that add_user_roles() raises UserNotFoundError when user doesn't exist."""
        service = QuiltService()

        mock_users_module = Mock()

        class MockQuilt3UserNotFoundError(Exception):
            pass

        mock_users_module.add_roles.side_effect = MockQuilt3UserNotFoundError("User 'nonexistent' not found")

        mock_exceptions = {
            'UserNotFoundError': MockQuilt3UserNotFoundError,
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            with patch.object(service, '_get_admin_exceptions', return_value=mock_exceptions):
                with pytest.raises(UserNotFoundError) as exc_info:
                    service.add_user_roles("nonexistent", ["viewer"])

                assert "nonexistent" in str(exc_info.value)


class TestRemoveUserRoles:
    """Test remove_user_roles() method."""

    def test_remove_user_roles_returns_updated_user(self):
        """Test that remove_user_roles() returns updated user details."""
        service = QuiltService()

        # Mock the admin module's remove_roles function
        mock_users_module = Mock()
        mock_users_module.remove_roles.return_value = {
            "name": "alice",
            "email": "alice@example.com",
            "role": "user",
            "extra_roles": [],
            "active": True,
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            user = service.remove_user_roles("alice", ["viewer", "editor"], None)

            # Verify the admin module was called with correct parameters
            mock_users_module.remove_roles.assert_called_once_with("alice", ["viewer", "editor"], None)
            # Verify we got the expected result
            assert user["name"] == "alice"
            assert user["extra_roles"] == []

    def test_remove_user_roles_with_fallback(self):
        """Test that remove_user_roles() properly handles fallback parameter."""
        service = QuiltService()

        mock_users_module = Mock()
        mock_users_module.remove_roles.return_value = {
            "name": "bob",
            "email": "bob@example.com",
            "role": "viewer",
            "extra_roles": [],
            "active": True,
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            user = service.remove_user_roles("bob", ["admin"], "viewer")

            # Verify the fallback parameter was passed
            mock_users_module.remove_roles.assert_called_once_with("bob", ["admin"], "viewer")
            assert user["role"] == "viewer"

    def test_remove_user_roles_raises_admin_not_available(self):
        """Test that remove_user_roles() raises AdminNotAvailableError when admin unavailable."""
        service = QuiltService()

        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service.remove_user_roles("alice", ["viewer"], None)

            assert "Admin operations not available" in str(exc_info.value)

    def test_remove_user_roles_raises_user_not_found(self):
        """Test that remove_user_roles() raises UserNotFoundError when user doesn't exist."""
        service = QuiltService()

        mock_users_module = Mock()

        class MockQuilt3UserNotFoundError(Exception):
            pass

        mock_users_module.remove_roles.side_effect = MockQuilt3UserNotFoundError("User 'nonexistent' not found")

        mock_exceptions = {
            'UserNotFoundError': MockQuilt3UserNotFoundError,
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            with patch.object(service, '_get_admin_exceptions', return_value=mock_exceptions):
                with pytest.raises(UserNotFoundError) as exc_info:
                    service.remove_user_roles("nonexistent", ["viewer"], None)

                assert "nonexistent" in str(exc_info.value)


class TestResetUserPassword:
    """Test reset_user_password() method."""

    def test_reset_user_password_returns_success_dict(self):
        """Test that reset_user_password() returns success information."""
        service = QuiltService()

        # Mock the admin module's reset_password function
        mock_users_module = Mock()
        mock_users_module.reset_password.return_value = {
            "name": "alice",
            "status": "password_reset_sent",
            "message": "Password reset email sent to alice@example.com",
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            result = service.reset_user_password("alice")

            # Verify the admin module was called with correct username
            mock_users_module.reset_password.assert_called_once_with("alice")
            # Verify we got the expected result
            assert result["name"] == "alice"
            assert result["status"] == "password_reset_sent"

    def test_reset_user_password_raises_admin_not_available(self):
        """Test that reset_user_password() raises AdminNotAvailableError when admin unavailable."""
        service = QuiltService()

        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service.reset_user_password("alice")

            assert "Admin operations not available" in str(exc_info.value)

    def test_reset_user_password_raises_user_not_found(self):
        """Test that reset_user_password() raises UserNotFoundError when user doesn't exist."""
        service = QuiltService()

        mock_users_module = Mock()

        class MockQuilt3UserNotFoundError(Exception):
            pass

        mock_users_module.reset_password.side_effect = MockQuilt3UserNotFoundError("User 'nonexistent' not found")

        mock_exceptions = {
            'UserNotFoundError': MockQuilt3UserNotFoundError,
        }

        with patch.object(service, '_get_users_admin_module', return_value=mock_users_module):
            with patch.object(service, '_get_admin_exceptions', return_value=mock_exceptions):
                with pytest.raises(UserNotFoundError) as exc_info:
                    service.reset_user_password("nonexistent")

                assert "nonexistent" in str(exc_info.value)
