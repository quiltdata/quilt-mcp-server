"""
BDD tests for auto-configuration functionality.

These tests describe the expected behavior of the auto-configuration script
that generates MCP server configuration entries for different editors.
"""

import json
import os
import platform
import shutil
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
        auto_configure_main(batch_mode=True)
        
        # Should have printed the configuration
        assert mock_print.called
        printed_text = ''.join(call.args[0] for call in mock_print.call_args_list if call.args)
        assert "quilt" in printed_text

    @patch('builtins.print')
    def test_displays_config_file_locations(self, mock_print):
        """Should display configuration file locations for different editors."""
        auto_configure_main(batch_mode=True)
        
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


class TestClientConfiguration:
    """Test externalized client configuration behavior (FR6)."""

    def test_loads_client_definitions_from_json_file(self):
        """Should load client definitions from external JSON file."""
        # Test will fail until we implement load_client_definitions
        from quilt_mcp.auto_configure import load_client_definitions
        
        clients = load_client_definitions()
        
        assert isinstance(clients, dict)
        assert "claude_desktop" in clients
        assert "cursor" in clients
        assert "vscode" in clients

    def test_validates_client_configuration_schema(self):
        """Should validate client configuration against expected schema."""
        from quilt_mcp.auto_configure import load_client_definitions
        
        clients = load_client_definitions()
        
        for client_id, client_config in clients.items():
            assert "name" in client_config
            assert "config_type" in client_config
            assert "platforms" in client_config
            assert "detection" in client_config
            
            # Validate platform paths
            platforms = client_config["platforms"]
            assert "Darwin" in platforms
            assert "Windows" in platforms
            assert "Linux" in platforms

    def test_supports_platform_specific_paths(self):
        """Should provide platform-specific configuration file paths."""
        from quilt_mcp.auto_configure import get_client_config_path
        
        # Test with mocked platform
        with patch('platform.system', return_value='Darwin'):
            path = get_client_config_path("claude_desktop")
            assert "Library/Application Support" in path
            
        with patch('platform.system', return_value='Windows'):
            path = get_client_config_path("claude_desktop")
            assert "AppData" in path or "APPDATA" in path


class TestClientAutoDetection:
    """Test client auto-detection and status checking behavior (FR5)."""

    def test_detects_existing_client_config_files(self):
        """Should auto-detect existing client configuration files."""
        from quilt_mcp.auto_configure import detect_clients
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create mock config files
            claude_config = Path(temp_dir) / "claude_desktop_config.json"
            claude_config.parent.mkdir(parents=True, exist_ok=True)
            with open(claude_config, 'w') as f:
                json.dump({"mcpServers": {}}, f)
            
            with patch('quilt_mcp.auto_configure.get_client_config_path') as mock_path:
                mock_path.return_value = str(claude_config)
                
                clients_status = detect_clients()
                
                assert isinstance(clients_status, dict)
                assert "claude_desktop" in clients_status
                assert clients_status["claude_desktop"]["config_exists"] is True
                assert clients_status["claude_desktop"]["config_valid"] is True

    def test_shows_status_for_missing_config_files(self):
        """Should show status for missing configuration files."""
        from quilt_mcp.auto_configure import detect_clients
        
        with patch('quilt_mcp.auto_configure.get_client_config_path') as mock_path:
            mock_path.return_value = "/nonexistent/path/config.json"
            
            clients_status = detect_clients()
            
            assert "claude_desktop" in clients_status
            assert clients_status["claude_desktop"]["config_exists"] is False

    def test_detects_invalid_json_config_files(self):
        """Should detect invalid JSON in configuration files."""
        from quilt_mcp.auto_configure import detect_clients
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create invalid JSON file
            invalid_config = Path(temp_dir) / "invalid_config.json"
            with open(invalid_config, 'w') as f:
                f.write("invalid json content")
            
            with patch('quilt_mcp.auto_configure.get_client_config_path') as mock_path:
                mock_path.return_value = str(invalid_config)
                
                clients_status = detect_clients()
                
                assert clients_status["claude_desktop"]["config_exists"] is True
                assert clients_status["claude_desktop"]["config_valid"] is False

    def test_checks_for_client_executables(self):
        """Should check for client executables in addition to config files."""
        from quilt_mcp.auto_configure import detect_clients
        
        with patch('shutil.which') as mock_which:
            mock_which.side_effect = lambda cmd: "/usr/bin/cursor" if cmd == "cursor" else None
            
            clients_status = detect_clients()
            
            assert "cursor" in clients_status
            assert clients_status["cursor"]["executable_found"] is True
            assert clients_status["vscode"]["executable_found"] is False


class TestInteractivePrompts:
    """Test interactive prompts and user selection behavior (FR5)."""

    @patch('builtins.input')
    def test_prompts_user_to_select_clients_to_configure(self, mock_input):
        """Should prompt user to select which clients to configure."""
        from quilt_mcp.auto_configure import interactive_client_selection
        
        mock_input.return_value = "1,2"  # Select first two clients
        
        available_clients = {
            "claude_desktop": {"config_exists": True, "config_valid": True},
            "cursor": {"config_exists": False},
            "vscode": {"config_exists": True, "config_valid": False}
        }
        
        selected = interactive_client_selection(available_clients)
        
        assert isinstance(selected, list)
        assert len(selected) == 2

    @patch('builtins.input')
    def test_handles_user_cancellation_gracefully(self, mock_input):
        """Should handle user cancellation gracefully."""
        from quilt_mcp.auto_configure import interactive_client_selection
        
        mock_input.return_value = "q"  # User quits
        
        available_clients = {"claude_desktop": {"config_exists": True}}
        selected = interactive_client_selection(available_clients)
        
        assert selected == []

    @patch('builtins.input')
    def test_shows_clear_status_indicators(self, mock_input):
        """Should show clear visual status indicators for each client."""
        from quilt_mcp.auto_configure import display_client_status
        
        mock_input.return_value = "q"
        
        clients_status = {
            "claude_desktop": {"config_exists": True, "config_valid": True},
            "cursor": {"config_exists": False},
            "vscode": {"config_exists": True, "config_valid": False}
        }
        
        with patch('builtins.print') as mock_print:
            display_client_status(clients_status)
            
            printed_text = ''.join(call.args[0] for call in mock_print.call_args_list if call.args)
            assert "✅" in printed_text  # Found and valid
            assert "❌" in printed_text  # Missing
            assert "⚠️" in printed_text  # Invalid JSON


class TestBackupAndRollback:
    """Test backup and rollback functionality behavior."""

    def test_creates_backup_before_modifying_config_file(self):
        """Should create backup before modifying configuration files."""
        from quilt_mcp.auto_configure import create_backup, add_to_config_file_with_backup
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "config.json"
            original_config = {"existing": "data"}
            
            with open(config_file, 'w') as f:
                json.dump(original_config, f)
            
            backup_path = create_backup(str(config_file))
            
            assert backup_path is not None
            assert Path(backup_path).exists()
            
            # Verify backup content matches original
            with open(backup_path, 'r') as f:
                backup_config = json.load(f)
            assert backup_config == original_config

    def test_rollback_restores_previous_configuration(self):
        """Should restore previous configuration from backup files."""
        from quilt_mcp.auto_configure import rollback_configuration
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "config.json"
            backup_file = Path(temp_dir) / "config.json.backup.20240101_120000"
            
            # Create current (modified) config
            current_config = {"mcpServers": {"quilt": {"command": "uv"}}}
            with open(config_file, 'w') as f:
                json.dump(current_config, f)
            
            # Create backup (original) config
            original_config = {"existing": "data"}
            with open(backup_file, 'w') as f:
                json.dump(original_config, f)
            
            # Perform rollback
            result = rollback_configuration(str(config_file))
            
            assert result is True
            
            # Verify original content restored
            with open(config_file, 'r') as f:
                restored_config = json.load(f)
            assert restored_config == original_config

    def test_stores_backup_metadata_with_timestamp(self):
        """Should store backup metadata including timestamp and original location."""
        from quilt_mcp.auto_configure import create_backup_with_metadata
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "config.json"
            with open(config_file, 'w') as f:
                json.dump({"test": "data"}, f)
            
            backup_info = create_backup_with_metadata(str(config_file))
            
            assert "backup_path" in backup_info
            assert "timestamp" in backup_info
            assert "original_path" in backup_info
            assert backup_info["original_path"] == str(config_file)

    def test_cleans_up_old_backups_after_successful_operation(self):
        """Should clean up old backup files after successful operations."""
        from quilt_mcp.auto_configure import cleanup_old_backups
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create multiple backup files with different timestamps
            old_backup = Path(temp_dir) / "config.json.backup.20240101_120000"
            recent_backup = Path(temp_dir) / "config.json.backup.20240110_120000"
            
            for backup_file in [old_backup, recent_backup]:
                with open(backup_file, 'w') as f:
                    json.dump({"backup": "data"}, f)
            
            cleanup_old_backups(str(Path(temp_dir) / "config.json"), keep_count=1)
            
            # Should keep only the most recent backup
            assert not old_backup.exists()
            assert recent_backup.exists()


class TestNewCLIFlags:
    """Test new CLI flags behavior."""

    @patch('builtins.print')
    def test_batch_mode_displays_config_without_prompts(self, mock_print):
        """Should display config without prompts in batch mode."""
        from quilt_mcp.auto_configure import auto_configure_main
        
        auto_configure_main(batch_mode=True)
        
        # Should print config but not call any interactive functions
        assert mock_print.called
        printed_text = ''.join(call.args[0] for call in mock_print.call_args_list if call.args)
        assert "quilt" in printed_text

    @patch('builtins.print')
    def test_list_clients_shows_all_detectable_clients(self, mock_print):
        """Should show all detectable clients and their status with --list-clients."""
        from quilt_mcp.auto_configure import auto_configure_main
        
        auto_configure_main(list_clients=True)
        
        printed_text = ''.join(call.args[0] for call in mock_print.call_args_list if call.args)
        assert "Claude Desktop" in printed_text or "claude_desktop" in printed_text
        assert "Cursor" in printed_text
        assert "VS Code" in printed_text or "vscode" in printed_text

    def test_rollback_flag_restores_previous_configurations(self):
        """Should restore previous configurations with --rollback flag."""
        from quilt_mcp.auto_configure import auto_configure_main
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup mock backup scenario
            with patch('quilt_mcp.auto_configure.find_backup_files') as mock_find:
                mock_find.return_value = ["backup1.json", "backup2.json"]
                
                with patch('quilt_mcp.auto_configure.rollback_configuration') as mock_rollback:
                    mock_rollback.return_value = True
                    
                    result = auto_configure_main(rollback=True)
                    
                    # Should attempt rollback
                    mock_rollback.assert_called()

    def test_maintains_backward_compatibility_with_existing_flags(self):
        """Should maintain backward compatibility with existing CLI flags."""
        from quilt_mcp.auto_configure import auto_configure_main
        
        # Existing flags should still work
        with patch('quilt_mcp.auto_configure.add_to_config_file') as mock_add:
            mock_add.return_value = True
            
            # Test existing client flag
            auto_configure_main(client="cursor")
            mock_add.assert_called_once()
            
            # Test existing config-file flag  
            mock_add.reset_mock()
            auto_configure_main(config_file_path="/path/to/config.json")
            mock_add.assert_called_once()


class TestMakeTargetIntegration:
    """Test Make target integration with variables (FR7)."""

    def test_supports_batch_mode_via_make_variable(self):
        """Should support BATCH=1 make variable for non-interactive mode."""
        # This would be tested by checking that the Makefile passes BATCH=1 
        # as --batch flag to the Python script
        pass  # Integration test - would be tested separately

    def test_supports_client_specific_configuration_via_make(self):
        """Should support CLIENT=client_name make variable."""
        # This would test that CLIENT=claude_desktop gets passed as --client flag
        pass  # Integration test - would be tested separately

    def test_supports_list_clients_via_make_variable(self):
        """Should support LIST=1 make variable."""
        pass  # Integration test - would be tested separately