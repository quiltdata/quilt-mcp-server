from __future__ import annotations

from quilt_mcp.tools.package_metadata import generate_package_metadata, generate_readme_content


def _sample_structure():
    return {
        "data/processed": [{"Key": "input/a.csv", "Size": 100}],
        "docs": [{"Key": "docs/readme.md", "Size": 20}],
    }


def test_generate_package_metadata_standard():
    metadata = generate_package_metadata(
        package_name="team/pkg",
        source_info={"bucket": "source-bucket", "prefix": "input/"},
        organized_structure=_sample_structure(),
        metadata_template="standard",
        user_metadata={"owner": "team-a"},
    )

    assert metadata["quilt"]["source"]["bucket"] == "source-bucket"
    assert metadata["quilt"]["source"]["total_objects"] == 2
    assert set(metadata["quilt"]["data_profile"]["file_types"]) == {"csv", "md"}
    assert metadata["user_metadata"]["owner"] == "team-a"


def test_generate_package_metadata_template_sections():
    ml_metadata = generate_package_metadata(
        package_name="team/ml",
        source_info={"bucket": "b"},
        organized_structure=_sample_structure(),
        metadata_template="ml",
    )
    analytics_metadata = generate_package_metadata(
        package_name="team/ana",
        source_info={"bucket": "b"},
        organized_structure=_sample_structure(),
        metadata_template="analytics",
    )

    assert "ml" in ml_metadata
    assert "analytics" in analytics_metadata


def test_generate_readme_content_contains_summary():
    readme = generate_readme_content(
        package_name="team/pkg",
        description="Demo package",
        organized_structure=_sample_structure(),
        total_size=120,
        source_info={"bucket": "source-bucket", "source_description": "S3 source"},
        metadata_template="standard",
    )

    assert "# team/pkg" in readme
    assert "Demo package" in readme
    assert "source-bucket" in readme
    assert "data/processed/" in readme
