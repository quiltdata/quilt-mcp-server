"""
Auto-configuration functionality for MCP server setup.

This module provides functionality to automatically generate configuration entries
for various editors and optionally add them to configuration files.
"""

import json
import os
import platform
from pathlib import Path
from typing import Dict, Any, Optional


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
        command = "uv"
        args = ["run", "quilt-mcp"]
    else:
        command = "uvx"
        args = ["quilt-mcp"]
    
    config = {
        server_name: {
            "command": command,
            "args": args,
            "env": {
                "QUILT_CATALOG_DOMAIN": catalog_domain
            },
            "description": "Quilt MCP Server"
        }
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


def auto_configure_main(
    client: Optional[str] = None,
    config_file_path: Optional[str] = None,
    catalog_domain: str = "demo.quiltdata.com",
    development_mode: bool = False
) -> None:
    """Main auto-configuration workflow.
    
    Args:
        client: Specific client to configure (e.g., 'cursor', 'claude_desktop', 'vscode')
        config_file_path: Explicit path to configuration file (overrides client detection)
        catalog_domain: Quilt catalog domain to use
        development_mode: Whether to use development mode configuration
    """
    # Generate the configuration entry
    config_entry = generate_config_entry(
        catalog_domain=catalog_domain,
        development_mode=development_mode
    )
    
    print("Generated MCP Server Configuration:")
    print("=" * 50)
    print(json.dumps({"mcpServers": config_entry}, indent=2))
    print()
    
    # Get configuration file locations
    locations = get_config_file_locations()
    
    print("Configuration File Locations:")
    print("=" * 50)
    for editor, path in locations.items():
        print(f"{editor.replace('_', ' ').title()}: {path}")
    print()
    
    # If a specific client or config file is specified, try to add the configuration
    if client or config_file_path:
        if config_file_path:
            target_file = config_file_path
        elif client in locations:
            target_file = locations[client]
        else:
            print(f"Error: Unknown client '{client}'. Available clients: {', '.join(locations.keys())}")
            return
        
        print(f"Adding configuration to: {target_file}")
        success = add_to_config_file(target_file, config_entry)
        
        if success:
            print("Successfully added MCP server configuration!")
        else:
            print("Failed to add configuration. Please check the file path and permissions.")
    else:
        print("To automatically add this configuration to a client, specify:")
        print("  --client cursor    # Add to Cursor settings")
        print("  --client claude_desktop    # Add to Claude Desktop settings")
        print("  --client vscode    # Add to VS Code settings")
        print("  --config-file /path/to/config.json    # Add to specific file")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Auto-configure Quilt MCP server for various editors")
    parser.add_argument("--client", choices=["cursor", "claude_desktop", "vscode"], 
                       help="Client to configure")
    parser.add_argument("--config-file", help="Explicit path to configuration file")
    parser.add_argument("--catalog-domain", default="demo.quiltdata.com",
                       help="Quilt catalog domain (default: demo.quiltdata.com)")
    parser.add_argument("--development", action="store_true",
                       help="Use development mode (uv run instead of uvx)")
    
    args = parser.parse_args()
    
    auto_configure_main(
        client=args.client,
        config_file_path=args.config_file,
        catalog_domain=args.catalog_domain,
        development_mode=args.development
    )