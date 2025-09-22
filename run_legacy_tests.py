#!/usr/bin/env python3
"""
Run legacy search function tests to establish baseline behavior.
"""

import subprocess
import sys
import os

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def run_tests():
    """Run the legacy search function tests."""
    print("Running legacy search function tests...")

    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest",
            "tests/unit/test_legacy_search_functions.py",
            "-v", "--tb=short"
        ], cwd=os.path.dirname(__file__), capture_output=True, text=True)

        print("STDOUT:")
        print(result.stdout)
        print("\nSTDERR:")
        print(result.stderr)
        print(f"\nReturn code: {result.returncode}")

        return result.returncode == 0

    except Exception as e:
        print(f"Error running tests: {e}")
        return False

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)