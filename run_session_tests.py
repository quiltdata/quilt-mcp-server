#!/usr/bin/env python3
"""Script to run session tests during TDD development."""

import subprocess
import sys
import os

def main():
    """Run the session tests."""
    # Set up environment
    env = os.environ.copy()
    env['PYTHONPATH'] = 'src'
    
    # Run the specific test
    cmd = [
        sys.executable, '-m', 'pytest', 
        'tests/utilities/aws/test_session.py', 
        '-v', '--tb=short'
    ]
    
    result = subprocess.run(cmd, env=env, cwd=os.getcwd())
    return result.returncode

if __name__ == '__main__':
    sys.exit(main())