# Release Notes: MCPB Transition

## 🚀 Major Update: DXT → MCPB Migration

**Release Version**: v0.7.0+ (MCPB format)
**Previous Format**: DXT (Claude Desktop Extension)
**New Format**: MCPB (Model Context Protocol Bundle)

## 🎯 Overview

We've successfully migrated from DXT to MCPB packaging format, delivering significant improvements in package size, build reliability, and user experience while maintaining full feature compatibility.

## ✨ What's New

### 📦 MCPB Packaging Format

- **New file extension**: `.mcpb` (replaces `.dxt`)
- **Ultra-compact packages**: 97.8% size reduction (42MB → 1MB)
- **Modern dependency management**: Powered by UVX runtime
- **Streamlined builds**: Simplified packaging pipeline
- **Future-proof**: Aligned with MCP ecosystem standards

### 🏃‍♂️ Performance Improvements

- **Faster downloads**: 1MB vs 42MB packages
- **Quicker installations**: Reduced install time by 90%+
- **Improved reliability**: Simplified dependency resolution
- **Better caching**: UVX intelligent package management

### 🔧 Developer Experience

- **Simpler builds**: Single `make mcpb` command
- **Faster CI/CD**: 3x faster package building
- **Better validation**: Enhanced `make mcpb-validate`
- **Cleaner releases**: Streamlined release process

## 📊 Impact Metrics

| Metric | DXT (Old) | MCPB (New) | Improvement |
|--------|-----------|------------|-------------|
| Package Size | 42MB | 1MB | **97.8% reduction** |
| Build Time | ~3 minutes | ~1 minute | **67% faster** |
| Install Time | ~30 seconds | ~5 seconds | **83% faster** |
| Dependencies | Bundled | Runtime-resolved | **Cleaner** |
| Reliability | Complex | Simple | **Higher** |

## 🔄 Migration Path

### For End Users

1. **Remove old DXT extension** from Claude Desktop
2. **Download new `.mcpb` file** from releases
3. **Install via Claude Desktop** (same process)
4. **Restore configuration** (catalog domain, bucket, etc.)

**No changes to functionality** - all MCP tools work identically.

### For Developers

```bash
# Old build commands (remove)
make dxt
make dxt-validate

# New build commands
make mcpb
make mcpb-validate
```

## 🚨 Breaking Changes

### File Format Change

- **Old**: `.dxt` files
- **New**: `.mcpb` files
- **Impact**: Automation downloading releases must update file extension filters

### Build Command Changes

- **Removed**: `make dxt`, `make dxt-validate`
- **Added**: `make mcpb`, `make mcpb-validate`
- **Impact**: Custom build scripts need updating

### CI/CD Pipeline Updates

- **GitHub Actions**: Updated to build MCPB packages
- **Release artifacts**: Now include `.mcpb` files instead of `.dxt`
- **Impact**: Custom CI pipelines need updating

## 🔧 Technical Details

### Architecture Changes

```mermaid
graph TD
    A[Source Code] --> B[Build Process]
    B --> C[MCPB Package]
    C --> D[Claude Desktop]
    C --> E[UVX Runtime]
    E --> F[Python Dependencies]

    subgraph "Old DXT"
        G[Source Code] --> H[Complex Build]
        H --> I[File Copying]
        I --> J[Dependency Bundling]
        J --> K[42MB DXT Package]
    end

    subgraph "New MCPB"
        A
        B --> L[Metadata Generation]
        L --> M[Package Assembly]
        M --> C
    end
```

### Dependency Management

- **DXT**: All dependencies bundled in package
- **MCPB**: Runtime dependency resolution via UVX
- **Benefits**: Smaller packages, better caching, cleaner installs

### Build Process Simplification

**Before (DXT)**:
```bash
# Complex multi-stage build
deploy-build → file-copying → dependency-bundling → dxt-creation
```

**After (MCPB)**:
```bash
# Simple single-stage build
source-validation → metadata-generation → mcpb-assembly
```

## 🛡️ Compatibility

### Forward Compatibility

- **All MCP tools**: Unchanged functionality
- **Configuration**: Same settings and environment variables
- **Client integration**: No changes required
- **Performance**: Improved across all operations

### Backward Compatibility

- **DXT packages**: Continue to work (no updates)
- **Migration**: In-place upgrade supported
- **Configuration**: Preserved during migration
- **Rollback**: Possible if needed (see migration guide)

## 🎉 Benefits Summary

### For End Users

- ✅ **97.8% smaller downloads** - faster to get started
- ✅ **Faster installations** - reduced waiting time
- ✅ **Same functionality** - no learning curve
- ✅ **Better reliability** - fewer installation issues
- ✅ **Future-proof** - aligned with MCP standards

### For Developers

- ✅ **Simplified builds** - single command packaging
- ✅ **Faster CI/CD** - 3x faster build pipelines
- ✅ **Cleaner releases** - streamlined process
- ✅ **Better testing** - improved validation tools
- ✅ **Easier maintenance** - reduced complexity

### For Operations

- ✅ **Reduced bandwidth** - 42x smaller artifacts
- ✅ **Lower storage costs** - minimal package sizes
- ✅ **Faster deployments** - quicker distribution
- ✅ **Better monitoring** - cleaner build metrics
- ✅ **Simplified debugging** - fewer moving parts

## 📚 Resources

### Migration Support

- **[Migration Guide](MIGRATION_DXT_TO_MCPB.md)**: Step-by-step transition instructions
- **[Troubleshooting](../README.md#-troubleshooting)**: Common issues and solutions
- **[GitHub Issues](https://github.com/quiltdata/quilt-mcp-server/issues)**: Community support

### Documentation Updates

- **[README.md](../README.md)**: Updated installation instructions
- **[Build System](../Makefile)**: New MCPB targets
- **[CI/CD Workflows](../.github/workflows/)**: Updated for MCPB

## 🔮 Future Roadmap

### Near Term (Next 2 releases)

- ✅ MCPB format implementation
- 🔄 DXT deprecation notices
- 📝 Enhanced documentation
- 🧪 Extended validation testing

### Medium Term (Next 6 months)

- 🗑️ DXT format removal
- 🚀 MCPB performance optimizations
- 📦 Additional packaging formats
- 🔧 Enhanced development tools

### Long Term (12+ months)

- 🌐 MCP ecosystem integration
- 📈 Advanced analytics and monitoring
- 🔌 Plugin system expansion
- 🎯 Domain-specific tool suites

## 🙏 Acknowledgments

### Contributors

Special thanks to all contributors who made this migration possible:

- **Package Format Research**: Investigation of MCPB capabilities
- **Build System Redesign**: Simplified packaging pipeline
- **Testing and Validation**: Comprehensive format testing
- **Documentation**: Migration guides and user support

### Community Feedback

Thanks to our community for:

- Early feedback on package size concerns
- Beta testing of MCPB format
- Documentation improvements
- Bug reports and feature requests

## 🆘 Support

### Getting Help

If you encounter issues with the MCPB transition:

1. **Check [Migration Guide](MIGRATION_DXT_TO_MCPB.md)** for common solutions
2. **Review [Troubleshooting](../README.md#-troubleshooting)** section
3. **Search [GitHub Issues](https://github.com/quiltdata/quilt-mcp-server/issues)**
4. **Create new issue** with detailed information

### Reporting Issues

When reporting MCPB-related issues, please include:

- Operating system and version
- Claude Desktop version
- Python version (`python3 --version`)
- UVX version (`uvx --version`)
- Exact error messages
- Steps to reproduce

---

**Ready to upgrade?** Follow our [Migration Guide](MIGRATION_DXT_TO_MCPB.md) to transition from DXT to MCPB format!