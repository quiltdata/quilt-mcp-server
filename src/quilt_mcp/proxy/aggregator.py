"""Aggregate native and remote MCP tools."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, List

from mcp.types import Tool as MCPTool

from quilt_mcp.proxy.router import ToolRouter

LOGGER = logging.getLogger(__name__)


class ToolAggregator:
    """Combine native Quilt tools with remote MCP tools."""

    def __init__(self, router: ToolRouter, *, cache_ttl: float = 300.0) -> None:
        self.router = router
        self._cache_ttl = cache_ttl
        self._cache: List[MCPTool] = []
        self._cache_timestamp: float = 0.0
        self._lock = asyncio.Lock()

    async def append_remote_tools(self, native_tools: List[MCPTool]) -> List[MCPTool]:
        """Return combined list of native + remote tools."""
        remote_tools = await self._get_cached_remote_tools()
        return list(native_tools) + list(remote_tools)

    async def _get_cached_remote_tools(self) -> List[MCPTool]:
        now = time.time()
        if self._cache and (now - self._cache_timestamp) < self._cache_ttl:
            return list(self._cache)

        async with self._lock:
            if self._cache and (time.time() - self._cache_timestamp) < self._cache_ttl:
                return list(self._cache)

            refreshed: List[MCPTool] = []
            for server in self.router.available_servers():
                try:
                    tools = await server.client.list_tools()
                except Exception as exc:
                    LOGGER.warning("Failed to fetch tools from %s: %s", server.config.id, exc)
                    continue

                display_name = self.router.server_display_name(server.config.id)
                for tool in tools:
                    mcptool = self._convert_remote_tool(server.config.id, display_name, tool)
                    if mcptool is not None:
                        refreshed.append(mcptool)

            self._cache = refreshed
            self._cache_timestamp = time.time()
            return list(self._cache)

    def _convert_remote_tool(
        self,
        server_id: str,
        display_name: str,
        tool: Dict[str, object],
    ) -> MCPTool | None:
        """Convert remote tool dict into MCPTool with namespace prefix."""
        remote_name = tool.get("name")
        if not isinstance(remote_name, str) or not remote_name:
            LOGGER.debug("Skipping remote tool with invalid name from %s: %r", server_id, tool)
            return None

        description = tool.get("description")
        if isinstance(description, str) and description:
            description = f"[{display_name}] {description}"
        else:
            description = f"[{display_name}]"

        input_schema = tool.get("inputSchema") or tool.get("input_schema") or {"type": "object", "properties": {}}
        output_schema = tool.get("outputSchema") or tool.get("output_schema")
        annotations = tool.get("annotations")

        try:
            return MCPTool(
                name=f"{server_id}__{remote_name}",
                description=description,
                inputSchema=input_schema,
                outputSchema=output_schema,
                annotations=annotations,
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            LOGGER.warning("Failed to convert remote tool %s from %s: %s", remote_name, server_id, exc)
            return None
