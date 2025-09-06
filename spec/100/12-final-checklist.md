<!-- markdownlint-disable MD013 -->
# Final Tasks: Repository Cleanup Completion

**Issue**: [#100 - cleanup repo/make](https://github.com/quiltdata/quilt-mcp-server/issues/100)  
**Status**: Core objectives achieved, critical gap requires fix

## Critical Task (Required)

- [ ] **Fix Build Cleanup Gap**: Edit `make.dev` file, add to `dev-clean` target:

  ```bash
  @rm -rf build/ dist/ .ruff_cache/ 2>/dev/null || true
  @find . -name ".DS_Store" -delete 2>/dev/null || true
  ```

  *Context*: Root `build/` and `dist/` contain Python build artifacts but aren't cleaned by current `make clean`

- [ ] **Test cleanup fix**: Verify `make clean` removes all build directories after fix

## Optional Tasks (Lower Priority)

- [ ] **Clean up .gitignore obsolete entries**: Remove unused entries:
  - `enterprise/`, `quilt/` (external repos no longer used)
  - `/deploy-aws/cdk.out`, `/deploy/cdk.out` (CDK not used)
  - `deployment/packager/test-event*.json` (old test events)
  - `marimo/_static/`, `__marimo__/`, `.abstra/` (frameworks not used)

- [ ] **Rename prerequisite scripts for clarity**: Current names are confusing
  - `bin/test-prereqs.sh` → `bin/check-dev.sh` (checks .env, AWS config for development)
  - `src/deploy/check-prereqs.sh` → `src/deploy/check-dxt.sh` (checks Python, Claude Desktop for end users)

- [ ] **Modernize test-endpoint script**: Convert `bin/test-endpoint.sh` (667 lines, 17 JSON-RPC calls) to Python
  - Replace bash/curl with `requests` library for cleaner HTTP handling
  - Restore `test-tools.json` from commit `aa001a4` (was in removed `shared/` directory)
  - Convert JSON config to YAML/TOML format with 14 pre-configured MCP tools
  - Add proper JSON schema validation for MCP responses
  - Better error handling and structured output
  - Suggested name: `bin/mcp-test.py` with `tests/configs/mcp-test.yaml`

## Completion Status

✅ **ACHIEVED**: All core cleanup requirements met

- Single consolidated Makefile system (3 files)
- Shallow directory hierarchy with logical organization  
- Files in obvious, predictable locations

❌ **REMAINING**: Build cleanup gap (critical fix needed)
