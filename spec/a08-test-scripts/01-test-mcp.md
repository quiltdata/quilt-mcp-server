# Test MCP: Efficient Local Docker Testing Strategy

## Overview

This spec documents the optimized workflow for running MCP endpoint tests against local Docker builds, leveraging the existing `docker.py` infrastructure and Makefile targets.

## Current State Analysis

### Uncommitted Changes (Key Insights)

1. **make.dev changes**:
   - `test-scripts` target now depends on `docker-build`
   - Calls `test_mcp.py --image quilt-mcp:test` after other script tests
   - Uses local image tag `quilt-mcp:test` (no registry prefix)

2. **docker.py changes**:
   - `build_local()` method now creates tags WITHOUT registry prefix
   - Local tags format: `{image_name}:{version}` (e.g., `quilt-mcp:test`)
   - Registry prefix only added for remote push operations

3. **scripts/tests/test_mcp.py**:
   - Comprehensive test orchestrator
   - Manages Docker container lifecycle
   - Filters tests by idempotence (read-only vs write)
   - Integrates with mcp-list.py for config generation

### Existing Infrastructure

#### docker.py Capabilities

```python
class DockerManager:
    def build_local(self, version: str = "dev") -> bool:
        """Build Docker image locally without pushing."""
        # Creates tag: {DOCKER_IMAGE_NAME}:{version}
        # Example: quilt-mcp:test, quilt-mcp:dev
```

#### Makefile Targets

**make.deploy** provides:
- `docker-build` - Builds locally using docker.py
- `docker-tools` - Validates Docker availability and AWS setup
- `docker-push` - Full build + push to ECR
- `docker-validate` - Validates pushed images in registry

**make.dev** provides:
- `test-scripts` - Now includes docker-build + mcp-test.py execution

#### Dockerfile

- Multi-stage build (builder + runtime)
- Based on `ghcr.io/astral-sh/uv:python3.11-bookworm-slim`
- Exposes port 8000 for HTTP transport
- Entry point: `quilt-mcp` command

## Efficient Testing Strategy

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     make test-scripts                        │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Step 1: docker-build (via docker.py)                   │ │
│  │   → uv run python scripts/docker.py build             │ │
│  │   → Creates: quilt-mcp:test                           │ │
│  └────────────────────────────────────────────────────────┘ │
│                           ↓                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Step 2: pytest scripts/tests/test_*.py                │ │
│  │   → Runs unit tests for scripts                       │ │
│  └────────────────────────────────────────────────────────┘ │
│                           ↓                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Step 3: MCP Integration Tests                         │ │
│  │   → uv run python scripts/tests/test_mcp.py           │ │
│  │      --image quilt-mcp:test                           │ │
│  │                                                        │ │
│  │   Sub-workflow:                                       │ │
│  │   a. mcp-list.py → generates test config             │ │
│  │   b. docker run -d -p 8765:8000 quilt-mcp:test       │ │
│  │   c. Wait for health check                           │ │
│  │   d. mcp-test.py --config mcp-test.yaml -t           │ │
│  │   e. docker stop + rm container                      │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Key Optimizations

#### 1. **Local Tagging Without Registry**

**Problem**: Original docker.py always prefixed tags with registry, requiring AWS credentials even for local builds.

**Solution**:
```python
# docker.py build_local() now uses:
local_tag = f"{self.image_name}:{version}"  # quilt-mcp:test
# NOT: f"{self.registry}/{self.image_name}:{version}"
```

**Benefits**:
- No AWS credentials required for local testing
- Faster builds (no registry detection overhead)
- Cleaner Docker image list locally

#### 2. **Dependency Chain in make.dev**

```makefile
test-scripts: docker-build scripts/tests/test_*.py | $(RESULTS_DIR)
    # 1. Build happens first (via dependency)
    # 2. Run pytest on scripts/tests
    # 3. Run mcp integration tests with built image
```

**Benefits**:
- Single command runs everything
- Build only happens once per test run
- Image reused across test invocations

#### 3. **Standardized Test Image Tag**

**Convention**: `quilt-mcp:test` for all test-scripts invocations

**Rationale**:
- Predictable, consistent naming
- Easy to identify test images: `docker images | grep test`
- No timestamp pollution in local Docker registry

#### 4. **Idempotent Test Filtering**

```python
# scripts/tests/test_mcp.py
def filter_tests_by_idempotence(config_path: Path, idempotent_only: bool):
    """Filter test tools based on idempotence flag."""
    # By default: only read-only operations
    # With --all: includes write operations
```

**Benefits**:
- CI/local development runs safe tests only
- Full test suite available when needed
- Prevents accidental data modification

## Usage Patterns

### Common Workflows

#### 1. **Standard Development Testing** (Most Common)

```bash
# Build + test in one command
make test-scripts

# What happens:
# 1. Builds quilt-mcp:test locally
# 2. Runs pytest on scripts/tests/*.py
# 3. Launches container from quilt-mcp:test
# 4. Runs idempotent MCP tests
# 5. Cleans up container
```

#### 2. **Rapid Iteration on Tests**

```bash
# First time: build image
make docker-build

# Then iterate on tests without rebuilding:
uv run python scripts/tests/test_mcp.py \
    --image quilt-mcp:test \
    --no-generate  # Skip config regeneration if not needed

# Or test specific endpoint:
uv run python scripts/tests/test_mcp.py \
    --no-docker \
    --endpoint http://localhost:8000/mcp/
```

#### 3. **Full Test Suite (Including Write Operations)**

```bash
# Build image
make docker-build

# Run ALL tests (careful - includes mutations)
uv run python scripts/tests/test_mcp.py \
    --image quilt-mcp:test \
    --all  # Include non-idempotent tests
```

#### 4. **Debug Test Failures**

```bash
# Keep container running to inspect
uv run python scripts/tests/test_mcp.py \
    --image quilt-mcp:test \
    --keep-container \
    --logs \
    --verbose

# Container stays up, you can:
# - docker exec -it <container> bash
# - curl http://localhost:8765/health
# - View logs
```

#### 5. **Test Against Different Build Stages**

```bash
# Test with dev version
uv run python scripts/docker.py build --version dev
uv run python scripts/tests/test_mcp.py --image quilt-mcp:dev

# Test specific git commit
VERSION=$(git rev-parse --short HEAD)
uv run python scripts/docker.py build --version $VERSION
uv run python scripts/tests/test_mcp.py --image quilt-mcp:$VERSION
```

### Advanced Patterns

#### Parallel Testing (Future Enhancement)

```bash
# Run multiple containers on different ports
uv run python scripts/tests/test_mcp.py \
    --image quilt-mcp:test \
    --port 8765 &

uv run python scripts/tests/test_mcp.py \
    --image quilt-mcp:test \
    --port 8766 &

wait
```

#### Cross-Platform Validation

```bash
# Build for amd64 (production target)
docker buildx build \
    --platform linux/amd64 \
    -t quilt-mcp:test-amd64 \
    .

# Test it
uv run python scripts/tests/test_mcp.py \
    --image quilt-mcp:test-amd64
```

## docker.py Integration Details

### Command Structure

```bash
# Build for local testing (no registry)
uv run python scripts/docker.py build [--version VERSION]
# Creates: quilt-mcp:{VERSION}

# Build for production (with registry)
uv run python scripts/docker.py push --version VERSION
# Creates: {REGISTRY}/quilt-mcp:{VERSION}
# Also tags: {REGISTRY}/quilt-mcp:latest
```

### Environment Variables

```bash
# Required for docker.py
export DOCKER_IMAGE_NAME=quilt-mcp

# Optional for push operations
export ECR_REGISTRY=123456789.dkr.ecr.us-east-1.amazonaws.com
export AWS_ACCOUNT_ID=123456789
export AWS_DEFAULT_REGION=us-east-1
```

### Docker Build Context

From [Dockerfile](../../Dockerfile):

```dockerfile
# Multi-stage build
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder
# ... installs dependencies ...

FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS runtime
# ... copies built artifacts ...
ENV FASTMCP_TRANSPORT=http \
    FASTMCP_HOST=0.0.0.0 \
    FASTMCP_PORT=8000
EXPOSE 8000
CMD ["quilt-mcp"]
```

**Key Points**:
- Port 8000 is standard container port
- `-p 8765:8000` maps to avoid localhost:8000 conflicts
- Health check endpoint: `/health`
- MCP endpoint: `/mcp/`

### AWS Credentials Management

**Best Practice: Volume Mount (Recommended)**

The test_mcp.py script automatically mounts `~/.aws` as a read-only volume:

```python
docker run -d \
    -v ~/.aws:/root/.aws:ro \
    -e AWS_REGION=us-east-1 \
    -e AWS_PROFILE=default \
    quilt-mcp:test
```

**Advantages:**
- ✅ Supports AWS profiles, SSO, and MFA
- ✅ Automatic credential rotation
- ✅ Read-only mount prevents modification
- ✅ Works with boto3's credential chain
- ✅ No credentials exposed in docker inspect

**Alternative: Environment Variables (CI/CD only)**

For automated environments without `~/.aws`:

```bash
docker run -d \
    -e AWS_ACCESS_KEY_ID=xxx \
    -e AWS_SECRET_ACCESS_KEY=yyy \
    -e AWS_SESSION_TOKEN=zzz \
    quilt-mcp:test
```

**Disadvantages:**
- ❌ Credentials visible in `docker inspect`
- ❌ No SSO/MFA support
- ❌ Manual credential management

The test_mcp.py script detects if `~/.aws` exists and automatically uses the secure volume mount approach.

## test_mcp.py Internals

### Class: DockerMCPServer

Manages container lifecycle:

```python
class DockerMCPServer:
    def start(self) -> bool:
        # 1. Check if image exists (pull if needed)
        # 2. docker run -d with port mapping
        # 3. Wait for health check
        # 4. Return success/failure

    def stop(self):
        # docker stop + rm

    def logs(self, tail: int = 50):
        # docker logs for debugging
```

### Test Filtering Logic

```python
def filter_tests_by_idempotence(config_path: Path, idempotent_only: bool):
    """
    Reads mcp-test.yaml, filters tools based on 'idempotent' flag.

    idempotent: true  -> Read-only, safe for CI
    idempotent: false -> Write operations, manual testing only
    """
```

### Configuration Flow

```
.env (user configuration)
    ↓
mcp-list.py (loads .env)
    ↓ (introspects server)
    ↓ (embeds environment config)
scripts/tests/mcp-test.yaml (self-contained)
    ↓ (read by test_mcp.py)
Filter by idempotence
    ↓
mcp-test.py (executes tests)
    ↓
Docker container (with ~/.aws mounted)
```

**Self-Contained Configuration:**

The mcp-test.yaml now includes an `environment` section populated from .env:

```yaml
environment:
  AWS_PROFILE: default
  AWS_DEFAULT_REGION: us-east-1
  QUILT_CATALOG_DOMAIN: nightly.quilttest.com
  QUILT_DEFAULT_BUCKET: s3://quilt-ernest-staging
  QUILT_TEST_PACKAGE: raw/test
  QUILT_TEST_ENTRY: README.md
test_tools:
  bucket_objects_list:
    arguments:
      bucket: quilt-ernest-staging  # from QUILT_DEFAULT_BUCKET
```

**Benefits:**
- ✅ Single source of truth (.env file)
- ✅ Test configuration is self-contained
- ✅ Easy to customize per environment
- ✅ No manual YAML editing required
- ✅ Works offline (only needs .env + ~/.aws)

## Makefile Target Dependencies

### Current Structure (make.dev)

```makefile
test-scripts: docker-build scripts/tests/test_*.py | $(RESULTS_DIR)
    @echo "===🔍Running script tests..."
    @if [ -d "scripts/tests" ] && [ "$$(find scripts/tests -name "test_*.py" | wc -l)" -gt 0 ]; then \
        export PYTHONPATH="src" && uv run python -m pytest scripts/tests/ -v; \
    else \
        echo "No script tests found"; \
    fi
    @echo "\n===🧪 Running MCP server integration tests (idempotent only)..."
    @uv run python scripts/tests/test_mcp.py --image quilt-mcp:test
    @echo "\n===✅ Finished all script tests"
```

**Dependency Chain**:
1. `test-scripts` depends on `docker-build`
2. `docker-build` (from make.deploy) runs `docker.py build`
3. Creates `quilt-mcp:test` image
4. test_mcp.py uses that image

### Integration with CI (make.dev)

```makefile
test-ci: | $(RESULTS_DIR)
    @echo "Running CI tests..."
    @uv sync --group test
    @export PYTHONPATH="src" && uv run python -m pytest tests/ -v \
        -m "not slow and not search and not admin" \
        --cov=quilt_mcp \
        --cov-report=xml:$(RESULTS_DIR)/coverage-all.xml
```

**Note**: `test-ci` does NOT run `test-scripts` to avoid Docker requirement in CI. Docker testing handled separately in CI via GitHub Actions.

## Performance Considerations

### Build Caching

Docker layer caching is optimized in Dockerfile:

```dockerfile
# Layer 1: Dependencies (rarely changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Layer 2: Source code (changes frequently)
COPY src ./src
RUN uv sync --frozen --no-dev
```

**Result**: Rebuilds are fast if only source code changes.

### Test Execution Time

**Typical Timings**:
- `docker build`: 60-90s (first time), 10-20s (cached)
- Container start + health check: 3-5s
- Idempotent test suite: ~30-60s
- Full test suite: ~2-5 minutes

**Total**: `make test-scripts` ~90-120s on first run, ~45-75s on subsequent runs.

## Error Handling

### Common Failure Modes

#### 1. Docker Not Running

```bash
$ make test-scripts
❌ Docker daemon is not running or not accessible
```

**Fix**: Start Docker Desktop or `dockerd`

#### 2. Port Already in Use

```bash
$ uv run python scripts/tests/test_mcp.py
❌ Failed to start container: port 8765 already in use
```

**Fix**:
```bash
# Kill existing container
docker ps | grep mcp-test
docker stop <container>

# Or use different port
uv run python scripts/tests/test_mcp.py --port 8766
```

#### 3. Image Not Found

```bash
$ uv run python scripts/tests/test_mcp.py --image quilt-mcp:test
❌ Image not found: quilt-mcp:test
```

**Fix**:
```bash
make docker-build
# Or let test_mcp.py handle it (it auto-pulls if needed)
```

#### 4. Health Check Timeout

```bash
⏳ Waiting for server to be ready...
....................
❌ Server failed to become ready within timeout
```

**Debug**:
```bash
# Check container logs
docker logs <container_name>

# Check container status
docker ps -a | grep mcp-test

# Try manual health check
curl http://localhost:8765/health
```

## Future Enhancements

### Short-Term

1. **Add `docker-test` target to make.dev**
   ```makefile
   docker-test: docker-build
       @uv run python scripts/tests/test_mcp.py --image quilt-mcp:test
   ```

2. **Add test result caching**
   - Cache test results based on git commit hash
   - Skip tests if code hasn't changed

3. **Parallel test execution**
   - Run multiple test suites in parallel
   - Each in separate container on different port

### Long-Term

1. **Multi-architecture testing**
   - Build images for arm64 + amd64
   - Test both architectures locally

2. **Test matrix**
   - Test against multiple Python versions
   - Test against multiple MCP client versions

3. **Performance benchmarking**
   - Track test execution time over releases
   - Alert on performance regressions

## Best Practices

### Development Workflow

1. **Always run `make test-scripts` before committing**
   - Ensures Docker build succeeds
   - Validates MCP endpoints work

2. **Use `--keep-container` for debugging**
   - Inspect container state after failures
   - Test fixes without rebuilding

3. **Filter tests appropriately**
   - Default (idempotent): Safe for CI
   - `--all`: Manual validation before releases

### CI/CD Integration

1. **Separate Docker builds in CI**
   - Build once, test multiple times
   - Cache Docker layers between jobs

2. **Use `docker-validate` in CI**
   - Verify pushed images are valid
   - Check architecture compatibility

3. **Tag images appropriately**
   - CI builds: `{version}-{commit}`
   - Release builds: `{version}` + `latest`
   - Test builds: `test` (local only)

## References

### Key Files

- [make.dev](../../make.dev) - Development workflow
- [make.deploy](../../make.deploy) - Production build workflow
- [scripts/docker.py](../../scripts/docker.py) - Docker operations
- [scripts/tests/test_mcp.py](../../scripts/tests/test_mcp.py) - Test orchestrator
- [scripts/mcp-list.py](../../scripts/mcp-list.py) - Config generator
- [Dockerfile](../../Dockerfile) - Container definition

### Related Specs

- [spec/feature-docker-container/](../../spec/feature-docker-container/) - Docker container feature
- [docs/developer/REPOSITORY.md](../../docs/developer/REPOSITORY.md) - Repository structure

### External Documentation

- [Docker BuildKit](https://docs.docker.com/build/buildkit/)
- [Docker Multi-stage builds](https://docs.docker.com/build/building/multi-stage/)
- [MCP Protocol](https://spec.modelcontextprotocol.io/)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)

## Appendix: Quick Reference

### Essential Commands

```bash
# Build and test everything
make test-scripts

# Build Docker image only
make docker-build

# Run tests against existing image
uv run python scripts/tests/test_mcp.py --image quilt-mcp:test

# Run tests with debugging
uv run python scripts/tests/test_mcp.py \
    --image quilt-mcp:test \
    --verbose \
    --keep-container \
    --logs

# Test external server (skip Docker)
uv run python scripts/tests/test_mcp.py \
    --no-docker \
    --endpoint http://localhost:8000/mcp/

# Full test suite (including writes)
uv run python scripts/tests/test_mcp.py \
    --image quilt-mcp:test \
    --all
```

### Environment Setup

```bash
# Verify prerequisites
docker --version
uv --version
python --version

# Set up project
uv sync
cp env.example .env

# Verify Docker is ready
make docker-tools
```

### Troubleshooting

```bash
# Check Docker images
docker images | grep quilt-mcp

# Check running containers
docker ps | grep mcp-test

# Clean up test containers
docker ps -a | grep mcp-test | awk '{print $1}' | xargs docker rm -f

# Clean up test images
docker images | grep quilt-mcp | grep test | awk '{print $3}' | xargs docker rmi -f

# Full Docker cleanup (careful!)
docker system prune -a
```

---

**Document Status**: ✅ Complete
**Last Updated**: 2025-01-11
**Author**: Analysis of uncommitted changes and existing infrastructure
**Related Issues**: N/A (documentation of current implementation)
