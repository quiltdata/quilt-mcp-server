"""Lazy exports for visualization generators."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "EChartsGenerator",
    "VegaLiteGenerator",
    "IGVGenerator",
    "MatplotlibGenerator",
    "PerspectiveGenerator",
]

_LAZY_IMPORTS = {
    "EChartsGenerator": ".echarts",
    "VegaLiteGenerator": ".vega_lite",
    "IGVGenerator": ".igv",
    "MatplotlibGenerator": ".matplotlib",
    "PerspectiveGenerator": ".perspective",
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

    module = importlib.import_module(_LAZY_IMPORTS[name], __name__)
    attr = getattr(module, name)
    globals()[name] = attr
    return attr


def __dir__() -> list[str]:
    return sorted(list(__all__) + [attr for attr in globals() if not attr.startswith("_")])
