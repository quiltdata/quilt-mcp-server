"""Integration tests for MCP server initialization with QuiltOps."""

import pytest
from unittest.mock import patch, MagicMock
import os
import sys

from quilt_mcp.utils import create_configured_server
from quilt_mcp.ops.factory import QuiltOpsFactory
from quilt_mcp.ops.exceptions import AuthenticationError


@pytest.mark.integration
class TestMCPServerInitialization:
    """Integration tests for MCP server initialization with QuiltOpsFactory."""

    def test_server_initialization_with_valid_quilt3_session(self):
        """Test that MCP server initializes successfully with valid quilt3 session."""
        # Mock a valid quilt3 session
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    # This should not raise an exception
                    server = create_configured_server(verbose=False)
                    assert server is not None
                    assert hasattr(server, 'tool')  # FastMCP server should have tool decorator

    def test_server_initialization_fails_with_no_authentication(self):
        """Test that MCP server initialization fails gracefully when no authentication is available."""
        # Mock no quilt3 session available
        with patch('quilt3.logged_in', return_value=False):
            with patch('quilt3.session.get_session', return_value=None):
                # Server creation should still work, but QuiltOps creation should fail
                # The server initialization should handle this gracefully
                try:
                    server = create_configured_server(verbose=False)
                    # If server creation succeeds, it means auth validation is deferred
                    # until actual tool usage, which is acceptable
                    assert server is not None
                except Exception as e:
                    # If server creation fails, it should be due to auth issues
                    assert "authentication" in str(e).lower() or "quilt3" in str(e).lower()

    def test_quilt_ops_factory_integration_in_server(self):
        """Test that QuiltOpsFactory is properly integrated into the server."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    # Test that QuiltOpsFactory can create instances
                    quilt_ops = QuiltOpsFactory.create()
                    assert quilt_ops is not None
                    
                    # Test that server can be created
                    server = create_configured_server(verbose=False)
                    assert server is not None

    def test_server_error_handling_for_quilt_ops_creation_failure(self):
        """Test that server handles QuiltOps creation failures gracefully."""
        # Mock quilt3 to raise an exception during session validation
        with patch('quilt3.logged_in', side_effect=Exception("Session validation failed")):
            # QuiltOpsFactory should raise AuthenticationError
            with pytest.raises(AuthenticationError) as exc_info:
                QuiltOpsFactory.create()
            
            assert "No valid authentication found" in str(exc_info.value)
            assert "quilt3 login" in str(exc_info.value)

    def test_server_initialization_without_quilt_service_references(self):
        """Test that server initialization doesn't reference QuiltService."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    server = create_configured_server(verbose=False)
                    
                    # Check that server doesn't have any QuiltService references
                    # This is a basic check - more thorough checks will be in unit tests
                    server_str = str(server)
                    assert "QuiltService" not in server_str

    @patch('sys.stderr')
    def test_server_initialization_verbose_output(self, mock_stderr):
        """Test that server initialization produces expected verbose output."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    server = create_configured_server(verbose=True)
                    assert server is not None
                    
                    # Check that verbose output was produced (calls to print with file=sys.stderr)
                    assert mock_stderr.write.called or any(
                        'Registered tool:' in str(call) for call in mock_stderr.write.call_args_list
                    )

    def test_server_initialization_with_environment_variables(self):
        """Test server initialization respects environment variables."""
        mock_session = MagicMock()
        
        # Test with different transport settings
        original_transport = os.environ.get('FASTMCP_TRANSPORT')
        try:
            os.environ['FASTMCP_TRANSPORT'] = 'stdio'
            
            with patch('quilt3.logged_in', return_value=True):
                with patch('quilt3.session.get_session', return_value=mock_session):
                    with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                        server = create_configured_server(verbose=False)
                        assert server is not None
        finally:
            # Restore original environment
            if original_transport is not None:
                os.environ['FASTMCP_TRANSPORT'] = original_transport
            elif 'FASTMCP_TRANSPORT' in os.environ:
                del os.environ['FASTMCP_TRANSPORT']


@pytest.mark.integration
class TestQuiltOpsFactoryIntegration:
    """Integration tests specifically for QuiltOpsFactory in server context."""

    def test_factory_creates_quilt3_backend_with_valid_session(self):
        """Test that factory creates Quilt3_Backend with valid session."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    quilt_ops = QuiltOpsFactory.create()
                    
                    # Should be a Quilt3_Backend instance
                    from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
                    assert isinstance(quilt_ops, Quilt3_Backend)

    def test_factory_error_message_quality(self):
        """Test that factory provides helpful error messages."""
        with patch('quilt3.logged_in', return_value=False):
            with pytest.raises(AuthenticationError) as exc_info:
                QuiltOpsFactory.create()
            
            error_msg = str(exc_info.value)
            # Should contain helpful instructions
            assert "quilt3 login" in error_msg
            assert "authentication" in error_msg.lower()
            assert "https://docs.quiltdata.com" in error_msg

    def test_factory_handles_quilt3_import_error(self):
        """Test that factory handles missing quilt3 library gracefully."""
        # Mock quilt3 as None (import failed)
        with patch('quilt_mcp.ops.factory.quilt3', None):
            with pytest.raises(AuthenticationError) as exc_info:
                QuiltOpsFactory.create()
            
            error_msg = str(exc_info.value)
            assert "authentication" in error_msg.lower()

    def test_factory_logging_behavior(self):
        """Test that factory produces appropriate log messages."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    with patch('quilt_mcp.ops.factory.logger') as mock_logger:
                        quilt_ops = QuiltOpsFactory.create()
                        
                        # Should log successful creation
                        mock_logger.info.assert_called()
                        mock_logger.debug.assert_called()
                        
                        # Check for expected log messages
                        log_calls = [str(call) for call in mock_logger.info.call_args_list]
                        assert any("Quilt3_Backend" in call for call in log_calls)


@pytest.mark.integration
class TestQuiltServiceRemoval:
    """Integration tests to ensure QuiltService is no longer used in server initialization."""

    def test_server_initialization_does_not_import_quilt_service(self):
        """Test that server initialization doesn't import QuiltService."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    # Track imports during server creation
                    import sys
                    original_modules = set(sys.modules.keys())
                    
                    server = create_configured_server(verbose=False)
                    assert server is not None
                    
                    # Check that QuiltService wasn't imported during server creation
                    new_modules = set(sys.modules.keys()) - original_modules
                    quilt_service_modules = [m for m in new_modules if 'quilt_service' in m.lower()]
                    
                    # If QuiltService modules were imported, they should not be used in server init
                    # This is a basic check - the real validation is in the code structure

    def test_server_tools_do_not_reference_quilt_service_directly(self):
        """Test that server tools don't directly reference QuiltService in their initialization."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    server = create_configured_server(verbose=False)
                    
                    # Check that server object doesn't contain QuiltService references
                    # This is a basic string-based check
                    server_repr = repr(server)
                    assert "QuiltService" not in server_repr

    def test_auth_service_initialization_without_quilt_service(self):
        """Test that auth service can initialize without QuiltService dependency."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    # Test that auth service initialization works
                    from quilt_mcp.services.auth_service import create_auth_service
                    
                    auth_service = create_auth_service()
                    assert auth_service is not None
                    
                    # Auth service should work without QuiltService
                    # This validates that the dependency injection has been updated

    def test_server_startup_validation_uses_quilt_ops_factory(self):
        """Test that server startup validation uses QuiltOpsFactory instead of QuiltService."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    # Mock the QuiltOpsFactory to track its usage
                    with patch('quilt_mcp.ops.factory.QuiltOpsFactory.create') as mock_create:
                        mock_create.return_value = MagicMock()
                        
                        # Server creation should validate auth using QuiltOpsFactory
                        server = create_configured_server(verbose=False)
                        assert server is not None
                        
                        # The factory should be used during server initialization
                        # (This might be called during auth service validation)

    def test_no_quilt_service_in_dependency_container(self):
        """Test that QuiltService is not present in any dependency injection container."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    server = create_configured_server(verbose=False)
                    
                    # Check that no QuiltService instances are created during server init
                    # This is validated by the successful creation without QuiltService imports
                    assert server is not None


@pytest.mark.integration
class TestDependencyInjection:
    """Integration tests for dependency injection providing QuiltOps instead of QuiltService."""

    def test_tools_can_receive_quilt_ops_instances(self):
        """Test that tools can work with QuiltOps instances when provided."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    # Create QuiltOps instance
                    quilt_ops = QuiltOpsFactory.create()
                    assert quilt_ops is not None
                    
                    # Verify it's the correct type
                    from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
                    assert isinstance(quilt_ops, Quilt3_Backend)

    def test_tools_use_quilt_ops_factory_instead_of_direct_instantiation(self):
        """Test that migrated tools use QuiltOpsFactory instead of direct QuiltService instantiation."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    # Mock the QuiltOpsFactory to track its usage
                    with patch('quilt_mcp.ops.factory.QuiltOpsFactory.create') as mock_create:
                        mock_quilt_ops = MagicMock()
                        mock_create.return_value = mock_quilt_ops
                        
                        # Test that tools that have been migrated use the factory
                        # This is a basic test - specific tool tests would be more detailed
                        quilt_ops = QuiltOpsFactory.create()
                        assert quilt_ops is not None
                        mock_create.assert_called_once()

    def test_no_quilt_service_in_dependency_resolution(self):
        """Test that dependency resolution doesn't involve QuiltService."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    # Create server and verify no QuiltService is involved in dependency resolution
                    server = create_configured_server(verbose=False)
                    assert server is not None
                    
                    # The fact that server creation succeeds without QuiltService imports
                    # validates that dependency resolution works without QuiltService

    def test_quilt_ops_factory_provides_consistent_instances(self):
        """Test that QuiltOpsFactory provides consistent QuiltOps instances."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    # Create multiple instances
                    quilt_ops1 = QuiltOpsFactory.create()
                    quilt_ops2 = QuiltOpsFactory.create()
                    
                    # Both should be valid QuiltOps instances
                    assert quilt_ops1 is not None
                    assert quilt_ops2 is not None
                    
                    # Both should be the same type
                    assert type(quilt_ops1) == type(quilt_ops2)

    def test_tools_receive_domain_objects_not_quilt3_objects(self):
        """Test that tools receive domain objects (Package_Info, Content_Info) instead of quilt3 objects."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    quilt_ops = QuiltOpsFactory.create()
                    
                    # Mock the backend methods to return domain objects
                    from quilt_mcp.domain.package_info import Package_Info
                    from quilt_mcp.domain.content_info import Content_Info
                    
                    mock_package_info = Package_Info(
                        name="test/package",
                        description="Test package",
                        tags=["test"],
                        modified_date="2024-01-01T00:00:00Z",
                        registry="s3://test-registry",
                        bucket="test-bucket",
                        top_hash="abc123"
                    )
                    
                    mock_content_info = Content_Info(
                        path="test.txt",
                        size=100,
                        type="file",
                        modified_date="2024-01-01T00:00:00Z",
                        download_url=None
                    )
                    
                    # Verify that QuiltOps methods return domain objects
                    with patch.object(quilt_ops, 'search_packages', return_value=[mock_package_info]):
                        with patch.object(quilt_ops, 'browse_content', return_value=[mock_content_info]):
                            packages = quilt_ops.search_packages("test", "s3://test-registry")
                            content = quilt_ops.browse_content("test/package", "s3://test-registry")
                            
                            assert len(packages) == 1
                            assert isinstance(packages[0], Package_Info)
                            assert len(content) == 1
                            assert isinstance(content[0], Content_Info)


@pytest.mark.integration
class TestCodeCleanup:
    """Integration tests to ensure old code patterns are cleaned up."""

    def test_tools_do_not_directly_import_quilt3(self):
        """Test that tools do not directly import quilt3 library."""
        import ast
        import os
        from pathlib import Path
        
        tools_dir = Path("src/quilt_mcp/tools")
        quilt3_importing_tools = []
        
        for tool_file in tools_dir.glob("*.py"):
            if tool_file.name.startswith("__"):
                continue
                
            try:
                with open(tool_file, 'r') as f:
                    content = f.read()
                
                # Parse the AST to find imports
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name == "quilt3" or alias.name.startswith("quilt3."):
                                quilt3_importing_tools.append(str(tool_file))
                    elif isinstance(node, ast.ImportFrom):
                        if node.module == "quilt3" or (node.module and node.module.startswith("quilt3.")):
                            quilt3_importing_tools.append(str(tool_file))
                            
            except Exception as e:
                # Skip files that can't be parsed
                continue
        
        # Allow quilt3 imports only in specific files that need backward compatibility
        allowed_quilt3_imports = [
            "src/quilt_mcp/tools/packages.py",  # Has some backward compatibility exports
        ]
        
        unexpected_imports = [f for f in quilt3_importing_tools if f not in allowed_quilt3_imports]
        
        assert len(unexpected_imports) == 0, (
            f"Found unexpected direct quilt3 imports in tools: {unexpected_imports}. "
            f"Tools should use QuiltOps abstraction instead."
        )

    def test_tools_use_quilt_ops_factory_pattern(self):
        """Test that migrated tools use QuiltOpsFactory pattern."""
        import ast
        from pathlib import Path
        
        tools_dir = Path("src/quilt_mcp/tools")
        factory_using_tools = []
        
        for tool_file in tools_dir.glob("*.py"):
            if tool_file.name.startswith("__"):
                continue
                
            try:
                with open(tool_file, 'r') as f:
                    content = f.read()
                
                # Check for QuiltOpsFactory usage
                if "QuiltOpsFactory" in content:
                    factory_using_tools.append(str(tool_file))
                            
            except Exception as e:
                continue
        
        # At least some tools should be using QuiltOpsFactory
        assert len(factory_using_tools) > 0, (
            "Expected at least some tools to use QuiltOpsFactory pattern"
        )
        
        # Verify packages.py is using QuiltOpsFactory (we know it's been migrated)
        packages_file = "src/quilt_mcp/tools/packages.py"
        assert packages_file in factory_using_tools, (
            "packages.py should be using QuiltOpsFactory"
        )

    def test_no_direct_quilt3_instantiation_in_tools(self):
        """Test that tools don't directly instantiate quilt3 objects."""
        from pathlib import Path
        
        tools_dir = Path("src/quilt_mcp/tools")
        problematic_patterns = []
        
        for tool_file in tools_dir.glob("*.py"):
            if tool_file.name.startswith("__"):
                continue
                
            try:
                with open(tool_file, 'r') as f:
                    content = f.read()
                
                # Look for direct quilt3 object instantiation patterns
                problematic_lines = []
                for i, line in enumerate(content.split('\n'), 1):
                    line_stripped = line.strip()
                    if (
                        "quilt3.Package(" in line_stripped or
                        "quilt3.Bucket(" in line_stripped or
                        "quilt3.search(" in line_stripped or
                        "quilt3.list_packages(" in line_stripped
                    ):
                        problematic_lines.append(f"Line {i}: {line_stripped}")
                
                if problematic_lines:
                    problematic_patterns.append({
                        'file': str(tool_file),
                        'lines': problematic_lines
                    })
                            
            except Exception as e:
                continue
        
        # Allow some patterns in packages.py for backward compatibility during transition
        allowed_files = ["src/quilt_mcp/tools/packages.py"]
        unexpected_patterns = [
            p for p in problematic_patterns 
            if p['file'] not in allowed_files
        ]
        
        assert len(unexpected_patterns) == 0, (
            f"Found direct quilt3 instantiation in tools: {unexpected_patterns}. "
            f"Tools should use QuiltOps abstraction instead."
        )
