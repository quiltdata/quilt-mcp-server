#!/usr/bin/env python3
"""Show actual connection information for Elasticsearch cluster."""

import os
from quilt_mcp.services.quilt_service import QuiltService

print("=" * 80)
print("ELASTICSEARCH CONNECTION INFO")
print("=" * 80)

# Environment variables
print("\nEnvironment Variables:")
print(f"  AWS_PROFILE: {os.getenv('AWS_PROFILE', '(not set)')}")
print(f"  AWS_DEFAULT_REGION: {os.getenv('AWS_DEFAULT_REGION', '(not set)')}")
print(f"  AWS_ACCOUNT_ID: {os.getenv('AWS_ACCOUNT_ID', '(not set)')}")
print(f"  QUILT_CATALOG_DOMAIN: {os.getenv('QUILT_CATALOG_DOMAIN', '(not set)')}")
print(f"  QUILT_TEST_BUCKET: {os.getenv('QUILT_TEST_BUCKET', '(not set)')}")

# Service info
service = QuiltService()
registry_url = service.get_registry_url()

print("\nQuilt Service:")
print(f"  Registry URL: {registry_url}")

# Extract domain from registry URL
if registry_url:
    # Format is typically: https://{prefix}-registry.{domain}
    # e.g., https://nightly-registry.quilttest.com
    parts = registry_url.replace("https://", "").replace("http://", "").split(".")
    print(f"  Parsed domain: {'.'.join(parts[1:])}")
    print(f"  Environment: {parts[0].replace('-registry', '')}")

print("\n" + "=" * 80)
print("AWS OpenSearch Domain Information:")
print("=" * 80)
print("\nThe Elasticsearch cluster backing this catalog is NOT directly accessible.")
print("The catalog API (registry URL above) acts as a proxy to Elasticsearch.")
print("\nTo view indices in AWS Console:")
print("1. Identify which AWS account/region hosts the Elasticsearch cluster")
print("2. Find the OpenSearch domain name (may be different from catalog domain)")
print("3. Navigate to AWS Console > OpenSearch Service > Domains")
print("\nFor nightly.quilttest.com, the backing OpenSearch domain is likely:")
print("  - Account: Quilt Test/Staging account")
print("  - Region: us-east-1 or us-east-2")
print("  - Domain: tf-dev-bench or similar")
