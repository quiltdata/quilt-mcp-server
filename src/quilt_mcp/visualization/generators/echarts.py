"""
ECharts Generator for Quilt Package Visualization

This module generates ECharts chart configurations for various data types
including bar charts, line charts, scatter plots, and heatmaps.
"""

import pandas as pd
from typing import Dict, List, Any, Optional
import json


class EChartsGenerator:
    """Generates ECharts chart configurations for data visualization."""

    def __init__(self):
        """Initialize the ECharts generator."""
        self.default_colors = [
            "#1f77b4",
            "#ff7f0e",
            "#2ca02c",
            "#d62728",
            "#9467bd",
            "#8c564b",
            "#e377c2",
            "#7f7f7f",
            "#bcbd22",
            "#17becf",
        ]

    def create_bar_chart(
        self,
        data: pd.DataFrame,
        categories: str,
        values: str,
        title: Optional[str] = None,
        color_scheme: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a bar chart configuration.

        Args:
            data: Pandas DataFrame with data
            categories: Column name for categories
            values: Column name for values
            title: Chart title
            color_scheme: List of colors for bars

        Returns:
            ECharts configuration dictionary
        """
        if data is None or data.empty:
            return self._create_empty_chart("Bar Chart")

        # Prepare data
        chart_data = data.groupby(categories)[values].sum().reset_index()
        chart_data = chart_data.sort_values(values, ascending=False)

        # Limit to top 20 categories for readability
        if len(chart_data) > 20:
            chart_data = chart_data.head(20)

        categories_list = chart_data[categories].tolist()
        values_list = chart_data[values].tolist()

        # Create chart configuration
        config = {
            "title": {
                "text": title or f"{values} by {categories}",
                "left": "center",
                "textStyle": {"fontSize": 16, "fontWeight": "bold"},
            },
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "xAxis": {
                "type": "category",
                "data": categories_list,
                "axisLabel": {"rotate": 45, "interval": 0},
            },
            "yAxis": {"type": "value", "name": values},
            "series": [
                {
                    "name": values,
                    "type": "bar",
                    "data": values_list,
                    "itemStyle": {"color": (color_scheme[0] if color_scheme else self.default_colors[0])},
                    "barWidth": "60%",
                }
            ],
            "grid": {"left": "10%", "right": "10%", "bottom": "20%"},
        }

        return config

    def create_line_chart(
        self,
        data: pd.DataFrame,
        x_col: str,
        y_col: str,
        title: Optional[str] = None,
        color_scheme: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a line chart configuration.

        Args:
            data: Pandas DataFrame with data
            x_col: Column name for x-axis
            y_col: Column name for y-axis
            title: Chart title
            color_scheme: List of colors for lines

        Returns:
            ECharts configuration dictionary
        """
        if data is None or data.empty:
            return self._create_empty_chart("Line Chart")

        # Prepare data
        chart_data = data.sort_values(x_col)

        # Limit data points for performance
        if len(chart_data) > 1000:
            chart_data = chart_data.sample(n=1000).sort_values(x_col)

        x_values = chart_data[x_col].tolist()
        y_values = chart_data[y_col].tolist()

        # Create chart configuration
        config = {
            "title": {
                "text": title or f"{y_col} over {x_col}",
                "left": "center",
                "textStyle": {"fontSize": 16, "fontWeight": "bold"},
            },
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "cross"}},
            "xAxis": {
                "type": "category",
                "data": x_values,
                "axisLabel": {"rotate": 45},
            },
            "yAxis": {"type": "value", "name": y_col},
            "series": [
                {
                    "name": y_col,
                    "type": "line",
                    "data": y_values,
                    "itemStyle": {"color": (color_scheme[0] if color_scheme else self.default_colors[0])},
                    "lineStyle": {"width": 2},
                    "symbol": "circle",
                    "symbolSize": 4,
                }
            ],
            "grid": {"left": "10%", "right": "10%", "bottom": "15%"},
        }

        return config

    def create_scatter_plot(
        self,
        data: pd.DataFrame,
        x_col: str,
        y_col: str,
        title: Optional[str] = None,
        color_scheme: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a scatter plot configuration.

        Args:
            data: Pandas DataFrame with data
            x_col: Column name for x-axis
            y_col: Column name for y-axis
            title: Chart title
            color_scheme: List of colors for points

        Returns:
            ECharts configuration dictionary
        """
        if data is None or data.empty:
            return self._create_empty_chart("Scatter Plot")

        # Prepare data
        chart_data = data.dropna(subset=[x_col, y_col])

        # Limit data points for performance
        if len(chart_data) > 2000:
            chart_data = chart_data.sample(n=2000)

        x_values = chart_data[x_col].tolist()
        y_values = chart_data[y_col].tolist()

        # Create scatter data
        scatter_data = list(zip(x_values, y_values))

        # Create chart configuration
        config = {
            "title": {
                "text": title or f"{y_col} vs {x_col}",
                "left": "center",
                "textStyle": {"fontSize": 16, "fontWeight": "bold"},
            },
            "tooltip": {
                "trigger": "item",
                "formatter": f"({x_col}: {{c[0]}}, {y_col}: {{c[1]}})",
            },
            "xAxis": {"type": "value", "name": x_col},
            "yAxis": {"type": "value", "name": y_col},
            "series": [
                {
                    "name": f"{y_col} vs {x_col}",
                    "type": "scatter",
                    "data": scatter_data,
                    "itemStyle": {"color": (color_scheme[0] if color_scheme else self.default_colors[0])},
                    "symbolSize": 6,
                }
            ],
            "grid": {"left": "10%", "right": "10%", "bottom": "15%"},
        }

        return config

    def create_heatmap(
        self,
        data: pd.DataFrame,
        x_col: str,
        y_col: str,
        value_col: str,
        title: Optional[str] = None,
        color_scheme: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a heatmap configuration.

        Args:
            data: Pandas DataFrame with data
            x_col: Column name for x-axis
            y_col: Column name for y-axis
            value_col: Column name for values
            title: Chart title
            color_scheme: List of colors for heatmap

        Returns:
            ECharts configuration dictionary
        """
        if data is None or data.empty:
            return self._create_empty_chart("Heatmap")

        # Prepare data
        chart_data = data.dropna(subset=[x_col, y_col, value_col])

        # Pivot data for heatmap
        try:
            pivot_data = chart_data.pivot_table(values=value_col, index=y_col, columns=x_col, aggfunc="mean").fillna(0)
        except Exception:
            return self._create_empty_chart("Heatmap - Data not suitable for heatmap")

        # Limit dimensions for readability
        if pivot_data.shape[0] > 50:
            pivot_data = pivot_data.head(50)
        if pivot_data.shape[1] > 50:
            pivot_data = pivot_data.iloc[:, :50]

        x_categories = pivot_data.columns.tolist()
        y_categories = pivot_data.index.tolist()

        # Create heatmap data
        heatmap_data = []
        for i, y_cat in enumerate(y_categories):
            for j, x_cat in enumerate(x_categories):
                value = pivot_data.iloc[i, j]
                heatmap_data.append([j, i, value])

        # Create chart configuration
        config = {
            "title": {
                "text": title or f"Heatmap: {value_col}",
                "left": "center",
                "textStyle": {"fontSize": 16, "fontWeight": "bold"},
            },
            "tooltip": {
                "position": "top",
                "formatter": f"({x_col}: {{c[0]}}, {y_col}: {{c[1]}}, {value_col}: {{c[2]}})",
            },
            "xAxis": {
                "type": "category",
                "data": x_categories,
                "axisLabel": {"rotate": 45},
            },
            "yAxis": {"type": "category", "data": y_categories},
            "visualMap": {
                "min": pivot_data.min().min(),
                "max": pivot_data.max().max(),
                "calculable": True,
                "orient": "horizontal",
                "left": "center",
                "bottom": "5%",
            },
            "series": [
                {
                    "name": value_col,
                    "type": "heatmap",
                    "data": heatmap_data,
                    "label": {"show": False},
                    "emphasis": {
                        "itemStyle": {
                            "shadowBlur": 10,
                            "shadowColor": "rgba(0, 0, 0, 0.5)",
                        }
                    },
                }
            ],
            "grid": {"left": "10%", "right": "10%", "bottom": "20%"},
        }

        return config

    def create_pie_chart(
        self,
        data: pd.DataFrame,
        labels: str,
        values: str,
        title: Optional[str] = None,
        color_scheme: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a pie chart configuration.

        Args:
            data: Pandas DataFrame with data
            labels: Column name for labels
            values: Column name for values
            title: Chart title
            color_scheme: List of colors for slices

        Returns:
            ECharts configuration dictionary
        """
        if data is None or data.empty:
            return self._create_empty_chart("Pie Chart")

        # Prepare data
        chart_data = data.groupby(labels)[values].sum().reset_index()
        chart_data = chart_data.sort_values(values, ascending=False)

        # Limit to top 10 categories for readability
        if len(chart_data) > 10:
            chart_data = chart_data.head(10)

        pie_data = []
        for _, row in chart_data.iterrows():
            pie_data.append({"name": str(row[labels]), "value": float(row[values])})

        # Create chart configuration
        config = {
            "title": {
                "text": title or f"Distribution of {values}",
                "left": "center",
                "textStyle": {"fontSize": 16, "fontWeight": "bold"},
            },
            "tooltip": {"trigger": "item", "formatter": "{a} <br/>{b}: {c} ({d}%)"},
            "legend": {"orient": "vertical", "left": "left", "top": "middle"},
            "series": [
                {
                    "name": values,
                    "type": "pie",
                    "radius": "50%",
                    "data": pie_data,
                    "emphasis": {
                        "itemStyle": {
                            "shadowBlur": 10,
                            "shadowOffsetX": 0,
                            "shadowColor": "rgba(0, 0, 0, 0.5)",
                        }
                    },
                }
            ],
        }

        return config

    def create_genomic_heatmap(
        self,
        genomic_data: Dict[str, Any],
        regions: List[str],
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a genomic heatmap configuration.

        Args:
            genomic_data: Dictionary with genomic data
            regions: List of genomic regions
            title: Chart title

        Returns:
            ECharts configuration dictionary
        """
        if not genomic_data or not regions:
            return self._create_empty_chart("Genomic Heatmap")

        # Create chart configuration
        config = {
            "title": {
                "text": title or "Genomic Data Heatmap",
                "left": "center",
                "textStyle": {"fontSize": 16, "fontWeight": "bold"},
            },
            "tooltip": {
                "position": "top",
                "formatter": "Region: {c[0]}, Value: {c[2]}",
            },
            "xAxis": {"type": "category", "data": regions, "axisLabel": {"rotate": 45}},
            "yAxis": {"type": "category", "data": ["Expression"]},
            "visualMap": {
                "min": 0,
                "max": 100,
                "calculable": True,
                "orient": "horizontal",
                "left": "center",
                "bottom": "5%",
            },
            "series": [
                {
                    "name": "Genomic Data",
                    "type": "heatmap",
                    "data": [[i, 0, 50] for i in range(len(regions))],  # Placeholder data
                    "label": {"show": False},
                    "emphasis": {
                        "itemStyle": {
                            "shadowBlur": 10,
                            "shadowColor": "rgba(0, 0, 0, 0.5)",
                        }
                    },
                }
            ],
            "grid": {"left": "10%", "right": "10%", "bottom": "20%"},
        }

        return config

    def create_expression_plot(
        self, gene_data: pd.DataFrame, samples: List[str], title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a gene expression plot configuration.

        Args:
            gene_data: Pandas DataFrame with gene expression data
            samples: List of sample names
            title: Chart title

        Returns:
            ECharts configuration dictionary
        """
        if gene_data is None or gene_data.empty or not samples:
            return self._create_empty_chart("Gene Expression Plot")

        # Prepare data
        chart_data = gene_data.head(20)  # Limit to top 20 genes

        # Create chart configuration
        config = {
            "title": {
                "text": title or "Gene Expression Across Samples",
                "left": "center",
                "textStyle": {"fontSize": 16, "fontWeight": "bold"},
            },
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "legend": {"data": samples, "top": "10%"},
            "xAxis": {
                "type": "category",
                "data": chart_data.index.tolist(),
                "axisLabel": {"rotate": 45},
            },
            "yAxis": {"type": "value", "name": "Expression Level"},
            "series": [
                {
                    "name": sample,
                    "type": "bar",
                    "data": (chart_data[sample].tolist() if sample in chart_data.columns else []),
                    "itemStyle": {"color": self.default_colors[i % len(self.default_colors)]},
                }
                for i, sample in enumerate(samples)
                if sample in gene_data.columns
            ],
            "grid": {"left": "10%", "right": "10%", "bottom": "20%"},
        }

        return config

    def _create_empty_chart(self, chart_type: str) -> Dict[str, Any]:
        """Create an empty chart configuration when data is not available."""
        return {
            "title": {
                "text": f"{chart_type} - No Data Available",
                "left": "center",
                "textStyle": {"fontSize": 16, "fontWeight": "bold", "color": "#999"},
            },
            "graphic": [
                {
                    "type": "text",
                    "left": "center",
                    "top": "middle",
                    "style": {
                        "text": "No data available for visualization",
                        "fontSize": 14,
                        "fill": "#999",
                    },
                }
            ],
        }
