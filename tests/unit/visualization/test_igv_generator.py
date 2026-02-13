from __future__ import annotations

from pathlib import Path

from quilt_mcp.visualization.generators.igv import IGVGenerator


def test_create_genome_track_variants():
    generator = IGVGenerator()

    annotation_track = generator.create_genome_track("s3://bucket/a.bed", "annotation", {})
    assert annotation_track["type"] == "ANNOTATION"
    assert annotation_track["height"] == 80
    assert annotation_track["autoScale"] is False

    sequence_track = generator.create_genome_track("s3://bucket/a.fa", "sequence", {})
    assert sequence_track["type"] == "SEQUENCE"
    assert sequence_track["height"] == 60
    assert sequence_track["autoScale"] is False

    default_track = generator.create_genome_track("s3://bucket/a.txt", "custom", {"height": 77})
    assert default_track["type"] == "custom"
    assert default_track["height"] == 77


def test_create_views_optional_fields():
    generator = IGVGenerator()

    sequence_view = generator.create_sequence_view("s3://bucket/sample.fa", annotations=[])
    assert "annotationTracks" not in sequence_view

    variant_no_ref = generator.create_variant_view("s3://bucket/sample.vcf", reference="")
    assert "referenceSequence" not in variant_no_ref

    expression_no_genes = generator.create_expression_profile("s3://bucket/expr.tsv", gene_annotations="")
    assert "geneAnnotations" not in expression_no_genes

    coverage_with_regions = generator.create_coverage_plot("s3://bucket/sample.bam", regions=["chr1:1-100"])
    assert coverage_with_regions["regions"] == ["chr1:1-100"]

    coverage_without_regions = generator.create_coverage_plot("s3://bucket/sample.bam", regions=[])
    assert "regions" not in coverage_without_regions


def test_create_igv_session_and_default_locus():
    generator = IGVGenerator()
    tracks = [{"name": "t1", "url": "s3://bucket/t1.bam", "type": "coverage"}]

    session = generator.create_igv_session(tracks, "ce11")
    assert session["genome"] == "ce11"
    assert session["locus"] == "I:1-1000000"
    assert session["genomeURL"] == generator.GENOME_ASSEMBLIES["ce11"]

    fallback_session = generator.create_igv_session(tracks, "unknown")
    assert fallback_session["genomeURL"] == generator.GENOME_ASSEMBLIES["hg38"]
    assert fallback_session["locus"] == "chr1:1-1000000"


def test_multi_track_view_and_dashboard_type_detection():
    generator = IGVGenerator()

    multi = generator.create_multi_track_view(
        ["s3://bucket/a.bam", "s3://bucket/b.vcf"], ["coverage", "variant"], "hg38"
    )
    assert multi["tracks"][0]["type"] == "COVERAGE"
    assert multi["tracks"][1]["type"] == "variant"

    dashboard = generator.create_genomic_dashboard(
        [
            "reads.bam",
            "calls.vcf",
            "genes.gtf",
            "ref.fa",
            "other.bin",
        ],
        "hg19",
        title="My Dashboard",
    )
    track_types = [track["type"] for track in dashboard["tracks"]]
    assert dashboard["title"] == "My Dashboard"
    assert track_types == ["COVERAGE", "variant", "ANNOTATION", "SEQUENCE", "ANNOTATION"]


def test_optimize_track_layout():
    generator = IGVGenerator()
    tracks = [{"name": "a", "height": 600}, {"name": "b", "height": 400}]

    unchanged = generator.optimize_track_layout(tracks, max_height=1200)
    assert unchanged == tracks

    optimized = generator.optimize_track_layout(tracks, max_height=500)
    assert [t["height"] for t in optimized] == [300, 200]

    # Minimum track height floor should be respected when scaling very aggressively.
    floored = generator.optimize_track_layout([{"name": "a", "height": 1000}], max_height=1)
    assert floored[0]["height"] == 30

    assert generator.optimize_track_layout([]) == []


def test_create_track_summary(tmp_path):
    generator = IGVGenerator()
    f1 = tmp_path / "a.bam"
    f2 = tmp_path / "b.vcf"
    f1.write_text("12345")
    f2.write_text("123")

    tracks = [
        {"name": "a", "url": str(f1), "type": "coverage", "height": 60},
        {"name": "b", "url": str(f2), "type": "variant", "height": 70},
        {"name": "c", "url": str(tmp_path / "missing.txt"), "height": 80},
    ]

    summary = generator.create_track_summary(tracks)
    assert summary["total_tracks"] == 3
    assert summary["track_types"]["coverage"] == 1
    assert summary["track_types"]["variant"] == 1
    assert summary["track_types"]["unknown"] == 1
    assert summary["total_height"] == 210
    assert summary["file_sizes"][str(f1)] == 5
    assert summary["file_sizes"][str(f2)] == 3


def test_export_and_validate_session_config(tmp_path):
    generator = IGVGenerator()
    session = generator.create_igv_session([], "hg38")
    output = tmp_path / "igv-session.json"

    assert generator.export_session_file(session, str(output)) is True
    assert output.exists()

    non_dict_tracks = {"version": "1.0", "genome": "unknown", "tracks": {}}
    validation = generator.validate_session_config(non_dict_tracks)
    assert validation["valid"] is False
    assert "Tracks must be a list" in validation["errors"]
    assert any("Unknown genome assembly" in msg for msg in validation["warnings"])

    missing_required = {"tracks": [123, {}]}
    validation2 = generator.validate_session_config(missing_required)
    assert validation2["valid"] is False
    assert "Missing required field: version" in validation2["errors"]
    assert "Missing required field: genome" in validation2["errors"]
    assert any("Track 0 must be a dictionary" in msg for msg in validation2["errors"])
    assert any("Track 1 missing URL" in msg for msg in validation2["warnings"])
    assert any("Track 1 missing type" in msg for msg in validation2["warnings"])

    # Force export failure path with directory target.
    assert generator.export_session_file(session, str(Path(tmp_path))) is False
