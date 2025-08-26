"""
Client Configuration Compatibility Tests (IT3)

These tests validate that generated configurations work with actual MCP clients
by testing configuration loading, format validation, and environment handling.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

from quilt_mcp.auto_configure import (
    generate_config_entry,
    get_config_file_locations,
    add_to_config_file,
)


class TestClientConfigurationCompatibility:
    """Test that generated configs are compatible with actual MCP clients (IT3)."""

    def test_claude_desktop_config_format_validation(self):
        """Should generate configuration compatible with Claude Desktop JSON schema."""
        config = generate_config_entry(development_mode=True, catalog_domain="test.example.com")
        
        # Claude Desktop requires specific structure
        assert "quilt" in config
        server_config = config["quilt"]
        
        # Required fields for Claude Desktop
        assert "command" in server_config
        assert "args" in server_config  
        assert isinstance(server_config["args"], list)
        
        # Environment variables should be properly structured
        assert "env" in server_config
        assert isinstance(server_config["env"], dict)
        assert "QUILT_CATALOG_DOMAIN" in server_config["env"]
        
        # Development mode should include cwd
        assert "cwd" in server_config
        assert isinstance(server_config["cwd"], str)
        
        # Optional but recommended fields
        if "description" in server_config:
            assert isinstance(server_config["description"], str)

    def test_cursor_vscode_config_format_validation(self):
        """Should generate configuration compatible with Cursor/VS Code MCP extensions."""
        config = generate_config_entry(development_mode=False, catalog_domain="prod.example.com")
        
        # VS Code/Cursor MCP extensions expect similar structure
        server_config = config["quilt"]
        
        # Must have command and args
        assert server_config["command"] == "uvx"
        assert server_config["args"] == ["quilt-mcp"]
        
        # Environment should be properly formatted
        assert server_config["env"]["QUILT_CATALOG_DOMAIN"] == "prod.example.com"
        
        # Production mode should NOT include cwd
        assert "cwd" not in server_config or server_config["cwd"] is None

    def test_full_mcpservers_structure_compatibility(self):
        """Should generate config that fits properly within mcpServers structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "mcp_config.json"
            
            # Add config using our function
            config = generate_config_entry(development_mode=True)
            result = add_to_config_file(str(config_file), config)
            
            assert result is True
            
            # Load and verify full structure
            with open(config_file, 'r') as f:
                full_config = json.load(f)
            
            # Should have proper top-level structure
            assert "mcpServers" in full_config
            assert "quilt" in full_config["mcpServers"]
            
            # Should be valid JSON (no syntax errors)
            json.dumps(full_config)  # Should not raise exception
            
            # Should match expected MCP client format
            quilt_server = full_config["mcpServers"]["quilt"]
            assert all(key in quilt_server for key in ["command", "args", "env"])

    def test_environment_variable_handling_compatibility(self):
        """Should handle environment variables in a way compatible with MCP clients."""
        # Test various catalog domains
        test_domains = [
            "demo.quiltdata.com",
            "custom-catalog.company.com", 
            "localhost:8080",
            "catalog.dev.quiltdata.io"
        ]
        
        for domain in test_domains:
            config = generate_config_entry(catalog_domain=domain, development_mode=True)
            server_config = config["quilt"]
            
            # Environment should be a dict
            assert isinstance(server_config["env"], dict)
            
            # Should contain catalog domain
            assert server_config["env"]["QUILT_CATALOG_DOMAIN"] == domain
            
            # Environment values should be strings
            for key, value in server_config["env"].items():
                assert isinstance(key, str)
                assert isinstance(value, str)

    def test_command_path_compatibility(self):
        """Should generate command paths compatible with different execution environments."""
        # Test development mode (uv run)
        dev_config = generate_config_entry(development_mode=True)
        assert dev_config["quilt"]["command"] == "uv"
        assert dev_config["quilt"]["args"] == ["run", "quilt-mcp"]
        
        # Test production mode (uvx)
        prod_config = generate_config_entry(development_mode=False)
        assert prod_config["quilt"]["command"] == "uvx"
        assert prod_config["quilt"]["args"] == ["quilt-mcp"]
        
        # Commands should be simple strings (not paths with spaces that need quoting)
        assert " " not in dev_config["quilt"]["command"]
        assert " " not in prod_config["quilt"]["command"]

    def test_cross_platform_config_file_paths(self):
        """Should generate appropriate config file paths for different platforms."""
        with patch('platform.system') as mock_system:
            # Test macOS
            mock_system.return_value = 'Darwin'
            macos_locations = get_config_file_locations()
            
            assert 'claude_desktop' in macos_locations
            assert 'Library/Application Support' in macos_locations['claude_desktop']
            assert macos_locations['claude_desktop'].endswith('.json')
            
            # Test Windows
            mock_system.return_value = 'Windows'
            windows_locations = get_config_file_locations()
            
            assert 'claude_desktop' in windows_locations
            assert 'AppData' in windows_locations['claude_desktop']
            
            # Test Linux
            mock_system.return_value = 'Linux'
            linux_locations = get_config_file_locations()
            
            assert 'claude_desktop' in linux_locations
            assert '.config' in linux_locations['claude_desktop']
            
            # All should use forward slashes in paths (Path handles conversion)
            for locations in [macos_locations, windows_locations, linux_locations]:
                for path in locations.values():
                    assert isinstance(path, str)
                    # Should be absolute paths from home directory
                    assert path.startswith(('/Users/', '/home/', 'C:')) or '~' in path or path.startswith('/')

    def test_json_serialization_compatibility(self):
        """Should generate configs that serialize/deserialize properly across Python versions."""
        config = generate_config_entry(
            development_mode=True,
            catalog_domain="test.quiltdata.com"
        )
        
        # Test JSON round-trip
        json_str = json.dumps(config)
        parsed_config = json.loads(json_str)
        
        assert parsed_config == config
        
        # Test with different JSON options
        compact_json = json.dumps(config, separators=(',', ':'))
        pretty_json = json.dumps(config, indent=2)
        
        assert json.loads(compact_json) == config
        assert json.loads(pretty_json) == config

    def test_config_merging_with_existing_servers(self):
        """Should properly merge with existing MCP server configurations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "existing_servers.json"
            
            # Create existing configuration with other MCP servers
            existing_config = {
                "mcpServers": {
                    "filesystem": {
                        "command": "npx",
                        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/files"],
                        "description": "Filesystem MCP Server"
                    },
                    "sqlite": {
                        "command": "uvx",
                        "args": ["mcp-server-sqlite"],
                        "env": {
                            "DATABASE_URL": "sqlite:///test.db"
                        }
                    }
                }
            }
            
            with open(config_file, 'w') as f:
                json.dump(existing_config, f, indent=2)
            
            # Add Quilt MCP server
            quilt_config = generate_config_entry(development_mode=True)
            result = add_to_config_file(str(config_file), quilt_config)
            
            assert result is True
            
            # Verify all servers preserved and properly structured
            with open(config_file, 'r') as f:
                merged_config = json.load(f)
            
            # Should have all three servers
            servers = merged_config["mcpServers"]
            assert len(servers) == 3
            assert "filesystem" in servers
            assert "sqlite" in servers  
            assert "quilt" in servers
            
            # Each server should have proper structure
            for server_name, server_config in servers.items():
                assert "command" in server_config
                assert "args" in server_config
                assert isinstance(server_config["args"], list)
                
                # Environment is optional but should be dict if present
                if "env" in server_config:
                    assert isinstance(server_config["env"], dict)

    def test_configuration_validation_against_common_mcp_patterns(self):
        """Should validate against common MCP server configuration patterns."""
        config = generate_config_entry(development_mode=True)
        server_config = config["quilt"]
        
        # Common MCP server patterns validation
        
        # 1. Command should not be a full path (for portability)
        command = server_config["command"]
        assert not command.startswith('/')
        assert not command.startswith('C:')
        
        # 2. Args should be list of strings
        args = server_config["args"]
        assert isinstance(args, list)
        assert all(isinstance(arg, str) for arg in args)
        
        # 3. Environment variables should be strings
        env = server_config["env"]
        assert all(isinstance(k, str) and isinstance(v, str) for k, v in env.items())
        
        # 4. Working directory should be absolute path when specified
        if "cwd" in server_config:
            cwd = server_config["cwd"]
            assert os.path.isabs(cwd) or cwd.startswith('~')
        
        # 5. Description should be human-readable string
        if "description" in server_config:
            desc = server_config["description"]
            assert isinstance(desc, str)
            assert len(desc) > 0

    def test_simulated_client_config_loading(self):
        """Should simulate how MCP clients would load and validate the configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "client_test.json"
            
            # Generate configuration
            config = generate_config_entry(
                development_mode=True,
                catalog_domain="integration.test.com"
            )
            
            result = add_to_config_file(str(config_file), config)
            assert result is True
            
            # Simulate client loading process
            try:
                # 1. Client reads JSON file
                with open(config_file, 'r') as f:
                    client_config = json.load(f)
                
                # 2. Client extracts mcpServers
                assert "mcpServers" in client_config
                mcp_servers = client_config["mcpServers"]
                
                # 3. Client processes each server
                for server_name, server_config in mcp_servers.items():
                    # Validate required fields exist
                    assert "command" in server_config
                    assert "args" in server_config
                    
                    # Simulate command construction
                    command_parts = [server_config["command"]] + server_config["args"]
                    assert all(isinstance(part, str) for part in command_parts)
                    
                    # Simulate environment setup
                    if "env" in server_config:
                        for env_key, env_value in server_config["env"].items():
                            # Client would set these in process environment
                            assert isinstance(env_key, str)
                            assert isinstance(env_value, str)
                    
                    # Simulate working directory setup
                    if "cwd" in server_config:
                        cwd = server_config["cwd"]
                        # Client would validate directory exists or use default
                        assert isinstance(cwd, str)
                
            except (json.JSONDecodeError, KeyError, TypeError, AssertionError) as e:
                pytest.fail(f"Configuration would fail client loading: {e}")

    def test_command_execution_compatibility(self):
        """Should generate commands that are executable in typical environments."""
        # Test development mode command
        dev_config = generate_config_entry(development_mode=True)
        dev_command = dev_config["quilt"]["command"]
        dev_args = dev_config["quilt"]["args"]
        
        # uv should be available for development
        try:
            result = subprocess.run(
                [dev_command, "--help"], 
                capture_output=True, 
                timeout=10
            )
            # If uv is installed, --help should work
            assert result.returncode == 0 or result.returncode == 1  # Some tools return 1 for help
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # uv might not be installed in test environment - that's OK
            pass
        
        # Test production mode command structure
        prod_config = generate_config_entry(development_mode=False)
        prod_command = prod_config["quilt"]["command"]
        prod_args = prod_config["quilt"]["args"]
        
        # Commands should be properly structured
        assert prod_command == "uvx"
        assert prod_args == ["quilt-mcp"]
        
        # Command should be simple executable name
        assert not " " in prod_command  # No spaces requiring shell quoting
        assert not prod_command.endswith(".exe")  # No platform-specific extensions