from pathlib import Path

from quilt_mcp.visualization.analyzers.file_analyzer import FileAnalyzer


def _write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_analyze_file_types_and_finders(tmp_path):
    analyzer = FileAnalyzer()

    _write_text(tmp_path / "data.csv", "a,b\n1,2\n")
    _write_text(tmp_path / "sample.fasta", ">chr1\nACGT\n")
    _write_bytes(tmp_path / "image.png", b"\x89PNG\r\n")
    _write_text(tmp_path / "notes.txt", "hello")
    _write_text(tmp_path / "data.unknown", '{"hello": "world"}')

    file_types = analyzer.analyze_file_types(tmp_path)
    assert any(path.endswith("data.csv") for path in file_types["data"])
    assert any(path.endswith("sample.fasta") for path in file_types["genomic"])
    assert any(path.endswith("image.png") for path in file_types["image"])
    assert any(path.endswith("notes.txt") for path in file_types["text"])
    assert any(path.endswith("data.unknown") for path in file_types["data"])

    data_files = analyzer.find_data_files(tmp_path)
    assert any(path.endswith("data.csv") for path in data_files)

    genomic_files = analyzer.find_genomic_files(tmp_path)
    assert any(path.endswith("sample.fasta") for path in genomic_files)

    image_files = analyzer.find_image_files(tmp_path)
    assert any(path.endswith("image.png") for path in image_files)

    text_files = analyzer.find_text_files(tmp_path)
    assert any(path.endswith("notes.txt") for path in text_files)
