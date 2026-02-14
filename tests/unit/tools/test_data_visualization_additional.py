from __future__ import annotations

from types import SimpleNamespace

import pytest

from quilt_mcp.tools import data_visualization as dv


def test_normalize_data_variants_and_errors():
    rows = dv._normalize_data([{"a": 1}, {"a": 2}])
    assert rows == [{"a": 1}, {"a": 2}]

    from_dict = dv._normalize_data({"a": [1, 2], "b": ["x", "y"]})
    assert from_dict == [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]

    with pytest.raises(ValueError, match="Column lengths must match"):
        dv._normalize_data({"a": [1], "b": [1, 2]})

    with pytest.raises(ValueError, match="Input data is empty"):
        dv._normalize_data({"a": []})

    with pytest.raises(ValueError, match="CSV string produced no rows"):
        dv._normalize_data("a,b\n")

    with pytest.raises(ValueError, match="Unsupported data type"):
        dv._normalize_data(123)  # type: ignore[arg-type]


def test_split_s3_uri_and_plot_type_normalization():
    assert dv._split_s3_uri("s3://bucket/key.csv") == ("bucket", "key.csv")
    assert dv._split_s3_uri("quilt+s3://bucket/path/file.tsv") == ("bucket", "path/file.tsv")

    with pytest.raises(ValueError, match="Invalid S3 URI"):
        dv._split_s3_uri("http://bucket/key")
    with pytest.raises(ValueError, match="Invalid S3 URI path"):
        dv._split_s3_uri("s3://bucket")
    with pytest.raises(ValueError, match="Invalid S3 URI components"):
        dv._split_s3_uri("s3:///key")

    assert dv._normalize_plot_type("box") == "boxplot"
    assert dv._normalize_plot_type("scatterplot") == "scatter"
    assert dv._normalize_plot_type("line-plot") == "line"
    assert dv._normalize_plot_type("bar_plot") == "bar_plot"


def test_load_from_s3_and_records_from_csv(monkeypatch):
    class FakeBody:
        def __init__(self, payload: bytes):
            self._payload = payload

        def read(self):
            return self._payload

    class FakeClient:
        def __init__(self, payload: bytes):
            self.payload = payload

        def get_object(self, **_kwargs):
            return {"Body": FakeBody(self.payload)}

    monkeypatch.setattr(dv, "get_s3_client", lambda: FakeClient(b"a,b\n1,2\n"))
    rows = dv._load_from_s3("s3://bucket/data.csv")
    assert rows == [{"a": "1", "b": "2"}]

    monkeypatch.setattr(dv, "get_s3_client", lambda: FakeClient(b"a\tb\n1\t2\n"))
    tsv_rows = dv._load_from_s3("s3://bucket/data.tsv")
    assert tsv_rows == [{"a": "1", "b": "2"}]

    monkeypatch.setattr(dv, "get_s3_client", lambda: FakeClient(b'[{"x":1}]'))
    json_rows = dv._load_from_s3("s3://bucket/data.json")
    assert json_rows == [{"x": 1}]

    monkeypatch.setattr(dv, "get_s3_client", lambda: FakeClient(b'{"x":[1,2]}'))
    json_dict_rows = dv._load_from_s3("s3://bucket/data.json")
    assert json_dict_rows == [{"x": 1}, {"x": 2}]

    monkeypatch.setattr(dv, "get_s3_client", lambda: FakeClient(b'"bad"'))
    with pytest.raises(ValueError, match="Unsupported JSON structure"):
        dv._load_from_s3("s3://bucket/data.json")

    monkeypatch.setattr(dv, "get_s3_client", lambda: FakeClient(b"hello"))
    with pytest.raises(ValueError, match="Unsupported file format"):
        dv._load_from_s3("s3://bucket/data.bin")

    class NoBodyClient:
        def get_object(self, **_kwargs):
            return {}

    monkeypatch.setattr(dv, "get_s3_client", lambda: NoBodyClient())
    with pytest.raises(ValueError, match="Body missing"):
        dv._load_from_s3("s3://bucket/data.csv")

    with pytest.raises(ValueError, match="contains no data rows"):
        dv._records_from_csv("a,b\n", delimiter=",")


def test_validate_requirements_and_create_visualization_config():
    records = [{"x": 1, "y": 2, "g": "a"}, {"x": 2, "y": 3, "g": "b"}]
    dv._validate_plot_requirements(records, "scatter", "x", "y", "g")

    with pytest.raises(ValueError, match="at least one data row"):
        dv._validate_plot_requirements([], "scatter", "x", "y", None)
    with pytest.raises(ValueError, match="Columns not found"):
        dv._validate_plot_requirements(records, "scatter", "missing", "y", None)
    with pytest.raises(ValueError, match="requires 'y_column'"):
        dv._validate_plot_requirements(records, "scatter", "x", None, None)

    res = dv._create_visualization_config(
        records=records,
        plot_type="scatter",
        x_column="x",
        y_column="y",
        group_column="g",
        title="T",
        xlabel="X",
        ylabel="Y",
        color_scheme="default",
        output_format="echarts",
    )
    assert res.engine == "echarts"
    assert res.option["series"][0]["type"] == "scatter"

    with pytest.raises(ValueError, match="only 'echarts'"):
        dv._create_visualization_config(
            records=records,
            plot_type="scatter",
            x_column="x",
            y_column="y",
            group_column=None,
            title="T",
            xlabel="X",
            ylabel="Y",
            color_scheme="default",
            output_format="vega",
        )
    with pytest.raises(ValueError, match="Unsupported plot_type"):
        dv._create_visualization_config(
            records=records,
            plot_type="pie",
            x_column="x",
            y_column="y",
            group_column=None,
            title="T",
            xlabel="X",
            ylabel="Y",
            color_scheme="default",
            output_format="echarts",
        )


def test_chart_helpers_data_file_and_stats():
    records = [
        {"x": "A", "y": "1", "g": "one"},
        {"x": "A", "y": "2", "g": "one"},
        {"x": "B", "y": "3", "g": "two"},
        {"x": "B", "y": "bad", "g": "two"},
    ]

    box = dv._create_echarts_boxplot(records, "x", "y", "", "X", "Y", dv.COLOR_SCHEMES["default"])
    assert box["series"][0]["type"] == "boxplot"

    scatter_grouped = dv._create_echarts_scatter(records, "y", "y", "g", "", "X", "Y", dv.COLOR_SCHEMES["default"])
    assert len(scatter_grouped["series"]) == 2
    scatter_single = dv._create_echarts_scatter(records, "y", "y", None, "", "X", "Y", dv.COLOR_SCHEMES["default"])
    assert scatter_single["series"][0]["type"] == "scatter"

    line_grouped = dv._create_echarts_line(records, "y", "y", "g", "", "X", "Y", dv.COLOR_SCHEMES["default"])
    assert len(line_grouped["series"]) == 2
    line_single = dv._create_echarts_line(records, "y", "y", None, "", "X", "Y", dv.COLOR_SCHEMES["default"])
    assert line_single["series"][0]["type"] == "line"

    bar_grouped = dv._create_echarts_bar(records, "x", "y", "g", "", "X", "Y", dv.COLOR_SCHEMES["default"])
    assert len(bar_grouped["series"]) == 2
    bar_single = dv._create_echarts_bar(records, "x", "y", None, "", "X", "Y", dv.COLOR_SCHEMES["default"])
    assert bar_single["series"][0]["type"] == "bar"

    data_file = dv._create_data_file(records, "bar", "x", "y", "g")
    assert data_file["filename"] == "viz_data_bar.csv"
    assert "x,y,g" in data_file["content"] or "g,x,y" in data_file["content"]
    with pytest.raises(ValueError, match="empty records"):
        dv._create_data_file([], "bar", "x", "y", None)

    stats = dv._calculate_statistics(records, "y")
    assert stats["count"] == 3
    assert stats["min"] == 1.0
    assert stats["max"] == 3.0
    assert dv._calculate_statistics(records, None) == {}
    assert dv._calculate_statistics([{"y": "bad"}], "y") == {}


def test_misc_utilities_and_error_paths():
    assert dv._make_filename("line", "time point", "value") == "viz_line_time_point_value.json"
    assert dv._make_filename("", "", "") == "viz_visualization.json"

    assert dv._five_number_summary([1]) == (1.0, 1.0, 1.0, 1.0, 1.0)
    assert dv._variance([2], 2.0) == 0.0
    assert dv._extract_point({"x": "1", "y": "2"}, "x", "y") == [1.0, 2.0]
    assert dv._extract_point({"x": "x", "y": "2"}, "x", "y") is None
    assert dv._to_float(" 2.5 ") == 2.5
    assert dv._to_float(None) is None
    assert dv._mean_or_zero([]) == 0.0

    assert "Verify x_column" in dv._get_error_suggestion(ValueError("Columns not found"))
    assert "Use one of" in dv._get_error_suggestion(ValueError("unsupported plot_type"))
    assert "Provide CSV" in dv._get_error_suggestion(ValueError("unsupported file format"))
    assert "Include y_column" in dv._get_error_suggestion(ValueError("requires 'y_column'"))
    assert "Check the error details" in dv._get_error_suggestion(ValueError("other"))

    assert "box plot" in dv._build_description("boxplot", "X", "Y").lower()
    assert "scatter plot" in dv._build_description("scatter", "X", "Y").lower()
    assert "line chart" in dv._build_description("line", "X", "Y").lower()
    assert "bar chart" in dv._build_description("bar", "X", "Y").lower()
    assert "interactive visualization" in dv._build_description("other", "X", "Y").lower()


def test_create_data_visualization_error_and_success_metadata(monkeypatch):
    # Force unsupported plot type path to verify error wrapper.
    err = dv.create_data_visualization(
        data=[{"x": 1, "y": 2}],
        plot_type="bar",
        x_column="x",
        y_column="y",
        output_format="echarts",
    )
    assert err.success is True

    bad = dv.create_data_visualization(
        data=[{"x": 1, "y": 2}],
        plot_type="bar",
        x_column="missing",
        y_column="y",
    )
    assert bad.success is False
    assert bad.possible_fixes

    # Exercise S3 pathway end-to-end with fake client.
    class FakeBody:
        def read(self):
            return b"x,y\n1,2\n2,4\n"

    class FakeClient:
        def get_object(self, **_kwargs):
            return {"Body": FakeBody()}

    monkeypatch.setattr(dv, "get_s3_client", lambda: FakeClient())
    ok = dv.create_data_visualization(
        data="s3://bucket/data.csv",
        plot_type="line",
        x_column="x",
        y_column="y",
    )
    assert ok.success is True
    assert ok.metadata["plot_type"] == "line"
    assert ok.metadata["statistics"]["count"] == 2
