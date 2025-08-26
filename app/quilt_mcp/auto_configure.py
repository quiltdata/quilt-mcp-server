"""
Auto-configuration functionality for MCP server setup.

This module provides functionality to automatically generate configuration entries
for various editors and optionally add them to configuration files.
"""

import json
import os
import platform
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List


def generate_config_entry(
    catalog_domain: str = "demo.quiltdata.com",
    development_mode: bool = False,
    server_name: str = "quilt"
) -> Dict[str, Any]:
    """Generate a configuration entry for the Quilt MCP server.
    
    Args:
        catalog_domain: The Quilt catalog domain to use
        development_mode: Whether to generate config for development (uv run) or production (uvx)
        server_name: Name for the server entry in configuration
        
    Returns:
        Dictionary containing the MCP server configuration
    """
    if development_mode:
        # Use make target - much more robust than trying to handle paths manually
        command = "make"
        args = ["-C", "app", "run"]
        
        # Find the project root (where Makefile exists)
        current_dir = Path.cwd()
        project_root = current_dir
        # Look for Makefile in current and parent directories
        while project_root != project_root.parent:
            if (project_root / "Makefile").exists():
                break
            project_root = project_root.parent
        
        config_entry = {
            "command": command,
            "args": args,
            "cwd": str(project_root),
            "env": {
                "QUILT_CATALOG_DOMAIN": catalog_domain
            },
            "description": "Quilt MCP Server"
        }
    else:
        command = "uvx"
        args = ["quilt-mcp"]
        # For production (uvx), no cwd needed as it should be globally available
        config_entry = {
            "command": command,
            "args": args,
            "env": {
                "QUILT_CATALOG_DOMAIN": catalog_domain
            },
            "description": "Quilt MCP Server"
        }
    
    config = {
        server_name: config_entry
    }
    
    return config


def get_config_file_locations() -> Dict[str, str]:
    """Get configuration file locations for different editors based on the current OS.
    
    Returns:
        Dictionary mapping editor names to their configuration file paths
    """
    system = platform.system()
    home = Path.home()
    
    locations = {}
    
    if system == "Darwin":  # macOS
        locations.update({
            "claude_desktop": str(home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"),
            "cursor": str(home / "Library" / "Application Support" / "Cursor" / "User" / "settings.json"),
            "vscode": str(home / "Library" / "Application Support" / "Code" / "User" / "settings.json"),
        })
    elif system == "Windows":
        locations.update({
            "claude_desktop": str(home / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"),
            "cursor": str(home / "AppData" / "Roaming" / "Cursor" / "User" / "settings.json"),
            "vscode": str(home / "AppData" / "Roaming" / "Code" / "User" / "settings.json"),
        })
    else:  # Linux and others
        locations.update({
            "claude_desktop": str(home / ".config" / "claude" / "claude_desktop_config.json"),
            "cursor": str(home / ".config" / "Cursor" / "User" / "settings.json"),
            "vscode": str(home / ".config" / "Code" / "User" / "settings.json"),
        })
    
    return locations


def add_to_config_file(config_file_path: str, mcp_config: Dict[str, Any]) -> bool:
    """Add MCP server configuration to a JSON configuration file.
    
    Args:
        config_file_path: Path to the configuration file
        mcp_config: MCP server configuration to add
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure directory exists
        config_dir = os.path.dirname(config_file_path)
        if config_dir:
            os.makedirs(config_dir, exist_ok=True)
        
        # Load existing config or create new one
        if os.path.exists(config_file_path):
            try:
                with open(config_file_path, 'r') as f:
                    existing_config = json.load(f)
            except json.JSONDecodeError:
                # Handle malformed JSON
                return False
        else:
            existing_config = {}
        
        # Add or update mcpServers section
        if "mcpServers" not in existing_config:
            existing_config["mcpServers"] = {}
        
        # Merge the new MCP config
        existing_config["mcpServers"].update(mcp_config)
        
        # Write back to file
        with open(config_file_path, 'w') as f:
            json.dump(existing_config, f, indent=2)
        
        return True
        
    except (OSError, IOError, json.JSONDecodeError):
        return False


def load_client_definitions() -> Dict[str, Any]:
    """Load client definitions from the external JSON configuration file.
    
    Returns:
        Dictionary containing client definitions loaded from clients.json
    """
    clients_file = Path(__file__).parent / "clients.json"
    
    try:
        with open(clients_file, 'r') as f:
            clients_data = json.load(f)
        return clients_data.get("clients", {})
    except (FileNotFoundError, json.JSONDecodeError) as e:
        # Fallback to hardcoded definitions if file is missing or invalid
        return {}


def get_client_config_path(client_id: str) -> Optional[str]:
    """Get the configuration file path for a specific client on the current platform.
    
    Args:
        client_id: The client identifier (e.g., 'claude_desktop', 'cursor', 'vscode')
        
    Returns:
        Path to the client's configuration file, or None if client is unknown
    """
    clients = load_client_definitions()
    
    if client_id not in clients:
        return None
    
    client_config = clients[client_id]
    platforms = client_config.get("platforms", {})
    current_platform = platform.system()
    
    if current_platform not in platforms:
        return None
    
    path_template = platforms[current_platform]
    
    # Expand path variables
    if path_template.startswith("~/"):
        return str(Path.home() / path_template[2:])
    elif "%APPDATA%" in path_template:
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return path_template.replace("%APPDATA%", appdata)
    else:
        return path_template


def detect_clients() -> Dict[str, Dict[str, Any]]:
    """Auto-detect existing client configurations and their status.
    
    Returns:
        Dictionary mapping client IDs to their detection status including:
        - config_exists: Whether config file exists
        - config_valid: Whether config file contains valid JSON
        - executable_found: Whether client executable is found in PATH
        - config_path: Path to configuration file
    """
    clients = load_client_definitions()
    status = {}
    
    for client_id, client_config in clients.items():
        client_status = {
            "name": client_config.get("name", client_id),
            "config_exists": False,
            "config_valid": False,
            "executable_found": False,
            "config_path": None
        }
        
        # Check configuration file
        config_path = get_client_config_path(client_id)
        if config_path:
            client_status["config_path"] = config_path
            config_file = Path(config_path)
            
            if config_file.exists():
                client_status["config_exists"] = True
                
                # Check if JSON is valid
                try:
                    with open(config_file, 'r') as f:
                        json.load(f)
                    client_status["config_valid"] = True
                except json.JSONDecodeError:
                    client_status["config_valid"] = False
        
        # Check for executable
        detection_config = client_config.get("detection", {})
        executables = detection_config.get("check_executable", [])
        
        for executable in executables:
            if shutil.which(executable):
                client_status["executable_found"] = True
                break
        
        status[client_id] = client_status
    
    return status


def display_client_status(clients_status: Dict[str, Dict[str, Any]]) -> None:
    """Display client status with visual indicators.
    
    Args:
        clients_status: Dictionary of client status from detect_clients()
    """
    print("Detected MCP Clients:")
    print("=" * 50)
    
    for client_id, status in clients_status.items():
        name = status.get("name", client_id)
        config_exists = status.get("config_exists", False)
        config_valid = status.get("config_valid", False)
        executable_found = status.get("executable_found", False)
        config_path = status.get("config_path", "Unknown")
        
        # Determine status indicator
        if config_exists and config_valid:
            indicator = "✅ Found"
        elif config_exists and not config_valid:
            indicator = "⚠️  Invalid JSON"
        else:
            indicator = "❌ Missing"
        
        executable_status = "📦 Installed" if executable_found else "❌ Not Found"
        
        print(f"{name}:")
        print(f"  Config: {indicator}")
        print(f"  Path: {config_path}")
        print(f"  Executable: {executable_status}")
        print()


def interactive_client_selection(available_clients: Dict[str, Dict[str, Any]]) -> List[str]:
    """Prompt user to select which clients to configure.
    
    Args:
        available_clients: Dictionary of available clients and their status
        
    Returns:
        List of selected client IDs
    """
    if not available_clients:
        print("No clients detected.")
        return []
    
    print("Select clients to configure:")
    print("=" * 50)
    
    client_list = list(available_clients.keys())
    
    # Display numbered list
    for i, client_id in enumerate(client_list, 1):
        status = available_clients[client_id]
        name = status.get("name", client_id)
        config_exists = status.get("config_exists", False)
        config_valid = status.get("config_valid", False)
        
        if config_exists and config_valid:
            status_indicator = "✅"
        elif config_exists and not config_valid:
            status_indicator = "⚠️"
        else:
            status_indicator = "❌"
        
        print(f"{i}. {name} {status_indicator}")
    
    print("\nEnter numbers (comma-separated) or 'q' to quit:")
    print("Example: 1,3 or 1 or q")
    
    try:
        user_input = input("> ").strip().lower()
        
        if user_input == 'q':
            return []
        
        # Parse selection
        selected_indices = []
        for part in user_input.split(','):
            try:
                index = int(part.strip()) - 1  # Convert to 0-based index
                if 0 <= index < len(client_list):
                    selected_indices.append(index)
            except ValueError:
                continue
        
        return [client_list[i] for i in selected_indices]
        
    except (KeyboardInterrupt, EOFError):
        return []


def create_backup(config_file_path: str) -> Optional[str]:
    """Create a backup of a configuration file.
    
    Args:
        config_file_path: Path to the configuration file to backup
        
    Returns:
        Path to the backup file, or None if backup failed
    """
    try:
        config_path = Path(config_file_path)
        if not config_path.exists():
            return None
            
        # Create backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = config_path.with_suffix(f"{config_path.suffix}.backup.{timestamp}")
        
        # Copy file
        import shutil
        shutil.copy2(config_file_path, backup_path)
        
        return str(backup_path)
        
    except (OSError, IOError):
        return None


def create_backup_with_metadata(config_file_path: str) -> Dict[str, Any]:
    """Create a backup with metadata.
    
    Args:
        config_file_path: Path to the configuration file to backup
        
    Returns:
        Dictionary containing backup information
    """
    backup_path = create_backup(config_file_path)
    
    return {
        "backup_path": backup_path,
        "timestamp": datetime.now().isoformat(),
        "original_path": config_file_path
    }


def find_backup_files(config_file_path: str) -> List[str]:
    """Find backup files for a given configuration file.
    
    Args:
        config_file_path: Path to the original configuration file
        
    Returns:
        List of backup file paths, sorted by timestamp (most recent first)
    """
    config_path = Path(config_file_path)
    parent_dir = config_path.parent
    base_name = config_path.name
    
    if not parent_dir.exists():
        return []
    
    # Find all backup files
    backup_files = []
    for file_path in parent_dir.glob(f"{base_name}.backup.*"):
        backup_files.append(str(file_path))
    
    # Sort by timestamp (most recent first)
    backup_files.sort(reverse=True)
    return backup_files


def rollback_configuration(config_file_path: str) -> bool:
    """Restore configuration from the most recent backup.
    
    Args:
        config_file_path: Path to the configuration file to restore
        
    Returns:
        True if rollback was successful, False otherwise
    """
    backup_files = find_backup_files(config_file_path)
    
    if not backup_files:
        return False
    
    # Use the most recent backup
    most_recent_backup = backup_files[0]
    
    try:
        # Copy backup back to original location
        shutil.copy2(most_recent_backup, config_file_path)
        return True
        
    except (OSError, IOError):
        return False


def cleanup_old_backups(config_file_path: str, keep_count: int = 3) -> None:
    """Clean up old backup files, keeping only the most recent ones.
    
    Args:
        config_file_path: Path to the original configuration file
        keep_count: Number of backup files to keep (default: 3)
    """
    backup_files = find_backup_files(config_file_path)
    
    # Remove old backups (keep only the most recent ones)
    for backup_file in backup_files[keep_count:]:
        try:
            Path(backup_file).unlink()
        except (OSError, IOError):
            pass  # Ignore errors when cleaning up


def add_to_config_file_with_backup(config_file_path: str, mcp_config: Dict[str, Any]) -> bool:
    """Add MCP server configuration to a JSON file with automatic backup.
    
    Args:
        config_file_path: Path to the configuration file
        mcp_config: MCP server configuration to add
        
    Returns:
        True if successful, False otherwise
    """
    # Create backup if file exists
    if Path(config_file_path).exists():
        backup_path = create_backup(config_file_path)
        if backup_path is None:
            return False
    
    # Add configuration
    success = add_to_config_file(config_file_path, mcp_config)
    
    if success:
        # Clean up old backups after successful operation
        cleanup_old_backups(config_file_path)
    
    return success


def auto_configure_main(
    client: Optional[str] = None,
    config_file_path: Optional[str] = None,
    catalog_domain: Optional[str] = None,
    batch_mode: bool = False,
    list_clients: bool = False,
    rollback: bool = False
) -> None:
    """Main auto-configuration workflow for local development.
    
    Args:
        client: Specific client to configure (e.g., 'cursor', 'claude_desktop', 'vscode')
        config_file_path: Explicit path to configuration file (overrides client detection)
        catalog_domain: Quilt catalog domain to use (overrides environment variable)
        batch_mode: Non-interactive mode (display only, no prompts)
        list_clients: Show all detectable clients and their status
        rollback: Restore previous configuration from backups
    """
    # Determine catalog domain: CLI arg > env var > default
    if catalog_domain is None:
        catalog_domain = os.environ.get("QUILT_CATALOG_DOMAIN", "demo.quiltdata.com")
    
    # Handle rollback mode
    if rollback:
        print("Rollback Mode - Restoring Previous Configurations")
        print("=" * 50)
        
        # Detect clients to find config files to rollback
        clients_status = detect_clients()
        rollback_count = 0
        
        for client_id, status in clients_status.items():
            if status.get("config_exists") and status.get("config_path"):
                config_path = status["config_path"]
                backup_files = find_backup_files(config_path)
                
                if backup_files:
                    print(f"Rolling back {status['name']}...")
                    success = rollback_configuration(config_path)
                    if success:
                        print(f"✅ Successfully restored {status['name']} configuration")
                        rollback_count += 1
                    else:
                        print(f"❌ Failed to restore {status['name']} configuration")
                else:
                    print(f"⚠️  No backup found for {status['name']}")
        
        if rollback_count == 0:
            print("No configurations were rolled back.")
        else:
            print(f"\nSuccessfully rolled back {rollback_count} configuration(s).")
        return
    
    # Handle list clients mode
    if list_clients:
        print("MCP Client Detection Results")
        print("=" * 50)
        clients_status = detect_clients()
        display_client_status(clients_status)
        return
    
    # Generate the configuration entry (always development mode for this spec)
    config_entry = generate_config_entry(
        catalog_domain=catalog_domain,
        development_mode=True
    )
    
    # Handle batch mode (non-interactive)
    if batch_mode:
        # In batch mode, only output JSON for scripting compatibility
        print(json.dumps({"mcpServers": config_entry}, indent=2))
        return
    
    # Handle specific client or config file (direct configuration)
    if client or config_file_path:
        if config_file_path:
            target_file = config_file_path
            client_name = "Custom File"
        else:
            target_path = get_client_config_path(client)
            if target_path is None:
                clients = load_client_definitions()
                available_clients = list(clients.keys())
                print(f"Error: Unknown client '{client}'. Available clients: {', '.join(available_clients)}")
                return
            target_file = target_path
            clients = load_client_definitions()
            client_name = clients.get(client, {}).get("name", client)
        
        print(f"Configuring {client_name}")
        print("=" * 50)
        print(f"Target file: {target_file}")
        
        # Create backup and add configuration
        success = add_to_config_file_with_backup(target_file, config_entry)
        
        if success:
            print(f"✅ Successfully configured {client_name}!")
        else:
            print(f"❌ Failed to configure {client_name}. Please check the file path and permissions.")
        return
    
    # Interactive mode (default)
    print("Quilt MCP Server Auto-Configuration")
    print("=" * 50)
    
    # Detect available clients
    clients_status = detect_clients()
    
    if not clients_status:
        print("No MCP clients detected on this system.")
        print("\nGenerated configuration for manual setup:")
        print(json.dumps({"mcpServers": config_entry}, indent=2))
        return
    
    # Display client status
    display_client_status(clients_status)
    
    # Interactive client selection
    selected_clients = interactive_client_selection(clients_status)
    
    if not selected_clients:
        print("No clients selected. Configuration cancelled.")
        return
    
    # Configure selected clients
    print(f"\nConfiguring {len(selected_clients)} client(s)...")
    print("=" * 50)
    
    success_count = 0
    for client_id in selected_clients:
        client_status = clients_status[client_id]
        client_name = client_status.get("name", client_id)
        config_path = client_status.get("config_path")
        
        if not config_path:
            print(f"⚠️  Skipping {client_name}: No config path available")
            continue
        
        print(f"Configuring {client_name}...")
        
        # Use backup-enabled configuration
        success = add_to_config_file_with_backup(config_path, config_entry)
        
        if success:
            print(f"✅ Successfully configured {client_name}")
            success_count += 1
        else:
            print(f"❌ Failed to configure {client_name}")
    
    print(f"\nConfiguration complete: {success_count}/{len(selected_clients)} clients configured successfully.")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Auto-configure Quilt MCP server for local development")
    parser.add_argument("--client", 
                       help="Client to configure (e.g., cursor, claude_desktop, vscode)")
    parser.add_argument("--config-file", help="Explicit path to configuration file")
    parser.add_argument("--catalog-domain",
                       help="Quilt catalog domain (overrides QUILT_CATALOG_DOMAIN env var, default: demo.quiltdata.com)")
    parser.add_argument("--batch", action="store_true",
                       help="Non-interactive mode (display config without prompts)")
    parser.add_argument("--list-clients", action="store_true",
                       help="Show all detectable clients and their status")
    parser.add_argument("--rollback", action="store_true",
                       help="Restore previous configuration from backups")
    
    args = parser.parse_args()
    
    auto_configure_main(
        client=args.client,
        config_file_path=args.config_file,
        catalog_domain=args.catalog_domain,
        batch_mode=args.batch,
        list_clients=args.list_clients,
        rollback=args.rollback
    )