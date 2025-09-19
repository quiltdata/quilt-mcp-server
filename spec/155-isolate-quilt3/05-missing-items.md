<!-- markdownlint-disable MD013 -->
# Missing Items Analysis - Isolate quilt3 Dependency

**GitHub Issue**: #155 "[isolate quilt3](https://github.com/quiltdata/quilt-mcp-server/issues/155)"

**Original Specification**: [03-specifications.md](./03-specifications.md)

## Executive Summary

The original specification focused primarily on MCP tool modules but missed several critical
service modules and infrastructure components that have direct `quilt3` dependencies. This
analysis identifies all missing items that must be abstracted to achieve complete isolation.

## Discovered Non-Tool quilt3 Dependencies

### 1. Service Layer Dependencies

#### 1.1 AWS Athena Service (`src/quilt_mcp/aws/athena_service.py`)

**Lines**: 68, 70, 155, 157, 169, 449, 451

**Current Usage Pattern**:

```python
import quilt3
botocore_session = quilt3.session.create_botocore_session()
credentials = botocore_session.get_credentials()
```

**Abstraction Impact**: HIGH

- Core authentication mechanism for AWS services
- Used for SQLAlchemy engine creation with Athena
- Provides region-specific credential handling
- Critical for Glue and S3 client creation

#### 1.2 AWS Permission Discovery (`src/quilt_mcp/aws/permission_discovery.py`)

**Lines**: 15, 74-90, 588-592, 620-624

**Current Usage Pattern**:

```python
import quilt3
session = quilt3.get_boto3_session()
registry_url = quilt3.session.get_registry_url()
session = quilt3.session.get_session()
```

**Abstraction Impact**: HIGH

- Permission discovery engine for bucket access
- GraphQL endpoint discovery
- Fallback authentication mechanisms
- Cross-account bucket detection

#### 1.3 Utils Module (`src/quilt_mcp/utils.py`)

**Lines**: 191, 194-198, 217, 220-224

**Current Usage Pattern**:

```python
import quilt3
if hasattr(quilt3, "logged_in") and quilt3.logged_in():
    session = quilt3.get_boto3_session()
```

**Abstraction Impact**: MEDIUM

- S3 client factory functions
- STS client factory functions
- Fallback authentication patterns

### 2. Search Backend Dependencies

#### 2.1 GraphQL Search Backend (`src/quilt_mcp/search/backends/graphql.py`)

**Lines**: 13, 46, 72-74, 589-592

**Current Usage Pattern**:

```python
import quilt3
registry_url = quilt3.session.get_registry_url()
session = quilt3.session.get_session()
```

**Abstraction Impact**: HIGH

- Enterprise GraphQL search functionality
- Session management for authenticated queries
- Registry URL discovery

#### 2.2 Elasticsearch Search Backend (`src/quilt_mcp/search/backends/elasticsearch.py`)

**Lines**: 11, 36, 49, 126

**Current Usage Pattern**:

```python
import quilt3
registry_url = quilt3.session.get_registry_url()
bucket_obj = quilt3.Bucket(bucket_uri)
```

**Abstraction Impact**: HIGH

- Bucket search functionality
- Session availability checking
- Direct Bucket object usage
