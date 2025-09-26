"""Tests for Quilt-style JWT decompression utilities."""

from __future__ import annotations

import base64
import json

import pytest

from quilt_mcp.services.jwt_decoder import process_compressed_jwt, safe_decompress_jwt


def test_process_compressed_jwt_handles_grouped_buckets():
    payload = {
        "sub": "abc",
        "p": ["g", "l", "amu"],
        "r": ["ReadWriteQuiltV2-sales-prod"],
        "b": {
            "_type": "groups",
            "_data": {
                "quilt": ["sandbox", "sales-prod"],
                "cell": ["cell-lake"],
            },
        },
        "l": "write",
    }

    result = process_compressed_jwt(payload)

    assert sorted(result["permissions"]) == [
        "s3:AbortMultipartUpload",
        "s3:GetObject",
        "s3:ListBucket",
    ]
    assert sorted(result["buckets"]) == ["cell-lake", "quilt-sales-prod", "quilt-sandbox"]
    assert result["roles"] == ["ReadWriteQuiltV2-sales-prod"]
    assert result["level"] == "write"


def test_safe_decompress_jwt_falls_back_on_errors():
    bogus_data = base64.b64encode(json.dumps(["quilt-sandbox"]).encode("utf-8")).decode("utf-8")
    bad_payload = {"b": {"_type": "compressed", "_data": bogus_data[:-2]}}  # corrupt data

    result = safe_decompress_jwt(bad_payload)

    assert result["permissions"] == ["s3:GetObject"]
    assert result["buckets"] == []
    assert result["scope"] == "read"

