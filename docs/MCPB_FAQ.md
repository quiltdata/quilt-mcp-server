<!-- markdownlint-disable MD013 MD024 -->
# MCPB Migration FAQ

## Frequently Asked Questions

### General Questions

#### Q: What is MCPB and why did you switch from DXT?

**A:** MCPB (Model Context Protocol Bundle) is the new packaging format for Claude Desktop extensions. We switched because:

- **97.8% smaller packages** (42MB → 1MB)
- **Faster downloads and installations**
- **Improved build reliability**
- **Better dependency management** through UVX
- **Future-proof format** aligned with MCP ecosystem

#### Q: Will my existing DXT installation continue to work?

**A:** Yes, existing DXT installations will continue to function, but:

- No new DXT packages will be released
- Updates and bug fixes will only be available in MCPB format
- We strongly recommend migrating to MCPB for continued support

#### Q: Is there any difference in functionality between DXT and MCPB?

**A:** No functional differences. MCPB provides the same MCP tools and capabilities as DXT, just with improved packaging and performance.

### Installation Questions

#### Q: How do I migrate from DXT to MCPB?

**A:** Follow these steps:

1. Backup your current configuration (catalog domain, bucket settings)
2. Remove the DXT extension from Claude Desktop
3. Download the latest `.mcpb` file from releases
4. Install the MCPB package in Claude Desktop
5. Restore your configuration settings

See our detailed [Migration Guide](MIGRATION_DXT_TO_MCPB.md) for step-by-step instructions.

#### Q: Do I need to install any additional software for MCPB?

**A:** The MCPB format uses UVX for dependency management, which is automatically handled. You still need:

- Python 3.11+ accessible in your login shell
- AWS credentials configured
- Same system requirements as before

#### Q: Why is my MCPB package so much smaller?

**A:** MCPB packages contain only metadata and use UVX to install Python dependencies at runtime, rather than bundling all dependencies in the package. This results in dramatically smaller download sizes.

### Technical Questions

#### Q: What happens to my Python dependencies with MCPB?

**A:** Dependencies are managed by UVX at runtime:

- First run may be slightly slower as dependencies are installed
- Subsequent runs are fast due to UVX caching
- Dependencies are automatically managed and updated
- More reliable than bundled dependencies

#### Q: Will MCPB work on my operating system?

**A:** MCPB works on the same platforms as DXT:

- ✅ macOS (Intel and Apple Silicon)
- ✅ Windows (via WSL recommended)
- ✅ Linux (all major distributions)

UVX handles cross-platform dependency management automatically.

#### Q: How do I troubleshoot MCPB installation issues?

**A:** Common troubleshooting steps:

1. Verify Python 3.11+ is in your PATH: `python3 --version`
2. Check that UVX is available: `uvx --version`
3. Restart Claude Desktop after installation
4. Check Claude Desktop logs for error messages
5. Verify AWS credentials are still valid

See our [Troubleshooting Guide](../README.md#-troubleshooting) for detailed solutions.

### Performance Questions

#### Q: Is MCPB faster or slower than DXT?

**A:** MCPB performance characteristics:

- **First run**: Slightly slower (dependency installation)
- **Subsequent runs**: Same speed or faster
- **Installation**: Much faster (1MB vs 42MB download)
- **Memory usage**: Lower (no bundled dependencies)
- **Startup time**: Similar or improved

#### Q: Why does the first MCPB run take longer?

**A:** The first run includes UVX dependency installation:

- UVX downloads and installs Python packages
- This happens only once per dependency set
- Subsequent runs use cached dependencies
- Network connection affects initial setup time

#### Q: How can I pre-install dependencies to speed up first run?

**A:** You can pre-warm the UVX cache:

```bash
# Pre-install dependencies (optional)
uvx run --from quilt-mcp-server --help
```

### Development Questions

#### Q: How do I build MCPB packages for development?

**A:** Use the updated build commands:

```bash
# Build MCPB package
make mcpb

# Validate MCPB package
make mcpb-validate

# Full local release workflow
make release-local
```

#### Q: What happened to the old DXT build commands?

**A:** DXT build commands are deprecated:

- `make dxt` - No longer functional (Phase 3 disabled)
- `make dxt-validate` - No longer functional
- Use `make mcpb` and `make mcpb-validate` instead

#### Q: How do I update my CI/CD pipelines for MCPB?

**A:** Update your workflows:

```yaml
# Old
- run: make dxt
- run: make dxt-validate

# New
- run: make mcpb
- run: make mcpb-validate
```

See our updated [GitHub Actions workflows](.github/workflows/) for examples.

### Migration Issues

#### Q: Claude Desktop doesn't recognize my MCPB file

**Possible solutions:**

1. Ensure you downloaded the `.mcpb` file (not `.dxt`)
2. Check Claude Desktop version supports MCPB format
3. Try restarting Claude Desktop
4. Verify file wasn't corrupted during download

#### Q: My tools disappeared after migrating to MCPB

**Likely causes and solutions:**

1. **Configuration lost**: Re-enter your settings in Claude Desktop → Extensions → Quilt MCP
2. **Python path issues**: Verify `python3 --version` works in terminal
3. **UVX not available**: Check `uvx --version` or install UVX
4. **Permission issues**: Verify AWS credentials still work

#### Q: MCPB installation succeeds but tools don't work

**Troubleshooting steps:**

1. Check Python 3.11+ is accessible: `which python3`
2. Verify UVX is installed: `uvx --version`
3. Test AWS credentials: `aws sts get-caller-identity`
4. Check Claude Desktop logs for error messages
5. Try reinstalling the MCPB package

#### Q: Can I roll back to DXT if MCPB doesn't work?

**A:** Yes, temporarily:

1. Remove MCPB extension from Claude Desktop
2. Download a legacy DXT package from older releases
3. Install the DXT package
4. Restore your configuration

**Note**: DXT is deprecated and won't receive updates. Please report MCPB issues so we can fix them.

### Specific Error Messages

#### Q: "ModuleNotFoundError: No module named 'quilt_mcp'"

**A:** This indicates UVX dependency installation failed:

1. Check internet connection
2. Verify UVX is installed: `uvx --version`
3. Clear UVX cache: `uvx cache clean`
4. Restart Claude Desktop
5. Check Python 3.11+ is in PATH

#### Q: "Command 'uvx' not found"

**A:** UVX is not installed or not in PATH:

```bash
# Install UVX
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add to PATH (add to ~/.bashrc or ~/.zshrc)
export PATH="$HOME/.cargo/bin:$PATH"

# Verify installation
uvx --version
```

#### Q: "Package validation failed"

**A:** The MCPB package may be corrupted:

1. Re-download the MCPB package
2. Verify file integrity (check file size)
3. Try downloading from a different browser
4. Check for antivirus interference

### Support Questions

#### Q: Where can I get help with MCPB migration?

**A:** Multiple support channels available:

1. **Migration Guide**: [MIGRATION_DXT_TO_MCPB.md](MIGRATION_DXT_TO_MCPB.md)
2. **GitHub Issues**: [Report bugs or ask questions](https://github.com/quiltdata/quilt-mcp-server/issues)
3. **Documentation**: [Complete documentation](../docs/)
4. **Troubleshooting**: [README troubleshooting section](../README.md#-troubleshooting)

#### Q: How do I report MCPB-specific issues?

**A:** When creating GitHub issues, include:

- Operating system and version
- Claude Desktop version
- Python version: `python3 --version`
- UVX version: `uvx --version`
- Exact error messages
- Steps to reproduce the issue
- Whether DXT worked previously

#### Q: Will you continue supporting DXT users?

**A:** Limited support:

- ✅ **Existing DXT installations**: Will continue to work
- ❌ **New DXT releases**: No longer provided
- ❌ **Bug fixes for DXT**: Only available in MCPB
- ✅ **Migration support**: Help transitioning to MCPB

### Future Questions

#### Q: What's the long-term plan for MCPB?

**A:** MCPB is our primary packaging format going forward:

- Continuous improvements and optimizations
- Better integration with MCP ecosystem
- Enhanced developer tools and validation
- Potential for additional packaging formats as MCP evolves

#### Q: Will there be other packaging formats besides MCPB?

**A:** Currently focused on MCPB, but we're monitoring:

- MCP ecosystem developments
- Community feedback and needs
- Platform-specific optimization opportunities
- Emerging packaging standards

---

**Still have questions?** Check our [Migration Guide](MIGRATION_DXT_TO_MCPB.md) or [create an issue](https://github.com/quiltdata/quilt-mcp-server/issues/new) on GitHub!
