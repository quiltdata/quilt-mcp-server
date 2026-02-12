# Catalog Package Revision Deletion Analysis

**Date:** 2026-02-11
**Context:** Understanding catalog's revision deletion for potential MCP implementation

## Architecture Overview

### Frontend (TypeScript/React)

- **UI Entry**: `RevisionMenu.tsx` - conditional menu item based on `actions.deleteRevision` permission
- **Confirmation**: `RevisionDeleteDialog.tsx` - warns about permanent metadata deletion
- **GraphQL Call**: `DeleteRevision.graphql` mutation with params `{bucket, name, hash}`

### Backend (GraphQL + Lambda)

- **Schema**: `shared/graphql/schema.graphql` - `packageRevisionDelete` mutation
- **Result Union**: `PackageRevisionDeleteSuccess | OperationError`
- **Iceberg Lambda**: `t4_lambda_iceberg` - processes S3 deletion events
- **SQL Execution**: Athena DELETE query on `package_revision` Iceberg table

## Flow

```
User clicks "Delete revision"
  → Confirmation dialog
  → GraphQL mutation: packageRevisionDelete(bucket, name, hash)
  → Backend deletes pointer file from S3: .quilt/named_packages/{name}/{timestamp}
  → S3 event triggers Iceberg Lambda
  → Lambda executes: DELETE FROM package_revision WHERE bucket=X AND pkg_name=Y AND timestamp=Z
  → Metadata removed from Iceberg tables
```

## Key Implementation Details

1. **Metadata Only**: Deletes package metadata, NOT the actual S3 objects
2. **Pointer Files**: Revision tracked at `.quilt/named_packages/{name}/{timestamp}`
3. **Iceberg Tables**: Package metadata stored in queryable Iceberg tables via Athena
4. **Dual Trigger**: Direct API call + S3 event-driven Lambda cleanup
5. **Permanent**: No soft delete - metadata gone forever

## SQL Query (from iceberg_queries.py:54-58)

```python
DELETE FROM package_revision
WHERE bucket = '{bucket}'
  AND pkg_name = '{pkg_name}'
  AND timestamp = from_unixtime({pointer})
```

## Relevant for MCP

If implementing package revision deletion in quilt-mcp-server:

- Need GraphQL mutation or REST API call to platform backend
- OR direct S3 deletion of pointer file (triggers same Iceberg cleanup)
- Must have write permissions on bucket
- Should show same warning about metadata vs object deletion
