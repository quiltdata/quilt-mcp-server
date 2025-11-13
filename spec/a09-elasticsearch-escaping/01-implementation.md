# Elasticsearch Query Escaping

## Problem

Elasticsearch's `query_string` query syntax treats certain characters as operators. When users search for strings containing these special characters (like forward slashes in package names `team/dataset`), the query would fail or return unexpected results.

## Solution

Added automatic escaping of Elasticsearch special characters in query strings.

### Special Characters Escaped

The following characters are now automatically escaped with a backslash:

- `+` `-` `=` `&&` `||` `>` `<` `!` `(` `)` `{` `}`
- `[` `]` `^` `"` `~` `*` `?` `:` `\` `/`

### Implementation

1. Created `escape_elasticsearch_query()` function in [elasticsearch.py](../../src/quilt_mcp/search/backends/elasticsearch.py)
2. Applied escaping in two locations:
   - `_execute_catalog_search()` - for direct query_string queries
   - `_build_elasticsearch_query()` - for queries with filters

### Examples

| Input | Escaped Output |
|-------|---------------|
| `team/dataset` | `team\/dataset` |
| `size>100` | `size\>100` |
| `field:value` | `field\:value` |
| `data/2024/results.csv` | `data\/2024\/results.csv` |

## Testing

Added comprehensive test suite in [test_elasticsearch_escaping.py](../../tests/test_elasticsearch_escaping.py) covering:

- Forward slash escaping (the primary issue)
- All other special characters
- Complex queries with multiple special characters
- Real-world package names and file paths
- Edge cases (empty strings, no special chars)

All 18 new tests pass, and all existing search tests continue to pass.

## Impact

This change is **backwards compatible**. Queries that previously worked will continue to work, and queries with special characters that previously failed will now work correctly.

### User Benefits

Users can now search for:
- Package names with slashes: `team/dataset`
- File paths: `data/2024/results.csv`
- Expressions with operators: `size>100`
- Any string containing special characters without manual escaping
