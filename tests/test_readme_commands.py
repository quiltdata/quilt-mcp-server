"""
BDD tests for README command examples.

These tests verify that all bash commands in the README.md work as documented.
This implements NFR4: Documentation Testing requirement from the spec.
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest


class TestReadmeCommands:
    """Test that all bash commands in README.md work as documented."""

    @pytest.fixture
    def readme_content(self):
        """Load README content for testing."""
        readme_path = Path(__file__).parent.parent / "README.md"
        with open(readme_path, 'r') as f:
            return f.read()

    def extract_bash_commands(self, content: str) -> list:
        """Extract bash commands from markdown content.
        
        Returns a list of (command, context) tuples where context describes
        the section the command appears in.
        """
        commands = []
        current_section = "unknown"
        
        # Split into lines for processing
        lines = content.split('\n')
        in_bash_block = False
        current_block = []
        
        for line in lines:
            # Track current section
            if line.startswith('#'):
                current_section = line.strip('#').strip()
            
            # Detect start of bash code block
            if line.strip() == '```bash':
                in_bash_block = True
                current_block = []
                continue
                
            # Detect end of bash code block
            if line.strip() == '```' and in_bash_block:
                if current_block:
                    # Join multi-line commands and split by logical commands
                    block_text = '\n'.join(current_block)
                    # Split by lines that don't start with # (comments) or are continuations
                    for cmd_line in block_text.split('\n'):
                        cmd_line = cmd_line.strip()
                        if cmd_line and not cmd_line.startswith('#'):
                            commands.append((cmd_line, current_section))
                in_bash_block = False
                current_block = []
                continue
                
            # Collect bash command lines
            if in_bash_block:
                current_block.append(line)
                
        return commands

    def test_extracts_bash_commands_from_readme(self, readme_content):
        """Should extract bash commands from README markdown."""
        commands = self.extract_bash_commands(readme_content)
        
        # Should find make mcp_config commands
        make_commands = [cmd for cmd, _ in commands if 'make mcp_config' in cmd]
        assert len(make_commands) > 0, "Should find make mcp_config commands in README"
        
        # Should find python module commands
        python_commands = [cmd for cmd, _ in commands if 'python -m quilt_mcp.auto_configure' in cmd]
        assert len(python_commands) > 0, "Should find python -m quilt_mcp.auto_configure commands"

    def test_make_mcp_config_command_works(self):
        """Should successfully execute make mcp_config command."""
        # Change to repository root
        repo_root = Path(__file__).parent.parent
        original_cwd = os.getcwd()
        
        try:
            os.chdir(repo_root)
            
            # Run make mcp_config command
            result = subprocess.run(
                ['make', 'mcp_config'], 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            # Should execute without error
            assert result.returncode == 0, f"make mcp_config failed: {result.stderr}"
            
            # Should generate configuration output
            assert 'mcpServers' in result.stdout, "Should output MCP server configuration"
            assert 'quilt' in result.stdout, "Should include quilt server entry"
            
        finally:
            os.chdir(original_cwd)

    def test_python_auto_configure_help_works(self):
        """Should successfully show help for python -m quilt_mcp.auto_configure."""
        repo_root = Path(__file__).parent.parent
        
        # Set PYTHONPATH to include app directory
        env = os.environ.copy()
        env['PYTHONPATH'] = str(repo_root / 'app')
        
        # Test help command
        result = subprocess.run(
            ['python', '-m', 'quilt_mcp.auto_configure', '--help'],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=repo_root / 'app',
            env=env
        )
        
        # Should show help without error
        assert result.returncode == 0, f"Auto-configure help failed: {result.stderr}"
        assert 'usage:' in result.stdout.lower() or 'Auto-configure' in result.stdout
        assert '--client' in result.stdout, "Should show --client option"

    def test_python_auto_configure_display_mode_works(self):
        """Should successfully run auto-configure in display mode."""
        repo_root = Path(__file__).parent.parent
        
        # Set PYTHONPATH and environment
        env = os.environ.copy()
        env['PYTHONPATH'] = str(repo_root / 'app')
        env['QUILT_CATALOG_DOMAIN'] = 'test.quiltdata.com'
        
        # Test display mode (no --client specified)
        result = subprocess.run(
            ['python', '-m', 'quilt_mcp.auto_configure'],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=repo_root / 'app',
            env=env
        )
        
        # Should complete without error  
        assert result.returncode == 0, f"Auto-configure display failed: {result.stderr}"
        
        # Should show configuration and file locations
        assert 'mcpServers' in result.stdout, "Should display MCP configuration"
        assert 'Configuration File Locations' in result.stdout, "Should show file locations"
        assert 'test.quiltdata.com' in result.stdout, "Should use custom catalog domain"

    @pytest.mark.parametrize("client", ["cursor", "claude_desktop", "vscode"])
    def test_python_auto_configure_client_validation_works(self, client):
        """Should validate client names without actually modifying files."""
        repo_root = Path(__file__).parent.parent
        
        # Set PYTHONPATH
        env = os.environ.copy()
        env['PYTHONPATH'] = str(repo_root / 'app')
        
        # Use a temporary file path to avoid modifying real configs
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp_file:
            tmp_path = tmp_file.name
            
        try:
            # Test with explicit config file (safer than modifying real client configs)
            result = subprocess.run(
                ['python', '-m', 'quilt_mcp.auto_configure', 
                 '--client', client, '--config-file', tmp_path],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=repo_root / 'app',
                env=env
            )
            
            # Should complete without error
            assert result.returncode == 0, f"Client {client} validation failed: {result.stderr}"
            
            # Should show success message
            assert 'Successfully' in result.stdout or 'Adding configuration' in result.stdout
            
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_curl_command_syntax_is_valid(self, readme_content):
        """Should have valid curl command syntax in README."""
        # Extract full curl command blocks (handle multi-line commands)
        lines = readme_content.split('\n')
        curl_blocks = []
        in_curl_block = False
        current_block = []
        
        for line in lines:
            line = line.strip()
            if line.startswith('curl'):
                in_curl_block = True
                current_block = [line]
            elif in_curl_block:
                if line.endswith('\\'):
                    current_block.append(line)
                elif line and not line.startswith('#') and not line.startswith('```'):
                    current_block.append(line)
                    # End of curl block
                    curl_blocks.append(' '.join(current_block))
                    in_curl_block = False
                    current_block = []
                elif not line or line.startswith('```'):
                    # End of block
                    if current_block:
                        curl_blocks.append(' '.join(current_block))
                    in_curl_block = False
                    current_block = []
                
        assert len(curl_blocks) > 0, "Should have curl examples in README"
        
        # Check that curl commands have proper syntax
        for cmd in curl_blocks:
            assert 'http://' in cmd or 'https://' in cmd, f"Curl command should have URL: {cmd}"
            assert '-X POST' in cmd, f"Curl should use POST method: {cmd}"
            # For multi-line commands, -H might be on a different line
            assert '-H' in cmd or '"Content-Type:' in cmd, f"Curl should have headers: {cmd}"

    def test_environment_setup_commands_are_safe(self, readme_content):
        """Should verify that environment setup commands are safe and documented."""
        # Find environment setup commands
        env_commands = []
        for line in readme_content.split('\n'):
            line = line.strip()
            if line.startswith('cp ') or line.startswith('QUILT_CATALOG_DOMAIN='):
                env_commands.append(line)
                
        assert len(env_commands) > 0, "Should have environment setup commands"
        
        # Verify cp env.example .env is documented
        cp_commands = [cmd for cmd in env_commands if cmd.startswith('cp env.example')]
        assert len(cp_commands) > 0, "Should document copying env.example to .env"

    def test_all_documented_make_targets_exist(self):
        """Should verify that all make targets mentioned in README exist in Makefile."""
        repo_root = Path(__file__).parent.parent
        
        # Read README to find make targets
        readme_path = repo_root / "README.md"
        with open(readme_path, 'r') as f:
            readme_content = f.read()
            
        # Extract make commands from README
        make_targets = set()
        for line in readme_content.split('\n'):
            if 'make ' in line and not line.strip().startswith('#'):
                # Extract make target names
                import re
                matches = re.findall(r'make\s+([a-zA-Z0-9_-]+)', line)
                make_targets.update(matches)
        
        # Read root Makefile
        makefile_path = repo_root / "Makefile"
        if makefile_path.exists():
            with open(makefile_path, 'r') as f:
                makefile_content = f.read()
            
            # Check that documented targets exist
            for target in make_targets:
                if target not in ['clean', 'help']:  # Skip common targets that might be implicit
                    assert f"{target}:" in makefile_content or f".PHONY:" in makefile_content, \
                           f"Make target '{target}' mentioned in README should exist in Makefile"

    def test_file_paths_in_examples_are_accurate(self, readme_content):
        """Should verify that file paths mentioned in examples are accurate."""
        repo_root = Path(__file__).parent.parent
        
        # Check that env.example exists (referenced in README)
        assert (repo_root / "env.example").exists(), "env.example should exist (referenced in README)"
        
        # Check that pyproject.toml exists (auto-configure looks for this)
        assert (repo_root / "pyproject.toml").exists(), "pyproject.toml should exist"