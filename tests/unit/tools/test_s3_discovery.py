from __future__ import annotations

from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from quilt_mcp.tools.s3_discovery import (
    discover_s3_objects,
    organize_file_structure,
    should_include_object,
    validate_bucket_access,
)


def test_validate_bucket_access_not_found():
    s3_client = Mock()
    s3_client.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "Not Found"}},
        "HeadBucket",
    )

    with pytest.raises(ValueError, match="does not exist"):
        validate_bucket_access(s3_client, "missing-bucket")


def test_validate_bucket_access_denied():
    s3_client = Mock()
    s3_client.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "403", "Message": "Access Denied"}},
        "HeadBucket",
    )

    with pytest.raises(ValueError, match="Access denied"):
        validate_bucket_access(s3_client, "private-bucket")


def test_should_include_object_pattern_filtering():
    assert should_include_object("data/table.csv", ["*.csv"], None) is True
    assert should_include_object("data/table.csv", ["*.json"], None) is False
    assert should_include_object("data/tmp.log", None, ["*.log"]) is False


def test_discover_s3_objects_applies_filters():
    page = {
        "Contents": [
            {"Key": "data/a.csv", "Size": 1},
            {"Key": "data/b.json", "Size": 1},
            {"Key": "folder/", "Size": 0},
        ]
    }
    paginator = Mock()
    paginator.paginate.return_value = [page]

    s3_client = Mock()
    s3_client.get_paginator.return_value = paginator

    objects = discover_s3_objects(
        s3_client=s3_client,
        bucket="b",
        prefix="data/",
        include_patterns=["*.csv"],
        exclude_patterns=None,
    )

    assert objects == [{"Key": "data/a.csv", "Size": 1}]


def test_organize_file_structure_auto():
    objects = [
        {"Key": "notes/readme.md", "Size": 1},
        {"Key": "tables/data.parquet", "Size": 1},
        {"Key": "images/plot.png", "Size": 1},
        {"Key": "misc/blob.bin", "Size": 1},
    ]

    organized = organize_file_structure(objects, auto_organize=True)

    assert "docs" in organized
    assert "data/processed" in organized
    assert "data/media" in organized
    assert "data/misc" in organized


def test_organize_file_structure_no_auto():
    objects = [{"Key": "a/b/file.csv", "Size": 1}]
    assert organize_file_structure(objects, auto_organize=False) == {"": objects}
