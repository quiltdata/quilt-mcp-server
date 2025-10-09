"""
ECharts Generator for Quilt Package Visualization

This module generates ECharts chart configurations for various data types
including bar charts, line charts, scatter plots, and heatmaps.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


class EChartsGenerator:
    """Generates ECharts chart configurations for data visualization."""

    def __init__(self) -> None:
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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _create_empty_chart(self, chart_type: str) -> Dict[str, Any]:
        """Return a placeholder chart when no data is available."""
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

    def _to_records(
        self,
        data: Any,
        required_fields: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Convert common tabular structures into a list of dictionaries.

        Supports:
        - list[dict]
        - dict -> single record
        - objects with to_dict() (e.g. pandas DataFrame / Series)
        """
        if data is None:
            return []

        records: List[Dict[str, Any]]
        if isinstance(data, list):
            records = [dict(row) for row in data]
        elif isinstance(data, dict):
            records = [dict(data)]
        elif hasattr(data, "to_dict"):
            to_dict = getattr(data, "to_dict")
            try:
                converted = to_dict(orient="records")
            except TypeError:
                converted = to_dict("records")
            records = [dict(row) for row in converted]
        else:
            raise TypeError("Unsupported data type for ECharts generation")

        if required_fields:
            filtered: List[Dict[str, Any]] = []
            for record in records:
                if all(field in record and record[field] is not None for field in required_fields):
                    filtered.append(record)
            return filtered
        return records

    def _aggregate_kv(
        self,
        records: Iterable[Dict[str, Any]],
        key_field: str,
        value_field: str,
    ) -> List[Tuple[Any, float]]:
        totals: Dict[Any, float] = {}
        for record in records:
            key = record.get(key_field)
            if key is None:
                continue
            try:
                value = float(record.get(value_field, 0) or 0)
            except (TypeError, ValueError):
                continue
            totals[key] = totals.get(key, 0.0) + value
        return sorted(totals.items(), key=lambda item: item[1], reverse=True)

    def _limit(self, items: Sequence[Any], limit: int) -> List[Any]:
        return list(items[:limit]) if len(items) > limit else list(items)

    @staticmethod
    def _format_axis_value(value: Any) -> Any:
        """Format axis values to be ECharts-friendly."""
        if value is None:
            return ""
        if isinstance(value, (int, float)):
            return value
        return str(value)

    def _coerce_expression_data(
        self,
        gene_data: Any,
        samples: Sequence[str],
    ) -> List[Dict[str, Any]]:
        if gene_data is None:
            return []

        if isinstance(gene_data, dict):
            iterable = gene_data.items()
        elif isinstance(gene_data, list):
            iterable = [
                (row.get("gene") or row.get("name"), {sample: row.get(sample) for sample in samples})
                for row in gene_data
            ]
        elif hasattr(gene_data, "to_dict"):
            try:
                converted = gene_data.to_dict(orient="index")
            except TypeError:
                converted = gene_data.to_dict("index")
            iterable = converted.items()
        else:
            return []

        result: List[Dict[str, Any]] = []
        for gene, values in iterable:
            if gene is None:
                continue
            value_map: Dict[str, float] = {}
            if isinstance(values, dict):
                for sample in samples:
                    raw = values.get(sample, 0)
                    try:
                        value_map[sample] = float(raw or 0)
                    except (TypeError, ValueError):
                        value_map[sample] = 0.0
            result.append({"gene": str(gene), "values": value_map})
        return result

    # ------------------------------------------------------------------
    # Chart creation
    # ------------------------------------------------------------------
    def create_bar_chart(
        self,
        data: Any,
        categories: str,
        values: str,
        title: Optional[str] = None,
        color_scheme: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        records = self._to_records(data, required_fields=[categories, values])
        if not records:
            return self._create_empty_chart("Bar Chart")

        aggregated = self._aggregate_kv(records, categories, values)
        if not aggregated:
            return self._create_empty_chart("Bar Chart")

        limited = self._limit(aggregated, 20)
        categories_list = [str(item[0]) for item in limited]
        values_list = [item[1] for item in limited]

        return {
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
                    "itemStyle": {"color": (color_scheme or self.default_colors)[0]},
                    "barWidth": "60%",
                }
            ],
            "grid": {"left": "10%", "right": "10%", "bottom": "20%"},
        }

    def create_line_chart(
        self,
        data: Any,
        x_col: str,
        y_col: str,
        title: Optional[str] = None,
        color_scheme: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        records = self._to_records(data, required_fields=[x_col, y_col])
        if not records:
            return self._create_empty_chart("Line Chart")

        filtered: List[Tuple[Any, float]] = []
        for record in records:
            x_value = record.get(x_col)
            y_value = record.get(y_col)
            try:
                y_numeric = float(y_value)
            except (TypeError, ValueError):
                continue
            filtered.append((x_value, y_numeric))

        if not filtered:
            return self._create_empty_chart("Line Chart")

        try:
            filtered.sort(key=lambda item: item[0])
        except TypeError:
            filtered.sort(key=lambda item: str(item[0]))

        limited = self._limit(filtered, 1000)
        x_values = [self._format_axis_value(item[0]) for item in limited]
        y_values = [item[1] for item in limited]

        return {
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
                    "itemStyle": {"color": (color_scheme or self.default_colors)[0]},
                    "lineStyle": {"width": 2},
                    "symbol": "circle",
                    "symbolSize": 4,
                }
            ],
            "grid": {"left": "10%", "right": "10%", "bottom": "15%"},
        }

    def create_scatter_plot(
        self,
        data: Any,
        x_col: str,
        y_col: str,
        title: Optional[str] = None,
        color_scheme: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        records = self._to_records(data, required_fields=[x_col, y_col])
        if not records:
            return self._create_empty_chart("Scatter Plot")

        scatter_data: List[Tuple[Any, Any]] = []
        for record in records:
            scatter_data.append((record.get(x_col), record.get(y_col)))

        limited = self._limit(scatter_data, 2000)
        if not limited:
            return self._create_empty_chart("Scatter Plot")

        return {
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
                    "data": [[item[0], item[1]] for item in limited],
                    "itemStyle": {"color": (color_scheme or self.default_colors)[0]},
                    "symbolSize": 6,
                }
            ],
            "grid": {"left": "10%", "right": "10%", "bottom": "15%"},
        }

    def create_heatmap(
        self,
        data: Any,
        x_col: str,
        y_col: str,
        value_col: str,
        title: Optional[str] = None,
        color_scheme: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        records = self._to_records(data, required_fields=[x_col, y_col, value_col])
        if not records:
            return self._create_empty_chart("Heatmap")

        x_labels: List[str] = []
        y_labels: List[str] = []
        value_map: Dict[Tuple[str, str], float] = {}

        for record in records:
            x_value = str(record.get(x_col))
            y_value = str(record.get(y_col))
            try:
                value = float(record.get(value_col, 0) or 0)
            except (TypeError, ValueError):
                value = 0.0

            value_map[(x_value, y_value)] = value
            if x_value not in x_labels:
                x_labels.append(x_value)
            if y_value not in y_labels:
                y_labels.append(y_value)

        if not x_labels or not y_labels:
            return self._create_empty_chart("Heatmap")

        heatmap_data: List[List[Any]] = []
        for y_index, y_value in enumerate(y_labels):
            for x_index, x_value in enumerate(x_labels):
                heatmap_data.append([x_index, y_index, value_map.get((x_value, y_value), 0)])

        return {
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
                "data": x_labels,
                "axisLabel": {"rotate": 45},
            },
            "yAxis": {"type": "category", "data": y_labels},
            "visualMap": {
                "min": min(value_map.values()) if value_map else 0,
                "max": max(value_map.values()) if value_map else 1,
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

    def create_pie_chart(
        self,
        data: Any,
        labels: str,
        values: str,
        title: Optional[str] = None,
        color_scheme: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        records = self._to_records(data, required_fields=[labels, values])
        if not records:
            return self._create_empty_chart("Pie Chart")

        aggregated = self._aggregate_kv(records, labels, values)
        if not aggregated:
            return self._create_empty_chart("Pie Chart")

        limited = self._limit(aggregated, 10)
        pie_data = [{"name": str(label), "value": float(value)} for label, value in limited]

        return {
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

    def create_genomic_heatmap(
        self,
        genomic_data: Dict[str, Any],
        regions: List[str],
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not genomic_data or not regions:
            return self._create_empty_chart("Genomic Heatmap")

        return {
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
                    "data": [[i, 0, genomic_data.get(region, 50)] for i, region in enumerate(regions)],
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

    def create_expression_plot(
        self,
        gene_data: Any,
        samples: List[str],
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        records = self._coerce_expression_data(gene_data, samples)
        if not records or not samples:
            return self._create_empty_chart("Gene Expression Plot")

        limited_records = records[:20]
        genes = [record["gene"] for record in limited_records]

        series = []
        for i, sample in enumerate(samples):
            series.append(
                {
                    "name": sample,
                    "type": "bar",
                    "data": [record["values"].get(sample, 0) for record in limited_records],
                    "itemStyle": {"color": self.default_colors[i % len(self.default_colors)]},
                }
            )

        return {
            "title": {
                "text": title or "Gene Expression Across Samples",
                "left": "center",
                "textStyle": {"fontSize": 16, "fontWeight": "bold"},
            },
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "legend": {"data": samples, "top": "10%"},
            "xAxis": {
                "type": "category",
                "data": genes,
                "axisLabel": {"rotate": 45},
            },
            "yAxis": {"type": "value", "name": "Expression Level"},
            "series": series,
            "grid": {"left": "10%", "right": "10%", "bottom": "20%"},
        }
