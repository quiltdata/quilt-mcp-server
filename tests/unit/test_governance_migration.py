"""
BDD tests for governance.py backend abstraction migration.

These tests verify that governance.py uses get_backend() instead of QuiltService,
following the Phase 4 backend abstraction migration pattern.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


class MockUser:
    """Mock user object for testing."""

    def __init__(
        self,
        name: str,
        email: str,
        is_active: bool = True,
        is_admin: bool = False,
        role: Mock = None,
        extra_roles: list = None,
    ):
        self.name = name
        self.email = email
        self.is_active = is_active
        self.is_admin = is_admin
        self.is_sso_only = False
        self.is_service = False
        self.date_joined = datetime.now()
        self.last_login = datetime.now()
        self.role = role
        self.extra_roles = extra_roles or []


class MockRole:
    """Mock role object for testing."""

    def __init__(self, id: str, name: str, arn: str = "arn:test", typename__: str = "Role"):
        self.id = id
        self.name = name
        self.arn = arn
        self.typename__ = typename__


class MockSSOConfig:
    """Mock SSO config object for testing."""

    def __init__(self, text: str, timestamp: datetime = None, uploader: MockUser = None):
        self.text = text
        self.timestamp = timestamp or datetime.now()
        self.uploader = uploader


@pytest.fixture
def mock_backend():
    """Create a mock backend with admin functionality."""
    backend = Mock()
    backend.is_admin_available.return_value = True

    # Mock admin objects
    backend.get_users_admin.return_value = Mock()
    backend.get_roles_admin.return_value = Mock()
    backend.get_sso_config_admin.return_value = Mock()
    backend.get_tabulator_admin.return_value = Mock()
    backend.get_admin_exceptions.return_value = {
        'UserNotFoundError': Exception,
        'BucketNotFoundError': Exception,
        'Quilt3AdminError': Exception,
    }

    return backend


class TestGovernanceUsesBackend:
    """Verify governance.py uses backend abstraction instead of QuiltService."""

    def test_governance_imports_get_backend(self):
        """
        GIVEN the governance module
        WHEN we inspect its imports
        THEN it should import get_backend from backends.factory
        AND it should NOT import QuiltService
        """
        from quilt_mcp.tools import governance
        import inspect

        source = inspect.getsource(governance)
        assert "from ..backends.factory import get_backend" in source
        assert "from ..services.quilt_service import QuiltService" not in source

    def test_governance_uses_backend_instance(self):
        """
        GIVEN the governance module
        WHEN we inspect its module-level variables
        THEN it should have _backend instead of quilt_service
        """
        from quilt_mcp.tools import governance

        # Should have _backend
        assert hasattr(governance, '_backend')

        # Should not have quilt_service
        assert not hasattr(governance, 'quilt_service')

    @patch('quilt_mcp.tools.governance._backend')
    def test_admin_users_list_uses_backend(self, mock_backend):
        """
        GIVEN a mock backend with admin users
        WHEN admin_users_list is called
        THEN it should use the backend to get admin users
        """
        from quilt_mcp.tools import governance
        import asyncio

        # Setup mock
        mock_backend.is_admin_available.return_value = True

        mock_admin_users = Mock()
        mock_role = MockRole("1", "admin")
        mock_user = MockUser("test_user", "test@example.com", role=mock_role)
        mock_admin_users.list.return_value = [mock_user]

        mock_backend.get_users_admin.return_value = mock_admin_users

        # Call the function
        result = asyncio.run(governance.admin_users_list())

        # Verify backend was used
        assert result['success'] is True
        assert len(result['users']) == 1
        assert result['users'][0]['name'] == 'test_user'

    @patch('quilt_mcp.tools.governance._backend')
    def test_admin_roles_list_uses_backend(self, mock_backend):
        """
        GIVEN a mock backend with admin roles
        WHEN admin_roles_list is called
        THEN it should use the backend to get admin roles
        """
        from quilt_mcp.tools import governance
        import asyncio

        # Setup mock
        mock_backend.is_admin_available.return_value = True

        mock_admin_roles = Mock()
        mock_role = MockRole("1", "admin")
        mock_admin_roles.list.return_value = [mock_role]

        mock_backend.get_roles_admin.return_value = mock_admin_roles

        # Call the function
        result = asyncio.run(governance.admin_roles_list())

        # Verify backend was used
        assert result['success'] is True
        assert len(result['roles']) == 1
        assert result['roles'][0]['name'] == 'admin'

    @patch('quilt_mcp.tools.governance._backend')
    def test_admin_sso_config_get_uses_backend(self, mock_backend):
        """
        GIVEN a mock backend with SSO config
        WHEN admin_sso_config_get is called
        THEN it should use the backend to get SSO config
        """
        from quilt_mcp.tools import governance
        import asyncio

        # Setup mock
        mock_backend.is_admin_available.return_value = True

        mock_admin_sso = Mock()
        mock_config = MockSSOConfig("test_config")
        mock_admin_sso.get.return_value = mock_config

        mock_backend.get_sso_config_admin.return_value = mock_admin_sso

        # Call the function
        result = asyncio.run(governance.admin_sso_config_get())

        # Verify backend was used
        assert result['success'] is True
        assert result['sso_config']['text'] == 'test_config'

    @patch('quilt_mcp.tools.governance._backend')
    def test_admin_tabulator_open_query_get_uses_backend(self, mock_backend):
        """
        GIVEN a mock backend with tabulator admin
        WHEN admin_tabulator_open_query_get is called
        THEN it should use the backend to get tabulator status
        """
        from quilt_mcp.tools import governance
        import asyncio

        # Setup mock
        mock_backend.is_admin_available.return_value = True

        mock_admin_tabulator = Mock()
        mock_admin_tabulator.get_open_query.return_value = True

        mock_backend.get_tabulator_admin.return_value = mock_admin_tabulator

        # Call the function
        result = asyncio.run(governance.admin_tabulator_open_query_get())

        # Verify backend was used
        assert result['success'] is True
        assert result['open_query_enabled'] is True


class TestGovernanceBackendIntegration:
    """Test that governance functions work correctly with backend abstraction."""

    @patch('quilt_mcp.tools.governance.ADMIN_AVAILABLE', False)
    def test_governance_service_respects_admin_availability(self):
        """
        GIVEN a backend with admin unavailable
        WHEN GovernanceService is initialized
        THEN it should respect the admin availability
        """
        from quilt_mcp.tools import governance

        service = governance.GovernanceService()
        error = service._check_admin_available()

        assert error is not None
        assert error['success'] is False
        assert 'Admin functionality not available' in error['error']

    @patch('quilt_mcp.tools.governance._backend')
    def test_admin_user_create_delegates_to_backend(self, mock_backend):
        """
        GIVEN a mock backend
        WHEN admin_user_create is called
        THEN it should delegate to backend.get_users_admin().create()
        """
        from quilt_mcp.tools import governance
        import asyncio

        # Setup mock
        mock_backend.is_admin_available.return_value = True
        mock_admin_users = Mock()
        mock_role = MockRole("1", "admin")
        mock_user = MockUser("new_user", "new@example.com", role=mock_role)
        mock_admin_users.create.return_value = mock_user
        mock_backend.get_users_admin.return_value = mock_admin_users

        # Call the function
        result = asyncio.run(governance.admin_user_create(name="new_user", email="new@example.com", role="admin"))

        # Verify backend was used
        assert result['success'] is True
        assert result['user']['name'] == 'new_user'
        mock_backend.get_users_admin.assert_called()

    @patch('quilt_mcp.tools.governance._backend')
    def test_admin_user_delete_delegates_to_backend(self, mock_backend):
        """
        GIVEN a mock backend
        WHEN admin_user_delete is called
        THEN it should delegate to backend.get_users_admin().delete()
        """
        from quilt_mcp.tools import governance
        import asyncio

        # Setup mock
        mock_backend.is_admin_available.return_value = True
        mock_admin_users = Mock()
        mock_backend.get_users_admin.return_value = mock_admin_users

        # Call the function
        result = asyncio.run(governance.admin_user_delete(name="test_user"))

        # Verify backend was used
        assert result['success'] is True
        mock_backend.get_users_admin.assert_called()
        mock_admin_users.delete.assert_called_with("test_user")


class TestGovernanceErrorPropagation:
    """Test that errors propagate correctly through backend abstraction."""

    @patch('quilt_mcp.tools.governance._backend')
    def test_user_not_found_error_propagates(self, mock_backend):
        """
        GIVEN a backend that raises UserNotFoundError
        WHEN admin_user_get is called
        THEN the error should propagate correctly
        """
        from quilt_mcp.tools import governance
        import asyncio

        # Setup mock to raise error
        mock_backend.is_admin_available.return_value = True
        mock_admin_users = Mock()

        # Create a custom exception class
        UserNotFoundError = type('UserNotFoundError', (Exception,), {})
        mock_backend.get_admin_exceptions.return_value = {
            'UserNotFoundError': UserNotFoundError,
            'BucketNotFoundError': Exception,
            'Quilt3AdminError': Exception,
        }

        mock_admin_users.get.side_effect = UserNotFoundError("User not found")
        mock_backend.get_users_admin.return_value = mock_admin_users

        # Call the function
        result = asyncio.run(governance.admin_user_get(name="nonexistent"))

        # Verify error was handled
        assert result['success'] is False
        assert 'not found' in result['error'].lower()
