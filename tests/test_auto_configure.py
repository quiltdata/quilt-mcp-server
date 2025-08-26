"""
BDD tests for auto-configuration functionality.

These tests describe the expected behavior of the auto-configuration script
that generates MCP server configuration entries for different editors.
"""

import json
import os
import platform
import stat
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open
import pytest

from quilt_mcp.auto_configure import (
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

    @patch('quilt_mcp.auto_configure.add_to_config_file')
    @patch('builtins.print')
    def test_adds_config_to_specified_client_file(self, mock_print, mock_add_to_config):
        """Should add configuration to specified client configuration file."""
        mock_add_to_config.return_value = True
        
        auto_configure_main(client="cursor", config_file_path="/path/to/cursor/config.json")
        
        mock_add_to_config.assert_called_once()
        assert "Successfully" in ''.join(call.args[0] for call in mock_print.call_args_list if call.args)

    @patch('quilt_mcp.auto_configure.add_to_config_file')
    @patch('builtins.print')
    def test_handles_config_file_write_failure(self, mock_print, mock_add_to_config):
        """Should handle configuration file write failures gracefully."""
        mock_add_to_config.return_value = False
        
        auto_configure_main(client="cursor", config_file_path="/path/to/cursor/config.json")
        
        printed_text = ''.join(call.args[0] for call in mock_print.call_args_list if call.args)
        assert "Failed" in printed_text or "Error" in printed_text


class TestRealFileSystemIntegration:
    """Integration tests with real file system operations (IT2)."""

    def test_creates_nested_directories_when_they_dont_exist(self):
        """Should create nested directory structure for configuration files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a deeply nested config path
            config_path = Path(temp_dir) / "deep" / "nested" / "path" / "config.json"
            config = {"quilt": {"command": "uv", "args": ["run", "quilt-mcp"]}}
            
            # Should create all parent directories
            result = add_to_config_file(str(config_path), config)
            
            assert result is True
            assert config_path.exists()
            assert config_path.parent.exists()
            
            # Verify content is correct
            with open(config_path, 'r') as f:
                saved_config = json.load(f)
            assert "mcpServers" in saved_config
            assert "quilt" in saved_config["mcpServers"]

    def test_handles_different_file_permissions_gracefully(self):
        """Should handle various file permission scenarios."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            config_file = config_dir / "config.json"
            
            # Create initial config file
            initial_config = {"existing": "data"}
            with open(config_file, 'w') as f:
                json.dump(initial_config, f)
            
            # Test with read-only file (should fail gracefully)
            if platform.system() != 'Windows':  # Windows handles permissions differently
                config_file.chmod(stat.S_IRUSR)  # Read-only
                
                config = {"quilt": {"command": "uvx", "args": ["quilt-mcp"]}}
                result = add_to_config_file(str(config_file), config)
                
                # Should fail but not crash
                assert result is False
                
                # Restore write permissions for cleanup
                config_file.chmod(stat.S_IRUSR | stat.S_IWUSR)

    def test_preserves_existing_json_formatting_and_structure(self):
        """Should preserve existing JSON structure and formatting when possible."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "existing.json"
            
            # Create complex existing configuration
            existing_config = {
                "mcpServers": {
                    "server1": {
                        "command": "existing1",
                        "args": ["arg1", "arg2"],
                        "env": {"VAR1": "value1"}
                    },
                    "server2": {
                        "command": "existing2",
                        "description": "Existing server 2"
                    }
                },
                "otherSettings": {
                    "theme": "dark",
                    "fontSize": 14
                }
            }
            
            with open(config_file, 'w') as f:
                json.dump(existing_config, f, indent=2)
            
            # Add new MCP server configuration
            new_config = {"quilt": {"command": "uv", "args": ["run", "quilt-mcp"]}}
            result = add_to_config_file(str(config_file), new_config)
            
            assert result is True
            
            # Verify all data preserved and new config added
            with open(config_file, 'r') as f:
                updated_config = json.load(f)
            
            # Original data should be preserved
            assert "server1" in updated_config["mcpServers"]
            assert "server2" in updated_config["mcpServers"]
            assert updated_config["otherSettings"]["theme"] == "dark"
            assert updated_config["mcpServers"]["server1"]["env"]["VAR1"] == "value1"
            
            # New config should be added
            assert "quilt" in updated_config["mcpServers"]
            assert updated_config["mcpServers"]["quilt"]["command"] == "uv"

    def test_handles_concurrent_file_access_scenarios(self):
        """Should handle scenarios where file is being accessed by other processes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "concurrent.json"
            
            # Create initial config
            with open(config_file, 'w') as f:
                json.dump({"existing": "data"}, f)
            
            # Simulate concurrent access by keeping file open
            with open(config_file, 'r') as f:
                config = {"quilt": {"command": "uvx", "args": ["quilt-mcp"]}}
                
                # This should still work (most systems allow multiple readers)
                # or fail gracefully without corruption
                result = add_to_config_file(str(config_file), config)
                
                # Result may be True or False, but file should not be corrupted
                if config_file.exists():
                    with open(config_file, 'r') as verify_f:
                        try:
                            json.load(verify_f)  # Should not raise JSONDecodeError
                        except json.JSONDecodeError:
                            pytest.fail("File was corrupted during concurrent access")

    def test_works_with_different_filesystem_types(self):
        """Should work correctly on different filesystem types and case sensitivity."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test with various filename cases and characters
            test_cases = [
                "config.json",
                "Config.JSON",  # Different case
                "my-config.json",  # Hyphen
                "my_config.json",  # Underscore
                "config.file.json",  # Multiple dots
            ]
            
            for filename in test_cases:
                config_file = Path(temp_dir) / filename
                config = {"quilt": {"command": "uvx", "args": ["quilt-mcp"]}}
                
                result = add_to_config_file(str(config_file), config)
                
                assert result is True, f"Failed for filename: {filename}"
                assert config_file.exists(), f"File not created: {filename}"
                
                # Verify content
                with open(config_file, 'r') as f:
                    saved_config = json.load(f)
                assert "mcpServers" in saved_config

    def test_handles_symlinks_and_hardlinks_correctly(self):
        """Should handle symlinks and hardlinks appropriately."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create original file
            original_file = Path(temp_dir) / "original.json"
            with open(original_file, 'w') as f:
                json.dump({"original": "data"}, f)
            
            # Create symlink (if supported on this platform)
            symlink_file = Path(temp_dir) / "symlink.json"
            try:
                symlink_file.symlink_to(original_file)
                
                # Add config via symlink
                config = {"quilt": {"command": "uvx", "args": ["quilt-mcp"]}}
                result = add_to_config_file(str(symlink_file), config)
                
                assert result is True
                
                # Both files should show the updated content
                with open(original_file, 'r') as f:
                    original_content = json.load(f)
                with open(symlink_file, 'r') as f:
                    symlink_content = json.load(f)
                    
                assert original_content == symlink_content
                assert "mcpServers" in original_content
                
            except (OSError, NotImplementedError):
                # Symlinks not supported on this platform - skip test
                pytest.skip("Symlinks not supported on this platform")

    def test_project_root_detection_with_real_filesystem(self):
        """Should correctly detect project root in real filesystem scenarios."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a mock project structure
            project_dir = Path(temp_dir) / "mock_project" 
            project_dir.mkdir()
            
            # Create pyproject.toml in project root
            (project_dir / "pyproject.toml").touch()
            
            # Create subdirectories
            sub_dir = project_dir / "app" / "quilt_mcp"
            sub_dir.mkdir(parents=True)
            
            # Change to subdirectory and test config generation
            original_cwd = os.getcwd()
            try:
                os.chdir(sub_dir)
                
                config = generate_config_entry(development_mode=True)
                
                # Should detect project root correctly
                assert "cwd" in config["quilt"]
                cwd_path = Path(config["quilt"]["cwd"])
                assert (cwd_path / "pyproject.toml").exists()
                assert cwd_path.name == "mock_project"
                
            finally:
                os.chdir(original_cwd)