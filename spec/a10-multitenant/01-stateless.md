# Stateless Architecture for Multitenant Deployment

**Status**: Draft
**Created**: 2026-01-28
**Objective**: Eliminate all local state to enable true stateless, read-only Docker deployments

## Problem Statement

The current MCP server architecture is **functionally stateless** but has three categories of filesystem dependencies that prevent truly stateless deployment:

1. **quilt3 Library Cache**: The quilt3 library maintains local caches and configuration in `~/.quilt/`
2. **Local Directory Mounts**: Example docker run commands show mounting local directories
3. **Writable Container Filesystem**: No explicit read-only constraints on the container

These create issues for:

- **Multitenant deployments**: Shared state across tenants
- **Container security**: Writable filesystem = attack surface
- **Horizontal scaling**: Cache inconsistency across replicas
- **Ephemeral environments**: Assumptions about filesystem persistence

## Current State Analysis

### 1. quilt3 Filesystem Usage

**Location**: `~/.quilt/` directory

**Contents observed**:

```
~/.quilt/
  ├── mcp_telemetry.jsonl   # 1.1 MB telemetry data
  └── (potentially other cache/config files)
```

**What needs investigation**:

- Does quilt3 cache downloaded package data?
- Are credentials stored locally? (Answer: Yes, confirmed in README.md)
- Does quilt3 support `QUILT_DISABLE_CACHE` or similar?
- What happens if `~/.quilt/` is not writable?

**Impact**:

- Credentials in `~/.quilt/` shouldn't be used in production (JWT-only mode exists via `MCP_REQUIRE_JWT=true`)
- Telemetry writes fail silently if filesystem is read-only (acceptable)
- Unknown if package operations cache data locally

### 2. Local Directory Mount Pattern

**Found in documentation** ([docs/archive/user/INSTALLATION.md:215](docs/archive/user/INSTALLATION.md#L215)):

```bash
docker run -p 8000:8000 \
  -e QUILT_CATALOG_URL=... \
  -e AWS_ACCESS_KEY_ID=... \
  -e AWS_SECRET_ACCESS_KEY=... \
  quilt-mcp-server:latest
```

**Good**: No volume mounts shown in main docs

**Issue**: Archive docs may contain outdated patterns with `-v` mounts

**What needs verification**:

- Are there any code paths that assume writable local directories?
- Do any tools write temporary files outside `/tmp`?
- Are there example configs that mount `~/.aws` or `~/.quilt`?

### 3. Container Filesystem Permissions

**Current Dockerfile** ([Dockerfile](Dockerfile)):

- No `USER` directive (runs as root)
- No read-only filesystem constraint
- No tmpfs mounts for writable locations
- No explicit security hardening

**What should change**:

- Container filesystem should be read-only (`--read-only`)
- Tmpfs mounts for required writable locations (`/tmp`, `/app/.cache`)
- Non-root user for reduced privilege
- Explicit declaration of writable paths

## Requirements for Stateless Operation

### Functional Requirements

1. **No Persistent Local State**
   - All authentication via JWT tokens (no `~/.quilt/` credentials)
   - No local caching of package data
   - No local telemetry accumulation
   - Ephemeral `/tmp` only (cleared on restart)

2. **Read-Only Filesystem**
   - Container runs with `--read-only` flag
   - All code and dependencies on read-only filesystem
   - Tmpfs mounts for truly ephemeral writes

3. **JWT-Only Authentication (Production Mode)**
   - `MCP_REQUIRE_JWT=true` enforced in Docker
   - No fallback to `~/.quilt/` credentials
   - Clear error messages when JWT missing

4. **Zero Local Configuration**
   - All configuration via environment variables
   - No assumption of `~/.aws/` or `~/.quilt/` directories
   - boto3 credentials from environment or IAM roles only

### Non-Functional Requirements

1. **Security**
   - Minimal attack surface (read-only FS)
   - No credential storage in container
   - Non-root user execution

2. **Scalability**
   - No state synchronization needed between replicas
   - Can scale horizontally without shared storage
   - No cache warming required

3. **Observability**
   - Startup logs confirm stateless mode
   - Warnings if cache writes attempted
   - Clear documentation of runtime expectations

## What Needs to Change

### 1. quilt3 Cache Behavior

**WHAT**: Disable all quilt3 local caching and telemetry

**Where**:

- Environment variable configuration in Dockerfile
- Potentially in QuiltService initialization
- Runtime context for quilt3 configuration

**Options to investigate**:

```python
# Option A: Environment variable (if quilt3 supports it)
QUILT_DISABLE_CACHE=true

# Option B: Configuration at runtime
quilt3.config(cache_dir=None)  # or cache_dir='/tmp/quilt-cache'

# Option C: Patch quilt3.util functions
# (Last resort, fragile)
```

**Success criteria**:

- No writes to `~/.quilt/` directory
- quilt3 operations complete successfully with read-only FS
- Package operations don't cache locally

### 2. Docker Container Configuration

**WHAT**: Enforce read-only container with tmpfs mounts

**Where**: Dockerfile and documentation

**Changes needed**:

a. **Dockerfile additions**:

- Add non-root USER directive
- Document required tmpfs mount points
- Set environment variable for JWT-only mode
- Add healthcheck that verifies stateless operation

b. **Runtime configuration** (docker run / docker-compose):

- `--read-only` flag
- `--tmpfs /tmp:size=100M,mode=1777`
- `--tmpfs /app/.cache:size=50M,mode=700` (if needed by quilt3)
- `--security-opt=no-new-privileges:true`
- `--cap-drop=ALL` (if compatible)

c. **Documentation updates**:

- README.md: Add "Production Deployment" section
- Show read-only Docker run example
- Explain JWT-only authentication requirement
- Document environment variable requirements

### 3. Authentication Flow

**WHAT**: Clarify and enforce JWT-only mode in production

**Where**:

- AuthService ([src/quilt_mcp/services/auth_service.py](src/quilt_mcp/services/auth_service.py))
- Tool authorization helpers
- Documentation

**Changes needed**:

a. **Environment variable** (already exists):

   ```
   MCP_REQUIRE_JWT=true  # Force JWT-only, no ~/.quilt/ fallback
   ```

b. **Dockerfile default**:

- Set `MCP_REQUIRE_JWT=true` by default in Docker
- Can be overridden for development

c. **Startup validation**:

- Log warning if running in JWT-only mode
- Verify no writable `~/.quilt/` directory accessible
- Confirm read-only filesystem if applicable

d. **Error messages**:

- Clear instructions when JWT missing
- No suggestion to run `quilt3 login` in production
- Point to JWT configuration docs

### 4. Temporary File Handling

**WHAT**: Verify all temporary files use `/tmp` (in-memory with tmpfs)

**Where**:

- Any file I/O operations
- Package creation/manipulation
- Data processing pipelines

**Verification needed**:

- Audit code for `tempfile.mkstemp()` usage
- Check if any tools write to current directory
- Verify boto3 doesn't cache in `~/.aws/`
- Test all tools with read-only filesystem

### 5. Configuration Management

**WHAT**: Document zero-filesystem-config deployment

**Where**:

- README.md
- docs/deployment/ (new)
- Example docker-compose.yml

**Changes needed**:

a. **Required environment variables**:

   ```bash
   # Authentication (production)
   MCP_REQUIRE_JWT=true

   # Catalog configuration
   QUILT_CATALOG_URL=https://your-catalog.quiltdata.com

   # AWS credentials (via IAM role preferred)
   AWS_REGION=us-east-1
   # OR
   AWS_ACCESS_KEY_ID=...
   AWS_SECRET_ACCESS_KEY=...

   # Optional: Disable caching
   QUILT_DISABLE_CACHE=true  # (if supported)
   ```

b. **IAM role authentication** (preferred over env vars):

- Document ECS task role pattern
- Document Kubernetes service account pattern
- Show how to test locally with AWS_PROFILE

c. **Remove examples** that show:

- Mounting `~/.aws/` or `~/.quilt/`
- Persisting volumes
- Writable container patterns

## Success Criteria

### Must Have

1. ✅ Docker container starts with `--read-only` flag
2. ✅ All MCP tools function correctly with read-only filesystem
3. ✅ No writes to persistent storage (only tmpfs)
4. ✅ JWT-only authentication works in production mode
5. ✅ Documentation shows secure deployment pattern

### Should Have

1. ✅ Non-root user in container
2. ✅ Startup health check validates stateless configuration
3. ✅ Clear error messages when misconfigured
4. ✅ Example docker-compose.yml with full security hardening
5. ✅ Integration test that verifies read-only operation

### Nice to Have

1. ⭕ Benchmark showing no performance impact
2. ⭕ Metrics on cache hit rate (should be 0)
3. ⭕ Comparison doc: development vs production mode
4. ⭕ Kubernetes deployment example

## Testing Strategy

### Unit Tests

- Mock filesystem to be read-only
- Verify no write attempts outside `/tmp`
- Test JWT-only authentication path

### Integration Tests

```bash
# Test 1: Read-only filesystem
docker run --read-only --tmpfs /tmp:size=100M \
  -e MCP_REQUIRE_JWT=true \
  -e AUTHORIZATION="Bearer $JWT_TOKEN" \
  quilt-mcp-server:test \
  # Run full tool suite

# Test 2: No quilt3 directory
docker run --read-only --tmpfs /tmp \
  -e HOME=/nonexistent \
  quilt-mcp-server:test

# Test 3: Verify no writes
docker run --read-only --tmpfs /tmp \
  --security-opt=no-new-privileges \
  quilt-mcp-server:test \
  # Check no files created except in /tmp
```

### Security Tests

- Run with minimal capabilities
- Verify no privilege escalation
- Test with security scanners (trivy, grype)

## Open Questions

1. **quilt3 cache control**:
   - Does quilt3 support `QUILT_DISABLE_CACHE` environment variable?
   - What breaks if `~/.quilt/` is not writable?
   - Can we configure quilt3 to use `/tmp/quilt-cache` instead?

2. **Package operations**:
   - Does `quilt3.Package.push()` cache data locally?
   - Are there temporary files created during package creation?
   - What's the memory impact of no-cache mode?

3. **Telemetry**:
   - Is `mcp_telemetry.jsonl` critical for operation?
   - Can telemetry be sent to remote endpoint instead?
   - Should we disable telemetry in stateless mode?

4. **Performance**:
   - What's the performance impact of no caching?
   - Are there hot paths that benefit from cache?
   - Do we need in-memory caching (TTL-based)?

5. **Backwards compatibility**:
   - Should desktop/stdio mode still support `~/.quilt/`?
   - How do we distinguish development vs production?
   - Is `FASTMCP_TRANSPORT` sufficient signal?

## Next Steps

1. **Investigation phase** (Don't implement yet):
   - [ ] Test quilt3 behavior with read-only `~/.quilt/`
   - [ ] Search quilt3 source for cache control options
   - [ ] Audit all file I/O in quilt-mcp-server codebase
   - [ ] Test current Docker image with `--read-only` flag

2. **Design phase**:
   - [ ] Choose quilt3 cache control mechanism
   - [ ] Design tmpfs mount strategy
   - [ ] Plan Dockerfile security hardening
   - [ ] Draft documentation updates

3. **Implementation phase** (After design approval):
   - [ ] Update Dockerfile with security measures
   - [ ] Add stateless mode configuration
   - [ ] Update documentation
   - [ ] Add integration tests
   - [ ] Update CI/CD pipeline

## References

- Current architecture analysis: (conversation context)
- MCP Protocol: <https://modelcontextprotocol.io>
- Docker security: <https://docs.docker.com/engine/security/>
- Dockerfile best practices: <https://docs.docker.com/develop/dev-best-practices/>
- quilt3 documentation: <https://docs.quilt.bio>

## Related Specifications

- (Future) `02-jwt-authentication.md` - Deep dive on JWT-only mode
- (Future) `03-deployment-patterns.md` - ECS, Kubernetes, etc.
- (Future) `04-performance-analysis.md` - Cache impact study
