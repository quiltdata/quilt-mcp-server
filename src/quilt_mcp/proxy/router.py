"""Tool routing logic for remote MCP servers."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from fastmcp.exceptions import ToolError

from quilt_mcp.config.remote_servers import RemoteServerConfig, get_remote_server_configs
from quilt_mcp.proxy.client import RemoteMCPClient, RemoteMCPError

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class RemoteServer:
    """Runtime representation of a remote MCP server."""

    config: RemoteServerConfig
    client: RemoteMCPClient


class ToolRouter:
    """Route namespaced tools to remote MCP servers."""

    def __init__(self, configs: Sequence[RemoteServerConfig] | None = None):
        configs = configs or get_remote_server_configs()
        self.servers: Dict[str, RemoteServer] = {}
        for cfg in configs:
            if not cfg.enabled:
                continue
            self.servers[cfg.id] = RemoteServer(
                config=cfg,
                client=RemoteMCPClient(endpoint=cfg.endpoint, server_id=cfg.id),
            )

    def available_servers(self) -> Iterable[RemoteServer]:
        """Return iterable of configured remote servers."""
        return self.servers.values()

    def parse_tool_name(self, tool_name: str) -> Tuple[Optional[str], str]:
        """Split namespaced tool names into server prefix and tool name."""
        if "__" in tool_name:
            prefix, actual = tool_name.split("__", 1)
            if prefix in self.servers and actual:
                return prefix, actual
        return None, tool_name

    async def call_remote_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: Dict[str, object],
    ) -> List[Dict[str, object]] | Tuple[List[Dict[str, object]], Dict[str, object]]:
        """Execute a tool on a remote MCP server and convert the response."""
        if server_id not in self.servers:
            raise ToolError(f"Unknown remote server '{server_id}'")

        remote = self.servers[server_id]
        try:
            remote_result = await remote.client.call_tool(tool_name, arguments)
        except RemoteMCPError as exc:
            LOGGER.warning("Remote tool %s on %s failed: %s", tool_name, server_id, exc)
            raise ToolError(str(exc)) from exc

        return self._convert_remote_result(remote_result, server_id, tool_name)

    def _convert_remote_result(
        self,
        result: Dict[str, object],
        server_id: str,
        tool_name: str,
    ) -> List[Dict[str, object]] | Tuple[List[Dict[str, object]], Dict[str, object]]:
        """Convert remote MCP response into FastMCP content blocks."""
        content = result.get("content")
        structured = (
            result.get("structuredContent")
            or result.get("structured_output")
            or result.get("structuredResult")
            or result.get("data")
        )

        blocks: List[Dict[str, object]] = []
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type"):
                    blocks.append(item)
                else:
                    blocks.append({"type": "text", "text": str(item)})
        elif isinstance(content, dict):
            if content.get("type"):
                blocks.append(content)
            else:
                blocks.append({"type": "text", "text": json.dumps(content, default=str)})
        else:
            # Fallback to structured data or string representation
            fallback_text = None
            if structured is not None:
                fallback_text = json.dumps(structured, default=str)
            elif content is not None:
                fallback_text = str(content)
            if fallback_text:
                blocks.append({"type": "text", "text": fallback_text})
            else:
                blocks.append(
                    {
                        "type": "text",
                        "text": f"[{server_id}] {tool_name} finished with no content",
                    }
                )

        structured_dict: Dict[str, object] | None = None
        if isinstance(structured, dict):
            structured_dict = structured
        elif structured is not None:
            structured_dict = {"result": structured}

        if structured_dict is not None:
            return list(blocks), structured_dict
        return list(blocks)

    async def shutdown(self) -> None:
        """Close all remote client sessions."""
        await asyncio.gather(
            *(server.client.close() for server in self.servers.values()),
            return_exceptions=True,
        )

    def server_display_name(self, server_id: str) -> str:
        """Return human-friendly server name."""
        remote = self.servers.get(server_id)
        if not remote:
            return server_id
        return remote.config.name or server_id.title()
