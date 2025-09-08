#!/usr/bin/env python3
"""Test that the session utilities can be imported."""

import sys
import os

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from quilt_mcp.utilities.aws.session import create_session, get_session_credentials, validate_session
    print("✅ Session utilities imported successfully")
    
    # Test that the functions exist and have docstrings
    print(f"create_session: {create_session.__doc__[:50]}...")
    print(f"get_session_credentials: {get_session_credentials.__doc__[:50]}...")
    print(f"validate_session: {validate_session.__doc__[:50]}...")
    
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    sys.exit(1)