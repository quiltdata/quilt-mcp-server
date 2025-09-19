<!-- markdownlint-disable MD013 -->
# Requirements - Isolate quilt3 Dependency

**GitHub Issue**: #155 "[isolate quilt3](https://github.com/quiltdata/quilt-mcp-server/issues/155)"
**Problem Statement**: We need the MCP server to work in two environments:

- Locally for development and testing (as today)
- Remotely when deployed as part of the stack (which cannot use quilt3's auth mechanisms)

## User Requirements

1. **Local Development**: Developers can run and test the MCP server locally using quilt3
2. **Stack Deployment**: The same MCP server can be deployed remotely as part of the stack without quilt3 dependencies
3. **Consistent Interface**: Same MCP tools and commands work in both environments

## Challenges

1. The current implementation uses `quilt3 login` to authenticate to the stack, which depends on having a local filesystem and user interaction
2. The stack provides higher-performance services that overlap with what is provided by `quilt3`.
3. We want to reuse the existing tool definitions for both convenience and consistency.
