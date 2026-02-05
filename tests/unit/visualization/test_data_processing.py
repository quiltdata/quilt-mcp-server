import json

import pandas as pd

from quilt_mcp.visualization.utils.data_processing import DataProcessor


def test_detect_file_format(tmp_path):
    processor = DataProcessor()

    csv_path = tmp_path / "data.csv"
    csv_path.write_text("a,b\n1,2\n", encoding="utf-8")

    tsv_path = tmp_path / "data.tsv"
    tsv_path.write_text("a\tb\n1\t2\n", encoding="utf-8")

    json_path = tmp_path / "data.json"
    json_path.write_text(json.dumps({"a": 1}), encoding="utf-8")

    unknown_path = tmp_path / "data.unknown"
    unknown_path.write_text('{"hello": "world"}', encoding="utf-8")

    assert processor.detect_file_format(str(csv_path)) == "csv"
    assert processor.detect_file_format(str(tsv_path)) == "csv"
    assert processor.detect_file_format(str(json_path)) == "json"
    assert processor.detect_file_format(str(unknown_path)) == "json"
    assert processor.detect_file_format(str(tmp_path / "missing.csv")) is None


def test_load_json_and_load_data(tmp_path):
    processor = DataProcessor()
    json_path = tmp_path / "data.json"
    json_path.write_text(json.dumps({"a": 1, "b": [1, 2]}), encoding="utf-8")

    loaded = processor.load_json(str(json_path))
    assert loaded == {"a": 1, "b": [1, 2]}

    loaded_auto = processor.load_data(str(json_path))
    assert loaded_auto == {"a": 1, "b": [1, 2]}


def test_preprocess_and_sample_data_dataframe():
    processor = DataProcessor()
    df = pd.DataFrame(
        {
            "category": ["a", None, "b"],
            "value": [1.0, None, 3.0],
        }
    )

    processed = processor.preprocess_data(df)
    assert processed.isnull().sum().sum() == 0
    assert set(processed["category"].unique()) >= {"a", "b", "Unknown"}

    sampled = processor.sample_data(processed, sample_size=1)
    assert len(sampled) == 1


def test_summary_and_validation_for_non_dataframe():
    processor = DataProcessor()
    payload = [1, 2, 3]

    summary = processor.get_data_summary(payload)
    assert summary["type"] == "list"
    assert summary["length"] == 3

    validation = processor.validate_data(payload)
    assert validation["valid"] is True
    assert "Data is not a pandas DataFrame" in validation["warnings"]
