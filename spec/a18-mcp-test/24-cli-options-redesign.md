# MCP Test CLI Options Redesign

## Context

The current CLI options for test execution are inconsistent in naming:
- Tools: `--tools-test` vs `--test-tool`
- Resources: `--resources-test` vs `--test-resource`
- Loops: `--loops-test` vs `--loop` (no consistent prefix)
- Idempotent: `--idempotent-only` (separate flag)

This redesign simplifies to a single consistent pattern using optional magic keywords.

## Proposed Design

### Pattern

Each test category uses a single flag with an argument:

```
--<category> <selector>
-<letter> <selector>
```

Where `<selector>` is:
- `all` - Run all items in category
- `none` - Skip all items in category
- `name1,name2,...` - Run specific named items (comma-separated, no spaces)

### New Options

| New Flag | Short | Replaces | Semantics |
|----------|-------|----------|-----------|
| `--tools <selector>` | `-t` | `--tools-test`, `--test-tool` | Select which tools to test |
| `--resources <selector>` | `-r` | `--resources-test`, `--test-resource` | Select which resources to test |
| `--loops <selector>` | `-l` | `--loops-test`, `--loop`, `--idempotent-only` | Select which loops to run |

### Default Behavior

When no test selection flags are provided: **run all tools, all resources, all loops**

### Examples

```bash
# Run everything (equivalent to no flags)
mcp-test --tools all --resources all --loops all

# Run specific tools only (resources and loops still run)
mcp-test --tools bucket_list,bucket_search

# Run idempotent operations only (tools only, no resources, no loops)
mcp-test --resources none --loops none

# Run specific tools and resources, skip loops
mcp-test -t package_browse,package_install -r quilt+s3://bucket#package=pkg -l none

# Run all tools and resources, specific loop only
mcp-test --tools all --resources all --loops crud_workflow

# Run specific tools only, suppress everything else
mcp-test -t bucket_list,package_browse -r none -l none
```

### Semantics

1. **Each category is independent**
   - Each flag (`--tools`, `--resources`, `--loops`) controls only that category
   - Other categories default to `all` unless explicitly specified
   - Example: `--loops none` suppresses loops but tools and resources still run

2. **Default is inclusive**
   - Omitting a flag means "all" for that category
   - `mcp-test` with no flags = `--tools all --resources all --loops all`

3. **`none` suppresses only that category**
   - `--tools none` = skip all tools (resources and loops still run)
   - `--resources none --loops none` = idempotent operations (only tools run)
   - `--tools none --resources none --loops none` = nothing runs

4. **Multiple selectors combine via AND**
   - `--tools t1,t2` means "run only t1 and t2"
   - Not "run t1 or run t2 separately"

5. **Comma-separated lists have no spaces**
   - ✅ Correct: `--tools t1,t2,t3`
   - ❌ Wrong: `--tools t1, t2, t3`

## Migration Notes

This design replaces the inconsistent flags: `--tools-test`, `--test-tool`, `--resources-test`, `--test-resource`,
`--loop`, `--loops-test`, and `--idempotent-only`.

## Implementation Notes

### Argument Parsing

Use `argparse` with:
- `nargs='?'` would allow optional argument, but we want **required** argument
- `nargs=1` or just default (scalar) to require exactly one argument
- No special parsing needed - "all", "none", or comma-separated names are all strings

### Validation

1. Validate `<selector>` is one of:
   - Keyword: `all` or `none`
   - Name list: Non-empty string containing valid identifiers/URIs

2. For name lists:
   - Split on comma
   - Validate each name exists in available tools/resources/loops
   - Report invalid names clearly

3. Flag combinations:
   - All flags are optional
   - All flags are independent (can be combined freely)
   - No mutual exclusivity needed
