# DXT Support Specification

## Overview

This specification defines how to package the Quilt MCP Server as a Claude Desktop Extension (.dxt) for one-click installation.

## Packaging Strategy

### Phase 5: DXT Packaging

Add a new phase to our 4-phase pipeline:

```
Phase 1: app/           # Local MCP server
Phase 2: build-docker/  # Docker containerization  
Phase 3: catalog-push/  # ECR registry
Phase 4: deploy-aws/    # ECS deployment
Phase 5: dxt-package/   # .dxt packaging
```

### Structure

```
dxt-package/
├── manifest.json       # DXT manifest
├── server/            # Python server code
│   ├── main.py        # MCP server entry point
│   └── lib/          # Bundled dependencies
├── pyproject.toml     # Python project config
└── dxt-package.sh     # Build script
```

### Manifest Configuration

```json
{
  "name": "quilt-mcp-server",
  "displayName": "Quilt Data MCP Server",
  "description": "Access Quilt data packages and catalogs",
  "version": "1.0.0",
  "runtime": "python",
  "entrypoint": "server/main.py",
  "env": {
    "PYTHONPATH": "server/lib"
  },
  "config": {
    "bucket": {
      "type": "string",
      "description": "Default S3 bucket for Quilt packages",
      "required": true
    },
    "catalog": {
      "type": "string", 
      "description": "Quilt catalog domain",
      "default": "open.quiltdata.com"
    }
  }
}
```

### Build Process

1. **Bundle Dependencies**: Copy app/ code and install packages to `server/lib/`
2. **Create Manifest**: Generate manifest.json with current git SHA as version
3. **Package Archive**: Use `dxt pack` to create `.dxt` file
4. **Validate**: Test installation and MCP functionality

### Integration Points

- **Makefile**: Add `make dxt` and `make validate-dxt` targets
- **Version Management**: Use git SHA for consistent versioning across phases
- **Testing**: Validate .dxt installs correctly and MCP endpoints work
- **CI/CD**: Include .dxt generation in release pipeline

### Security Considerations

- Bundle only production dependencies
- Exclude development tools and secrets
- Use same JWT authentication as other phases
- Test on clean systems before release

### Distribution

- Host .dxt files on GitHub releases
- Provide installation instructions for Claude Desktop
- Maintain compatibility with MCP protocol updates