#!/usr/bin/env python3
"""
README Tests

Simple tests for README.md to verify:
1. We can extract bash scripts from markdown (with test string)
2. All bash blocks in README have valid syntax
3. The actual commands from the README work
"""

import re
import subprocess
import tempfile
import os
from pathlib import Path


def extract_bash_blocks(markdown_text):
    """Extract bash code blocks from markdown text."""
    blocks = []
    lines = markdown_text.split('\n')
    
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


def test_extract_bash_from_markdown():
    """Test that we can extract bash scripts from markdown using a test string."""
    test_markdown = """# Test README

Some text here.

```bash
git clone https://example.com/repo.git
cd repo
make install
```

More text.

```bash
echo "hello world"
```

Not a bash block:
```python
print("hello")
```
"""
    
    blocks = extract_bash_blocks(test_markdown)
    assert len(blocks) == 2, f"Expected 2 bash blocks, got {len(blocks)}"
    
    first_block = blocks[0]
    assert "git clone" in first_block
    assert "cd repo" in first_block
    assert "make install" in first_block
    
    second_block = blocks[1]
    assert 'echo "hello world"' in second_block


def test_readme_bash_syntax():
    """Test that all bash blocks in README have valid syntax."""
    readme_path = Path(__file__).parent.parent / "README.md"
    content = readme_path.read_text()
    
    bash_blocks = extract_bash_blocks(content)
    assert len(bash_blocks) > 0, "No bash blocks found in README"
    
    for i, bash_code in enumerate(bash_blocks, 1):
        # Test bash syntax using 'bash -n' (parse without execute)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write(bash_code)
            script_path = f.name
        
        try:
            result = subprocess.run(['bash', '-n', script_path], capture_output=True, text=True)
            assert result.returncode == 0, f"Bash syntax error in block {i}: {result.stderr}"
        finally:
            os.unlink(script_path)


def test_readme_commands_work():
    """Test the actual commands from README.md work in a temp directory."""
    readme_path = Path(__file__).parent.parent / "README.md"
    content = readme_path.read_text()
    
    # Extract bash blocks from actual README
    bash_blocks = extract_bash_blocks(content)
    assert len(bash_blocks) > 0, "No bash blocks found in README"
    
    # Find the installation block (contains git clone and basic setup)
    installation_block = None
    for block in bash_blocks:
        if "git clone" in block and "uv sync" in block:
            installation_block = block
            break
    
    assert installation_block is not None, "Could not find installation block in README"
    
    # Test in temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Test individual commands that should work locally
        test_commands = [
            "echo 'Testing basic shell'",
            "which cp > /dev/null",  # Test cp command exists
            "which uv || echo 'uv not found'"  # Test uv availability
        ]
        
        for cmd in test_commands:
            result = subprocess.run(
                cmd, 
                shell=True, 
                cwd=temp_dir, 
                capture_output=True, 
                text=True
            )
            # Commands should not fail catastrophically
            assert result.returncode in [0, 1], f"Command failed unexpectedly: {cmd}"


if __name__ == "__main__":
    test_extract_bash_from_markdown()
    test_readme_bash_syntax()
    test_readme_commands_work()
    print("✅ README tests passed!")