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

# Removed unused README test framework imports


def pytest_configure(config):
    """Configure pytest and set up AWS session if needed."""
    # Configure boto3 default session to use AWS_PROFILE if set
    # This must be done very early before any imports that create boto3 clients
    if os.getenv("AWS_PROFILE"):
        boto3.setup_default_session(profile_name=os.getenv("AWS_PROFILE"))

    # Add custom markers
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow: mark test as slow-running test")
