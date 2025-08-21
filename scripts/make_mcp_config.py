#!/usr/bin/env python3
"""
Generate MCP client configuration files for Quilt MCP Server.

This script generates the proper JSON configuration for various MCP clients
(Claude Desktop, VS Code, etc.) with the correct absolute paths.
"""

import json
import os
import sys
import subprocess
from pathlib import Path

def get_project_root():
    """Get the absolute path to the project root directory."""
    script_dir = Path(__file__).parent.absolute()
    return script_dir.parent

def get_dist_dir():
    """Get the dist directory path, creating it if it doesn't exist."""
    dist_dir = get_project_root() / "dist"
    dist_dir.mkdir(exist_ok=True)
    return dist_dir

def get_python_executable():
    """Get the current Python executable path."""
    return sys.executable

def run_check_env(client_type):
    """Run the check-env script for the specified client type."""
    script_dir = Path(__file__).parent.absolute()
    check_env_script = script_dir / "check-env.sh"
    
    try:
        result = subprocess.run(
            [str(check_env_script), client_type],
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print("❌ Environment check failed:")
        print(e.stdout)
        print(e.stderr)
        return False

def generate_claude_desktop_config(project_root, python_exe):
    """Generate Claude Desktop MCP configuration."""
    main_py_path = project_root / "app" / "main.py"
    
    config = {
        "mcpServers": {
            "quilt": {
                "command": python_exe,
                "args": [str(main_py_path)],
                "env": {
                    "PYTHONPATH": str(project_root / "app")
                }
            }
        }
    }
    return config

def generate_vscode_config(project_root):
    """Generate VS Code MCP configuration."""
    config = {
        "mcp": {
            "servers": [
                {
                    "name": "quilt",
                    "transport": {
                        "type": "stdio",
                        "command": get_python_executable(),
                        "args": [str(project_root / "app" / "main.py")],
                        "env": {
                            "PYTHONPATH": str(project_root / "app")
                        }
                    }
                }
            ]
        }
    }
    return config

def generate_http_config():
    """Generate HTTP-based MCP configuration."""
    config = {
        "mcpServers": {
            "quilt": {
                "url": "http://127.0.0.1:8000/mcp",
                "method": "POST"
            }
        }
    }
    return config

def print_claude_instructions(config_path):
    """Print instructions for Claude Desktop setup."""
    print(f"""
📋 CLAUDE DESKTOP SETUP INSTRUCTIONS
{'='*50}

1. Locate your Claude Desktop configuration file:
   • macOS: ~/Library/Application Support/Claude/claude_desktop_config.json
   • Windows: %APPDATA%\\Claude\\claude_desktop_config.json
   • Linux: ~/.config/Claude/claude_desktop_config.json

2. Copy the generated configuration from:
   {config_path}

3. Add or merge the "mcpServers" section into your claude_desktop_config.json

4. Restart Claude Desktop

5. You should see "Quilt MCP Server" available in the tool selection
""")

def print_vscode_instructions(config_path):
    """Print instructions for VS Code setup."""
    print(f"""
📋 VS CODE SETUP INSTRUCTIONS
{'='*50}

1. Install the "MCP Client" extension in VS Code

2. Open VS Code settings (Cmd/Ctrl + ,)

3. Search for "mcp" and find "MCP: Configuration"

4. Copy the configuration from:
   {config_path}

5. Paste into the MCP configuration settings

6. Restart VS Code or reload the window

7. Open the MCP panel to access Quilt tools
""")

def print_http_instructions():
    """Print instructions for HTTP-based setup."""
    print(f"""
📋 HTTP MCP SERVER SETUP INSTRUCTIONS
{'='*50}

1. Start the local MCP server:
   make app
   # Server will run on http://127.0.0.1:8000/mcp

2. For web applications or remote clients, configure your MCP client to connect to:
   • URL: http://127.0.0.1:8000/mcp
   • Method: HTTP POST
   • Content-Type: application/json

3. For remote access via ngrok:
   # Terminal 1: Start server
   make app
   
   # Terminal 2: Expose via ngrok
   make run-app-tunnel
   # Use the ngrok HTTPS URL displayed
""")

def main():
    """Main function to generate configurations and instructions."""
    if len(sys.argv) < 2:
        print("Usage: python make_mcp_config.py <client_type>")
        print("Client types: claude, vscode, http, all")
        sys.exit(1)

    client_type = sys.argv[1].lower()
    project_root = get_project_root()
    dist_dir = get_dist_dir()
    python_exe = get_python_executable()
    
    print(f"🔧 Generating MCP configuration for Quilt MCP Server")
    print(f"📁 Project root: {project_root}")
    print(f"📦 Output directory: {dist_dir}")
    print(f"🐍 Python executable: {python_exe}")
    print()

    if client_type in ["claude", "all"]:
        config = generate_claude_desktop_config(project_root, python_exe)
        config_path = dist_dir / "claude_desktop_config.json"
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"✅ Generated Claude Desktop configuration: {config_path}")
        if client_type == "claude":
            print_claude_instructions(config_path)

    if client_type in ["vscode", "all"]:
        config = generate_vscode_config(project_root)
        config_path = dist_dir / "vscode_mcp_config.json"
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"✅ Generated VS Code configuration: {config_path}")
        if client_type == "vscode":
            print_vscode_instructions(config_path)

    if client_type in ["http", "all"]:
        config = generate_http_config()
        config_path = dist_dir / "http_mcp_config.json"
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"✅ Generated HTTP configuration: {config_path}")
        if client_type == "http":
            print_http_instructions()

    if client_type not in ["claude", "vscode", "http", "all"]:
        print(f"❌ Unknown client type: {client_type}")
        print("Available types: claude, vscode, http, all")
        sys.exit(1)

    # Finally, validate the environment and provide next steps
    print("🔍 Checking environment configuration...")
    if not run_check_env(client_type):
        print("⚠️  Environment validation failed. Please fix the issues above before using the MCP server.")
        sys.exit(1)

if __name__ == "__main__":
    main()
