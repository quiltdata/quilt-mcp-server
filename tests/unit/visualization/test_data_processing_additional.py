from __future__ import annotations

import json

import pandas as pd

from quilt_mcp.visualization.utils.data_processing import DataProcessor


def test_detect_file_format_extensions_and_content(tmp_path, monkeypatch):
    processor = DataProcessor()

    xlsx_path = tmp_path / "data.xlsx"
    xlsx_path.write_text("placeholder", encoding="utf-8")
    parquet_path = tmp_path / "data.parquet"
    parquet_path.write_text("placeholder", encoding="utf-8")
    h5_path = tmp_path / "data.h5"
    h5_path.write_text("placeholder", encoding="utf-8")
    csv_content_path = tmp_path / "content.unknown"
    csv_content_path.write_text("a,b\n1,2\n", encoding="utf-8")
    tsv_content_path = tmp_path / "content2.unknown"
    tsv_content_path.write_text("a\tb\n1\t2\n", encoding="utf-8")
    unknown_path = tmp_path / "unknown.bin"
    unknown_path.write_text("nodelimiter", encoding="utf-8")

    assert processor.detect_file_format(str(xlsx_path)) == "excel"
    assert processor.detect_file_format(str(parquet_path)) == "parquet"
    assert processor.detect_file_format(str(h5_path)) == "hdf5"
    assert processor.detect_file_format(str(csv_content_path)) == "csv"
    assert processor.detect_file_format(str(tsv_content_path)) == "tsv"
    assert processor.detect_file_format(str(unknown_path)) is None

    def _open_boom(*_args, **_kwargs):
        raise OSError("denied")

    monkeypatch.setattr("builtins.open", _open_boom)
    assert processor.detect_file_format(str(csv_content_path)) is None


def test_loaders_and_load_data_dispatch(tmp_path, monkeypatch):
    processor = DataProcessor()

    csv_path = tmp_path / "data.csv"
    csv_path.write_text("a,b\n1,2\n", encoding="utf-8")
    json_path = tmp_path / "data.json"
    json_path.write_text(json.dumps({"x": 1}), encoding="utf-8")
    xlsx_path = tmp_path / "data.xlsx"
    xlsx_path.write_text("placeholder", encoding="utf-8")
    parquet_path = tmp_path / "data.parquet"
    parquet_path.write_text("placeholder", encoding="utf-8")

    assert processor.load_data(str(json_path)) == {"x": 1}
    assert isinstance(processor.load_data(str(csv_path)), pd.DataFrame)

    monkeypatch.setattr(pd, "read_excel", lambda *_args, **_kwargs: pd.DataFrame({"a": [1]}))
    monkeypatch.setattr(pd, "read_parquet", lambda *_args, **_kwargs: pd.DataFrame({"a": [1]}))
    assert isinstance(processor.load_data(str(xlsx_path)), pd.DataFrame)
    assert isinstance(processor.load_data(str(parquet_path)), pd.DataFrame)

    bad_path = tmp_path / "bad.json"
    bad_path.write_text("{", encoding="utf-8")
    assert processor.load_json(str(bad_path)) is None

    monkeypatch.setattr(pd, "read_csv", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("csv bad")))
    monkeypatch.setattr(pd, "read_excel", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("xlsx bad")))
    monkeypatch.setattr(pd, "read_parquet", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("pq bad")))
    assert processor.load_csv(str(csv_path)) is None
    assert processor.load_excel(str(xlsx_path)) is None
    assert processor.load_parquet(str(parquet_path)) is None

    unsupported = tmp_path / "data.unsupported"
    unsupported.write_text("x", encoding="utf-8")
    assert processor.load_data(str(unsupported)) is None


def test_preprocess_and_sample_branches(monkeypatch):
    processor = DataProcessor()
    df = pd.DataFrame(
        {
            "cat": ["a", None, "b", None],
            "num": [1.0, None, 3.0, 4.0],
            "all_null": [None, None, None, None],
        }
    )

    processed = processor.preprocess_data(df, max_rows=10)
    assert len(processed) <= 4
    assert "all_null" not in processed.columns
    assert processed["cat"].isnull().sum() == 0
    assert processed["num"].isnull().sum() == 0

    assert processor.preprocess_data({"a": 1}) == {"a": 1}
    assert processor.preprocess_data(None) is None

    sampled_small = processor.sample_data(processed, sample_size=50)
    assert len(sampled_small) == len(processed)
    sampled_one = processor.sample_data(processed, sample_size=1)
    assert len(sampled_one) == 1
    assert processor.sample_data([1, 2, 3], sample_size=1) == [1, 2, 3]
    assert processor.sample_data(None, sample_size=1) is None

    class BoomFrame(pd.DataFrame):
        @property
        def _constructor(self):
            return BoomFrame

        def dropna(self, *args, **kwargs):
            raise RuntimeError("dropna failed")

    boom = BoomFrame({"a": [1, 2]})
    assert processor.preprocess_data(boom).equals(boom)


def test_get_data_summary_and_validate_data_branches():
    processor = DataProcessor()

    assert processor.get_data_summary(None) == {"error": "No data provided"}

    df = pd.DataFrame({**{f"c{i}": [None if i % 2 == 0 else i, i] for i in range(101)}, "mixed": ["x", 1]})
    summary = processor.get_data_summary(df)
    assert "shape" in summary
    assert "numeric_columns" in summary

    non_df_summary = processor.get_data_summary((1, 2, 3))
    assert non_df_summary["type"] == "tuple"
    assert non_df_summary["length"] == 3

    none_validation = processor.validate_data(None)
    assert none_validation["valid"] is False

    empty_validation = processor.validate_data(pd.DataFrame())
    assert empty_validation["valid"] is False
    assert "DataFrame is empty" in empty_validation["errors"]

    huge_rows = pd.DataFrame({"x": list(range(100001)), "y": [None] * 100001, "z": [None] * 100001})
    huge_validation = processor.validate_data(huge_rows)
    assert any("many rows" in w for w in huge_validation["warnings"])
    assert any("sample_data" in s.lower() for s in huge_validation["suggestions"])
    assert any("many missing values" in w for w in huge_validation["warnings"])

    mixed_validation = processor.validate_data(df)
    assert any("many columns" in w for w in mixed_validation["warnings"])
    assert any("mixed data types" in w for w in mixed_validation["warnings"])

    list_validation = processor.validate_data([1, 2, 3])
    assert list_validation["valid"] is True
    assert any("not a pandas DataFrame" in w for w in list_validation["warnings"])


def test_create_sample_dataset_and_error(monkeypatch):
    processor = DataProcessor()
    sample = processor.create_sample_dataset(size=25)
    assert isinstance(sample, pd.DataFrame)
    assert len(sample) == 25
    assert {"category", "value", "date", "score"} <= set(sample.columns)

    import numpy as np

    monkeypatch.setattr(np.random, "choice", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("rand bad")))
    assert processor.create_sample_dataset(size=5) is None
