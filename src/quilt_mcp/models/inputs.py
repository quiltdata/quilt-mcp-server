"""Pydantic models for MCP tool input parameters.

This module defines rigorous type models for tool inputs,
ensuring MCP generates useful input schemas and provides
proper validation for tool parameters.

NOTE: Most tool parameters have been flattened (v0.10.0+) and no longer use
Params classes. This file is retained for legacy complex types that may be
needed in nested structures.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, Field, conint, constr, field_validator


# ============================================================================
# Legacy Placeholder - All Params classes removed after flattening
# ============================================================================
# This file previously contained Params classes for all tools, but these have
# been removed as part of the parameter flattening initiative (v0.10.0).
# Tools now use flattened parameters directly via typing.Annotated with Field().
#
# If you need to add new complex nested types (e.g., for list[dict] parameters),
# add them here. Otherwise, use flattened parameters in tool function signatures.
# ============================================================================
