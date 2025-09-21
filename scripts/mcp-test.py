#!/usr/bin/env python3
"""
Modern MCP endpoint testing tool.

Replaces the legacy bash script with a cleaner Python implementation
using requests library for HTTP handling and proper JSON schema validation.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import yaml
from jsonschema import validate, ValidationError


class MCPTester:
    """MCP endpoint testing client with JSON-RPC support."""
    
    def __init__(self, endpoint: str, verbose: bool = False):
        self.endpoint = endpoint
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream'
        })
        self.request_id = 1
        
    def _log(self, message: str, level: str = "INFO") -> None:
        """Log message with timestamp."""
        if level == "DEBUG" and not self.verbose:
            return
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        prefix = "🔍" if level == "DEBUG" else "ℹ️" if level == "INFO" else "❌"
        print(f"[{timestamp}] {prefix} {message}")
        
    def _make_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make JSON-RPC request to MCP endpoint."""
        request_data = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method
        }
        if params:
            request_data["params"] = params
            
        self.request_id += 1
        
        self._log(f"Making request: {method}", "DEBUG")
        if self.verbose and params:
            self._log(f"Params: {json.dumps(params, indent=2)}", "DEBUG")
            
        try:
            response = self.session.post(
                self.endpoint,
                json=request_data,
                timeout=10
            )
            response.raise_for_status()
            
            result = response.json()
            self._log(f"Response: {json.dumps(result, indent=2)}", "DEBUG")
            
            if "error" in result:
                raise Exception(f"JSON-RPC error: {result['error']}")
                
            return result.get("result", {})
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"HTTP request failed: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response: {e}")
    
    def initialize(self) -> Dict[str, Any]:
        """Initialize MCP session."""
        self._log("Initializing MCP session...")
        
        params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "mcp-test",
                "version": "1.0.0"
            }
        }
        
        result = self._make_request("initialize", params)
        self._log("✅ Session initialized successfully")
        return result
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from MCP server."""
        self._log("Querying available tools...")
        
        result = self._make_request("tools/list")
        tools = result.get("tools", [])
        
        self._log(f"✅ Found {len(tools)} tools")
        return tools
    
    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Call a specific tool."""
        self._log(f"Calling tool: {name}")
        
        params = {"name": name}
        if arguments:
            params["arguments"] = arguments
            
        result = self._make_request("tools/call", params)
        self._log(f"✅ Tool {name} executed successfully")
        return result


def load_test_config(config_path: Path) -> Dict[str, Any]:
    """Load test configuration from YAML file."""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"❌ Test config not found: {config_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"❌ Invalid YAML config: {e}")
        sys.exit(1)


def run_tools_test(tester: MCPTester, config: Dict[str, Any], specific_tool: Optional[str] = None) -> bool:
    """Run comprehensive tools test."""
    test_tools = config.get("test_tools", {})
    
    if specific_tool:
        if specific_tool not in test_tools:
            print(f"❌ Tool '{specific_tool}' not found in test config")
            return False
        test_tools = {specific_tool: test_tools[specific_tool]}
    
    success_count = 0
    total_count = len(test_tools)
    
    print(f"\n🧪 Running tools test ({total_count} tools)...")
    
    for tool_name, test_config in test_tools.items():
        try:
            print(f"\n--- Testing tool: {tool_name} ---")
            
            # Get test arguments
            test_args = test_config.get("arguments", {})
            
            # Call the tool
            result = tester.call_tool(tool_name, test_args)
            
            # Validate response if schema provided
            if "response_schema" in test_config:
                validate(result, test_config["response_schema"])
                tester._log("✅ Response schema validation passed")
            
            success_count += 1
            print(f"✅ {tool_name}: PASSED")
            
        except Exception as e:
            print(f"❌ {tool_name}: FAILED - {e}")
    
    print(f"\n📊 Test Results: {success_count}/{total_count} tools passed")
    return success_count == total_count


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Modern MCP endpoint testing tool",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("endpoint", help="MCP endpoint URL to test")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-t", "--tools-test", action="store_true", 
                       help="Run tools test with test configurations")
    parser.add_argument("-T", "--test-tool", metavar="TOOL_NAME",
                       help="Test specific tool by name")
    parser.add_argument("--list-tools", action="store_true",
                       help="List available tools from MCP server")
    parser.add_argument("--config", type=Path, 
                       default=Path(__file__).parent.parent / "tests" / "fixtures" / "mcp-test.yaml",
                       help="Path to test configuration file")
    
    args = parser.parse_args()
    
    # Create tester instance
    tester = MCPTester(args.endpoint, args.verbose)
    
    try:
        # Initialize session
        tester.initialize()
        
        if args.list_tools:
            # List available tools
            tools = tester.list_tools()
            print(f"\n📋 Available Tools ({len(tools)}):")
            for tool in tools:
                print(f"  • {tool.get('name', 'Unknown')}: {tool.get('description', 'No description')}")
            return
        
        if args.tools_test or args.test_tool:
            # Load test configuration
            config = load_test_config(args.config)
            
            # Run tools test
            success = run_tools_test(tester, config, args.test_tool)
            sys.exit(0 if success else 1)
        
        # Default: basic connectivity test
        tools = tester.list_tools()
        print(f"✅ Successfully connected to MCP endpoint")
        print(f"📋 Server has {len(tools)} available tools")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()