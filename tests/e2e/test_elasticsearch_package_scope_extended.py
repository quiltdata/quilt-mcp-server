"""Extended package scope tests for Elasticsearch backend."""

import os
import pytest
import logging
from quilt_mcp.search.backends.elasticsearch import Quilt3ElasticsearchBackend

pytestmark = pytest.mark.usefixtures("requires_search")

logger = logging.getLogger(__name__)
QUILT_TEST_BUCKET = os.getenv("QUILT_TEST_BUCKET", "")

ELASTICSEARCH_SUPPORTS_COLLAPSE = False  # Set to False until backend adds support

requires_collapse = pytest.mark.xfail(
    not ELASTICSEARCH_SUPPORTS_COLLAPSE,
    reason="Elasticsearch backend does not support collapse feature yet",
    raises=AssertionError,
)


@pytest.fixture
def backend(quilt3_backend):
    """Get initialized Elasticsearch backend."""
    backend = Quilt3ElasticsearchBackend(backend=quilt3_backend)
    backend._initialize()
    return backend


class TestPackageScopeIntegrationExtended:
    """Extended package scope coverage tests."""

    @requires_collapse
    async def test_package_scope_wildcard_query(self, backend, test_bucket):
        """Should handle wildcard queries correctly."""
        response = await backend.search(query="*", scope="package", bucket=test_bucket, limit=10)

        assert response.status.value == "available", f"Wildcard search failed: {response.error_message}"

        if len(response.results) == 0:
            logger.warning(
                f"Wildcard query returned no results in {test_bucket}. "
                f"This may indicate no packages exist or wildcard queries are disabled."
            )
            pytest.skip("No packages found with wildcard query")

        for result in response.results:
            assert result.type == "package"
            assert result.metadata.get("ptr_name")

        logger.info(f"✅ Wildcard query returned {len(response.results)} packages")

    @requires_collapse
    async def test_package_scope_limit_respected(self, backend, test_bucket):
        """Should respect limit parameter."""
        limit = 3
        response = await backend.search(query="*", scope="package", bucket=test_bucket, limit=limit)

        assert response.status.value in ["available", "not_found"], f"Limited search failed: {response.error_message}"
        assert len(response.results) <= limit, f"Results ({len(response.results)}) exceeded limit ({limit})"

        logger.info(f"✅ Limit respected: {len(response.results)} <= {limit}")

    @requires_collapse
    async def test_package_scope_metadata_completeness(self, backend, test_bucket):
        """Should include all required metadata fields."""
        response = await backend.search(query="*", scope="package", bucket=test_bucket, limit=5)

        assert response.status.value == "available", f"Package search failed: {response.error_message}"
        assert len(response.results) > 0, f"No packages found in {test_bucket}"

        required_fields = ["ptr_name", "matched_entries", "matched_entry_count", "showing_entries", "_index"]

        for result in response.results:
            for field in required_fields:
                assert field in result.metadata, f"Package {result.name} missing required field: {field}"

            logger.debug(
                f"Package {result.name}: "
                f"ptr_name={result.metadata['ptr_name']}, "
                f"entries={result.metadata['matched_entry_count']}"
            )

        logger.info("✅ All required metadata fields present")


class TestPackageScopeEdgeCases:
    """Test edge cases and error conditions for package scope."""

    async def test_package_scope_nonexistent_bucket(self, backend):
        """Should handle nonexistent bucket gracefully."""
        response = await backend.search(
            query="test", scope="package", bucket="this-bucket-definitely-does-not-exist-12345", limit=10
        )

        assert response.status.value == "error", f"Expected error for nonexistent bucket, got: {response.status.value}"
        assert response.error_message, "Error response should have error message"

        logger.info("✅ Nonexistent bucket handled gracefully")

    async def test_package_scope_empty_query(self, backend, test_bucket):
        """Should handle empty query string."""
        response = await backend.search(query="", scope="package", bucket=test_bucket, limit=10)

        assert response.status.value in ["available", "not_found", "error"], (
            f"Unexpected status for empty query: {response.status.value}"
        )

        logger.info(f"Empty query status: {response.status.value}")

    @requires_collapse
    async def test_package_scope_special_characters(self, backend, test_bucket):
        """Should handle special characters in queries."""
        special_queries = ["test-file", "test_file", "test.csv"]

        for query in special_queries:
            logger.info(f"Testing query with special chars: {query}")

            response = await backend.search(query=query, scope="package", bucket=test_bucket, limit=5)

            assert response.status.value in ["available", "not_found"], (
                f"Query '{query}' failed: {response.error_message}"
            )

        logger.info("✅ Special character queries handled properly")
