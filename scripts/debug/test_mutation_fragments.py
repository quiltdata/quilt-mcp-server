#!/usr/bin/env python3
"""Test mutation with inline fragments."""

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

headers = {}
if hasattr(session, 'headers'):
    headers.update(session.headers)

# Try mutation with fragments
mutation = """
mutation SetTabulatorTable($bucketName: String!, $tableName: String!, $config: String) {
  bucketSetTabulatorTable(bucketName: $bucketName, tableName: $tableName, config: $config) {
    __typename
    ... on BucketConfig {
      name
      tabulatorTables {
        name
        config
      }
    }
    ... on InvalidInput {
      errors {
        path
        message
        name
        context
      }
    }
    ... on OperationError {
      message
    }
  }
}
"""

variables = {
    "bucketName": "quilt-ernest-staging",
    "tableName": "test_fragment_success",
    "config": """schema:
- name: sample_id
  type: STRING
- name: collection_date
  type: TIMESTAMP
- name: concentration
  type: FLOAT
- name: quality_score
  type: INT
- name: passed_qc
  type: BOOLEAN
source:
  type: quilt-packages
  package_name: ^experiments/(?P<year>\\d{4})/(?P<experiment_id>[^/]+)$
  logical_key: samples/(?P<sample_type>[^/]+)\\.csv$
parser:
  format: csv
  delimiter: ","
  header: true"""
}

print("=== Attempting mutation with inline fragments ===")
response = requests.post(api_url, json={"query": mutation, "variables": variables}, headers=headers)
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")
