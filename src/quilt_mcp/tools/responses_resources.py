"""Resource-access response models extracted from tools.responses."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from .responses_base import ErrorResponse, SuccessResponse


class ResourceMetadata(BaseModel):
    """Metadata for a single resource in discovery mode."""

    uri: str = Field(..., description="Resource URI pattern (may contain {variables})")
    name: str = Field(..., description="Human-readable resource name")
    description: str = Field(..., description="Functional description")
    is_template: bool = Field(..., description="True if URI contains template variables")
    template_variables: list[str] = Field(
        default_factory=list, description="List of variable names in URI (empty if not templated)"
    )
    requires_admin: bool = Field(..., description="True if admin privileges required")
    category: str = Field(..., description="Resource category (auth, admin, etc.)")


class GetResourceSuccess(SuccessResponse):
    """Successful resource access response."""

    uri: str = Field(..., description="The resolved URI (expanded if templated)")
    resource_name: str = Field(..., description="Human-readable name of the resource")
    data: dict[str, Any] = Field(..., description="The actual resource data")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="When the data was retrieved"
    )
    mime_type: str = Field(default="application/json", description="Resource MIME type")


class GetResourceError(ErrorResponse):
    """Failed resource access response."""

    valid_uris: Optional[list[str]] = Field(default=None, description="Available URIs (for invalid URI errors)")
