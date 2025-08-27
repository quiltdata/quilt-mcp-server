"""
Test Environment Configuration

Configuration settings and utilities for README automation tests.
Provides centralized configuration management and test data fixtures.
"""

import os
from typing import Dict, Any, List

# Test execution configuration
TEST_CONFIG = {
    "timeouts": {
        "total_test_timeout": 60,  # Total test execution time limit
        "server_startup_timeout": 10,  # Server startup timeout
        "command_timeout": 30,  # Individual command timeout
        "shutdown_timeout": 5   # Server shutdown timeout
    },
    
    "server": {
        "endpoint": "http://127.0.0.1:8000/mcp",
        "host": "127.0.0.1", 
        "port": 8000,
        "startup_check_interval": 0.5,  # Seconds between startup checks
        "max_startup_attempts": 20
    },
    
    "environment": {
        "temp_dir_prefix": "readme_test_",
        "cleanup_on_success": True,
        "cleanup_on_failure": False,  # Keep for debugging
        "preserve_logs": True
    },
    
    "commands": {
        "git_clone_simulation": True,  # Simulate git clone instead of real clone
        "skip_network_commands": False,  # Skip commands requiring network
        "dry_run_mode": False  # Only validate commands without execution
    }
}

# Expected README commands from "Option B: Local Development"
EXPECTED_README_COMMANDS = [
    "git clone https://github.com/quiltdata/quilt-mcp-server.git",
    "cd quilt-mcp-server",
    "cp env.example .env", 
    "uv sync",
    "make app"
]

# MCP protocol test requests
MCP_TEST_REQUESTS = {
    "tools_list": {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    },
    
    "initialize": {
        "jsonrpc": "2.0", 
        "id": 2,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "readme-test", "version": "1.0.0"}
        }
    }
}

# Expected MCP response structure validation
MCP_RESPONSE_SCHEMA = {
    "required_fields": ["jsonrpc", "id"],
    "success_fields": ["result"],
    "error_fields": ["error"],
    "jsonrpc_version": "2.0"
}

# Expected tools that should be available in MCP server
EXPECTED_MCP_TOOLS = [
    "packages_list",
    "bucket_objects_list", 
    "package_browse",
    "bucket_object_info",
    "auth_status"
]

# Environment variable configurations for testing
TEST_ENV_VARS = {
    "PYTHONPATH": None,  # Will be set to app directory
    "QUILT_CATALOG_DOMAIN": "demo.quiltdata.com",
    "QUILT_DEFAULT_BUCKET": "s3://test-bucket",
    "AWS_PROFILE": "default",
    "TEST_MODE": "true",
    "MCP_SERVER_PORT": "8000"
}

# Cross-platform configuration
PLATFORM_CONFIG = {
    "linux": {
        "shell": "/bin/bash",
        "path_separator": "/",
        "executable_extension": ""
    },
    "darwin": {  # macOS
        "shell": "/bin/bash", 
        "path_separator": "/",
        "executable_extension": ""
    },
    "windows": {
        "shell": "cmd.exe",
        "path_separator": "\\",
        "executable_extension": ".exe"
    }
}

def get_test_config() -> Dict[str, Any]:
    """
    Get test configuration with environment variable overrides.
    
    Returns:
        Complete test configuration dictionary
    """
    config = TEST_CONFIG.copy()
    
    # Override with environment variables if present
    if "TEST_TIMEOUT" in os.environ:
        config["timeouts"]["total_test_timeout"] = int(os.environ["TEST_TIMEOUT"])
        
    if "SERVER_STARTUP_TIMEOUT" in os.environ:
        config["timeouts"]["server_startup_timeout"] = int(os.environ["SERVER_STARTUP_TIMEOUT"])
        
    if "TEST_PORT" in os.environ:
        config["server"]["port"] = int(os.environ["TEST_PORT"])
        config["server"]["endpoint"] = f"http://127.0.0.1:{config['server']['port']}/mcp"
    
    return config

def get_platform_config() -> Dict[str, str]:
    """
    Get platform-specific configuration for current OS.
    
    Returns:
        Platform configuration dictionary
    """
    import platform
    system = platform.system().lower()
    return PLATFORM_CONFIG.get(system, PLATFORM_CONFIG["linux"])

def get_expected_commands() -> List[str]:
    """
    Get expected README commands with any platform-specific modifications.
    
    Returns:
        List of expected commands
    """
    return EXPECTED_README_COMMANDS.copy()

def get_mcp_test_request(request_type: str = "tools_list") -> Dict[str, Any]:
    """
    Get MCP test request payload.
    
    Args:
        request_type: Type of request ("tools_list" or "initialize")
        
    Returns:
        MCP request payload dictionary
    """
    return MCP_TEST_REQUESTS.get(request_type, MCP_TEST_REQUESTS["tools_list"])

def validate_mcp_response_structure(response: Dict[str, Any]) -> List[str]:
    """
    Validate MCP response against expected structure.
    
    Args:
        response: MCP response to validate
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    schema = MCP_RESPONSE_SCHEMA
    
    # Check required fields
    for field in schema["required_fields"]:
        if field not in response:
            errors.append(f"Missing required field: {field}")
    
    # Check jsonrpc version
    if response.get("jsonrpc") != schema["jsonrpc_version"]:
        errors.append(f"Invalid jsonrpc version: expected {schema['jsonrpc_version']}")
    
    # Check for result or error
    has_result = any(field in response for field in schema["success_fields"])
    has_error = any(field in response for field in schema["error_fields"])
    
    if not has_result and not has_error:
        errors.append("Response must contain either 'result' or 'error'")
    
    return errors

def get_test_environment_vars() -> Dict[str, str]:
    """
    Get environment variables for test execution.
    
    Returns:
        Dictionary of environment variables
    """
    env_vars = TEST_ENV_VARS.copy()
    
    # Set PYTHONPATH to current app directory
    current_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    app_dir = os.path.join(current_dir, "app")
    env_vars["PYTHONPATH"] = app_dir
    
    return env_vars