# Consolidate MCP Test Scripts

## Problem

Three overlapping scripts create confusion:

- `mcp-test-runner.py` - spawns stdio servers + orchestrates tests
- `docker_manager.py` - spawns HTTP servers only
- `mcp-test.py` - test execution engine

Relationship is unclear, maintenance burden high.

## Proposed Architecture

1. **docker_manager.py** -  LAUNCH DOCKER container using HTTP+JWT (like now)
2. **mcp-test.py** - Test execution
   - connect to existing HTTP server
   - run its OWN stdio server
3. **DELETE** - mcp-test-runner.py

## Tasks

### 1. Update mcp-test.py CLI interface

#### Current: external process passes FDs

mcp-test.py --stdio --stdin-fd 3 --stdout-fd 4

#### Proposed: mcp-test.py spawns its own server

mcp-test.py --spawn-local [--python /path/to/python]

#### mcp-test.py tasks

- [x] Add `--spawn-local` flag for local stdio server spawning (pull from LocalMCPServer in mcp-test-runner.py as needed)
- [x] REPLACES `--stdio --read-fd --write-fd` for external stdio (marked as deprecated)
- [x] Keep existing `--http URL` for HTTP testing
- [x] Update `--help` documentation

### 2. Update Makefile targets

- [x] `test-mcp`: Use `mcp-test.py --spawn-local`
- [x] `test-mcp-legacy`: Same with different envars
- [x] `test-mcp-docker`: as today
- [x] Remove all references to `mcp-test-runner.py`

### 3. Delete mcp-test-runner.py

- [x] Verify all functionality migrated
- [x] Delete `scripts/mcp-test-runner.py`
- [x] Update any documentation references (none found outside spec)
- [ ] Run full test suite: `make test-all` (ready to verify)

## Benefits

✅ Single source of truth for Docker HTTP running (docker_manager.py)
✅ Clear separation: docker_manager = Docker HTTP, mcp-test = testing, stdio
✅ Removes confusing "runner" concept
✅ Easier to understand and maintain

## Testing

```bash
# Verify local stdio
make test-mcp-legacy

# Verify Docker HTTP
make test-mcp-docker

# Full suite
make test-all
```
