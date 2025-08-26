"""UV Publishing Module for TestPyPI and PyPI package publishing.

This module provides environment validation and publishing utilities
for the Quilt MCP server package using UV commands.
"""

import os
import subprocess
from typing import Dict, List, Optional, Tuple


class PublishingError(Exception):
    """Raised when publishing operations fail."""
    pass


class EnvironmentValidationError(Exception):
    """Raised when environment validation fails."""
    pass


def validate_testpypi_environment() -> Tuple[bool, List[str]]:
    """
    Validate TestPyPI publishing environment variables.
    
    Returns:
        Tuple of (is_valid, missing_variables)
        
    Raises:
        EnvironmentValidationError: If validation fails with details
    """
    required_vars = [
        'TESTPYPI_TOKEN'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    is_valid = len(missing_vars) == 0
    
    if not is_valid:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        raise EnvironmentValidationError(error_msg)
    
    return is_valid, missing_vars


def validate_uv_availability() -> bool:
    """
    Check if UV command is available in the system.
    
    Returns:
        True if UV is available, False otherwise
    """
    try:
        result = subprocess.run(
            ['uv', '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def build_package(directory: str = ".") -> Tuple[bool, str]:
    """
    Build package using UV build command.
    
    Args:
        directory: Directory to build from (default: current directory)
        
    Returns:
        Tuple of (success, output_message)
        
    Raises:
        PublishingError: If build fails
    """
    try:
        result = subprocess.run(
            ['uv', 'build'],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes max for build
        )
        
        if result.returncode == 0:
            return True, result.stdout
        else:
            error_msg = f"Build failed: {result.stderr}"
            raise PublishingError(error_msg)
            
    except subprocess.TimeoutExpired:
        raise PublishingError("Build timed out after 5 minutes")
    except Exception as e:
        raise PublishingError(f"Build failed: {str(e)}")


def publish_to_testpypi(directory: str = ".") -> Tuple[bool, str]:
    """
    Publish package to TestPyPI using UV publish command.
    
    Args:
        directory: Directory containing built packages
        
    Returns:
        Tuple of (success, output_message)
        
    Raises:
        PublishingError: If publishing fails
        EnvironmentValidationError: If environment is not configured
    """
    # Validate environment first
    validate_testpypi_environment()
    
    # Set up environment variables for UV publish
    env = os.environ.copy()
    env['UV_PUBLISH_URL'] = 'https://test.pypi.org/legacy/'
    env['UV_PUBLISH_TOKEN'] = os.getenv('TESTPYPI_TOKEN')
    
    try:
        result = subprocess.run(
            ['uv', 'publish'],
            cwd=directory,
            env=env,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes max for publish
        )
        
        if result.returncode == 0:
            return True, result.stdout
        else:
            error_msg = f"Publishing failed: {result.stderr}"
            raise PublishingError(error_msg)
            
    except subprocess.TimeoutExpired:
        raise PublishingError("Publishing timed out after 5 minutes")
    except Exception as e:
        raise PublishingError(f"Publishing failed: {str(e)}")


def generate_test_version() -> str:
    """
    Generate a unique test version string for TestPyPI publishing.
    
    Returns:
        Version string in format "0.4.1-test-{timestamp}"
    """
    import time
    timestamp = int(time.time())
    return f"0.4.1-test-{timestamp}"


def get_publishing_environment_status() -> Dict[str, any]:
    """
    Get comprehensive status of publishing environment.
    
    Returns:
        Dictionary with environment status information
    """
    status = {
        'uv_available': validate_uv_availability(),
        'testpypi_configured': False,
        'missing_variables': [],
        'errors': []
    }
    
    try:
        is_valid, missing_vars = validate_testpypi_environment()
        status['testpypi_configured'] = is_valid
        status['missing_variables'] = missing_vars
    except EnvironmentValidationError as e:
        status['errors'].append(str(e))
        status['missing_variables'] = ['TESTPYPI_TOKEN']
    
    return status