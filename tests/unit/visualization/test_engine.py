from pathlib import Path

from quilt_mcp.visualization.engine import VisualizationEngine


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_analyze_package_contents(tmp_path):
    package_path = tmp_path / "pkg"
    package_path.mkdir()

    _write_text(package_path / "data.csv", "x,y\n1,2\n3,4\n")
    _write_text(package_path / "readme.md", "# README\n")
    _write_text(package_path / "notes.txt", "hello")
    _write_text(package_path / "metadata.json", '{"name": "pkg"}')

    (package_path / "image.png").write_bytes(b"\x89PNG\r\n")

    engine = VisualizationEngine()
    analysis = engine.analyze_package_contents(str(package_path))

    assert analysis.package_path == str(package_path)
    assert analysis.metadata["file_count"] >= 4
    assert analysis.metadata["data_count"] == 1
    assert analysis.metadata["image_count"] == 1
    assert analysis.metadata["text_count"] >= 2
    assert "image_gallery" in analysis.suggested_visualizations
    assert "text_summary" in analysis.suggested_visualizations
    assert any(viz in analysis.suggested_visualizations for viz in ["bar_chart", "line_chart", "scatter_plot"])
