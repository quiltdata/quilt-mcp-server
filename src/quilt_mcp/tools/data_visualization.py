"""Quilt-native visualization helpers without heavy plotting dependencies."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from io import BytesIO, StringIO
from statistics import mean, median, quantiles, StatisticsError
from typing import Annotated, Any, Dict, Iterable, List, Literal, Optional, Sequence, Tuple

from pydantic import Field

from ..models import (
    DataVisualizationSuccess,
    DataVisualizationError,
    VisualizationConfig,
    VisualizationFile,
)
from ..utils import get_s3_client


COLOR_SCHEMES = {
    "genomics": ["#2E8B57", "#20B2AA", "#48D1CC", "#00CED1", "#40E0D0"],
    "ml": ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7"],
    "research": ["#6C5CE7", "#A29BFE", "#FD79A8", "#FDCB6E", "#E17055"],
    "analytics": ["#00B894", "#00CEC9", "#74B9FF", "#FDCB6E", "#E17055"],
    "default": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"],
}


@dataclass
class VisualizationResult:
    option: dict[str, Any]
    filename: str
    engine: str


Records = List[Dict[str, Any]]


def create_data_visualization(
    data: Annotated[
        dict[str, list] | list[dict[str, str | int | float]] | str,
        Field(
            description="Source data as dict of columns, list of row dicts, CSV/TSV string, or S3 URI",
            examples=[
                {"gene": ["BRCA1", "TP53"], "expression": [42.5, 38.1]},
                [{"gene": "BRCA1", "expression": 42.5}, {"gene": "TP53", "expression": 38.1}],
                "gene,expression\nBRCA1,42.5\nTP53,38.1",
                "s3://bucket/data.csv",
            ],
        ),
    ],
    plot_type: Annotated[
        Literal["boxplot", "scatter", "line", "bar"],
        Field(
            description="Visualization type to generate",
        ),
    ],
    x_column: Annotated[
        str,
        Field(
            description="Column name for x-axis (category or numeric depending on plot type)",
            examples=["gene", "sample_id", "timestamp"],
        ),
    ],
    y_column: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Column name for y-axis (required for all plot types)",
            examples=["expression", "value", "count"],
        ),
    ] = None,
    group_column: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional column for grouping/coloring (scatter/line/bar)",
            examples=["condition", "treatment", "category"],
        ),
    ] = None,
    title: Annotated[
        str,
        Field(
            default="",
            description="Chart title (auto-generated if empty)",
        ),
    ] = "",
    xlabel: Annotated[
        str,
        Field(
            default="",
            description="X-axis label (defaults to x_column name if empty)",
        ),
    ] = "",
    ylabel: Annotated[
        str,
        Field(
            default="",
            description="Y-axis label (defaults to y_column name if empty)",
        ),
    ] = "",
    color_scheme: Annotated[
        Literal["genomics", "ml", "research", "analytics", "default"],
        Field(
            default="genomics",
            description="Color palette to use for the visualization",
        ),
    ] = "genomics",
    template: Annotated[
        str,
        Field(
            default="research",
            description="Metadata template label for quilt_summarize.json",
        ),
    ] = "research",
    output_format: Annotated[
        Literal["echarts"],
        Field(
            default="echarts",
            description="Visualization engine (currently only 'echarts' is supported)",
        ),
    ] = "echarts",
) -> DataVisualizationSuccess | DataVisualizationError:
    """Create interactive data visualization for Quilt packages - Generate ECharts configurations from tabular data.

    WORKFLOW:
        1. Collect data (Athena JSON, CSV string, S3 object, or list of records)
        2. Call this tool to obtain visualization JSON + supporting files
        3. Upload files to S3 using bucket_objects_put() with a base prefix (e.g., "my-analysis/")
        4. Create package with package_create(), ensuring file paths match quilt_summarize.json references

    IMPORTANT: The quilt_summarize.json file references filenames WITHOUT directory prefixes (flat structure).
    When creating packages, either:
        - Use flatten=True (default) so all files are at root level, OR
        - Ensure S3 keys match exactly what's in quilt_summarize.json

    Args:
        data: Source data accepted as dict of columns, list of row dicts, CSV/TSV string, or S3 URI
        plot_type: Visualization type ("boxplot", "scatter", "line", "bar")
        x_column: Column used for x-axis (category or numeric depending on plot)
        y_column: Column used for y-axis (required for all four plot types)
        group_column: Optional grouping/color column (scatter/line/bar)
        title: Chart title override (auto-generated when empty)
        xlabel: X-axis label override (defaults to x_column)
        ylabel: Y-axis label override (defaults to y_column)
        color_scheme: Palette name ("genomics", "ml", "research", "analytics", "default")
        template: Metadata template label written into quilt_summarize metadata
        output_format: Visualization engine, currently "echarts" only

    Returns:
        DataVisualizationSuccess on success containing:
            - visualization_config: VisualizationConfig with ECharts configuration
            - data_file: VisualizationFile with CSV data
            - quilt_summarize: VisualizationFile with Quilt metadata
            - files_to_upload: List of VisualizationFile ready for bucket_objects_put()
            - metadata: Statistics and info about the visualization

        DataVisualizationError on failure containing:
            - error: Error message
            - suggestions: Helpful suggestions for fixing the error
            - plot_type, x_column, y_column: Context about what was attempted

    Next step:
        Upload files with bucket_objects_put() using a common prefix, then create package referencing those exact S3 URIs.

    Example:
        ```python
        from quilt_mcp.tools import data_visualization, buckets, package_ops

        # Step 1: Create visualization
        query_result = {"gene": ["BRCA1", "BRCA1", "TP53", "TP53"], "expression": [42.5, 45.2, 38.1, 40.3]}
        viz = data_visualization.create_data_visualization(
            data=query_result,
            plot_type="boxplot",
            x_column="gene",
            y_column="expression",
            title="Expression by Gene",
            color_scheme="genomics",
        )

        # Step 2: Prepare upload items with a base prefix
        base_prefix = "my-analysis/"
        upload_items = [
            {
                "key": base_prefix + item["key"],
                "text": item["text"],
                "content_type": item["content_type"]
            }
            for item in viz["files_to_upload"]
        ]

        # Step 3: Upload to S3
        buckets.bucket_objects_put("s3://my-bucket", upload_items)

        # Step 4: Create package with exact S3 URIs (flatten=True by default flattens to root)
        package_ops.package_create(
            package_name="genomics/visualized-results",
            s3_uris=[
                "s3://my-bucket/" + base_prefix + viz["visualization_config"]["filename"],
                "s3://my-bucket/" + base_prefix + viz["data_file"]["filename"],
                "s3://my-bucket/" + base_prefix + viz["quilt_summarize"]["filename"],
            ],
            registry="s3://my-bucket",
            message="Gene expression visualization",
        )
        # With flatten=True (default), package structure will be:
        # ├── viz_boxplot_gene_expression.json
        # ├── viz_data_boxplot.csv
        # └── quilt_summarize.json
        ```
    """

    try:
        records = _normalize_data(data)  # type: ignore[arg-type]  # Internal function with broader types
        plot_type_normalized = _normalize_plot_type(plot_type)
        _validate_plot_requirements(records, plot_type_normalized, x_column, y_column, group_column)

        viz = _create_visualization_config(
            records=records,
            plot_type=plot_type_normalized,
            x_column=x_column,
            y_column=y_column or "",
            group_column=group_column,
            title=title,
            xlabel=xlabel or x_column,
            ylabel=ylabel or (y_column or ""),
            color_scheme=color_scheme,
            output_format=output_format,
        )

        data_file = _create_data_file(records, plot_type_normalized, x_column, y_column, group_column)
        quilt_sum = _generate_quilt_summarize(
            viz_config=viz,
            data_file=data_file,
            title=title or viz.option.get("title", {}).get("text") or "Visualization",
            description=_build_description(plot_type_normalized, xlabel or x_column, ylabel or (y_column or "")),
            template=template,
        )
        stats = _calculate_statistics(records, y_column)

        files_to_upload = [
            VisualizationFile(
                key=viz.filename,
                text=json.dumps(viz.option, indent=2),
                content_type="application/json",
            ),
            VisualizationFile(
                key=data_file["filename"],
                text=data_file["content"],
                content_type=data_file["content_type"],
            ),
            VisualizationFile(
                key=quilt_sum["filename"],
                text=json.dumps(quilt_sum["content"], indent=2),
                content_type="application/json",
            ),
        ]

        return DataVisualizationSuccess(
            visualization_config=VisualizationConfig(
                type="echarts",
                option=viz.option,
                filename=viz.filename,
            ),
            data_file=VisualizationFile(
                key=data_file["filename"],
                text=data_file["content"],
                content_type=data_file["content_type"],
            ),
            quilt_summarize=VisualizationFile(
                key=quilt_sum["filename"],
                text=json.dumps(quilt_sum["content"], indent=2),
                content_type="application/json",
            ),
            files_to_upload=files_to_upload,
            metadata={
                "plot_type": plot_type_normalized,
                "statistics": stats,
                "data_points": len(records),
                "visualization_engine": viz.engine,
                "columns_used": [x_column, y_column, group_column],
            },
        )
    except Exception as exc:  # noqa: BLE001
        return DataVisualizationError(
            error=str(exc),
            possible_fixes=[_get_error_suggestion(exc)],
            plot_type=plot_type,
            x_column=x_column,
            y_column=y_column,
        )


def _normalize_data(data: dict[str, Iterable[Any]] | Sequence[Dict[str, Any]] | str) -> Records:
    if isinstance(data, list):
        return [dict(row) for row in data]

    if isinstance(data, dict):
        columns = {key: list(values) for key, values in data.items()}
        lengths = {len(values) for values in columns.values()}
        if len(lengths) != 1:
            raise ValueError("Column lengths must match for dict input")
        rows: Records = []
        for idx in range(next(iter(lengths))):
            row = {key: columns[key][idx] for key in columns}
            rows.append(row)
        if not rows:
            raise ValueError("Input data is empty")
        return rows

    if isinstance(data, str):
        if data.startswith(("s3://", "quilt+s3://")):
            return _load_from_s3(data)
        buffer = StringIO(data)
        reader = csv.DictReader(buffer)
        rows = [dict(row) for row in reader]
        if not rows:
            raise ValueError("CSV string produced no rows")
        return rows

    raise ValueError(f"Unsupported data type: {type(data).__name__}")


def _load_from_s3(uri: str) -> Records:
    bucket, key = _split_s3_uri(uri)
    client = get_s3_client()
    response = client.get_object(Bucket=bucket, Key=key)
    body = response.get("Body")
    if body is None:
        raise ValueError(f"S3 object Body missing for {uri}")
    payload = body.read()

    if key.endswith(".csv"):
        return _records_from_csv(payload.decode("utf-8"), delimiter=",")
    if key.endswith(".tsv"):
        return _records_from_csv(payload.decode("utf-8"), delimiter="\t")
    if key.endswith(".json"):
        data = json.loads(payload.decode("utf-8"))
        if isinstance(data, list):
            return [dict(row) for row in data]
        if isinstance(data, dict):
            return _normalize_data(data)
        raise ValueError(f"Unsupported JSON structure for {uri}")

    raise ValueError(f"Unsupported file format for {uri}. Provide CSV, TSV, or JSON data.")


def _records_from_csv(text: str, delimiter: str) -> Records:
    reader = csv.DictReader(StringIO(text), delimiter=delimiter)
    rows = [dict(row) for row in reader]
    if not rows:
        raise ValueError("CSV source contains no data rows")
    return rows


def _split_s3_uri(uri: str) -> Tuple[str, str]:
    stripped = uri.replace("quilt+", "")
    if not stripped.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {uri}")
    path = stripped[5:]
    if "/" not in path:
        raise ValueError(f"Invalid S3 URI path: {uri}")
    bucket, key = path.split("/", 1)
    if not bucket or not key:
        raise ValueError(f"Invalid S3 URI components: {uri}")
    return bucket, key


def _normalize_plot_type(plot_type: str) -> str:
    normalized = (plot_type or "").strip().lower()
    mapping = {
        "box": "boxplot",
        "box_plot": "boxplot",
        "box-plot": "boxplot",
        "scatterplot": "scatter",
        "scatter-plot": "scatter",
        "lineplot": "line",
        "line-plot": "line",
        "barplot": "bar",
        "bar-plot": "bar",
    }
    return mapping.get(normalized, normalized)


def _validate_plot_requirements(
    records: Records,
    plot_type: str,
    x_column: str,
    y_column: Optional[str],
    group_column: Optional[str],
) -> None:
    if not records:
        raise ValueError("Visualization requires at least one data row")
    available_columns = sorted({key for row in records for key in row.keys()})
    required = [x_column, y_column]
    if group_column:
        required.append(group_column)
    missing = [column for column in required if column and column not in available_columns]
    if missing:
        raise ValueError(f"Columns not found: {missing}. Available columns: {available_columns}")
    if plot_type in {"boxplot", "scatter", "line", "bar"} and not y_column:
        raise ValueError(f"Plot type '{plot_type}' requires 'y_column'.")


def _create_visualization_config(
    records: Records,
    plot_type: str,
    x_column: str,
    y_column: str,
    group_column: Optional[str],
    title: str,
    xlabel: str,
    ylabel: str,
    color_scheme: str,
    output_format: str,
) -> VisualizationResult:
    engine = (output_format or "echarts").lower()
    if engine != "echarts":
        raise ValueError("Currently only 'echarts' output_format is supported.")

    colors = COLOR_SCHEMES.get(color_scheme, COLOR_SCHEMES["default"])
    filename = _make_filename(plot_type, x_column, y_column)

    if plot_type == "boxplot":
        option = _create_echarts_boxplot(records, x_column, y_column, title, xlabel, ylabel, colors)
    elif plot_type == "scatter":
        option = _create_echarts_scatter(records, x_column, y_column, group_column, title, xlabel, ylabel, colors)
    elif plot_type == "line":
        option = _create_echarts_line(records, x_column, y_column, group_column, title, xlabel, ylabel, colors)
    elif plot_type == "bar":
        option = _create_echarts_bar(records, x_column, y_column, group_column, title, xlabel, ylabel, colors)
    else:
        raise ValueError(f"Unsupported plot_type '{plot_type}'.")

    return VisualizationResult(option=option, filename=filename, engine=engine)


def _create_echarts_boxplot(
    records: Records,
    x_column: str,
    y_column: str,
    title: str,
    xlabel: str,
    ylabel: str,
    colors: List[str],
) -> dict[str, Any]:
    categories = []
    data_map: Dict[str, List[float]] = {}
    for row in records:
        category = str(row.get(x_column, ""))
        try:
            value = float(row.get(y_column, 0))
        except (TypeError, ValueError):
            continue
        categories.append(category)
        data_map.setdefault(category, []).append(value)
    ordered_categories = []
    seen = set()
    for category in categories:
        if category not in seen:
            seen.add(category)
            ordered_categories.append(category)

    series_data: list[list[float]] = []
    for category in ordered_categories:
        values = data_map.get(category, [])
        if not values:
            series_data.append([0, 0, 0, 0, 0])
            continue
        minimum, q1, med, q3, maximum = _five_number_summary(values)
        series_data.append([minimum, q1, med, q3, maximum])

    return {
        "title": {"text": title or f"{ylabel} by {xlabel}", "left": "center"},
        "tooltip": {"trigger": "item", "axisPointer": {"type": "shadow"}},
        "xAxis": {
            "type": "category",
            "data": ordered_categories,
            "name": xlabel,
            "nameLocation": "middle",
            "nameGap": 30,
        },
        "yAxis": {"type": "value", "name": ylabel, "nameLocation": "middle", "nameGap": 45},
        "series": [
            {
                "name": ylabel,
                "type": "boxplot",
                "data": series_data,
                "itemStyle": {"color": colors[0], "borderColor": colors[min(1, len(colors) - 1)]},
            }
        ],
        "color": colors,
    }


def _create_echarts_scatter(
    records: Records,
    x_column: str,
    y_column: str,
    group_column: Optional[str],
    title: str,
    xlabel: str,
    ylabel: str,
    colors: List[str],
) -> dict[str, Any]:
    if group_column:
        grouped: Dict[str, List[List[float]]] = {}
        for row in records:
            group_key = str(row.get(group_column, ""))
            point = _extract_point(row, x_column, y_column)
            if point is None:
                continue
            grouped.setdefault(group_key, []).append(point)
        series = []
        for idx, (group_key, points) in enumerate(grouped.items()):
            series.append(
                {
                    "name": group_key,
                    "type": "scatter",
                    "data": points,
                    "symbolSize": 12,
                    "itemStyle": {"color": colors[idx % len(colors)]},
                }
            )
    else:
        points = []
        for row in records:
            point = _extract_point(row, x_column, y_column)
            if point is not None:
                points.append(point)
        series = [
            {
                "type": "scatter",
                "data": points,
                "symbolSize": 12,
                "itemStyle": {"color": colors[0]},
            }
        ]

    return {
        "title": {"text": title or f"{ylabel} vs {xlabel}", "left": "center"},
        "tooltip": {"trigger": "item"},
        "legend": {"show": bool(group_column)},
        "xAxis": {"type": "value", "name": xlabel},
        "yAxis": {"type": "value", "name": ylabel},
        "series": series,
        "color": colors,
    }


def _create_echarts_line(
    records: Records,
    x_column: str,
    y_column: str,
    group_column: Optional[str],
    title: str,
    xlabel: str,
    ylabel: str,
    colors: List[str],
) -> dict[str, Any]:
    if group_column:
        grouped: Dict[str, List[List[float]]] = {}
        for row in records:
            point = _extract_point(row, x_column, y_column)
            if point is None:
                continue
            group_key = str(row.get(group_column, ""))
            grouped.setdefault(group_key, []).append(point)
        series = []
        for idx, (group_key, points) in enumerate(grouped.items()):
            sorted_points = sorted(points, key=lambda item: item[0])
            series.append(
                {
                    "name": group_key,
                    "type": "line",
                    "smooth": True,
                    "data": sorted_points,
                    "lineStyle": {"width": 2},
                    "itemStyle": {"color": colors[idx % len(colors)]},
                }
            )
    else:
        points = [p for p in [_extract_point(row, x_column, y_column) for row in records] if p is not None]
        filtered = sorted([pt for pt in points if pt is not None], key=lambda item: item[0])
        series = [
            {
                "type": "line",
                "smooth": True,
                "data": filtered,
                "lineStyle": {"width": 2, "color": colors[0]},
            }
        ]

    return {
        "title": {"text": title or f"{ylabel} over {xlabel}", "left": "center"},
        "tooltip": {"trigger": "axis"},
        "legend": {"show": bool(group_column)},
        "xAxis": {"type": "value", "name": xlabel},
        "yAxis": {"type": "value", "name": ylabel},
        "series": series,
        "color": colors,
    }


def _create_echarts_bar(
    records: Records,
    x_column: str,
    y_column: str,
    group_column: Optional[str],
    title: str,
    xlabel: str,
    ylabel: str,
    colors: List[str],
) -> dict[str, Any]:
    if group_column:
        grouped: Dict[str, Dict[str, List[float]]] = {}
        for row in records:
            group_key = str(row.get(group_column, ""))
            x_key = str(row.get(x_column, ""))
            value = _to_float(row.get(y_column))
            if value is None:
                continue
            grouped.setdefault(group_key, {}).setdefault(x_key, []).append(value)

        categories = sorted({x for group in grouped.values() for x in group.keys()})
        series = []
        for idx, (group_key, bucket) in enumerate(grouped.items()):
            series.append(
                {
                    "name": group_key,
                    "type": "bar",
                    "data": [_mean_or_zero(bucket.get(category, [])) for category in categories],
                    "itemStyle": {"color": colors[idx % len(colors)]},
                }
            )
    else:
        buckets: Dict[str, List[float]] = {}
        for row in records:
            x_key = str(row.get(x_column, ""))
            value = _to_float(row.get(y_column))
            if value is None:
                continue
            buckets.setdefault(x_key, []).append(value)
        categories = list(buckets.keys())
        series = [
            {
                "type": "bar",
                "data": [_mean_or_zero(buckets.get(category, [])) for category in categories],
                "itemStyle": {"color": colors[0]},
            }
        ]

    return {
        "title": {"text": title or f"{ylabel} by {xlabel}", "left": "center"},
        "tooltip": {"trigger": "axis"},
        "legend": {"show": bool(group_column)},
        "xAxis": {"type": "category", "data": categories, "name": xlabel},
        "yAxis": {"type": "value", "name": ylabel},
        "series": series,
        "color": colors,
    }


def _create_data_file(
    records: Records,
    plot_type: str,
    x_column: str,
    y_column: Optional[str],
    group_column: Optional[str],
) -> Dict[str, Any]:
    if not records:
        raise ValueError("Cannot create data file from empty records.")
    fieldnames = sorted({key for row in records for key in row.keys()})
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(records)
    filename = f"viz_data_{plot_type}.csv".replace(" ", "_")
    return {"content": output.getvalue(), "filename": filename, "content_type": "text/csv"}


def _generate_quilt_summarize(
    viz_config: VisualizationResult,
    data_file: Dict[str, Any],
    title: str,
    description: str,
    template: str,
) -> Dict[str, Any]:
    content = [
        {
            "path": viz_config.filename,
            "title": title,
            "description": description,
            "types": [viz_config.engine],
            "expand": True,
            "metadata_template": template,
        },
        {"path": data_file["filename"], "title": "Raw Data", "types": [{"name": "perspective"}]},
    ]
    return {"content": content, "filename": "quilt_summarize.json"}


def _calculate_statistics(records: Records, y_column: Optional[str]) -> Dict[str, Any]:
    if not y_column:
        return {}
    values = [_to_float(row.get(y_column)) for row in records]
    numeric_values = [value for value in values if value is not None]
    if not numeric_values:
        return {}
    numeric_values.sort()
    minimum, q1, med, q3, maximum = _five_number_summary(numeric_values)
    try:
        avg = mean(numeric_values)
    except StatisticsError:
        avg = numeric_values[0]
    variance = _variance(numeric_values, avg)
    return {
        "mean": avg,
        "median": med,
        "std": variance**0.5,
        "min": minimum,
        "max": maximum,
        "q1": q1,
        "q3": q3,
        "count": len(numeric_values),
    }


def _make_filename(kind: str, primary: str, secondary: str) -> str:
    parts = [kind, primary or "", secondary or ""]
    slug = "_".join(
        segment.strip().lower().replace(" ", "_").replace("/", "_") for segment in parts if segment and segment.strip()
    )
    if not slug:
        slug = "visualization"
    return f"viz_{slug}.json"


def _five_number_summary(values: List[float]) -> Tuple[float, float, float, float, float]:
    sorted_vals = sorted(values)
    minimum = sorted_vals[0]
    maximum = sorted_vals[-1]
    if len(sorted_vals) == 1:
        return (minimum, minimum, minimum, minimum, maximum)
    try:
        q_values = quantiles(sorted_vals, n=4, method="inclusive")
        q1, med, q3 = q_values[0], q_values[1], q_values[2]
    except StatisticsError:
        med = median(sorted_vals)
        mid = len(sorted_vals) // 2
        lower = sorted_vals[:mid] or [sorted_vals[0]]
        upper = sorted_vals[mid + (0 if len(sorted_vals) % 2 == 0 else 1) :] or [sorted_vals[-1]]
        q1 = median(lower)
        q3 = median(upper)
    return (float(minimum), float(q1), float(med), float(q3), float(maximum))


def _variance(values: List[float], mean_value: float) -> float:
    if len(values) <= 1:
        return 0.0
    squared = [(value - mean_value) ** 2 for value in values]
    return sum(squared) / len(values)


def _extract_point(row: Dict[str, Any], x_column: str, y_column: str) -> Optional[List[float]]:
    x_val = _to_float(row.get(x_column))
    y_val = _to_float(row.get(y_column))
    if x_val is None or y_val is None:
        return None
    return [x_val, y_val]


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _mean_or_zero(values: List[float]) -> float:
    if not values:
        return 0.0
    return mean(values)


def _get_error_suggestion(exc: Exception) -> str:
    message = str(exc).lower()
    if "columns not found" in message:
        return "Verify x_column, y_column, and group_column names against your dataset header."
    if "unsupported plot_type" in message:
        return "Use one of: boxplot, scatter, line, or bar."
    if "unsupported file format" in message:
        return "Provide CSV, TSV, or JSON data, or convert the file before visualizing."
    if "requires 'y_column'" in message:
        return "Include y_column for the requested visualization."
    return "Check the error details and ensure the input data is structured correctly."


def _build_description(plot_type: str, xlabel: str, ylabel: str) -> str:
    if plot_type == "boxplot":
        return f"Interactive box plot summarizing {ylabel} across {xlabel}."
    if plot_type == "scatter":
        return f"Scatter plot comparing {xlabel} against {ylabel}."
    if plot_type == "line":
        return f"Line chart visualising {ylabel} over {xlabel}."
    if plot_type == "bar":
        return f"Bar chart aggregating {ylabel} by {xlabel}."
    return "Interactive visualization generated from tabular data."
