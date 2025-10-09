"""
Vega-Lite Generator for Quilt Package Visualization

This module generates Vega-Lite visualization specifications.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class VegaLiteGenerator:
    """Generates Vega-Lite visualization specifications."""

    SCHEMA_URL = "https://vega.github.io/schema/vega-lite/v5.json"

    def __init__(self) -> None:
        self.default_color = "#1f77b4"

    def create_bar_chart(
        self,
        data: List[Dict[str, Any]],
        x_field: str,
        y_field: str,
        title: str,
        description: Optional[str] = None,
        color_field: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a Vega-Lite bar chart specification."""
        spec: Dict[str, Any] = {
            "$schema": self.SCHEMA_URL,
            "description": description or title,
            "title": title,
            "data": {"values": data},
            "mark": {"type": "bar"},
            "encoding": {
                "x": {"field": x_field, "type": "nominal", "sort": "-y"},
                "y": {"field": y_field, "type": "quantitative"},
                "tooltip": [
                    {"field": x_field, "type": "nominal"},
                    {"field": y_field, "type": "quantitative"},
                ],
            },
        }
        if color_field:
            spec["encoding"]["color"] = {"field": color_field, "type": "nominal"}
        return spec

    def create_line_chart(
        self,
        data: List[Dict[str, Any]],
        x_field: str,
        y_field: str,
        title: str,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a Vega-Lite line chart specification."""
        return {
            "$schema": self.SCHEMA_URL,
            "description": description or title,
            "title": title,
            "data": {"values": data},
            "mark": {"type": "line", "point": True},
            "encoding": {
                "x": {"field": x_field, "type": "temporal"},
                "y": {"field": y_field, "type": "quantitative"},
                "tooltip": [
                    {"field": x_field, "type": "temporal"},
                    {"field": y_field, "type": "quantitative"},
                ],
            },
        }

    def create_histogram(
        self,
        data: List[Dict[str, Any]],
        field: str,
        title: str,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a Vega-Lite histogram specification."""
        return {
            "$schema": self.SCHEMA_URL,
            "description": description or title,
            "title": title,
            "data": {"values": data},
            "mark": "bar",
            "encoding": {
                "x": {"field": field, "bin": True},
                "y": {"aggregate": "count", "type": "quantitative"},
                "tooltip": [
                    {"field": field, "type": "quantitative", "bin": True},
                    {"aggregate": "count", "type": "quantitative"},
                ],
            },
        }

    def integrate_data_sources(self, spec: Dict[str, Any], package_files: List[str]) -> Dict[str, Any]:
        """Integrate package data references into a Vega-Lite spec."""
        if not package_files:
            return spec
        spec.setdefault("usermeta", {})
        spec["usermeta"]["quilt"] = {"data_sources": package_files}
        return spec

    def optimize_for_quilt(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply light-weight optimizations for Quilt.

        Currently this simply ensures tooltips are enabled.
        """
        encoding = spec.setdefault("encoding", {})
        if "tooltip" not in encoding:
            encoding["tooltip"] = [{"field": field, "type": "nominal"} for field in encoding.keys()]
        return spec
