import pandas as pd

from quilt_mcp.visualization.generators.echarts import EChartsGenerator
from quilt_mcp.visualization.generators.igv import IGVGenerator
from quilt_mcp.visualization.generators.matplotlib import MatplotlibGenerator
from quilt_mcp.visualization.generators.perspective import PerspectiveGenerator
from quilt_mcp.visualization.generators.vega_lite import VegaLiteGenerator
from quilt_mcp.visualization.layouts.grid_layout import GridLayout


def test_echarts_bar_chart():
    generator = EChartsGenerator()
    df = pd.DataFrame({"category": ["a", "b"], "value": [1, 2]})

    config = generator.create_bar_chart(df, categories="category", values="value", title="Test")
    assert config["title"]["text"] == "Test"
    assert config["series"][0]["type"] == "bar"
    assert config["xAxis"]["data"] == ["b", "a"] or config["xAxis"]["data"] == ["a", "b"]


def test_igv_track_and_sequence_view():
    generator = IGVGenerator()

    track = generator.create_genome_track("s3://bucket/sample.bam", track_type="coverage", config={})
    assert track["type"] == "COVERAGE"
    assert track["height"] == 100

    sequence_view = generator.create_sequence_view("s3://bucket/sample.fa", annotations=["s3://bucket/ann.gtf"])
    assert sequence_view["type"] == "sequence"
    assert "annotationTracks" in sequence_view


def test_layout_and_generator_placeholders():
    layout = GridLayout()
    assert layout.optimize_layout([{"id": "v1"}], {}) == {"layout": "grid", "visualizations": 1}

    assert isinstance(MatplotlibGenerator(), MatplotlibGenerator)
    assert isinstance(PerspectiveGenerator(), PerspectiveGenerator)
    vega = VegaLiteGenerator()
    spec = vega.create_vega_spec("bar", {"values": []}, {})
    assert spec["chart_type"] == "bar"
