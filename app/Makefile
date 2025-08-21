
test-ci:
	@echo "Running CI test subset (skipping AWS/integration-heavy tests)..."
	@uv sync --group test
	@export PYTHONPATH="$(PWD)" && uv run python -m pytest tests/ -v -m "not aws" -k "not TestPermissionDiscoveryEngine and not TestEnhancedPackageBrowsing"