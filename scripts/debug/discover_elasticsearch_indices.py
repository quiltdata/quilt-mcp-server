#!/usr/bin/env python3
"""Discover actual Elasticsearch index structure.

This script makes REAL calls to:
1. Discover available buckets
2. Execute searches against different index patterns
3. Examine actual document structure in each index type

Goal: Learn what indices actually exist and what they contain.

Usage:
    python scripts/discover_elasticsearch_indices.py [bucket_name]

If bucket_name is not provided, uses QUILT_TEST_BUCKET from .env
"""

import asyncio
import json
import os
import sys
from quilt_mcp.search.backends.elasticsearch import Quilt3ElasticsearchBackend
from quilt_mcp.services.quilt_service import QuiltService


async def main():
    print("=" * 80)
    print("ELASTICSEARCH INDEX DISCOVERY")
    print("=" * 80)

    # Get bucket from command line or environment
    if len(sys.argv) > 1:
        test_bucket = sys.argv[1]
        print(f"\nUsing bucket from command line: {test_bucket}")
    else:
        test_bucket_env = os.getenv("QUILT_TEST_BUCKET", "")
        if test_bucket_env:
            test_bucket = test_bucket_env.replace("s3://", "").split("/")[0]
            print(f"\nUsing QUILT_TEST_BUCKET from .env: {test_bucket}")
        else:
            print("\nERROR: No bucket specified and QUILT_TEST_BUCKET not set in .env")
            print("Usage: python scripts/discover_elasticsearch_indices.py [bucket_name]")
            return

    # Initialize backend
    service = QuiltService()
    backend = Quilt3ElasticsearchBackend(quilt_service=service)
    backend._initialize()

    # Verify bucket exists in available buckets
    print("\n1. VERIFYING BUCKET ACCESS...")
    buckets = backend._get_available_buckets()
    print(f"   Found {len(buckets)} available buckets")

    if test_bucket not in buckets:
        print(f"   ⚠️  WARNING: '{test_bucket}' not in available buckets list")
        print(f"   Available buckets: {buckets[:5]}...")
        print(f"   Continuing anyway...")

    print(f"\n2. INSPECTING BUCKET: {test_bucket}")

    # Test different index patterns
    patterns_to_test = [
        (f"{test_bucket}", "FILE INDEX - S3 objects"),
        (f"{test_bucket}_packages", "ENTRY INDEX - package entries (_packages suffix)"),
        (f"{test_bucket}_manifests", "MANIFEST INDEX? (_manifests suffix)"),
        (f"{test_bucket}_package", "MANIFEST INDEX? (_package suffix, singular)"),
        (f"*{test_bucket}*", "WILDCARD - all indices containing bucket name"),
    ]

    print("\n3. TESTING INDEX PATTERNS...")
    for pattern, description in patterns_to_test:
        print(f"\n   Testing: {pattern} ({description})")
        print(f"   {'=' * 70}")

        try:
            # Execute search directly via quilt3 API
            search_api = service.get_search_api()
            dsl_query = {
                "from": 0,
                "size": 3,
                "query": {"query_string": {"query": "*"}},
            }

            response = search_api(query=dsl_query, index=pattern, limit=3)

            if "error" in response:
                print(f"   ❌ ERROR: {response['error']}")
                continue

            hits = response.get("hits", {}).get("hits", [])
            print(f"   ✅ SUCCESS: Got {len(hits)} results")

            if hits:
                print(f"\n   SAMPLE DOCUMENT STRUCTURE:")
                first_hit = hits[0]
                source = first_hit.get("_source", {})

                # Show top-level fields
                print(f"   Fields: {list(source.keys())[:15]}")

                # Show sample values for key fields
                key_fields = [
                    "key",
                    "ptr_name",
                    "mnfst_name",
                    "entry_lk",
                    "entry_pk",
                    "name",
                    "handle",
                    "package_name",
                    "manifest_name",
                ]

                print(f"\n   Field Values:")
                for field in key_fields:
                    if field in source:
                        value = str(source[field])[:60]
                        print(f"     {field}: {value}")

                # Show full document for first hit (compact)
                print(f"\n   FULL DOCUMENT (first hit):")
                print(f"   {json.dumps(source, indent=2)[:500]}...")

        except Exception as e:
            print(f"   ❌ EXCEPTION: {e}")

    print("\n" + "=" * 80)
    print("DISCOVERY COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
