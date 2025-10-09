from quilt_mcp.tools.quilt_summary import generate_multi_format_visualizations


def _sample_structure():
    return {
        "data": [
            {"Key": "data/customers.csv", "Size": 4096},
            {"Key": "data/network.json", "Size": 1024},
        ],
        "genomics": [
            {"Key": "genomics/sample.bam", "Size": 512000},
        ],
    }


def test_generate_multi_format_visualizations_selects_formats():
    package_name = "team/example"
    organized_structure = _sample_structure()
    file_types = {"csv": 1, "json": 1, "bam": 1}

    result = generate_multi_format_visualizations(
        package_name=package_name,
        organized_structure=organized_structure,
        file_types=file_types,
    )

    assert result["success"] is True
    assert result["count"] == len(result["visualizations"])

    formats = {viz["format"] for viz in result["visualizations"].values()}
    assert "echarts" in formats
    assert "perspective" in formats
    assert "igv" in formats

    assert len(result["quilt_summarize_entries"]) == result["count"]

    # Perspective entry should provide enriched type metadata
    perspective_entry = next(
        entry
        for entry in result["quilt_summarize_entries"]
        if any(isinstance(t, dict) and t.get("name") == "perspective" for t in entry["types"])
    )
    assert perspective_entry["path"].startswith("visualizations/")
    assert perspective_entry["description"]

    igv_viz = next(viz for viz in result["visualizations"].values() if viz["format"] == "igv")
    assert igv_viz["config"]["tracks"]

    for path in [entry["path"] for entry in result["quilt_summarize_entries"]]:
        assert path in result["files"]
