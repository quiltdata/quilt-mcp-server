#!/usr/bin/env python3
"""Test the Quilt MCP client connection."""

import os
import sys
import json
import asyncio
from mcp import ClientSession

async def test_connection():
    """Test connection to the Quilt MCP server asynchronously."""
    print("Testing connection to Quilt MCP server...")
    
    try:
        # Connect to the server using the "quilt" tool
        session = ClientSession("quilt")
        await session.initialize()
        
        # List available tools
        result = await session.call("tools/list", {})
        
        print(f"Connection successful!")
        print(f"Available tools: {json.dumps(result, indent=2)}")
        
        await session.shutdown()
        return 0
    except Exception as e:
        print(f"Error connecting to Quilt MCP server: {e}", file=sys.stderr)
        return 1

def main():
    """Run the async test."""
    return asyncio.run(test_connection())

if __name__ == "__main__":
    sys.exit(main())
