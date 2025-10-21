from __future__ import annotations

import json

import pytest

import importlib

data_visualization = importlib.import_module("quilt_mcp.tools.data_visualization")
from quilt_mcp.models import DataVisualizationParams


def test_boxplot_from_dict_data():
    params = DataVisualizationParams(
        data={
            "gene": ["BRCA1", "BRCA1", "TP53", "TP53"],
            "expression": [42.5, 45.2, 38.1, 40.3],
        },
        plot_type="boxplot",
        x_column="gene",
        y_column="expression",
        title="Expression by Gene",
        color_scheme="genomics",
    )
    result = data_visualization.create_data_visualization(params)

    assert result.success is True
    viz_config = result.visualization_config
    assert viz_config.type == "echarts"
    assert viz_config.option["series"][0]["type"] == "boxplot"
    assert viz_config.option["xAxis"]["data"] == ["BRCA1", "TP53"]

    files = {item.key: item for item in result.files_to_upload}
    assert "quilt_summarize.json" in files
    assert result.data_file.key in files
    assert result.visualization_config.filename in files

    # Ensure quilt_summarize references visualization
    summarize_content = json.loads(files["quilt_summarize.json"].text)
    assert summarize_content[0]["path"] == result.visualization_config.filename
    assert summarize_content[1]["path"] == result.data_file.key


def test_scatter_from_csv_string():
    csv_data = "time_point,signal_intensity\n0,1.0\n1,2.2\n2,3.1\n"

    params = DataVisualizationParams(
        data=csv_data,
        plot_type="scatter",
        x_column="time_point",
        y_column="signal_intensity",
        title="Signal Over Time",
        color_scheme="analytics",
    )
    result = data_visualization.create_data_visualization(params)

    assert result.success is True
    viz_config = result.visualization_config
    assert viz_config.option["series"][0]["type"] == "scatter"
    assert viz_config.option["xAxis"]["type"] == "value"
    assert viz_config.option["yAxis"]["type"] == "value"


def test_missing_column_returns_error():
    params = DataVisualizationParams(
        data={"gene": ["BRCA1"], "expression": [42.5]},
        plot_type="boxplot",
        x_column="gene",
        y_column="missing_column",
    )
    result = data_visualization.create_data_visualization(params)

    assert result.success is False
    assert "missing_column" in result.error
