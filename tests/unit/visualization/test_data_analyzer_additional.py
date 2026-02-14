from __future__ import annotations

from pathlib import Path

import pandas as pd

from quilt_mcp.visualization.analyzers.data_analyzer import DataAnalyzer


def test_analyze_package_metadata_counts_and_flags(tmp_path):
    analyzer = DataAnalyzer()
    package_path = tmp_path / "pkg"
    package_path.mkdir()

    (package_path / "README.md").write_text("# readme", encoding="utf-8")
    (package_path / "metadata.json").write_text("{}", encoding="utf-8")
    (package_path / "table.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (package_path / "table.tsv").write_text("a\tb\n1\t2\n", encoding="utf-8")
    (package_path / "reads.bam").write_text("bam", encoding="utf-8")
    (package_path / "plot.png").write_bytes(b"\x89PNG\r\n")
    (package_path / "notes.txt").write_text("hello", encoding="utf-8")

    metadata = analyzer.analyze_package_metadata(package_path)
    assert metadata["package_name"] == "pkg"
    assert metadata["file_count"] >= 7
    assert metadata["data_count"] == 2
    assert metadata["genomic_count"] == 1
    assert metadata["image_count"] == 1
    assert metadata["text_count"] >= 2
    assert metadata["has_readme"] is True
    assert metadata["has_metadata"] is True
    assert metadata["total_size"] > 0


def test_analyze_package_metadata_error_path():
    analyzer = DataAnalyzer()

    class BrokenPath:
        name = "broken"

        def __str__(self):
            return "/tmp/broken"  # noqa: S108

        def rglob(self, _pattern):
            raise RuntimeError("no access")

    metadata = analyzer.analyze_package_metadata(BrokenPath())  # type: ignore[arg-type]
    assert metadata["package_name"] == "broken"
    assert "error" in metadata


def test_analyze_dataframe_empty_and_rich_types():
    analyzer = DataAnalyzer()
    assert analyzer.analyze_dataframe(pd.DataFrame()) == {}

    df = pd.DataFrame(
        {
            "category": pd.Categorical(["a", "b"] * 30),
            "text": [f"text-{i}" for i in range(60)],
            "num1": list(range(60)),
            "num2": [x * 2 for x in range(60)],
            "when": pd.date_range("2024-01-01", periods=60),
        }
    )
    analysis = analyzer.analyze_dataframe(df)
    assert analysis["has_categorical"] is True
    assert analysis["has_numerical"] is True
    assert analysis["has_temporal"] is True
    assert analysis["has_text"] is True
    assert "category" in analysis["categorical_cols"]
    assert "text" in analysis["text_cols"]
    assert "num1" in analysis["numerical_cols"]
    assert "when" in analysis["temporal_cols"]
    assert "num1" in analysis["correlations"]


def test_analyze_dataframe_correlation_exception(monkeypatch):
    analyzer = DataAnalyzer()
    df = pd.DataFrame({"a": [1, 2, 3], "b": [2, 3, 4]})

    def _bad_corr(*_args, **_kwargs):
        raise RuntimeError("no corr")

    monkeypatch.setattr(pd.DataFrame, "corr", _bad_corr, raising=True)
    analysis = analyzer.analyze_dataframe(df)
    assert analysis["has_numerical"] is True
    assert analysis["correlations"] == {}


def test_analyze_csv_file_error():
    analyzer = DataAnalyzer()
    result = analyzer.analyze_csv_file("/tmp/does-not-exist.csv")  # noqa: S108
    assert result is not None
    assert "error" in result


def test_analyze_json_file_dict_list_and_error(tmp_path):
    analyzer = DataAnalyzer()

    dict_file = tmp_path / "simple.json"
    dict_file.write_text('{"a": 1, "b": 2, "c": 3}', encoding="utf-8")
    dict_analysis = analyzer.analyze_json_file(str(dict_file))
    assert dict_analysis is not None
    assert dict_analysis["type"] == "dict"
    assert dict_analysis["chartable"] is True
    assert dict_analysis["chart_type"] in {"bar_chart", "line_chart"}

    list_file = tmp_path / "rows.json"
    list_file.write_text('[{"x": 1, "y": 2, "z": 3}, {"x": 2, "y": 3, "z": 4}]', encoding="utf-8")
    list_analysis = analyzer.analyze_json_file(str(list_file))
    assert list_analysis is not None
    assert list_analysis["type"] == "list"
    assert list_analysis["array_length"] == 2
    assert list_analysis["chartable"] is True
    assert list_analysis["chart_type"] == "scatter_plot"

    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{", encoding="utf-8")
    bad_analysis = analyzer.analyze_json_file(str(bad_file))
    assert bad_analysis is not None
    assert "error" in bad_analysis


def test_depth_chartability_and_chart_suggestion_helpers():
    analyzer = DataAnalyzer()

    assert analyzer._get_max_depth({"a": {"b": [1, {"c": 2}]}}) >= 4
    assert analyzer._get_max_depth([]) == 1

    assert analyzer._is_chartable_dict({}) is False
    assert analyzer._is_chartable_dict({"a": 1, "b": 2, "c": "x"}) is True
    assert analyzer._is_chartable_dict({"a": "x", "b": "y"}) is False

    assert analyzer._is_chartable_list([]) is False
    assert analyzer._is_chartable_list([{"a": 1}, {"a": 2}]) is False
    assert analyzer._is_chartable_list([{"a": 1, "b": 2}, {"a": 3, "b": 4}]) is True
    assert analyzer._is_chartable_list([{"a": True, "b": False}, {"a": True, "b": False}]) is False

    assert analyzer._suggest_chart_type({"a": 1, "b": 2}) == "bar_chart"
    assert analyzer._suggest_chart_type({str(i): i for i in range(11)}) == "line_chart"
    assert analyzer._suggest_chart_type([{"a": 1, "b": 2}]) == "line_chart"
    assert analyzer._suggest_chart_type([{"a": 1, "b": 2, "c": 3}]) == "scatter_plot"
    assert analyzer._suggest_chart_type("fallback") == "bar_chart"
