#!/usr/bin/env python3
"""Introspect the GraphQL schema to see available types."""

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

# Introspection query for BucketSetTabulatorTableResult type
query = """
{
  __type(name: "BucketSetTabulatorTableResult") {
    name
    kind
    fields {
      name
      type {
        name
        kind
        ofType {
          name
          kind
        }
      }
    }
    interfaces {
      name
    }
  }
}
"""

headers = {}
if hasattr(session, 'headers'):
    headers.update(session.headers)

response = requests.post(api_url, json={"query": query}, headers=headers)
print("BucketSetTabulatorTableResult fields:")
print(json.dumps(response.json(), indent=2))

# Query the bucketSetTabulatorTable mutation
mutation_query = """
{
  __type(name: "Mutation") {
    fields {
      name
      args {
        name
        type {
          name
          kind
          ofType {
            name
            kind
          }
        }
      }
      type {
        name
        kind
        ofType {
          name
          kind
        }
      }
    }
  }
}
"""

response2 = requests.post(api_url, json={"query": mutation_query}, headers=headers)
result = response2.json()
if 'data' in result and '__type' in result['data'] and result['data']['__type']:
    for field in result['data']['__type']['fields']:
        if 'bucketSetTabulatorTable' in field['name'] or 'bucketRenameTabulatorTable' in field['name']:
            print(f"\n{field['name']}:")
            print(json.dumps(field, indent=2))
