# List Buckets Tool Spec

## Overview

MCP tool to list S3 buckets accessible to the authenticated user via the Quilt platform.

## Implementation Location

- **QuiltOps** class directly (no separate backend implementations)
- Consolidates logic previously split across Quilt3Backend and QuiltOpsBackend

## Upstream API

Uses GraphQL `bucketConfigs` query from `~/GitHub/enterprise/registry/quilt_server/graphql/buckets.py`:

- Query: `bucketConfigs` (line 126)
- Returns: Buckets filtered by `auth.get_buckets_listable_by(context.get_user())`
- Respects user permissions and role-based access

## Tool Interface

**Name**: `bucket_list`

**Input**: None (uses authenticated user context from JWT)

**Output**: List of bucket configurations with:

- `name` (string, required)
- `title` (string)
- `description` (string, optional)
- `iconUrl` (string, optional)
- `relevanceScore` (int)
- `browsable` (bool)
- `tags` (array, optional)

## Auth Requirements

- Requires valid JWT in request context
- Returns only buckets user has permission to list
- Empty list if no accessible buckets (not an error)

## Error Cases

- **401 Unauthorized**: Missing/invalid JWT
- **Network errors**: Standard retry/backoff
- **GraphQL errors**: Map to tool-level errors with message

## Related Components

- JWT discovery: `src/quilt_mcp/auth/jwt_discovery.py`
- Context management: `src/quilt_mcp/context/request_context.py`
- Tool registration: `src/quilt_mcp/tools/buckets.py`
