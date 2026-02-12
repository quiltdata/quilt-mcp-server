# Docker Build Caching Optimization

## Problem

The `docker-build` target was rebuilding every time, even when source files hadn't changed.

**Root cause:** No file dependencies or sentinel tracking in [make.deploy:162](../../make.deploy#L162)

```make
# OLD (always rebuilds)
docker-build: docker-check
 @uv run python scripts/docker_manager.py build --version test
```

## Solution

Added proper Makefile dependency tracking with a sentinel file:

```make
# NEW (only rebuilds when source changes)
DOCKER_SENTINEL := $(BUILD_DIR)/.docker-build-test
DOCKER_DEPS := Dockerfile pyproject.toml uv.lock $(APP_FILES)

$(DOCKER_SENTINEL): $(DOCKER_DEPS) | docker-check
 @echo "🐳 Building Docker image (source files changed)..."
 @mkdir -p $(BUILD_DIR)
 @uv run python scripts/docker_manager.py build --version test
 @touch $(DOCKER_SENTINEL)

docker-build: $(DOCKER_SENTINEL)
 @echo "✅ Docker image up to date"
```

## How It Works

1. **First build:** Sentinel file doesn't exist → Full build → Creates `build/.docker-build-test`
2. **Subsequent builds:**
   - If source files unchanged → Sentinel newer → **Instant (no rebuild)**
   - If source files changed → Sentinel older → Rebuild → Update sentinel
3. **Force rebuild:** `make docker-rebuild` (bypasses sentinel)

## Dependencies Tracked

Changes to any of these trigger a rebuild:

- `Dockerfile` - Build configuration
- `pyproject.toml` - Python dependencies
- `uv.lock` - Locked dependency versions
- `src/quilt_mcp/**/*.py` - All Python source files

## Performance Impact

### Before (Always Rebuilds)

```bash
make run-docker-remote
# 🐳 Building Docker image... (2-5 minutes)
# Every single time, even if nothing changed!
```

### After (Cached)

```bash
make run-docker-remote
# ✅ Docker image up to date (instant)

# Only rebuilds when source changes:
touch src/quilt_mcp/main.py
make run-docker-remote
# 🐳 Building Docker image (source files changed)... (2-5 minutes)
```

## Usage

```bash
# Smart build (only if needed)
make docker-build

# Force rebuild (bypass cache)
make docker-rebuild

# Clean sentinel to force next build
make clean
```

## Implementation

- **[make.deploy:162-177](../../make.deploy#L162-L177)** - Sentinel-based docker-build
- **[make.deploy:30](../../make.deploy#L30)** - Added docker-rebuild to .PHONY
- **[Makefile:57-58](../../Makefile#L57-L58)** - Updated help text
- **[build/.docker-build-test](../../build/.docker-build-test)** - Sentinel file (created on first build)

## Docker Layer Caching

The Dockerfile already has excellent layer caching:

1. **Metadata layer** (rarely changes): `pyproject.toml`, `uv.lock`, `README.md`
2. **Dependencies layer** (changes occasionally): `uv sync --no-install-project`
3. **Source code layer** (changes frequently): `COPY src`, `uv sync`

With both Makefile gating AND Docker layer caching, builds are now blazingly fast!
