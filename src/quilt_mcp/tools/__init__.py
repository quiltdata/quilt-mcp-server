"""Tool package with lazy sub-module loading."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "auth",
    "buckets",
    "packaging",
    "permissions",
    "metadata_examples",
    "quilt_summary",
    "graphql",
    "search",
    "athena_glue",
    "tabulator",
    "workflow_orchestration",
    "package_visualization",
    "governance",
]

_LAZY_IMPORTS = {
    "auth": ".auth",
    "buckets": ".buckets",
    "packaging": ".packaging",
    "permissions": ".permissions",
    "metadata_examples": ".metadata_examples",
    "quilt_summary": ".quilt_summary",
    "graphql": ".graphql",
    "search": ".search",
    "athena_glue": ".athena_glue",
    "tabulator": ".tabulator",
    "workflow_orchestration": ".workflow_orchestration",
    "package_visualization": ".package_visualization",
    "governance": ".governance",
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

    module = importlib.import_module(_LAZY_IMPORTS[name], __name__)
    globals()[name] = module
    return module


def __dir__() -> list[str]:
    dynamic = [attr for attr in globals() if not attr.startswith("_")]
    return sorted(set(__all__ + dynamic))
