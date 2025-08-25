"""
BDD tests for auto-configuration functionality.

These tests describe the expected behavior of the auto-configuration script
that generates MCP server configuration entries for different editors.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open
import pytest

from app.quilt_mcp.auto_configure import (
    generate_config_entry,
    get_config_file_locations,
    add_to_config_file,
    auto_configure_main,
)


class TestGenerateConfigEntry:
    """Test configuration entry generation behavior."""

    def test_generates_basic_config_entry_with_uvx_command(self):
        """Should generate a basic configuration entry using uvx command."""
        config = generate_config_entry()
        
        assert config["quilt"]["command"] == "uvx"
        assert config["quilt"]["args"] == ["quilt-mcp"]
        assert "env" in config["quilt"]
        assert "description" in config["quilt"]

    def test_includes_current_working_directory_in_config(self):
        """Should include the current working directory in the configuration."""
        with patch('os.getcwd', return_value='/Users/test/quilt-mcp-server'):
            config = generate_config_entry()
            
            assert config["quilt"]["env"]["QUILT_CATALOG_DOMAIN"] == "demo.quiltdata.com"
            # Working directory should be included in config context

    def test_allows_custom_catalog_domain(self):
        """Should allow customization of catalog domain."""
        config = generate_config_entry(catalog_domain="custom.quiltdata.com")
        
        assert config["quilt"]["env"]["QUILT_CATALOG_DOMAIN"] == "custom.quiltdata.com"

    def test_generates_different_config_for_development_mode(self):
        """Should generate different config for development vs production mode."""
        dev_config = generate_config_entry(development_mode=True)
        prod_config = generate_config_entry(development_mode=False)
        
        assert dev_config["quilt"]["command"] == "uv"
        assert dev_config["quilt"]["args"] == ["run", "quilt-mcp"]
        assert prod_config["quilt"]["command"] == "uvx"
        assert prod_config["quilt"]["args"] == ["quilt-mcp"]


class TestGetConfigFileLocations:
    """Test configuration file location discovery behavior."""

    @patch('platform.system')
    def test_returns_macos_config_locations(self, mock_system):
        """Should return macOS-specific config file locations."""
        mock_system.return_value = 'Darwin'
        
        locations = get_config_file_locations()
        
        assert 'claude_desktop' in locations
        assert 'cursor' in locations
        assert 'vscode' in locations
        assert locations['claude_desktop'].endswith('claude_desktop_config.json')
        assert 'Library/Application Support' in locations['claude_desktop']

    @patch('platform.system')
    def test_returns_windows_config_locations(self, mock_system):
        """Should return Windows-specific config file locations."""
        mock_system.return_value = 'Windows'
        
        locations = get_config_file_locations()
        
        assert 'claude_desktop' in locations
        assert 'cursor' in locations
        assert 'AppData' in locations['claude_desktop']

    @patch('platform.system')
    def test_returns_linux_config_locations(self, mock_system):
        """Should return Linux-specific config file locations."""
        mock_system.return_value = 'Linux'
        
        locations = get_config_file_locations()
        
        assert 'claude_desktop' in locations
        assert 'cursor' in locations
        assert '.config' in locations['claude_desktop']


class TestAddToConfigFile:
    """Test configuration file modification behavior."""

    def test_adds_config_to_existing_json_file(self):
        """Should add MCP server config to existing JSON configuration file."""
        existing_config = {"existing": "value"}
        new_config = {"quilt": {"command": "uvx", "args": ["quilt-mcp"]}}
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(existing_config, f)
            temp_file = f.name
        
        try:
            result = add_to_config_file(temp_file, new_config)
            
            assert result is True
            with open(temp_file, 'r') as f:
                updated_config = json.load(f)
            assert "existing" in updated_config
            assert "mcpServers" in updated_config
            assert "quilt" in updated_config["mcpServers"]
        finally:
            os.unlink(temp_file)

    def test_creates_new_config_file_if_not_exists(self):
        """Should create new configuration file if it doesn't exist."""
        config = {"quilt": {"command": "uvx", "args": ["quilt-mcp"]}}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = os.path.join(temp_dir, "config.json")
            
            result = add_to_config_file(config_file, config)
            
            assert result is True
            assert os.path.exists(config_file)
            with open(config_file, 'r') as f:
                saved_config = json.load(f)
            assert "mcpServers" in saved_config
            assert "quilt" in saved_config["mcpServers"]

    def test_handles_malformed_json_gracefully(self):
        """Should handle malformed JSON files gracefully."""
        config = {"quilt": {"command": "uvx", "args": ["quilt-mcp"]}}
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            f.write("invalid json content")
            temp_file = f.name
        
        try:
            result = add_to_config_file(temp_file, config)
            
            assert result is False  # Should return False for malformed JSON
        finally:
            os.unlink(temp_file)

    def test_preserves_existing_mcp_servers(self):
        """Should preserve existing MCP servers when adding new one."""
        existing_config = {
            "mcpServers": {
                "existing_server": {"command": "existing", "args": []}
            }
        }
        new_config = {"quilt": {"command": "uvx", "args": ["quilt-mcp"]}}
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(existing_config, f)
            temp_file = f.name
        
        try:
            result = add_to_config_file(temp_file, new_config)
            
            assert result is True
            with open(temp_file, 'r') as f:
                updated_config = json.load(f)
            assert "existing_server" in updated_config["mcpServers"]
            assert "quilt" in updated_config["mcpServers"]
        finally:
            os.unlink(temp_file)


class TestAutoConfigureMain:
    """Test main auto-configuration workflow behavior."""

    @patch('builtins.print')
    def test_displays_config_entry_when_no_client_specified(self, mock_print):
        """Should display generated config entry when no specific client is specified."""
        auto_configure_main()
        
        # Should have printed the configuration
        assert mock_print.called
        printed_text = ''.join(call.args[0] for call in mock_print.call_args_list if call.args)
        assert "quilt" in printed_text

    @patch('builtins.print')
    def test_displays_config_file_locations(self, mock_print):
        """Should display configuration file locations for different editors."""
        auto_configure_main()
        
        printed_text = ''.join(call.args[0] for call in mock_print.call_args_list if call.args)
        assert "Claude Desktop" in printed_text or "claude_desktop" in printed_text
        assert "Cursor" in printed_text or "cursor" in printed_text

    @patch('app.quilt_mcp.auto_configure.add_to_config_file')
    @patch('builtins.print')
    def test_adds_config_to_specified_client_file(self, mock_print, mock_add_to_config):
        """Should add configuration to specified client configuration file."""
        mock_add_to_config.return_value = True
        
        auto_configure_main(client="cursor", config_file_path="/path/to/cursor/config.json")
        
        mock_add_to_config.assert_called_once()
        assert "Successfully" in ''.join(call.args[0] for call in mock_print.call_args_list if call.args)

    @patch('app.quilt_mcp.auto_configure.add_to_config_file')
    @patch('builtins.print')
    def test_handles_config_file_write_failure(self, mock_print, mock_add_to_config):
        """Should handle configuration file write failures gracefully."""
        mock_add_to_config.return_value = False
        
        auto_configure_main(client="cursor", config_file_path="/path/to/cursor/config.json")
        
        printed_text = ''.join(call.args[0] for call in mock_print.call_args_list if call.args)
        assert "Failed" in printed_text or "Error" in printed_text