"""
BDD tests for tabulator.py backend abstraction migration.

These tests verify that tabulator.py uses get_backend() instead of QuiltService,
following the Phase 4 backend abstraction migration pattern.
"""

import pytest
from unittest.mock import Mock, patch


class MockTable:
    """Mock tabulator table object for testing."""

    def __init__(self, name: str, config: str):
        self.name = name
        self.config = config


@pytest.fixture
def mock_backend():
    """Create a mock backend with tabulator functionality."""
    backend = Mock()
    backend.is_admin_available.return_value = True

    # Mock tabulator admin
    backend.get_tabulator_admin.return_value = Mock()

    return backend


class TestTabulatorUsesBackend:
    """Verify tabulator.py uses backend abstraction instead of QuiltService."""

    def test_tabulator_imports_get_backend(self):
        """
        GIVEN the tabulator module
        WHEN we inspect its imports
        THEN it should import get_backend from backends.factory
        AND it should NOT import QuiltService
        """
        from quilt_mcp.tools import tabulator
        import inspect

        source = inspect.getsource(tabulator)
        assert "from ..backends.factory import get_backend" in source
        assert "from ..services.quilt_service import QuiltService" not in source

    def test_tabulator_uses_backend_instance(self):
        """
        GIVEN the tabulator module
        WHEN we inspect its module-level variables
        THEN it should have _backend instead of quilt_service
        """
        from quilt_mcp.tools import tabulator

        # Should have _backend
        assert hasattr(tabulator, '_backend')

        # Should not have quilt_service
        assert not hasattr(tabulator, 'quilt_service')

    @patch('quilt_mcp.tools.tabulator._backend')
    def test_list_tables_uses_backend(self, mock_backend):
        """
        GIVEN a mock backend with tabulator tables
        WHEN list_tables is called
        THEN it should use the backend to get tabulator admin
        """
        from quilt_mcp.tools import tabulator

        # Setup mock
        mock_backend.is_admin_available.return_value = True

        mock_admin_tabulator = Mock()
        mock_table = MockTable("test_table", "schema:\n- name: col1\n  type: STRING")
        mock_admin_tabulator.list_tables.return_value = [mock_table]

        mock_backend.get_tabulator_admin.return_value = mock_admin_tabulator

        # Create service and call method
        service = tabulator.TabulatorService()
        result = service.list_tables("test-bucket")

        # Verify backend was used
        assert result['success'] is True
        assert len(result['tables']) == 1
        assert result['tables'][0]['name'] == 'test_table'

    @patch('quilt_mcp.tools.tabulator._backend')
    def test_create_table_uses_backend(self, mock_backend):
        """
        GIVEN a mock backend with tabulator admin
        WHEN create_table is called
        THEN it should use the backend to create a table
        """
        from quilt_mcp.tools import tabulator

        # Setup mock
        mock_backend.is_admin_available.return_value = True

        mock_admin_tabulator = Mock()
        mock_admin_tabulator.create_table.return_value = None

        mock_backend.get_tabulator_admin.return_value = mock_admin_tabulator

        # Create service and call method
        service = tabulator.TabulatorService()
        schema = [{"name": "col1", "type": "STRING"}]
        parser_config = {"format": "csv", "delimiter": ",", "header": True}

        result = service.create_table(
            bucket_name="test-bucket",
            table_name="test_table",
            schema=schema,
            package_pattern=".*",
            logical_key_pattern=".*",
            parser_config=parser_config
        )

        # Verify backend was used
        assert result['success'] is True

    @patch('quilt_mcp.tools.tabulator._backend')
    def test_delete_table_uses_backend(self, mock_backend):
        """
        GIVEN a mock backend with tabulator admin
        WHEN delete_table is called
        THEN it should use the backend to delete a table
        """
        from quilt_mcp.tools import tabulator

        # Setup mock
        mock_backend.is_admin_available.return_value = True

        mock_admin_tabulator = Mock()
        mock_admin_tabulator.delete_table.return_value = None

        mock_backend.get_tabulator_admin.return_value = mock_admin_tabulator

        # Create service and call method
        service = tabulator.TabulatorService()
        result = service.delete_table("test-bucket", "test_table")

        # Verify backend was used
        assert result['success'] is True

    @patch('quilt_mcp.tools.tabulator._backend')
    def test_rename_table_uses_backend(self, mock_backend):
        """
        GIVEN a mock backend with tabulator admin
        WHEN rename_table is called
        THEN it should use the backend to rename a table
        """
        from quilt_mcp.tools import tabulator

        # Setup mock
        mock_backend.is_admin_available.return_value = True

        mock_admin_tabulator = Mock()
        mock_admin_tabulator.rename_table.return_value = None

        mock_backend.get_tabulator_admin.return_value = mock_admin_tabulator

        # Create service and call method
        service = tabulator.TabulatorService()
        result = service.rename_table("test-bucket", "old_table", "new_table")

        # Verify backend was used
        assert result['success'] is True


class TestTabulatorBackendIntegration:
    """Test that tabulator functions work correctly with backend abstraction."""

    @patch('quilt_mcp.tools.tabulator.ADMIN_AVAILABLE', False)
    def test_tabulator_service_respects_admin_availability(self):
        """
        GIVEN a backend with admin unavailable
        WHEN TabulatorService is initialized
        THEN it should respect the admin availability
        """
        from quilt_mcp.tools import tabulator

        service = tabulator.TabulatorService()

        assert service.admin_available is False

    @patch('quilt_mcp.tools.tabulator._backend')
    def test_list_tables_delegates_to_backend(self, mock_backend):
        """
        GIVEN a mock backend
        WHEN list_tables is called
        THEN it should delegate to backend.get_tabulator_admin().list_tables()
        """
        from quilt_mcp.tools import tabulator

        # Setup mock
        mock_backend.is_admin_available.return_value = True
        mock_admin_tabulator = Mock()
        mock_table = MockTable("test_table", "schema:\n- name: col1\n  type: STRING")
        mock_admin_tabulator.list_tables.return_value = [mock_table]
        mock_backend.get_tabulator_admin.return_value = mock_admin_tabulator

        # Create service and call method
        service = tabulator.TabulatorService()
        result = service.list_tables("test-bucket")

        # Verify backend was used
        assert result['success'] is True
        mock_backend.get_tabulator_admin.assert_called()
        mock_admin_tabulator.list_tables.assert_called_with("test-bucket")

    @patch('quilt_mcp.tools.tabulator._backend')
    def test_create_table_validates_before_backend_call(self, mock_backend):
        """
        GIVEN a mock backend
        WHEN create_table is called with invalid schema
        THEN it should validate before calling backend
        """
        from quilt_mcp.tools import tabulator

        # Setup mock
        mock_backend.is_admin_available.return_value = True

        # Create service with invalid schema
        service = tabulator.TabulatorService()
        result = service.create_table(
            bucket_name="test-bucket",
            table_name="test_table",
            schema=[],  # Empty schema should fail validation
            package_pattern=".*",
            logical_key_pattern=".*",
            parser_config={"format": "csv"}
        )

        # Verify validation error
        assert result['success'] is False
        assert 'Schema cannot be empty' in result['error']

        # Backend should not have been called
        mock_backend.get_tabulator_admin.assert_not_called()


class TestTabulatorErrorPropagation:
    """Test that errors propagate correctly through backend abstraction."""

    @patch('quilt_mcp.tools.tabulator._backend')
    def test_backend_error_propagates(self, mock_backend):
        """
        GIVEN a backend that raises an error
        WHEN list_tables is called
        THEN the error should propagate correctly
        """
        from quilt_mcp.tools import tabulator

        # Setup mock to raise error
        mock_backend.is_admin_available.return_value = True
        mock_admin_tabulator = Mock()
        mock_admin_tabulator.list_tables.side_effect = Exception("Backend error")
        mock_backend.get_tabulator_admin.return_value = mock_admin_tabulator

        # Create service and call method
        service = tabulator.TabulatorService()
        result = service.list_tables("test-bucket")

        # Verify error was handled
        assert result['success'] is False
        assert 'Backend error' in result['error']

    @patch('quilt_mcp.tools.tabulator.ADMIN_AVAILABLE', False)
    def test_admin_unavailable_returns_error(self):
        """
        GIVEN a backend with admin unavailable
        WHEN any tabulator operation is called
        THEN it should return an appropriate error
        """
        from quilt_mcp.tools import tabulator

        # Create service and call method
        service = tabulator.TabulatorService()
        result = service.list_tables("test-bucket")

        # Verify error response
        assert result['success'] is False
        assert 'Admin functionality not available' in result['error']


class TestTabulatorValidation:
    """Test that tabulator validation logic works with backend abstraction."""

    def test_schema_validation_independent_of_backend(self):
        """
        GIVEN a TabulatorService
        WHEN _validate_schema is called
        THEN it should work independently of backend
        """
        from quilt_mcp.tools import tabulator

        service = tabulator.TabulatorService()

        # Valid schema
        valid_schema = [{"name": "col1", "type": "STRING"}]
        errors = service._validate_schema(valid_schema)
        assert len(errors) == 0

        # Invalid schema - missing type
        invalid_schema = [{"name": "col1"}]
        errors = service._validate_schema(invalid_schema)
        assert len(errors) > 0
        assert any('type' in error.lower() for error in errors)

    def test_pattern_validation_independent_of_backend(self):
        """
        GIVEN a TabulatorService
        WHEN _validate_patterns is called
        THEN it should work independently of backend
        """
        from quilt_mcp.tools import tabulator

        service = tabulator.TabulatorService()

        # Valid patterns
        errors = service._validate_patterns(".*", ".*")
        assert len(errors) == 0

        # Invalid patterns
        errors = service._validate_patterns("", "")
        assert len(errors) > 0

    def test_parser_config_validation_independent_of_backend(self):
        """
        GIVEN a TabulatorService
        WHEN _validate_parser_config is called
        THEN it should work independently of backend
        """
        from quilt_mcp.tools import tabulator

        service = tabulator.TabulatorService()

        # Valid parser config
        valid_config = {"format": "csv"}
        errors = service._validate_parser_config(valid_config)
        assert len(errors) == 0

        # Invalid parser config
        invalid_config = {"format": "invalid"}
        errors = service._validate_parser_config(invalid_config)
        assert len(errors) > 0
        assert any('invalid' in error.lower() for error in errors)
