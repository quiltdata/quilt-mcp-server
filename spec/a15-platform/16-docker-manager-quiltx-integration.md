# Docker Manager: Quiltx Integration & Container Management

## Objective

Extend `scripts/docker_manager.py` with container management capabilities and `quiltx` integration for automatic catalog configuration discovery, eliminating the need for separate bash scripts and manual environment variable management.

## Problem Statement

### Current State Issues

1. **Scattered Docker Scripts** - Multiple bash scripts for container management:
   - `scripts/tests/start-stateless-docker.sh` (78 lines)
   - `scripts/tests/stop-stateless-docker.sh` (29 lines)
   - `scripts/tests/start-multitenant-fake-docker.sh` (similar pattern)
   - `scripts/test-docker-health.sh` (279 lines)

2. **Manual Configuration** - Bash scripts require manual environment variables:
   ```bash
   export QUILT_CATALOG_URL=https://your-catalog.quiltdata.com
   export QUILT_REGISTRY_URL=https://registry.your-catalog.quiltdata.com
   ```

3. **Configuration Duplication** - Tabulator uses `quiltx` for auto-discovery, but Docker scripts don't:
   ```python
   # scripts/tests/tabulator_query.py (lines 37-38)
   from quiltx import get_catalog_url, get_catalog_region
   from quiltx.stack import find_matching_stack, fetch_catalog_config
   ```

4. **Code Duplication** - `docker_manager.py` handles image builds/push, but lacks container lifecycle management

### Error Example

```bash
make test-mcp-stateless
# ❌ QUILT_CATALOG_URL and QUILT_REGISTRY_URL must be set
#    Example:
#      export QUILT_CATALOG_URL=https://your-catalog.quiltdata.com
#      export QUILT_REGISTRY_URL=https://registry.your-catalog.quiltdata.com
```

## Proposed Solution

### Architecture

Extend existing `scripts/docker_manager.py` (769 lines) with:

1. **Container Management Methods** - Add to `DockerManager` class
2. **Quiltx Integration** - Auto-discover catalog/registry URLs
3. **New Subcommands** - `start`, `stop`, `logs` alongside existing `build`, `push`, `validate`
4. **Configuration Presets** - Stateless, multitenant-fake, health-check modes

### Design Principles

- ✅ Extend existing file (no new `docker_container_manager.py`)
- ✅ Reuse `DockerManager` infrastructure
- ✅ Follow existing patterns (subparsers, error handling)
- ✅ Maintain backward compatibility with all existing commands
- ✅ Use `quiltx` for auto-discovery (like `tabulator_query.py`)

## Implementation Tasks

### Task 1: Add Quiltx Configuration Discovery

**Location:** `scripts/docker_manager.py` - Add new method to `DockerManager` class

**Subtasks:**

1.1. Import `quiltx` with graceful fallback:
```python
try:
    from quiltx import get_catalog_url, get_catalog_region
except ImportError:
    # Fallback to environment variables only
```

1.2. Add `get_quilt_config()` method:
- Try `QUILT_CATALOG_URL` and `QUILT_REGISTRY_URL` from environment
- If not set, call `get_catalog_url()` from quiltx
- Construct registry URL from catalog URL (add `registry.` subdomain)
- Return tuple `(catalog_url, registry_url)` or `(None, None)`

1.3. Add `validate_quilt_config()` helper:
- Check if URLs are set
- Print helpful error messages if not
- Suggest using `quilt3 login` if auto-discovery fails

**Reference:** `scripts/tests/tabulator_query.py` lines 61-68, 73-79

### Task 2: Add Container Configuration Presets

**Location:** `scripts/docker_manager.py` - Add new methods to `DockerManager` class

**Subtasks:**

2.1. Create `ContainerConfig` dataclass:
```python
@dataclass
class ContainerConfig:
    name: str
    image: str
    port: int
    env_vars: dict[str, str]
    security_opts: list[str]
    resource_limits: dict[str, str]
```

2.2. Add `create_stateless_config()` method:
- Call `get_quilt_config()` for URLs
- Build env vars dict with QUILT_MULTITENANT_MODE, JWT settings, catalog URLs
- Set security constraints: `--read-only`, `--cap-drop=ALL`, tmpfs mounts
- Set resource limits: 512MB memory, CPU quota
- Return `ContainerConfig` instance

2.3. Add `create_multitenant_fake_config()` method:
- Similar to stateless but with different defaults
- Port 8003 vs 8002
- Same security/resource constraints

2.4. Add `create_health_check_config()` method:
- Minimal config for health testing
- No JWT/auth requirements
- Port 8080

**Reference:** `scripts/tests/start-stateless-docker.sh` lines 37-62

### Task 3: Add Container Lifecycle Methods

**Location:** `scripts/docker_manager.py` - Add new methods to `DockerManager` class

**Subtasks:**

3.1. Add `container_exists()` helper:
- Run `docker ps -a --format '{{.Names}}'`
- Check if container name in output

3.2. Add `container_is_running()` helper:
- Run `docker ps --format '{{.Names}}'`
- Check if container name in output

3.3. Add `start_container(config: ContainerConfig)` method:
- Stop/remove existing container if exists
- Build `docker run` command from config
- Add security opts, resource limits, env vars, port mapping
- Execute command with `_run_command()`
- Wait 3 seconds for startup
- Verify container is running
- Show access URL and log command

3.4. Add `stop_container(name: str)` method:
- Check if container exists
- Stop if running: `docker stop <name>`
- Remove container: `docker rm <name>`
- Print status messages

3.5. Add `show_logs(name: str, tail: int, follow: bool)` method:
- Build `docker logs` command with --tail and -f flags
- Execute without capturing output (stream to stdout)

**Reference:** `scripts/tests/start-stateless-docker.sh` and `scripts/tests/stop-stateless-docker.sh`

### Task 4: Add New Subcommands to Argument Parser

**Location:** `scripts/docker_manager.py` - Extend `parse_args()` function

**Subtasks:**

4.1. Add `start` subcommand:
```python
start_parser = subparsers.add_parser("start", help="Start a container")
start_parser.add_argument("--mode", choices=["stateless", "multitenant-fake", "health-check"])
start_parser.add_argument("--image", default="quilt-mcp:test")
start_parser.add_argument("--port", type=int)
start_parser.add_argument("--jwt-secret")
```

4.2. Add `stop` subcommand:
```python
stop_parser = subparsers.add_parser("stop", help="Stop a container")
stop_parser.add_argument("--name", required=True)
```

4.3. Add `logs` subcommand:
```python
logs_parser = subparsers.add_parser("logs", help="Show container logs")
logs_parser.add_argument("--name", required=True)
logs_parser.add_argument("--tail", type=int, default=50)
logs_parser.add_argument("--follow", action="store_true")
```

4.4. Update help text and examples in `epilog`

### Task 5: Add Command Handler Functions

**Location:** `scripts/docker_manager.py` - Add new functions after existing `cmd_*` functions

**Subtasks:**

5.1. Add `cmd_start(args: argparse.Namespace)` function:
- Create `DockerManager` instance
- Check Docker availability
- Based on `args.mode`, call appropriate `create_*_config()` method
- Call `manager.start_container(config)`
- Return exit code

5.2. Add `cmd_stop(args: argparse.Namespace)` function:
- Create `DockerManager` instance
- Call `manager.stop_container(args.name)`
- Return exit code

5.3. Add `cmd_logs(args: argparse.Namespace)` function:
- Create `DockerManager` instance
- Call `manager.show_logs(args.name, args.tail, args.follow)`
- Return exit code

5.4. Update `main()` function to dispatch new commands:
```python
elif args.command == "start":
    return cmd_start(args)
elif args.command == "stop":
    return cmd_stop(args)
elif args.command == "logs":
    return cmd_logs(args)
```

### Task 6: Update Makefile Targets

**Location:** `make.dev` - Update container test targets

**Subtasks:**

6.1. Update `test-mcp-stateless` target:
```makefile
test-mcp-stateless: docker-build
    @echo "🔐 Testing stateless MCP with JWT authentication..."
    @uv run python scripts/docker_manager.py start --mode stateless && \
        (uv run python scripts/mcp-test.py http://localhost:8002/mcp --jwt ... && \
        uv run python scripts/docker_manager.py stop --name mcp-stateless-test) || \
        (uv run python scripts/docker_manager.py stop --name mcp-stateless-test && exit 1)
```

6.2. Update `test-multitenant-fake` target:
```makefile
test-multitenant-fake: docker-build
    @uv run python scripts/docker_manager.py start --mode multitenant-fake && \
        (uv run python scripts/test-multitenant.py http://localhost:8003/mcp --verbose && \
        uv run python scripts/docker_manager.py stop --name mcp-multitenant-fake-test) || \
        (uv run python scripts/docker_manager.py stop --name mcp-multitenant-fake-test && exit 1)
```

### Task 7: Remove Legacy Bash Scripts (Breaking Change)

**Location:** `scripts/tests/` directory

**Subtasks:**

7.1. **Delete bash scripts:**
- `scripts/tests/start-stateless-docker.sh`
- `scripts/tests/stop-stateless-docker.sh`
- `scripts/tests/start-multitenant-fake-docker.sh`

7.2. **Update all references:**
- Update `CLAUDE.md` to use new Python commands
- Update any documentation that references old bash scripts
- Update `.github/workflows/` if they reference bash scripts

7.3. **Version bump:**
- This is a breaking change for anyone using bash scripts directly
- Requires minor version bump (e.g., 0.7.x → 0.8.0)

## Testing Requirements

### Unit Tests

**Location:** New file `tests/unit/test_docker_manager.py`

**Test Cases:**

1. `test_get_quilt_config_from_env` - Verify environment variable precedence
2. `test_get_quilt_config_from_quiltx` - Verify quiltx auto-discovery
3. `test_get_quilt_config_fallback` - Verify fallback when quiltx unavailable
4. `test_create_stateless_config` - Verify config structure and defaults
5. `test_create_multitenant_fake_config` - Verify config structure
6. `test_container_config_security_opts` - Verify security constraints
7. `test_container_config_resource_limits` - Verify resource limits

### Integration Tests

**Location:** `tests/integration/test_docker_operations.py` or similar

**Test Cases:**

1. `test_start_stop_container_lifecycle` - Full start/stop cycle
2. `test_container_logs_output` - Verify logs command
3. `test_auto_discovery_with_quilt3_config` - End-to-end with quiltx

### Manual Testing Checklist

- [ ] Run `make test-mcp-stateless` without setting env vars (should auto-discover)
- [ ] Run `make test-multitenant-fake` without setting env vars
- [ ] Verify `uv run python scripts/docker_manager.py start --mode stateless` works
- [ ] Verify `uv run python scripts/docker_manager.py logs --name mcp-stateless-test` shows logs
- [ ] Verify `uv run python scripts/docker_manager.py stop --name mcp-stateless-test` cleans up
- [ ] Verify backward compatibility: all existing `docker_manager.py` commands still work

## Migration Path (Breaking Change)

### Single Phase: Replace Bash Scripts with Python

**All changes in one PR:**

1. Extend `docker_manager.py` with container management
2. Update Makefile targets to use Python commands
3. **DELETE all legacy bash scripts** (breaking change)
4. Update documentation (`CLAUDE.md`, `README.md`)
5. Bump version to indicate breaking change

**Rationale for Breaking Change:**
- Bash scripts are internal test tooling, not public API
- Cleaner codebase without deprecated code paths
- Forces immediate adoption of better auto-configuration
- No external users depend on these specific bash scripts

## Success Criteria

- [ ] `make test-mcp-stateless` works without manual env vars
- [ ] `make test-multitenant-fake` works without manual env vars
- [ ] All existing `docker_manager.py` commands still work
- [ ] New commands have help text and examples
- [ ] **All legacy bash scripts deleted** (breaking change)
- [ ] Tests pass for new functionality
- [ ] Version bumped to reflect breaking change
- [ ] Documentation updated with new commands only

## Non-Goals

- **Not refactoring existing build/push/validate logic** - Only adding container management
- **Not changing Docker image build process** - Keep existing `build` and `push` commands
- **Not replacing docker_manager.py** - Extending it with new capabilities
- ~~**Not removing bash scripts immediately** - Deprecate first, remove later~~ **REMOVED: Delete immediately**

## References

- **Existing Implementation:** `scripts/docker_manager.py` (769 lines)
- **Pattern Reference:** `scripts/tests/tabulator_query.py` (quiltx usage, lines 37-39, 61-68, 73-79)
- **Container Scripts:** `scripts/tests/start-stateless-docker.sh`, `scripts/tests/stop-stateless-docker.sh`
- **Makefile Targets:** `make.dev` lines 136-172 (`test-mcp-stateless`, `test-multitenant-fake`)
- **Error Context:** Make output showing missing QUILT_CATALOG_URL/QUILT_REGISTRY_URL

## Related Specifications

- [09-quick-start-multitenant.md](./09-quick-start-multitenant.md) - Testing setup that will benefit from auto-config
- [08-multitenant-testing-spec.md](./08-multitenant-testing-spec.md) - Testing strategy using these containers

## Estimated Effort

- **Implementation:** 3-4 hours
- **Testing:** 1-2 hours
- **Documentation:** 1 hour
- **Total:** ~6 hours

## Priority

**Medium-High** - Improves developer experience and eliminates common configuration errors. Not blocking but provides significant quality-of-life improvement for testing workflows.

## Breaking Change Notice

**This is a breaking change** for anyone using the bash scripts directly:
- `scripts/tests/start-stateless-docker.sh` → **DELETED**
- `scripts/tests/stop-stateless-docker.sh` → **DELETED**
- `scripts/tests/start-multitenant-fake-docker.sh` → **DELETED**

**Migration:** All functionality moved to `scripts/docker_manager.py` with better auto-configuration.

**Impact:** Internal test tooling only - no external API changes. Makefile targets remain the same.
