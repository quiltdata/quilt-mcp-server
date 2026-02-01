#!/usr/bin/env python3
"""Test simple GraphQL mutation."""

import sys
from pathlib import Path
import requests
import json

# Add src to path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root / "src"))

from quilt_mcp.ops.factory import QuiltOpsFactory

backend = QuiltOpsFactory.create()

# Get the session and endpoint
import quilt3
session = quilt3.session.get_session()
logged_in_url = quilt3.logged_in()
catalog_config = backend.get_catalog_config(logged_in_url)

from quilt_mcp.utils import graphql_endpoint
api_url = graphql_endpoint(catalog_config.registry_url)

# Try the simplest possible mutation
mutation = """
mutation SetTabulatorTable($bucketName: String!, $tableName: String!, $config: String) {
  bucketSetTabulatorTable(bucketName: $bucketName, tableName: $tableName, config: $config)
}
"""

variables = {
    "bucketName": "quilt-ernest-staging",
    "tableName": "test_simple",
    "config": """schema:
- name: id
  type: STRING"""
}

headers = {}
if hasattr(session, 'headers'):
    headers.update(session.headers)

print("=== Attempting simple mutation ===")
response = requests.post(api_url, json={"query": mutation, "variables": variables}, headers=headers)
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")
