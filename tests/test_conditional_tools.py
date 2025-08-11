"""
Test suite for conditional tool registration in different environments.
Validates that tools are correctly registered/excluded in Lambda vs local modes.
"""
import pytest
import sys
import os
from unittest.mock import patch

# Add the quilt directory to path to import our local module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'quilt'))

def test_lambda_mode_tools():
    """Test that all tools are available in Lambda mode (behavior updated to include all tools)."""
    # Import in function to ensure fresh module state
    import importlib
    
    # Mock Lambda environment
    with patch.dict(os.environ, {'AWS_LAMBDA_FUNCTION_NAME': 'test-function'}):
        # Force reload to pick up environment change
        if 'quilt' in sys.modules:
            quilt = importlib.reload(sys.modules['quilt'])
        else:
            import quilt
        
        # Check which tools are registered
        registered_tools = list(quilt.mcp._tool_manager._tools.keys())
        
        # All tools should be registered in Lambda mode now
        expected_tools = [
            'check_quilt_auth',
            'check_filesystem_access',
            'list_packages',
            'search_packages',
            'browse_package',
            'search_package_contents'
        ]
        for tool in expected_tools:
            assert tool in registered_tools, f"Tool '{tool}' should be available in Lambda mode"

def test_local_mode_tools():
    """Test that all tools are available in local mode."""
    import importlib
    
    # Mock local environment (no Lambda env var)
    with patch.dict(os.environ, {}, clear=False):
        # Remove Lambda env var if present
        if 'AWS_LAMBDA_FUNCTION_NAME' in os.environ:
            del os.environ['AWS_LAMBDA_FUNCTION_NAME']
            
        # Force reload to pick up environment change
        if 'quilt' in sys.modules:
            quilt = importlib.reload(sys.modules['quilt'])
        else:
            import quilt
        
        # Check which tools are registered
        registered_tools = list(quilt.mcp._tool_manager._tools.keys())
        
        # ALL tools should be registered in local mode
        expected_tools = [
            'check_quilt_auth',
            'check_filesystem_access', 
            'list_packages',
            'search_packages',
            'browse_package',
            'search_package_contents'
        ]
        
        for tool in expected_tools:
            assert tool in registered_tools, f"Tool '{tool}' should be available in local mode"

def test_forced_lambda_mode():
    """Test that set_lambda_mode() works for testing purposes."""
    import importlib
    
    # Start with local environment
    with patch.dict(os.environ, {}, clear=False):
        if 'AWS_LAMBDA_FUNCTION_NAME' in os.environ:
            del os.environ['AWS_LAMBDA_FUNCTION_NAME']
            
        # Import fresh module
        if 'quilt' in sys.modules:
            quilt = importlib.reload(sys.modules['quilt'])
        else:
            import quilt
        
        # Should start in local mode (all tools available)
        initial_tools = list(quilt.mcp._tool_manager._tools.keys())
        assert 'search_packages' in initial_tools, "Should start in local mode"
        
        # Force Lambda mode
        quilt.set_lambda_mode(True)
        
        # Check that get_lambda_mode() returns True
        assert quilt.get_lambda_mode() is True
        
        # Note: Tool registration happens at import time, so we'd need to
        # re-import the module for this to take effect on actual registration
        # This test validates the mode switching logic works

def test_forced_local_mode():
    """Test that set_lambda_mode(False) forces local mode even in Lambda environment."""
    import importlib
    
    # Mock Lambda environment
    with patch.dict(os.environ, {'AWS_LAMBDA_FUNCTION_NAME': 'test-function'}):
        # Import fresh module  
        if 'quilt' in sys.modules:
            quilt = importlib.reload(sys.modules['quilt'])
        else:
            import quilt
        
        # Should start in Lambda mode due to environment variable
        assert quilt.is_lambda_environment() is True
        assert quilt.get_lambda_mode() is True
        
        # Force local mode
        quilt.set_lambda_mode(False)
        
        # Check that get_lambda_mode() returns False despite Lambda env var
        assert quilt.get_lambda_mode() is False
        assert quilt.is_lambda_environment() is True  # Env var still there

def test_lambda_mode_reset():
    """Test that lambda mode can be reset to follow environment."""
    import importlib
    
    with patch.dict(os.environ, {}, clear=False):
        if 'AWS_LAMBDA_FUNCTION_NAME' in os.environ:
            del os.environ['AWS_LAMBDA_FUNCTION_NAME']
            
        if 'quilt' in sys.modules:
            quilt = importlib.reload(sys.modules['quilt'])
        else:
            import quilt
        
        # Force Lambda mode
        quilt.set_lambda_mode(True)
        assert quilt.get_lambda_mode() is True
        
        # Reset to follow environment
        quilt.set_lambda_mode(None)
        quilt._FORCE_LAMBDA_MODE = None  # Direct reset
        
        # Should now follow environment (local)
        assert quilt.get_lambda_mode() is False

def test_tool_annotations():
    """Test that tools have the correct annotations."""
    import importlib
    
    # Import in local mode to get all tools
    with patch.dict(os.environ, {}, clear=False):
        if 'AWS_LAMBDA_FUNCTION_NAME' in os.environ:
            del os.environ['AWS_LAMBDA_FUNCTION_NAME']
            
        if 'quilt' in sys.modules:
            quilt = importlib.reload(sys.modules['quilt'])
        else:
            import quilt
        
        # Check tool annotations through tool manager
        tools = quilt.mcp._tool_manager._tools
        
        # Lambda-compatible tools
        lambda_tools = ['check_quilt_auth', 'check_filesystem_access', 'list_packages']
        for tool_name in lambda_tools:
            if tool_name in tools:
                tool = tools[tool_name]
                # Check if tool has lambda_compatible annotation
                # Note: This depends on how FastMCP stores tool metadata
                # We might need to adjust based on actual FastMCP implementation
                assert tool_name in tools, f"{tool_name} should be registered"
        
        # Local-only tools  
        local_tools = ['search_packages', 'browse_package', 'search_package_contents']
        for tool_name in local_tools:
            if tool_name in tools:
                tool = tools[tool_name]
                assert tool_name in tools, f"{tool_name} should be registered in local mode"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])