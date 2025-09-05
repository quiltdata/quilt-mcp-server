"""
Automatic Visualization Generation for Quilt Packages

This module provides automatic visualization generation for Quilt packages,
including support for ECharts, Vega-Lite, IGV, and other visualization types.
"""

from .engine import VisualizationEngine
from .generators.echarts import EChartsGenerator
from .generators.vega_lite import VegaLiteGenerator
from .generators.igv import IGVGenerator
from .generators.matplotlib import MatplotlibGenerator
from .generators.perspective import PerspectiveGenerator
from .analyzers.data_analyzer import DataAnalyzer
from .analyzers.file_analyzer import FileAnalyzer
from .analyzers.genomic_analyzer import GenomicAnalyzer
from .layouts.grid_layout import GridLayout
from .utils.data_processing import DataProcessor
from .utils.file_utils import FileUtils

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

__version__ = "0.1.0"
