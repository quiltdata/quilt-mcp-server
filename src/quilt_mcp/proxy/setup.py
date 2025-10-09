"""Setup helpers to integrate the proxy router with FastMCP."""

from __future__ import annotations

import types
from typing import Callable, List, Tuple

from fastmcp import FastMCP
from mcp.types import Tool as MCPTool

from quilt_mcp.config.remote_servers import get_remote_server_configs
from quilt_mcp.proxy.aggregator import ToolAggregator
from quilt_mcp.proxy.router import ToolRouter


def setup_proxy(mcp: FastMCP) -> Tuple[ToolRouter, ToolAggregator]:
    """Attach proxy handlers for tools/list and tools/call."""

    router = ToolRouter(get_remote_server_configs())
    aggregator = ToolAggregator(router)

    original_list_tools = mcp._mcp_list_tools
    original_call_tool = mcp._mcp_call_tool

    async def proxied_list_tools(self: FastMCP) -> List[MCPTool]:
        native = await original_list_tools()
        return await aggregator.append_remote_tools(native)

    async def proxied_call_tool(self: FastMCP, key: str, arguments: dict) -> list | tuple:
        server_id, remote_name = router.parse_tool_name(key)
        if server_id:
            return await router.call_remote_tool(server_id, remote_name, arguments or {})
        return await original_call_tool(key, arguments)

    mcp._mcp_list_tools = types.MethodType(proxied_list_tools, mcp)
    mcp._mcp_call_tool = types.MethodType(proxied_call_tool, mcp)

    # Expose router/aggregator for diagnostics or testing
    setattr(mcp, "_proxy_router", router)
    setattr(mcp, "_proxy_aggregator", aggregator)

    return router, aggregator
