"""Test configuration for pytest."""

import sys
import os
import boto3
import pytest
import tempfile
from pathlib import Path
from typing import Dict, Any

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Load from .env file in the project root
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"Loaded environment from {env_path}")
except ImportError:
    # python-dotenv not available, try manual loading
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key, value)
        print(f"Manually loaded environment from {env_path}")

# Add the app directory to Python path so quilt_mcp module can be imported
app_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app')
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

# Import the README test framework components once implemented
try:
    from readme_test_framework import (
        TestEnvironmentManager,
        ReadmeCommandExtractor,
        CommandExecutor,
        ServerVerifier
    )
    FRAMEWORK_AVAILABLE = True
except ImportError:
    # Framework not yet implemented - tests will fail until implementation
    FRAMEWORK_AVAILABLE = False


def pytest_configure(config):
    """Configure pytest and set up AWS session if needed."""
    # Configure boto3 default session to use AWS_PROFILE if set
    # This must be done very early before any imports that create boto3 clients
    if os.getenv("AWS_PROFILE"):
        boto3.setup_default_session(profile_name=os.getenv("AWS_PROFILE"))
    
    # Add custom markers for README tests
    config.addinivalue_line(
        "markers", 
        "readme_test: mark test as README automation test"
    )
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test"  
    )
    config.addinivalue_line(
        "markers", 
        "slow: mark test as slow-running test"
    )


# README Test Fixtures

@pytest.fixture(scope="session")
def readme_test_config():
    """
    Provide test configuration for README automation tests.
    
    Returns:
        Dictionary containing test configuration settings
    """
    return {
        "timeouts": {
            "total_test_timeout": int(os.environ.get("TEST_TIMEOUT", "60")),
            "server_startup_timeout": int(os.environ.get("SERVER_STARTUP_TIMEOUT", "10")),
            "command_timeout": 30,
            "shutdown_timeout": 5
        },
        "server": {
            "endpoint": f"http://127.0.0.1:{os.environ.get('TEST_PORT', '8000')}/mcp",
            "host": "127.0.0.1",
            "port": int(os.environ.get("TEST_PORT", "8000"))
        },
        "environment": {
            "cleanup_on_success": True,
            "cleanup_on_failure": bool(os.environ.get("PRESERVE_TEST_ENV", False)),
            "preserve_logs": True
        }
    }


@pytest.fixture
def temp_test_environment(readme_test_config):
    """
    Provide isolated temporary environment for README tests.
    
    This fixture creates a clean temporary directory, sets up the test
    environment, and ensures proper cleanup after test completion.
    """
    if not FRAMEWORK_AVAILABLE:
        # Use basic tempfile for compatibility when framework not implemented
        with tempfile.TemporaryDirectory(prefix="readme_test_") as temp_dir:
            yield Path(temp_dir)
        return
    
    # Use full framework when available
    env_manager = TestEnvironmentManager()
    temp_dir = None
    
    try:
        temp_dir = env_manager.create_temp_environment()
        env_manager.setup_repository_copy()
        yield temp_dir
    except Exception as e:
        # Test will fail gracefully - this is expected until implementation
        pytest.skip(f"Test environment setup failed: {e}")
    finally:
        if temp_dir and env_manager:
            env_manager.cleanup_environment()


@pytest.fixture  
def readme_extractor():
    """
    Provide README command extractor for parsing tests.
    
    Returns:
        ReadmeCommandExtractor instance pointing to project README.md
    """
    if not FRAMEWORK_AVAILABLE:
        pytest.skip("README test framework not yet implemented")
    
    readme_path = Path(__file__).parent.parent / "README.md"
    return ReadmeCommandExtractor(str(readme_path))


@pytest.fixture
def command_executor(temp_test_environment):
    """
    Provide command executor for running bash commands in test environment.
    
    Args:
        temp_test_environment: Temporary test directory from fixture
        
    Returns:
        CommandExecutor instance configured for test environment
    """
    if not FRAMEWORK_AVAILABLE:
        pytest.skip("README test framework not yet implemented")
        
    return CommandExecutor(str(temp_test_environment))


@pytest.fixture
def server_verifier(readme_test_config):
    """
    Provide server verifier for MCP protocol testing.
    
    Args:
        readme_test_config: Test configuration from fixture
        
    Returns:
        ServerVerifier instance with automatic cleanup
    """
    if not FRAMEWORK_AVAILABLE:
        pytest.skip("README test framework not yet implemented")
    
    verifier = ServerVerifier(readme_test_config["server"]["endpoint"])
    
    yield verifier
    
    # Ensure server is properly shutdown after test
    try:
        verifier.shutdown_server()
    except:
        # Ignore cleanup errors - server may not be running
        pass


@pytest.fixture(scope="session", autouse=True)
def setup_readme_test_environment():
    """
    Set up global test environment for README automation tests.
    
    This fixture runs once per test session and sets up environment
    variables and other global configuration needed for README tests.
    """
    # Set environment variables for test execution
    test_env_vars = {
        "TEST_MODE": "true",
        "QUILT_DISABLE_QUILT3_SESSION": "1"
    }
    
    # Backup original environment variables
    original_env = {}
    for key, value in test_env_vars.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value
    
    yield
    
    # Restore original environment variables
    for key, original_value in original_env.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value