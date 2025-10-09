"""
Perspective Generator for Quilt Package Visualization

This module generates interactive Perspective configurations that can be
rendered by the Quilt catalog.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class PerspectiveGenerator:
    """Generates interactive data grid configurations for Perspective."""

    DEFAULT_PLUGIN = "Datagrid"
    DEFAULT_THEME = "Material Light"

    def __init__(self) -> None:
        self.default_columns: List[str] = []

    def create_grid_config(
        self,
        dataset_name: str,
        data_path: str,
        approx_size: int = 0,
        plugin: str = DEFAULT_PLUGIN,
        theme: str = DEFAULT_THEME,
        columns: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Build a Perspective configuration for a tabular dataset.

        Args:
            dataset_name: Friendly dataset name (used in titles).
            data_path: Relative path to the data object within the package.
            approx_size: Approximate dataset size in bytes (for metadata only).
            plugin: Perspective plugin to use (Datagrid, Hypergrid, etc.).
            theme: Visual theme for the Perspective view.
            columns: Optional list of column names when known.

        Returns:
            Dictionary describing the Perspective view configuration.
        """
        column_list = list(columns) if columns else self.default_columns
        return {
            "title": f"{dataset_name} (Perspective)",
            "plugin": plugin,
            "theme": theme,
            "settings": True,
            "group_by": [],
            "split_by": [],
            "sort": [],
            "filter": [],
            "expressions": [],
            "columns": column_list,
            "data": {
                "type": "table",
                "source": data_path,
                "format": "auto",
                "approximate_size": approx_size,
            },
        }
