"""
MCP-Use based proxy for remote MCP servers.

This module provides a hybrid approach:
- Native Quilt tools remain unchanged
- Remote MCP servers (Benchling, BioContextAI) are handled by mcp-use
"""

import logging
from typing import Any

from mcp_use import MCPClient

logger = logging.getLogger(__name__)


class MCPUseProxy:
    """
    Proxy that uses mcp-use library to manage remote MCP servers.
    
    Benefits over custom implementation:
    - Automatic connection management and retries
    - Built-in session pooling
    - Community-maintained and updated
    - Handles SSE and stdio transports
    """
    
    def __init__(self):
        self.remote_client: MCPClient | None = None
        self._initialized = False
        
    async def initialize(self):
        """Initialize remote MCP client with configured servers."""
        if self._initialized:
            return
            
        # Configuration for remote servers
        config = {
            "mcpServers": {
                # Benchling MCP (same domain, no CORS)
                "benchling": {
                    "url": "https://demo.quiltdata.com/benchling/mcp",
                    "transport": "sse",
                },
                # BioContextAI MCP (remote, may have CORS issues from browser)
                "biocontext": {
                    "url": "https://mcp.biocontext.ai/mcp",
                    "transport": "sse",
                },
            }
        }
        
        logger.info("🔌 Initializing mcp-use client with remote servers")
        self.remote_client = MCPClient.from_dict(config)
        
        try:
            await self.remote_client.create_all_sessions()
            logger.info("✅ All remote MCP sessions created successfully")
            self._initialized = True
        except Exception as e:
            logger.error(f"❌ Failed to create remote MCP sessions: {e}")
            raise
    
    async def list_remote_tools(self) -> list[dict[str, Any]]:
        """
        List all tools from remote MCP servers.
        
        Returns:
            List of tools with namespace prefixes (e.g., benchling__get_entries)
        """
        if not self._initialized:
            await self.initialize()
            
        try:
            # Get all sessions (one per server)
            sessions = self.remote_client.get_sessions()
            all_tools = []
            
            for server_name, session in sessions.items():
                try:
                    logger.info(f"📋 Listing tools from {server_name}")
                    
                    # List tools from this server
                    tools_response = await session.list_tools()
                    
                    # Add namespace prefix to each tool
                    for tool in tools_response.tools:
                        tool_dict = {
                            "name": f"{server_name}__{tool.name}",
                            "description": f"[{server_name.title()}] {tool.description or ''}",
                            "inputSchema": tool.inputSchema,
                        }
                        all_tools.append(tool_dict)
                    
                    logger.info(f"✅ Found {len(tools_response.tools)} tools from {server_name}")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Failed to list tools from {server_name}: {e}")
                    # Continue with other servers
                    
            return all_tools
            
        except Exception as e:
            logger.error(f"❌ Error listing remote tools: {e}")
            return []
    
    async def call_remote_tool(
        self, 
        tool_name: str, 
        arguments: dict[str, Any]
    ) -> Any:
        """
        Call a tool on a remote MCP server.
        
        Args:
            tool_name: Namespaced tool name (e.g., "benchling__get_entries")
            arguments: Tool arguments
            
        Returns:
            Tool execution result
            
        Raises:
            ValueError: If tool name doesn't contain namespace
            Exception: If tool call fails
        """
        if not self._initialized:
            await self.initialize()
            
        # Parse namespace
        if "__" not in tool_name:
            raise ValueError(f"Tool name must be namespaced: {tool_name}")
            
        server_name, actual_tool_name = tool_name.split("__", 1)
        
        logger.info(f"🔧 Calling {actual_tool_name} on {server_name} with args: {arguments}")
        
        try:
            # Get the session for this server
            session = self.remote_client.get_session(server_name)
            
            # Call the tool
            result = await session.call_tool(
                name=actual_tool_name,
                arguments=arguments
            )
            
            logger.info(f"✅ Tool call successful: {actual_tool_name}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Tool call failed for {tool_name}: {e}")
            raise
    
    async def close(self):
        """Close all remote MCP sessions."""
        if self.remote_client and self._initialized:
            logger.info("🔌 Closing all remote MCP sessions")
            await self.remote_client.close_all_sessions()
            self._initialized = False


# Global instance
_proxy_instance: MCPUseProxy | None = None


def get_mcp_use_proxy() -> MCPUseProxy:
    """Get or create the global MCP-Use proxy instance."""
    global _proxy_instance
    if _proxy_instance is None:
        _proxy_instance = MCPUseProxy()
    return _proxy_instance

