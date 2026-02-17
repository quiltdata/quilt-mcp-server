"""Centralized GraphQL query strings for platform backend."""

from __future__ import annotations


PACKAGE_CONSTRUCT_MUTATION = """
mutation PackageConstruct($params: PackagePushParams!, $src: PackageConstructSource!) {
  packageConstruct(params: $params, src: $src) {
    __typename
    ... on PackagePushSuccess {
      package { name }
      revision { hash }
    }
  }
}
"""

GET_PACKAGE_QUERY = """
query GetPackage($bucket: String!, $name: String!, $hash: String!) {
  package(bucket: $bucket, name: $name) {
    revision(hashOrTag: $hash) {
      hash
      userMeta
      contentsFlatMap(max: 10000)
    }
  }
}
"""

PACKAGE_REVISIONS_FOR_DELETE_QUERY = """
query PackageRevisionsForDelete($bucket: String!, $name: String!, $page: Int!, $perPage: Int!) {
  package(bucket: $bucket, name: $name) {
    revisions {
      total
      page(number: $page, perPage: $perPage) {
        hash
      }
    }
  }
}
"""

DELETE_REVISION_MUTATION = """
mutation DeleteRevision($bucket: String!, $name: String!, $hash: String!) {
  packageRevisionDelete(bucket: $bucket, name: $name, hash: $hash) {
    __typename
    ... on PackageRevisionDeleteSuccess {
      _
    }
    ... on OperationError {
      message
    }
  }
}
"""
