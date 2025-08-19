# DXT Requirements

## References

- https://www.anthropic.com/engineering/desktop-extensions
- https://github.com/anthropics/dxt/tree/main/examples/file-manager-python

## Goals

### Motivation

- **One-click installation** of Quilt MCP Server for Claude Desktop users
- **Eliminate setup friction** - no Python/AWS/Docker knowledge required
- **Self-contained package** with all dependencies bundled
- **Consistent user experience** across different machines and OS environments

### Objectives

1. Make it easy to build locally, during development (Makefile target)
2. Automatically build when merging PRs (deploy GitHub action)
3. Create releases including a clear customer-facing README of how to use/configure it

## Key Questions

### Configuration Issues

1. How should we specify `QUILT_CATALOG_DOMAIN`
2. Requires implicit AWS Credentials -- how do we warn if not present?
3. Search functionality requires quilt3 confg + login.  
   1. Do we require them to do it in via CLI, or can we trigger the UI from Python? 
   1. Are we even allowed to store credentials into the Library location?
   1. Will we be allowed to read it if created from the CLI?
   1. Can we intelligently disable (or switch to list) if not present?
4. Should we default to stdio? Allow overriding?

## Success Criteria

### Internal Use

- ✅ .dxt installs with single click in Claude Desktop
- ✅ MCP server responds correctly to `tools/list` and `tools/call`
- ✅ User can access Quilt packages with proper authentication
- ✅ Works on clean system without pre-installed dependencies

### Public Use

- ✅ Documentation for end user installation
- ✅ Configuration UI for catalog settings
- ✅ Clear error messages for common setup issues
- ✅ Automated testing in CI for .dxt generation
- ✅ UI to specify which AWS_PROFILE to use
