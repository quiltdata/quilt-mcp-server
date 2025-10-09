from quilt_mcp.config.remote_servers import RemoteServerConfig
from quilt_mcp.proxy.aggregator import ToolAggregator
from quilt_mcp.proxy.client import RemoteMCPClient
from quilt_mcp.proxy.router import RemoteServer, ToolRouter


def test_tool_router_parse_namespaced_tool():
    router = ToolRouter([])
    server_id, tool_name = router.parse_tool_name("benchling__get_entries")
    assert server_id == "benchling"
    assert tool_name == "get_entries"

    server_id, tool_name = router.parse_tool_name("search_packages")
    assert server_id is None
    assert tool_name == "search_packages"


def test_tool_aggregator_convert_remote_tool():
    router = ToolRouter([])
    aggregator = ToolAggregator(router)

    tool = aggregator._convert_remote_tool(
        "benchling",
        "Benchling",
        {
            "name": "get_projects",
            "description": "List Benchling projects",
            "inputSchema": {"type": "object", "properties": {}},
        },
    )

    assert tool is not None
    assert tool.name == "benchling__get_projects"
    assert tool.description.startswith("[Benchling]")


def test_tool_router_convert_remote_result():
    router = ToolRouter([])
    payload = {"content": [{"type": "text", "text": "Hello!"}]}
    result = router._convert_remote_result(payload, "benchling", "get_projects")
    assert isinstance(result, list)
    assert result[0]["type"] == "text"
    assert result[0]["text"] == "Hello!"
