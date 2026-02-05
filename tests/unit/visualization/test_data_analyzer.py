import pandas as pd

from quilt_mcp.visualization.analyzers.data_analyzer import DataAnalyzer


def test_analyze_dataframe_detects_column_types():
    analyzer = DataAnalyzer()
    df = pd.DataFrame(
        {
            "category": ["a", "b", "c"],
            "value": [1.0, 2.0, 3.0],
        }
    )

    analysis = analyzer.analyze_dataframe(df)
    assert analysis["has_categorical"] is True
    assert analysis["has_numerical"] is True
    assert "category" in analysis["categorical_cols"]
    assert "value" in analysis["numerical_cols"]


def test_analyze_csv_file(tmp_path):
    analyzer = DataAnalyzer()
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("category,value\na,1\nb,2\n", encoding="utf-8")

    analysis = analyzer.analyze_csv_file(str(csv_path))
    assert analysis is not None
    assert "columns" in analysis
