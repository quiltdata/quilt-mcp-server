"""UV Package Publishing functionality.

This module provides functions for building and publishing Python packages
using UV to TestPyPI and PyPI, with environment validation and CI/CD integration.
"""

import os
import subprocess
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any


@dataclass
class ValidationResult:
    """Result of environment validation."""
    is_valid: bool
    missing_variables: List[str]
    error_message: str = ""
    success_message: str = ""


@dataclass
class PublishResult:
    """Result of package publishing operation."""
    success: bool
    output: str
    error: str = ""


def validate_testpypi_environment(env_vars: Dict[str, str]) -> ValidationResult:
    """Validate TestPyPI publishing environment variables.
    
    Args:
        env_vars: Dictionary of environment variables to validate
        
    Returns:
        ValidationResult with validation status and messages
    """
    missing_variables = []
    
    # Check required TestPyPI token
    if not env_vars.get("TESTPYPI_TOKEN"):
        missing_variables.append("TESTPYPI_TOKEN")
    
    if missing_variables:
        return ValidationResult(
            is_valid=False,
            missing_variables=missing_variables,
            error_message="TestPyPI credentials not configured"
        )
    
    return ValidationResult(
        is_valid=True,
        missing_variables=[],
        success_message="TestPyPI configuration valid"
    )


def build_package() -> PublishResult:
    """Build the package using UV.
    
    Returns:
        PublishResult with build status and output
    """
    try:
        result = subprocess.run(
            ["uv", "build"],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        return PublishResult(
            success=result.returncode == 0,
            output=result.stdout,
            error=result.stderr if result.returncode != 0 else ""
        )
    except subprocess.TimeoutExpired:
        return PublishResult(
            success=False,
            output="",
            error="UV build timed out after 120 seconds"
        )
    except FileNotFoundError:
        return PublishResult(
            success=False,
            output="",
            error="UV command not found. Please install UV first."
        )


def publish_to_testpypi(config: Dict[str, str]) -> PublishResult:
    """Publish package to TestPyPI using UV.
    
    Args:
        config: Configuration dictionary with TESTPYPI_TOKEN and optional UV_PUBLISH_URL
        
    Returns:
        PublishResult with publish status and output
    """
    env = os.environ.copy()
    env.update({
        "UV_PUBLISH_TOKEN": config["TESTPYPI_TOKEN"],
        "UV_PUBLISH_URL": config.get("UV_PUBLISH_URL", "https://test.pypi.org/legacy/")
    })
    
    try:
        result = subprocess.run(
            ["uv", "publish"],
            capture_output=True,
            text=True,
            env=env,
            timeout=180
        )
        
        return PublishResult(
            success=result.returncode == 0,
            output=result.stdout,
            error=result.stderr if result.returncode != 0 else ""
        )
    except subprocess.TimeoutExpired:
        return PublishResult(
            success=False,
            output="",
            error="UV publish timed out after 180 seconds"
        )
    except FileNotFoundError:
        return PublishResult(
            success=False,
            output="",
            error="UV command not found. Please install UV first."
        )


def generate_test_version() -> str:
    """Generate a unique test version for TestPyPI publishing.
    
    Returns:
        Test version string in format: 0.4.1-test-{timestamp_ns}
    """
    # Use nanosecond precision for uniqueness
    timestamp_ns = time.time_ns()
    return f"0.4.1-test-{timestamp_ns}"