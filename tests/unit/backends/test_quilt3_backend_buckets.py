from __future__ import annotations

import pytest

from quilt_mcp.backends.quilt3_backend_buckets import Quilt3_Backend_Buckets
from quilt_mcp.ops.exceptions import BackendError


class DummyBucketsBackend(Quilt3_Backend_Buckets):
    def _normalize_string_field(self, value):
        return str(value).strip()

    def _normalize_datetime(self, dt):
        if dt is None:
            return None
        return "2025-01-01T00:00:00Z"


def test_transform_bucket_success_with_defaults():
    backend = DummyBucketsBackend()
    info = backend._transform_bucket("my-bucket", {"region": "", "access_level": "", "created_date": None})

    assert info.name == "my-bucket"
    assert info.region == "unknown"
    assert info.access_level == "unknown"
    assert info.created_date is None


def test_validate_bucket_fields_errors():
    backend = DummyBucketsBackend()

    with pytest.raises(BackendError, match="missing name"):
        backend._validate_bucket_fields("", {})

    with pytest.raises(BackendError, match="bucket_data is None"):
        backend._validate_bucket_fields("bucket", None)


def test_transform_bucket_wraps_unexpected_errors():
    class BadBackend(DummyBucketsBackend):
        def _normalize_string_field(self, value):
            raise RuntimeError("normalize failed")

    backend = BadBackend()
    with pytest.raises(BackendError, match="bucket transformation failed"):
        backend._transform_bucket("bucket", {"region": "us-east-1", "access_level": "read"})
