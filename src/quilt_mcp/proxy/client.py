"""HTTP client for communicating with remote MCP servers."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from importlib import metadata
from typing import Any, Dict, List, Optional

import httpx

from quilt_mcp.runtime import get_active_token, get_request_metadata

LOGGER = logging.getLogger(__name__)

try:
    _PACKAGE_VERSION = metadata.version("quilt-mcp-server")
except metadata.PackageNotFoundError:  # pragma: no cover - fallback when running from source tree
    _PACKAGE_VERSION = "0.0.0"

MCP_PROTOCOL_VERSION = "2024-11-05"


class RemoteMCPError(RuntimeError):
    """Remote MCP communication error."""


@dataclass(slots=True)
class RemoteServerInfo:
    """Simple container for remote server metadata."""

    name: str | None = None
    version: str | None = None
    capabilities: Dict[str, Any] | None = None


class RemoteMCPClient:
    """Async HTTP client for remote MCP servers."""

    def __init__(
        self,
        endpoint: str,
        server_id: str,
        *,
        timeout: float = 30.0,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.server_id = server_id
        self._timeout = timeout
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10.0))
        self._initialize_lock = asyncio.Lock()
        self._initialized = False
        self._server_info: RemoteServerInfo | None = None

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        await self._client.aclose()

    async def ensure_initialized(self) -> RemoteServerInfo | None:
        """Perform MCP initialize handshake once per client."""
        if self._initialized:
            return self._server_info

        async with self._initialize_lock:
            if self._initialized:  # double-checked
                return self._server_info

            payload = {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "clientInfo": {
                    "name": "Quilt MCP Proxy",
                    "version": _PACKAGE_VERSION,
                },
            }

            try:
                response = await self._request("initialize", payload)
                result = response.get("result") or {}
                self._server_info = RemoteServerInfo(
                    name=result.get("serverInfo", {}).get("name"),
                    version=result.get("serverInfo", {}).get("version"),
                    capabilities=result.get("capabilities"),
                )
            except Exception as exc:  # pragma: no cover - remote initialize optional
                LOGGER.debug("Remote initialize failed for %s: %s", self.server_id, exc)
                self._server_info = None
            finally:
                self._initialized = True
        return self._server_info

    async def list_tools(self) -> List[Dict[str, Any]]:
        """Fetch list of tools from remote server."""
        await self.ensure_initialized()
        response = await self._request("tools/list", {})
        result = response.get("result") or {}
        tools = result.get("tools") or []
        if not isinstance(tools, list):
            raise RemoteMCPError(f"Remote server {self.server_id} returned invalid tools payload")
        return tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool on the remote server and return the raw result."""
        await self.ensure_initialized()
        response = await self._request(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments or {},
            },
        )

        if "result" in response:
            return response["result"]

        if "error" in response:
            raise RemoteMCPError(f"Remote tool error: {response['error']}")

        raise RemoteMCPError(f"Unexpected remote response: {response}")

    async def _request(self, method: str, params: Dict[str, Any] | None) -> Dict[str, Any]:
        """Send JSON-RPC request to remote server."""
        payload = {
            "jsonrpc": "2.0",
            "id": method,
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        headers = self._build_headers()

        LOGGER.debug("Proxy → %s: %s", self.server_id, method)
        response = await self._client.post(
            self.endpoint,
            json=payload,
            headers=headers,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RemoteMCPError(
                f"Remote server {self.server_id} returned status {response.status_code}: {response.text[:200]}"
            ) from exc

        text = response.text.strip()
        if not text:
            raise RemoteMCPError(f"Remote server {self.server_id} returned empty response")

        return self._parse_response(text)

    def _build_headers(self) -> Dict[str, str]:
        """Build headers for outgoing requests."""
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "mcp-protocol-version": MCP_PROTOCOL_VERSION,
            "User-Agent": f"quilt-mcp-proxy/{_PACKAGE_VERSION}",
        }

        token = get_active_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        metadata = get_request_metadata()
        benchling_key = metadata.get("benchling_api_key")
        if benchling_key:
            headers["X-Benchling-API-Key"] = benchling_key

        session_id = metadata.get("session_id")
        if session_id:
            headers["X-Session-ID"] = session_id

        return headers

    def _parse_response(self, text: str) -> Dict[str, Any]:
        """Parse JSON or SSE-formatted response payload."""
        if text.startswith("data:") or "event:" in text:
            # Server-Sent Events format - concatenate data lines
            data_segments = []
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("data:"):
                    data_segments.append(line[5:].strip())
            if not data_segments:
                raise RemoteMCPError("Malformed SSE response from remote server")
            text = "".join(data_segments)

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise RemoteMCPError(f"Failed to parse response from {self.server_id}: {text[:200]}") from exc
