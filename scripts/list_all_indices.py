#!/usr/bin/env python3
"""List ALL Elasticsearch indices for a specific bucket.

This script calls the Elasticsearch API directly to list all indices,
then filters for the specified bucket.

Usage:
    python scripts/list_all_indices.py [bucket_name]

If bucket_name is not provided, uses QUILT_TEST_BUCKET from .env
"""

import asyncio
import json
import os
import sys
from quilt_mcp.services.quilt_service import QuiltService


async def main():
    print("=" * 80)
    print("ELASTICSEARCH INDEX LISTING")
    print("=" * 80)

    # Get bucket from command line or environment
    if len(sys.argv) > 1:
        search_bucket = sys.argv[1]
        print(f"\nSearching for indices containing: {search_bucket}")
    else:
        test_bucket_env = os.getenv("QUILT_TEST_BUCKET", "")
        if test_bucket_env:
            search_bucket = test_bucket_env.replace("s3://", "").split("/")[0]
            print(f"\nUsing QUILT_TEST_BUCKET from .env: {search_bucket}")
        else:
            print("\nERROR: No bucket specified and QUILT_TEST_BUCKET not set in .env")
            print("Usage: python scripts/list_all_indices.py [bucket_name]")
            return

    # Initialize service
    service = QuiltService()
    registry_url = service.get_registry_url()
    session = service.get_session()

    if not registry_url or not session:
        print("ERROR: Could not get registry URL or session")
        return

    print(f"\nRegistry URL: {registry_url}")

    # Try to list indices via the catalog API
    # The catalog wraps Elasticsearch, so we need to find the right endpoint
    print("\n" + "=" * 80)
    print("ATTEMPTING TO LIST INDICES...")
    print("=" * 80)

    # Method 1: Try to search with _cat/indices equivalent
    print("\n1. Attempting catalog search API inspection...")
    search_api = service.get_search_api()

    # Try searching all indices with a wildcard pattern
    wildcard_patterns = [
        f"{search_bucket}*",
        f"*{search_bucket}*",
        f"{search_bucket},{search_bucket}_*",
    ]

    for pattern in wildcard_patterns:
        print(f"\n   Pattern: {pattern}")
        try:
            dsl_query = {
                "from": 0,
                "size": 0,  # Just want aggregations/metadata
                "query": {"match_all": {}},
            }
            response = search_api(query=dsl_query, index=pattern, limit=0)

            if "error" not in response:
                # Check if we can get index info from the response
                if "_shards" in response:
                    print(f"   ✅ Pattern matched! Shards info: {response.get('_shards')}")

                # Try to extract index names from hits
                hits = response.get("hits", {}).get("hits", [])
                if hits:
                    indices = set()
                    for hit in hits:
                        idx = hit.get("_index")
                        if idx:
                            indices.add(idx)
                    print(f"   Found indices in results: {sorted(indices)}")
            else:
                print(f"   ❌ Error: {response.get('error')}")
        except Exception as e:
            print(f"   ❌ Exception: {e}")

    # Method 2: Try known suffixes
    print("\n" + "=" * 80)
    print("2. TESTING KNOWN INDEX PATTERNS...")
    print("=" * 80)

    known_suffixes = [
        "",  # Base index (files)
        "_packages",  # Package entries
        "_manifests",  # Maybe package manifests?
        "_package",  # Singular?
        "-packages",  # Different separator?
        "-reindex-v*",  # Reindexed versions
        "_packages-reindex-v*",  # Reindexed packages
    ]

    found_indices = []

    for suffix in known_suffixes:
        pattern = f"{search_bucket}{suffix}"
        try:
            dsl_query = {
                "from": 0,
                "size": 1,
                "query": {"match_all": {}},
            }
            response = search_api(query=dsl_query, index=pattern, limit=1)

            if "error" not in response:
                hits = response.get("hits", {}).get("hits", [])
                if hits:
                    actual_index = hits[0].get("_index")
                    print(f"   ✅ {pattern:50} -> {actual_index}")
                    found_indices.append(actual_index)
                else:
                    print(f"   ⚠️  {pattern:50} -> exists but empty")
                    found_indices.append(pattern)
            else:
                print(f"   ❌ {pattern:50} -> not found")
        except Exception as e:
            error_msg = str(e)
            if "No valid indices" in error_msg:
                print(f"   ❌ {pattern:50} -> not found")
            else:
                print(f"   ❌ {pattern:50} -> error: {error_msg[:50]}")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\nFound {len(set(found_indices))} unique indices for bucket '{search_bucket}':")
    for idx in sorted(set(found_indices)):
        print(f"  - {idx}")


if __name__ == "__main__":
    asyncio.run(main())
