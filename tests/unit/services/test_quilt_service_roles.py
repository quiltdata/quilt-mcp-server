"""Tests for QuiltService role management methods (Phase 3.1).

These tests verify the behavior of role CRUD operations following
strict TDD principles. All tests use behavior-driven patterns.
"""

import pytest
from unittest.mock import Mock, patch

from quilt_mcp.services.quilt_service import QuiltService
from quilt_mcp.services.exceptions import (
    AdminNotAvailableError,
    RoleNotFoundError,
    RoleAlreadyExistsError,
)


class TestRoleManagementAvailability:
    """Tests for role management availability checking."""

    def test_list_roles_requires_admin_available(self):
        """list_roles() raises AdminNotAvailableError when admin not available."""
        service = QuiltService()

        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service.list_roles()

            assert "Admin operations not available" in str(exc_info.value)
            assert "quilt3.admin module not installed" in str(exc_info.value)

    def test_get_role_requires_admin_available(self):
        """get_role() raises AdminNotAvailableError when admin not available."""
        service = QuiltService()

        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service.get_role("test_role")

            assert "Admin operations not available" in str(exc_info.value)

    def test_create_role_requires_admin_available(self):
        """create_role() raises AdminNotAvailableError when admin not available."""
        service = QuiltService()

        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service.create_role("test_role", {"read": True})

            assert "Admin operations not available" in str(exc_info.value)

    def test_delete_role_requires_admin_available(self):
        """delete_role() raises AdminNotAvailableError when admin not available."""
        service = QuiltService()

        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service.delete_role("test_role")

            assert "Admin operations not available" in str(exc_info.value)


class TestListRoles:
    """Tests for list_roles() method."""

    def test_list_roles_returns_list_of_dicts(self):
        """list_roles() returns a list of role dictionaries."""
        service = QuiltService()
        mock_roles_admin = Mock()
        mock_roles_admin.list.return_value = [
            {"name": "admin", "permissions": {"read": True, "write": True}},
            {"name": "viewer", "permissions": {"read": True, "write": False}},
        ]

        with patch.object(service, '_get_roles_admin_module', return_value=mock_roles_admin):
            roles = service.list_roles()

        assert isinstance(roles, list)
        assert len(roles) == 2
        assert all(isinstance(role, dict) for role in roles)
        assert roles[0]["name"] == "admin"
        assert roles[1]["name"] == "viewer"
        mock_roles_admin.list.assert_called_once()

    def test_list_roles_returns_empty_list_when_no_roles(self):
        """list_roles() returns empty list when no roles exist."""
        service = QuiltService()
        mock_roles_admin = Mock()
        mock_roles_admin.list.return_value = []

        with patch.object(service, '_get_roles_admin_module', return_value=mock_roles_admin):
            roles = service.list_roles()

        assert isinstance(roles, list)
        assert len(roles) == 0


class TestGetRole:
    """Tests for get_role() method."""

    def test_get_role_returns_role_dict(self):
        """get_role() returns a dictionary with role information."""
        service = QuiltService()
        mock_roles_admin = Mock()
        expected_role = {
            "name": "editor",
            "permissions": {"read": True, "write": True},
        }
        mock_roles_admin.get.return_value = expected_role

        with patch.object(service, '_get_roles_admin_module', return_value=mock_roles_admin):
            role = service.get_role("editor")

        assert isinstance(role, dict)
        assert role["name"] == "editor"
        assert "permissions" in role
        mock_roles_admin.get.assert_called_once_with("editor")

    def test_get_role_raises_not_found_when_role_does_not_exist(self):
        """get_role() raises RoleNotFoundError when role doesn't exist."""
        service = QuiltService()
        mock_roles_admin = Mock()

        # Simulate quilt3.admin.roles.get() raising RoleNotFoundError
        from quilt_mcp.services.exceptions import QuiltServiceError
        mock_quilt3_error = type('RoleNotFoundError', (Exception,), {})
        mock_roles_admin.get.side_effect = mock_quilt3_error("Role 'nonexistent' not found")

        with patch.object(service, '_get_roles_admin_module', return_value=mock_roles_admin):
            with patch.object(service, '_get_admin_exceptions', return_value={
                'RoleNotFoundError': mock_quilt3_error
            }):
                with pytest.raises(RoleNotFoundError) as exc_info:
                    service.get_role("nonexistent")

                assert "Role 'nonexistent' not found" in str(exc_info.value)


class TestCreateRole:
    """Tests for create_role() method."""

    def test_create_role_returns_created_role_dict(self):
        """create_role() returns a dictionary with created role information."""
        service = QuiltService()
        mock_roles_admin = Mock()
        expected_role = {
            "name": "contributor",
            "permissions": {"read": True, "write": True, "delete": False},
        }
        mock_roles_admin.create.return_value = expected_role

        with patch.object(service, '_get_roles_admin_module', return_value=mock_roles_admin):
            role = service.create_role(
                "contributor",
                {"read": True, "write": True, "delete": False}
            )

        assert isinstance(role, dict)
        assert role["name"] == "contributor"
        assert role["permissions"]["read"] is True
        mock_roles_admin.create.assert_called_once_with(
            "contributor",
            {"read": True, "write": True, "delete": False}
        )

    def test_create_role_raises_already_exists_when_role_exists(self):
        """create_role() raises RoleAlreadyExistsError when role already exists."""
        service = QuiltService()
        mock_roles_admin = Mock()

        # Simulate quilt3.admin raising an error indicating role exists
        mock_admin_error = type('Quilt3AdminError', (Exception,), {})
        mock_roles_admin.create.side_effect = mock_admin_error("Role 'editor' already exists")

        with patch.object(service, '_get_roles_admin_module', return_value=mock_roles_admin):
            with patch.object(service, '_get_admin_exceptions', return_value={
                'Quilt3AdminError': mock_admin_error
            }):
                with pytest.raises(RoleAlreadyExistsError) as exc_info:
                    service.create_role("editor", {"read": True})

                assert "Role 'editor' already exists" in str(exc_info.value)


class TestDeleteRole:
    """Tests for delete_role() method."""

    def test_delete_role_completes_without_error(self):
        """delete_role() completes successfully without returning a value."""
        service = QuiltService()
        mock_roles_admin = Mock()
        mock_roles_admin.delete.return_value = None

        with patch.object(service, '_get_roles_admin_module', return_value=mock_roles_admin):
            result = service.delete_role("contributor")

        assert result is None
        mock_roles_admin.delete.assert_called_once_with("contributor")

    def test_delete_role_raises_not_found_when_role_does_not_exist(self):
        """delete_role() raises RoleNotFoundError when role doesn't exist."""
        service = QuiltService()
        mock_roles_admin = Mock()

        # Simulate quilt3.admin.roles.delete() raising RoleNotFoundError
        mock_quilt3_error = type('RoleNotFoundError', (Exception,), {})
        mock_roles_admin.delete.side_effect = mock_quilt3_error("Role 'nonexistent' not found")

        with patch.object(service, '_get_roles_admin_module', return_value=mock_roles_admin):
            with patch.object(service, '_get_admin_exceptions', return_value={
                'RoleNotFoundError': mock_quilt3_error
            }):
                with pytest.raises(RoleNotFoundError) as exc_info:
                    service.delete_role("nonexistent")

                assert "Role 'nonexistent' not found" in str(exc_info.value)


class TestGetRolesAdminModuleHelper:
    """Tests for _get_roles_admin_module() helper."""

    def test_get_roles_admin_module_returns_module_when_available(self):
        """_get_roles_admin_module() returns the roles admin module when available."""
        service = QuiltService()

        with patch.object(service, 'is_admin_available', return_value=True):
            with patch('quilt_mcp.services.quilt_service.quilt3') as mock_quilt3:
                mock_roles_module = Mock()
                mock_quilt3.admin.roles = mock_roles_module

                module = service._get_roles_admin_module()

                assert module is mock_roles_module

    def test_get_roles_admin_module_raises_when_unavailable(self):
        """_get_roles_admin_module() raises AdminNotAvailableError when unavailable."""
        service = QuiltService()

        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service._get_roles_admin_module()

            assert "Admin operations not available" in str(exc_info.value)
            assert "Role management operations require admin access" in str(exc_info.value)
