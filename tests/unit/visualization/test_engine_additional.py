from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from quilt_mcp.visualization.engine import PackageAnalysis, Visualization, VisualizationEngine


def _analysis(package_path: Path) -> PackageAnalysis:
    return PackageAnalysis(
        package_path=str(package_path),
        file_types={"data": ["a.csv"], "text": ["readme.md"]},
        data_files=[],
        genomic_files=[],
        image_files=[],
        text_files=[],
        metadata={},
        suggested_visualizations=[],
    )


def test_analyze_package_contents_missing_path_raises():
    engine = VisualizationEngine()
    missing = "/tmp/this-path-should-not-exist-for-quilt-tests"  # noqa: S108
    try:
        engine.analyze_package_contents(missing)
    except ValueError as exc:
        assert "does not exist" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing package path")


def test_suggest_visualizations_covers_data_genomic_and_metadata():
    engine = VisualizationEngine()
    suggestions = engine._suggest_visualizations(
        file_types={},
        data_files=["a.csv", "b.json"],
        genomic_files=["reads.bam"],
        metadata={"image_count": 1, "text_count": 2},
    )
    assert "bar_chart" in suggestions
    assert "tree_map" in suggestions
    assert "genome_track" in suggestions
    assert "image_gallery" in suggestions
    assert "text_summary" in suggestions


def test_generate_data_visualization_dispatch_and_error(monkeypatch, tmp_path):
    engine = VisualizationEngine()
    viz_dir = tmp_path / "visualizations"
    viz_dir.mkdir()
    sentinel = Visualization("id", "bar_chart", "t", "d", "f", {})

    monkeypatch.setattr(engine, "_generate_csv_visualization", lambda *_: sentinel)
    monkeypatch.setattr(engine, "_generate_json_visualization", lambda *_: sentinel)
    monkeypatch.setattr(engine, "_generate_excel_visualization", lambda *_: sentinel)
    monkeypatch.setattr(engine, "_generate_parquet_visualization", lambda *_: sentinel)

    assert engine._generate_data_visualization("a.csv", viz_dir) is sentinel
    assert engine._generate_data_visualization("a.tsv", viz_dir) is sentinel
    assert engine._generate_data_visualization("a.json", viz_dir) is sentinel
    assert engine._generate_data_visualization("a.xlsx", viz_dir) is sentinel
    assert engine._generate_data_visualization("a.xls", viz_dir) is sentinel
    assert engine._generate_data_visualization("a.parquet", viz_dir) is sentinel
    assert engine._generate_data_visualization("a.unknown", viz_dir) is None

    def _boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(engine, "_generate_csv_visualization", _boom)
    assert engine._generate_data_visualization("a.csv", viz_dir) is None


def test_generate_csv_visualization_branches(monkeypatch, tmp_path):
    engine = VisualizationEngine()
    viz_dir = tmp_path / "visualizations"
    viz_dir.mkdir()
    csv_file = str(tmp_path / "sample.csv")

    df = pd.DataFrame({"cat": ["a", "b"], "n1": [1, 2], "n2": [3, 4], "t": ["2024-01-01", "2024-01-02"]})
    monkeypatch.setattr(engine.data_processor, "load_csv", lambda *_: df)

    monkeypatch.setattr(
        engine.data_analyzer,
        "analyze_dataframe",
        lambda *_: {
            "has_categorical": True,
            "has_numerical": True,
            "has_temporal": False,
            "categorical_cols": ["cat"],
            "numerical_cols": ["n1", "n2"],
            "temporal_cols": [],
        },
    )
    viz1 = engine._generate_csv_visualization(csv_file, viz_dir)
    assert viz1 is not None and viz1.type == "bar_chart"

    monkeypatch.setattr(
        engine.data_analyzer,
        "analyze_dataframe",
        lambda *_: {
            "has_categorical": False,
            "has_numerical": True,
            "has_temporal": True,
            "categorical_cols": [],
            "numerical_cols": ["n1", "n2"],
            "temporal_cols": ["t"],
        },
    )
    viz2 = engine._generate_csv_visualization(csv_file, viz_dir)
    assert viz2 is not None and viz2.type == "line_chart"

    monkeypatch.setattr(
        engine.data_analyzer,
        "analyze_dataframe",
        lambda *_: {
            "has_categorical": False,
            "has_numerical": False,
            "has_temporal": False,
            "categorical_cols": [],
            "numerical_cols": ["n1", "n2"],
            "temporal_cols": [],
        },
    )
    viz3 = engine._generate_csv_visualization(csv_file, viz_dir)
    assert viz3 is not None and viz3.type == "scatter_plot"

    monkeypatch.setattr(
        engine.data_analyzer,
        "analyze_dataframe",
        lambda *_: {
            "has_categorical": False,
            "has_numerical": False,
            "has_temporal": False,
            "categorical_cols": [],
            "numerical_cols": [],
            "temporal_cols": [],
        },
    )
    assert engine._generate_csv_visualization(csv_file, viz_dir) is None


def test_generate_csv_visualization_handles_empty_and_exceptions(monkeypatch, tmp_path):
    engine = VisualizationEngine()
    viz_dir = tmp_path / "visualizations"
    viz_dir.mkdir()
    csv_file = str(tmp_path / "sample.csv")

    monkeypatch.setattr(engine.data_processor, "load_csv", lambda *_: pd.DataFrame())
    assert engine._generate_csv_visualization(csv_file, viz_dir) is None

    def _boom(*_args, **_kwargs):
        raise RuntimeError("bad csv")

    monkeypatch.setattr(engine.data_processor, "load_csv", _boom)
    assert engine._generate_csv_visualization(csv_file, viz_dir) is None


def test_track_type_mapping_and_genomic_track_generation(tmp_path):
    engine = VisualizationEngine()
    genomics_dir = tmp_path / "genomics"
    genomics_dir.mkdir()

    assert engine._get_track_type_from_extension(".bam") == "alignment"
    assert engine._get_track_type_from_extension(".vcf") == "variant"
    assert engine._get_track_type_from_extension(".zzz") == "annotation"

    bam_viz = engine._generate_genomic_track("reads.bam", genomics_dir)
    assert bam_viz is not None and bam_viz.type == "coverage_plot"

    vcf_viz = engine._generate_genomic_track("calls.vcf", genomics_dir)
    assert vcf_viz is not None and vcf_viz.type == "variant_view"

    bed_viz = engine._generate_genomic_track("genes.bed", genomics_dir)
    assert bed_viz is not None and bed_viz.type == "annotation_track"

    assert engine._generate_genomic_track("other.txt", genomics_dir) is None


def test_generate_genomic_visualizations_and_error(monkeypatch, tmp_path):
    engine = VisualizationEngine()
    viz_dir = tmp_path / "viz"
    viz_dir.mkdir()

    track_viz = Visualization("id1", "coverage_plot", "t", "d", "p", {})
    monkeypatch.setattr(engine, "_generate_genomic_track", lambda f, _d: track_viz if f.endswith(".bam") else None)

    v = engine._generate_genomic_visualizations(
        ["reads.bam", "notes.txt"],
        viz_dir,
        {"genome_assembly": "hg19"},
    )
    assert any(x.id == "igv_session" for x in v)
    assert any(x.type == "coverage_plot" for x in v)
    assert (viz_dir / "genomics" / "igv_session.json").exists()

    monkeypatch.setattr(
        engine.igv_generator, "create_igv_session", lambda *_: (_ for _ in ()).throw(RuntimeError("x"))
    )
    assert engine._generate_genomic_visualizations(["reads.bam"], viz_dir, {}) == []


def test_generate_summary_visualizations_and_error(monkeypatch, tmp_path):
    engine = VisualizationEngine()
    analysis = _analysis(tmp_path)
    viz_dir = tmp_path / "viz"
    viz_dir.mkdir()

    v = engine._generate_summary_visualizations(analysis, viz_dir)
    assert len(v) == 1
    assert v[0].id == "package_overview"
    assert (viz_dir / "package_overview.json").exists()

    import builtins

    real_open = builtins.open

    def _open_boom(*args, **kwargs):
        if str(args[0]).endswith("package_overview.json"):
            raise OSError("no write")
        return real_open(*args, **kwargs)

    monkeypatch.setattr("builtins.open", _open_boom)
    assert engine._generate_summary_visualizations(analysis, viz_dir) == []


def test_create_quilt_summarize_and_generate_package_visualizations(monkeypatch, tmp_path):
    engine = VisualizationEngine()
    viz = [
        Visualization("package_overview", "pie_chart", "Package Overview", "desc", "a/package_overview.json", {}),
        Visualization("id2", "bar_chart", "Bar", "desc", "a/bar.json", {}),
        Visualization("id3", "igv_session", "IGV", "desc", "a/igv_session.json", {}),
        Visualization("id4", "image_gallery", "Images", "desc", "a/images.html", {}),
    ]

    summary = json.loads(engine.create_quilt_summarize(viz))
    assert len(summary) == 4
    assert summary[0]["title"] == "Package Overview"
    assert summary[2]["types"] == ["igv"]

    monkeypatch.setattr(engine, "analyze_package_contents", lambda _p: _analysis(tmp_path))
    monkeypatch.setattr(engine, "generate_visualizations", lambda _a: viz)
    monkeypatch.setattr(engine, "create_quilt_summarize", lambda _v: "[]")
    monkeypatch.setattr(engine, "optimize_layout", lambda _v: {"layout": "grid"})
    result = engine.generate_package_visualizations(str(tmp_path))
    assert result["success"] is True
    assert result["visualization_count"] == 4
    assert result["layout"] == {"layout": "grid"}

    monkeypatch.setattr(engine, "analyze_package_contents", lambda _p: (_ for _ in ()).throw(RuntimeError("bad pkg")))
    failed = engine.generate_package_visualizations(str(tmp_path))
    assert failed["success"] is False
    assert "bad pkg" in failed["error"]
