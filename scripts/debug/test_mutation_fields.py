#!/usr/bin/env python3
"""Test different field selections for mutation result."""

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

variables = {
    "bucketName": "quilt-ernest-staging",
    "tableName": "test_fields",
    "config": """schema:
- name: id
  type: STRING""",
}

# Try different field selections
field_tests = [
    ("success", "{ success }"),
    ("name", "{ name }"),
    ("tableName", "{ tableName }"),
    ("config", "{ config }"),
    ("table", "{ table { name config } }"),
    ("tabulatorTable", "{ tabulatorTable { name config } }"),
]

for name, fields in field_tests:
    mutation = f"""
mutation SetTabulatorTable($bucketName: String!, $tableName: String!, $config: String) {{
  bucketSetTabulatorTable(bucketName: $bucketName, tableName: $tableName, config: $config) {fields}
}}
"""
    print(f"\n=== Testing field: {name} ===")
    response = requests.post(api_url, json={"query": mutation, "variables": variables}, headers=headers)
    if response.status_code == 200 and 'errors' not in response.json():
        print(f"✅ SUCCESS with field '{name}'")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        break
    else:
        print(f"❌ Failed")
        errors = response.json().get('errors', [])
        if errors:
            print(f"Error: {errors[0].get('message', str(errors[0]))}")
