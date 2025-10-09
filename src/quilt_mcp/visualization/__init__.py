"""Visualization package with lazy exports."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "VisualizationEngine",
    "EChartsGenerator",
    "VegaLiteGenerator",
    "IGVGenerator",
    "MatplotlibGenerator",
    "PerspectiveGenerator",
    "DataAnalyzer",
    "FileAnalyzer",
    "GenomicAnalyzer",
    "GridLayout",
    "DataProcessor",
    "FileUtils",
]

_LAZY_IMPORTS = {
    "VisualizationEngine": ".engine",
    "EChartsGenerator": ".generators.echarts",
    "VegaLiteGenerator": ".generators.vega_lite",
    "IGVGenerator": ".generators.igv",
    "MatplotlibGenerator": ".generators.matplotlib",
    "PerspectiveGenerator": ".generators.perspective",
    "DataAnalyzer": ".analyzers.data_analyzer",
    "FileAnalyzer": ".analyzers.file_analyzer",
    "GenomicAnalyzer": ".analyzers.genomic_analyzer",
    "GridLayout": ".layouts.grid_layout",
    "DataProcessor": ".utils.data_processing",
    "FileUtils": ".utils.file_utils",
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


__version__ = "0.1.0"
