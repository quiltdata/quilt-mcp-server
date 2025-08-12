# Import the mcp instance and all tools from the quilt package
import sys
from pathlib import Path

# Add the parent directory to sys.path to allow importing quilt
sys.path.insert(0, str(Path(__file__).parent.parent))

from quilt import mcp

# Export the server object for fastmcp dev
server = mcp

if __name__ == "__main__":
    # Run the MCP server with streamable HTTP transport
    mcp.run(transport="streamable-http")
