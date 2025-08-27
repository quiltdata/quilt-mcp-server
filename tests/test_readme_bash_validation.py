#!/usr/bin/env python3
"""
README Bash Validation Tests

Tests the ACTUAL bash code blocks in README.md to ensure:
1. All bash code has valid syntax
2. Referenced files exist in the repository  
3. Installation commands are present and correct

This follows the core insight: test the actual README content, 
not separate duplicated logic.
"""

import re
import subprocess
import tempfile
import os
from pathlib import Path


def extract_bash_blocks(readme_path):
    """Extract bash code blocks from README.md."""
    content = Path(readme_path).read_text()
    blocks = []
    lines = content.split('\n')
    
    in_bash_block = False
    current_block = []
    
    for line in lines:
        if line.strip() == '```bash':
            in_bash_block = True
            current_block = []
        elif line.strip() == '```' and in_bash_block:
            if current_block:
                blocks.append('\n'.join(current_block))
            in_bash_block = False
        elif in_bash_block:
            current_block.append(line)
    
    return blocks


def validate_bash_syntax(bash_code):
    """Test bash syntax using 'bash -n' (parse without execute)."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
        f.write(bash_code)
        script_path = f.name
    
    try:
        result = subprocess.run(['bash', '-n', script_path], capture_output=True, text=True)
        return result.returncode == 0, result.stderr
    finally:
        os.unlink(script_path)


def test_readme_bash_syntax():
    """Test all bash blocks have valid syntax."""
    readme_path = Path(__file__).parent.parent / "README.md"
    bash_blocks = extract_bash_blocks(readme_path)
    
    assert len(bash_blocks) > 0, "No bash blocks found in README"
    
    for i, bash_code in enumerate(bash_blocks, 1):
        is_valid, error = validate_bash_syntax(bash_code)
        assert is_valid, f"Bash syntax error in block {i}: {error}"


def test_readme_file_references():
    """Test referenced files exist in repository."""
    readme_path = Path(__file__).parent.parent / "README.md"
    project_root = readme_path.parent
    bash_blocks = extract_bash_blocks(readme_path)
    
    for bash_code in bash_blocks:
        # Check for critical file references
        if "env.example" in bash_code:
            env_file = project_root / "env.example"
            assert env_file.exists(), "env.example referenced in README but doesn't exist"
        
        if "shared/test-endpoint.sh" in bash_code:
            script_file = project_root / "shared" / "test-endpoint.sh"
            assert script_file.exists(), "shared/test-endpoint.sh referenced but doesn't exist"
            assert os.access(script_file, os.X_OK), "shared/test-endpoint.sh is not executable"


def test_installation_commands():
    """Test Option B contains expected installation commands."""
    readme_path = Path(__file__).parent.parent / "README.md"
    content = readme_path.read_text()
    
    # Extract Option B section
    option_b_match = re.search(
        r'#### Option B: Local Development.*?```bash\n(.*?)\n```',
        content, 
        re.DOTALL
    )
    
    assert option_b_match, "Option B bash block not found in README"
    
    option_b_code = option_b_match.group(1)
    
    # Check for required installation commands
    required_commands = [
        "git clone",
        "cd quilt-mcp-server", 
        "cp env.example .env",
        "uv sync",
        "make app"
    ]
    
    for cmd in required_commands:
        assert cmd in option_b_code, f"Required command '{cmd}' missing from Option B"


if __name__ == "__main__":
    # Allow running as standalone script
    test_readme_bash_syntax()
    test_readme_file_references() 
    test_installation_commands()
    print("✅ All README bash validation tests passed!")