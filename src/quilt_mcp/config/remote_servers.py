"""Configuration for remote MCP servers routed through the proxy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(slots=True)
class RemoteServerConfig:
    """Remote MCP server configuration."""

    id: str
    name: str
    endpoint: str
    auth_type: str = "none"
    enabled: bool = True


def get_remote_server_configs() -> List[RemoteServerConfig]:
    """Return configured remote MCP servers (MVP: Benchling only)."""

    return [
        RemoteServerConfig(
            id="benchling",
            name="Benchling",
            endpoint="https://demo.quiltdata.com/benchling/mcp",
            auth_type="proxy",
            enabled=True,
        ),
    ]
