#!/usr/bin/env python3
"""Test raw GraphQL request to see actual error."""

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
print(f"Logged in URL: {logged_in_url}")

# Get catalog config
catalog_config = backend.get_catalog_config(logged_in_url)
print(f"Registry URL: {catalog_config.registry_url}")

from quilt_mcp.utils import graphql_endpoint

api_url = graphql_endpoint(catalog_config.registry_url)
print(f"GraphQL endpoint: {api_url}")

# Test create table mutation
mutation = """
mutation SetTabulatorTable($bucketName: String!, $tableName: String!, $config: String) {
  bucketSetTabulatorTable(bucketName: $bucketName, tableName: $tableName, config: $config) {
    __typename
    ... on BucketSetTabulatorTableResult {
      bucketConfig {
        name
        tabulatorTables {
          name
          config
        }
      }
    }
    ... on InvalidInput {
      message
    }
    ... on BucketNotFound {
      message
    }
    ... on BucketNotAllowed {
      message
    }
  }
}
"""

variables = {
    "bucketName": "quilt-ernest-staging",
    "tableName": "test_debug_table",
    "config": """schema:
- name: id
  type: STRING""",
}

# Make request with quilt session
print("\n=== Using quilt3 session ===")
try:
    response1 = session.post(api_url, json={"query": mutation, "variables": variables})
    print(f"Status: {response1.status_code}")
    print(f"Response: {json.dumps(response1.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")

# Make request with raw requests
print("\n=== Using raw requests with session headers ===")
headers = {}
if hasattr(session, 'headers'):
    headers.update(session.headers)
    print(f"Headers: {headers}")

try:
    response2 = requests.post(api_url, json={"query": mutation, "variables": variables}, headers=headers)
    print(f"Status: {response2.status_code}")
    print(f"Response body: {response2.text}")
    try:
        print(f"Response JSON: {json.dumps(response2.json(), indent=2)}")
    except Exception:
        pass
except Exception as e:
    print(f"Error: {e}")
