import json
from contextlib import contextmanager
from typing import Dict, List, NamedTuple, Optional, Set

import pytest

from quilt_mcp.constants import (
    KNOWN_TEST_ENTRY as QUILT_TEST_ENTRY,
    KNOWN_TEST_PACKAGE as QUILT_TEST_PACKAGE,
)
from quilt_mcp.tools.search import search_catalog


@pytest.fixture
def test_package():
    """Return known test package name from environment."""
    return QUILT_TEST_PACKAGE


@pytest.fixture
def test_entry():
    """Return known test entry filename from environment."""
    return QUILT_TEST_ENTRY


class ResultShape(NamedTuple):
    """Shape of search results for easy assertion."""

    count: int
    types: Set[str]
    buckets: Set[str]
    indices: Set[str]


def get_result_shape(results: List[Dict]) -> ResultShape:
    """Extract shape of search results for validation."""
    return ResultShape(
        count=len(results),
        types={r.get("type") for r in results if "type" in r},
        buckets={r.get("bucket") for r in results if "bucket" in r},
        indices={r.get("index") for r in results if "index" in r},
    )


@contextmanager
def diagnostic_search(test_name: str, query: str, scope: str, bucket: str, limit: int = 10):
    """Context manager that executes search and dumps diagnostics on test failure."""
    result = search_catalog(query=query, scope=scope, bucket=bucket, limit=limit)

    try:
        yield result
    except (AssertionError, Exception):
        print(f"\n{'!' * 80}")
        print(f"SEARCH FAILED: {test_name}")
        print(f"{'!' * 80}")
        print(f"Query: {query!r}")

        if isinstance(result, dict) and "results" in result:
            result_count = len(result["results"])
            print(f"Result count: {result_count}")

            if result_count > 0:
                print("\nFirst result:")
                print(json.dumps(result["results"][0], indent=2, default=str))
            else:
                print("No results returned")
        else:
            print(f"Invalid result structure: {type(result)}")

        print(f"{'!' * 80}\n")
        raise


def assert_valid_search_response(result: Dict) -> None:
    """Validate basic search response structure."""
    assert isinstance(result, dict), f"Expected result dict, got {type(result)}"
    assert "results" in result, f"Result missing 'results': {result}"
    assert isinstance(result["results"], list), f"Expected list results, got {type(result['results'])}"

    if "error" in result:
        raise AssertionError(f"Search returned error: {result['error']}")
