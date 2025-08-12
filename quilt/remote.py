# Import the mcp instance and all tools from the quilt package
from . import mcp

if __name__ == "__main__":
    # Run the MCP server with streamable HTTP transport
    mcp.run(transport="streamable-http")
