# Migration Guide: DXT to MCPB Format

## Overview

The Quilt MCP Server has transitioned from DXT (Claude Desktop Extension) format to MCPB (Model Context Protocol Bundle) format. This guide helps you migrate to the new packaging system.

## What Changed and Why

### Before: DXT Format
- **File extension**: `.dxt`
- **Package size**: ~42MB (includes full Python dependencies)
- **Build complexity**: Multi-stage file copying and dependency bundling
- **Compatibility**: Claude Desktop only

### After: MCPB Format
- **File extension**: `.mcpb`
- **Package size**: ~1MB (97.8% size reduction)
- **Build complexity**: Simplified packaging with UVX runtime dependency management
- **Compatibility**: Claude Desktop with improved performance

### Key Benefits
- **97.8% smaller packages** (42MB → 1MB)
- **Faster downloads** and installations
- **Improved build reliability** with simplified packaging
- **Better dependency management** through UVX
- **Future-proof** packaging format

## Migration Steps

### For Existing Users

#### Step 1: Backup Current Configuration

Before migrating, save your current configuration:

1. Open Claude Desktop → Settings → Extensions
2. Find "Quilt MCP" extension
3. Note your current settings:
   - Quilt Catalog Domain
   - Default Bucket
   - Any custom environment variables

#### Step 2: Remove DXT Extension

1. In Claude Desktop → Settings → Extensions
2. Find "Quilt MCP" (DXT version)
3. Click "Remove" or "Uninstall"
4. Restart Claude Desktop

#### Step 3: Download MCPB Package

1. Visit [Quilt MCP Server Releases](https://github.com/quiltdata/quilt-mcp-server/releases)
2. Download the latest `.mcpb` file (not `.dxt`)
3. Verify the file has `.mcpb` extension

#### Step 4: Install MCPB Package

1. Double-click the `.mcpb` file, or
2. Use Claude Desktop → Settings → Extensions → Install from File
3. Select the downloaded `.mcpb` file

#### Step 5: Configure Extension

1. Open Claude Desktop → Settings → Extensions → Quilt MCP
2. Restore your saved configuration:
   - Set Quilt Catalog Domain
   - Set Default Bucket
   - Configure any custom settings

#### Step 6: Verify Installation

1. Open a new chat in Claude Desktop
2. Check Tools panel - you should see Quilt MCP tools available
3. Test a simple operation like `packages_list`

### For Developers

#### Update Build Commands

Replace DXT build commands with MCPB equivalents:

```bash
# Old DXT commands
make dxt              # Remove
make dxt-validate     # Remove

# New MCPB commands
make mcpb             # Create MCPB package
make mcpb-validate    # Validate MCPB package
```

#### Update CI/CD Pipelines

If you have custom CI/CD pipelines, update them:

```yaml
# Old
- name: Build DXT package
  run: make dxt

# New
- name: Build MCPB package
  run: make mcpb
```

#### Update Documentation References

Search your documentation for DXT references and update them:

- `.dxt` → `.mcpb`
- "DXT package" → "MCPB package"
- "Claude Desktop Extension" → "Model Context Protocol Bundle"

## Common Issues and Solutions

### Issue: "Package not recognized by Claude Desktop"

**Symptoms**: Claude Desktop doesn't recognize the `.mcpb` file

**Solutions**:
1. Ensure you downloaded the `.mcpb` file (not `.dxt`)
2. Check that Claude Desktop is updated to support MCPB format
3. Try restarting Claude Desktop after installation

### Issue: "Tool execution errors after migration"

**Symptoms**: MCP tools fail to execute or show errors

**Solutions**:
1. Verify Python 3.11+ is installed and accessible:
   ```bash
   python3 --version  # Should show 3.11+
   which python3      # Should be in PATH
   ```
2. Check that UVX is available:
   ```bash
   uvx --version
   ```
3. Restart Claude Desktop completely

### Issue: "Configuration lost during migration"

**Symptoms**: Extension settings are empty after migration

**Solutions**:
1. Manually re-enter your configuration in Claude Desktop → Settings → Extensions
2. Check that environment variables are properly set
3. Verify AWS credentials are still valid

### Issue: "Performance issues with MCPB"

**Symptoms**: Slower tool execution or timeouts

**Solutions**:
1. MCPB should be faster, not slower. If you experience issues:
2. Check your internet connection (UVX may need to download dependencies on first run)
3. Verify no antivirus software is interfering with UVX
4. Try clearing Claude Desktop cache and reinstalling

## Rollback Instructions

If you need to rollback to DXT format temporarily:

1. **Remove MCPB extension** from Claude Desktop
2. **Download legacy DXT package** from [releases](https://github.com/quiltdata/quilt-mcp-server/releases) (look for older versions with `.dxt` files)
3. **Install DXT package** following the old installation process
4. **Restore configuration** using your backed-up settings

**Important**: DXT format is deprecated and will not receive updates. Plan to migrate to MCPB when issues are resolved.

## Validation Checklist

After migration, verify these items work correctly:

- [ ] Extension appears in Claude Desktop Extensions list
- [ ] Configuration dialog shows your settings
- [ ] Tools panel displays Quilt MCP tools in new chat
- [ ] Basic operations work (e.g., `packages_list`)
- [ ] S3 operations function correctly
- [ ] Authentication with Quilt catalog works
- [ ] Performance is acceptable (should be faster than DXT)

## Getting Help

If you encounter issues during migration:

1. **Check this guide** for common solutions
2. **Review troubleshooting** in [README.md](../README.md#-troubleshooting)
3. **Search existing issues** at [GitHub Issues](https://github.com/quiltdata/quilt-mcp-server/issues)
4. **Create new issue** with:
   - Your operating system
   - Python version (`python3 --version`)
   - Claude Desktop version
   - Exact error messages
   - Steps to reproduce the issue

## FAQ

### Q: Why did you switch from DXT to MCPB?

A: MCPB provides significant advantages:
- 97.8% smaller package size (42MB → 1MB)
- Faster builds and installations
- More reliable dependency management
- Better alignment with MCP standards

### Q: Will DXT packages continue to work?

A: Existing DXT installations will continue to function, but:
- No new DXT packages will be released
- Updates and bug fixes will only be available in MCPB format
- We recommend migrating to MCPB for continued support

### Q: What if I have automation that depends on DXT files?

A: Update your automation to use MCPB format:
- Change file extension checks from `.dxt` to `.mcpb`
- Update download URLs to fetch MCPB packages
- Modify installation scripts for MCPB format

### Q: Is there any functional difference between DXT and MCPB?

A: No functional differences in MCP tools or capabilities. MCPB provides the same functionality with:
- Smaller package size
- Faster installation
- More reliable execution

### Q: Do I need to change my MCP client code?

A: No. The MCP protocol remains unchanged. Your existing client code will work identically with MCPB packages.

---

**Migration Support**: For additional help with migration, please see our [Getting Help](#getting-help) section or file an issue on GitHub.