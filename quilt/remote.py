import importlib.util
from pathlib import Path

# Import the mcp instance from the local quilt.py file
spec = importlib.util.spec_from_file_location("quilt_server", Path(__file__).parent / "quilt.py")
if spec and spec.loader:
    quilt_server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(quilt_server)
    mcp = quilt_server.mcp
else:
    raise ImportError("Could not load quilt.py module")

if __name__ == "__main__":
    # Run the MCP server with streamable HTTP transport
    mcp.run(transport="streamable-http")
