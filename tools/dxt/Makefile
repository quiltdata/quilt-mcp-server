# DXT Build Makefile
# Build Claude Desktop Extension (.dxt) for Quilt MCP Server

# Paths
APP_DIR := ../app
ASSETS_DIR := assets
BUILD_DIR := build
BUILD_PKGS_DIR := $(BUILD_DIR)/lib
DIST_DIR := dist

# Variables
DXT_NAME := quilt-mcp
# Allow VERSION to be overridden from command line, otherwise read from pyproject.toml
MANIFEST_VERSION := $(shell python3 ../../scripts/version-utils.py get-version --pyproject ../../pyproject.toml 2>/dev/null || echo "dev")
PACKAGE_VERSION := $(if $(VERSION),$(VERSION),$(MANIFEST_VERSION))
PACKAGE_ID := $(DIST_DIR)/$(DXT_NAME)-$(PACKAGE_VERSION)
PACKAGE_NAME := $(PACKAGE_ID).dxt
RELEASE_NAME := $(PACKAGE_ID)-release.zip
CHECK_PREREQS_SCRIPT := $(ASSETS_DIR)/check-prereqs.sh

# Marker files for incremental builds
ASSETS_MARKER := $(BUILD_DIR)/.assets-copied
APP_MARKER := $(BUILD_DIR)/.app-copied
DEPS_MARKER := $(BUILD_DIR)/.deps-installed

# Source file dependencies
ASSET_FILES := $(wildcard $(ASSETS_DIR)/*)
APP_FILES := $(shell find $(APP_DIR)/quilt_mcp -name "*.py" 2>/dev/null || true)

.PHONY: help contents build test validate release assess clean check-tools debug

# Check for required tools
check-tools:
	@command -v npx >/dev/null 2>&1 || { echo "❌ npx not found - install Node.js"; exit 1; }
	@command -v uv >/dev/null 2>&1 || { echo "❌ uv not found - install uv package manager"; exit 1; }
	@echo "✅ All required tools found"

help:
	@echo "Available targets:"
	@echo "  build      - Build DXT package using official dxt pack"
	@echo "  test       - Test import structure in build directory before packaging"
	@echo "  validate   - Validate the DXT package (with official validator)"
	@echo "  release    - Build the standalone release package"
	@echo "  assess     - Run check-prereqs.sh script"
	@echo "  check-tools - Check for required tools"
	@echo "  debug      - Show build variables and configuration"
	@echo "  clean      - Clean build artifacts"

debug: check-tools
	@echo "DXT_NAME=$(DXT_NAME)"
	@echo "PACKAGE_VERSION=$(PACKAGE_VERSION)"
	@echo "PACKAGE_NAME=$(PACKAGE_NAME)"
	@echo "RELEASE_NAME=$(RELEASE_NAME)"
	@echo "APP_DIR=$(APP_DIR)"
	@echo "ASSETS_DIR=$(ASSETS_DIR)"
	@echo "BUILD_DIR=$(BUILD_DIR)"
	@echo "BUILD_PKGS_DIR=$(BUILD_PKGS_DIR)"
	@echo "DIST_DIR=$(DIST_DIR)"
	@echo "CHECK_PREREQS_SCRIPT=$(CHECK_PREREQS_SCRIPT)"
	@echo "ASSETS_MARKER=$(ASSETS_MARKER)"
	@echo "APP_MARKER=$(APP_MARKER)"
	@echo "DEPS_MARKER=$(DEPS_MARKER)"
	@echo "ASSET_FILES=$(ASSET_FILES)"
	@echo "APP_FILES=$(APP_FILES)"

# Intermediate targets for incremental builds
$(ASSETS_MARKER): $(ASSET_FILES)
	@echo "Copying DXT assets..."
	@mkdir -p $(BUILD_DIR)
	@cp -r $(ASSETS_DIR)/* $(BUILD_DIR)/
	@chmod +x $(BUILD_DIR)/check-prereqs.sh
	@echo "Generating manifest.json from template..."
	@python3 ../../scripts/version-utils.py generate-manifest $(BUILD_DIR)/manifest.json.j2 $(BUILD_DIR)/manifest.json --version $(PACKAGE_VERSION)
	@rm $(BUILD_DIR)/manifest.json.j2
	@touch $@

$(APP_MARKER): $(APP_FILES)
	@echo "Copying app source code..."
	@for file in $(APP_FILES); do \
		rel_path=$${file#../app/}; \
		mkdir -p "$$(dirname "$(BUILD_DIR)/$$rel_path")"; \
		cp $$file $(BUILD_DIR)/$$rel_path; \
	done
	@touch $@

$(DEPS_MARKER): ../pyproject.toml
	@echo "Installing Python dependencies..."
	@mkdir -p $(BUILD_PKGS_DIR)
	@cd .. && uv pip install --target $(CURDIR)/$(BUILD_PKGS_DIR) --no-cache-dir --quiet --no-binary=pydantic-core .
	@touch $@

contents: $(ASSETS_MARKER) $(APP_MARKER)

# Build the DXT package only if dependencies have changed
$(PACKAGE_NAME): contents
	@echo "Packing with official DXT CLI..."
	@mkdir -p $(DIST_DIR)
	@npx @anthropic-ai/dxt pack $(BUILD_DIR) $(PACKAGE_NAME)
	@echo "✅ Built $(PACKAGE_NAME)"

build: check-tools test $(PACKAGE_NAME)

# Create the release zip file
$(RELEASE_NAME): $(PACKAGE_NAME) $(ASSETS_DIR)/README.md $(CHECK_PREREQS_SCRIPT)
	@echo "Creating release package..."
	@mkdir -p $(DIST_DIR)/release
	@cp $(PACKAGE_NAME) $(DIST_DIR)/release/
	@cp $(ASSETS_DIR)/README.md $(DIST_DIR)/release/
	@cp $(CHECK_PREREQS_SCRIPT) $(DIST_DIR)/release/
	@cd $(DIST_DIR)/release && zip -r ../$(DXT_NAME)-$(PACKAGE_VERSION)-release.zip .
	@rm -rf $(DIST_DIR)/release
	@echo "✅ Built $(RELEASE_NAME)"

validate: check-tools $(PACKAGE_NAME)
	@echo "Validating DXT package..."
	@echo "Validating with official DXT CLI..."
	@npx @anthropic-ai/dxt info $(PACKAGE_NAME)
	@echo "Validating generated manifest.json..."
	@npx @anthropic-ai/dxt validate $(BUILD_DIR)/manifest.json
	@echo "✅ DXT package validation passed"

release: validate $(RELEASE_NAME)
	@echo "✅ Release package $(RELEASE_NAME) ready for distribution"

test: contents
	@echo "Testing bootstrap script in build directory..."
	@echo "Verifying bootstrap.py can import dependencies and start setup..."
	@cd $(BUILD_DIR) && python -c "import bootstrap; print('Bootstrap module imported successfully')" && echo "✅ Bootstrap test passed"

bootstrap: contents
	@echo "Testing bootstrap in build directory..."
	@echo "Running bootstrap.py to verify imports work correctly..."
	@cd $(BUILD_DIR) && timeout 1 python bootstrap.py || [ $$? -eq 124 ] && echo "✅ Bootstrap test passed (server started successfully)"

assess:
	@echo "Running prerequisites assessment..."
	@if [ -f $(CHECK_PREREQS_SCRIPT) ]; then \
		chmod +x $(CHECK_PREREQS_SCRIPT) && $(CHECK_PREREQS_SCRIPT); \
	else \
		echo "❌ check-prereqs.sh not found in $(ASSETS_DIR)"; \
		exit 1; \
	fi

clean:
	@echo "Cleaning build artifacts..."
	@rm -rf $(BUILD_DIR) $(DIST_DIR)
	@echo "✅ Clean complete"
