"""Quilt3-specific operations for the MCP server.

This module contains operations that interact with Quilt3 services
but are isolated from global quilt3 state. All operations accept
explicit configuration parameters instead of relying on global
quilt3.config() or quilt3.logged_in() state.

Design principles:
- Configuration-driven execution (no global state dependencies)
- Consistent result formatting for MCP compatibility
- Proper error handling and categorization
- Isolated testing capabilities

Available operations:
- auth.check_auth_status: Check authentication status with explicit config
"""

from __future__ import annotations

__all__ = []