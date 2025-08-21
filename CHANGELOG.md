<!-- markdownlint-disable MD025 -->
# Changelog

All notable changes to the Quilt MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.1] - 2025-08-21

### Added

- GraphQL-based bucket discovery fallback via Quilt Catalog `/graphql` when IAM denies `s3:ListBuckets`/`ListAllMyBuckets` (merges with Glue/Athena fallbacks; de-duplicates)
- Tests covering GraphQL discovery path, IAM-denied paths, and package operations (`app/tests/test_package_ops.py`)
- Enhanced permission discovery leveraging `quilt3.get_boto3_session()` when logged in

### Changed

- Improved bucket discovery to prefer catalog-backed enumeration, maintaining AWS-native fallbacks
- CI: Build DXT after unit tests on `develop`; stop nightly push; upgrade artifact actions

### Fixed

- Ensure `README.md` and Quilt summary files are added to the package files themselves, not only metadata (addresses prior behavior)

### Internal / Maintenance

- Expanded unit tests across package tools and permissions
- Minor tooling and scripts updates (e.g., `check_all_readme.py`)

Thanks to contributions in [PR #45](https://github.com/quiltdata/quilt-mcp-server/pull/45), [PR #44](https://github.com/quiltdata/quilt-mcp-server/pull/44), and related fixes.

## [0.3.6] - 2025-08-21

### Fixed

- Updated prerequisite check to detect user's default Python from login environment instead of current Python
- Fixed Python version detection for Claude Desktop compatibility (now checks login shell Python, not virtual environment Python)

### Changed

- Improved prerequisite validation to more accurately simulate Claude Desktop's environment
- Added guidance for pyenv users in prerequisite check error messages

## [0.3.5] - 2025-01-20

### Added

- Initial DXT (Desktop Extension) release for Claude Desktop
- Claude Desktop integration with manifest.json configuration
- Prerequisite checking script for DXT installation
- Bootstrap script for Claude Desktop Python execution
- User configuration options for catalog domain, AWS profile, and region

### Features

- 13 secure MCP tools for Quilt data operations
- Package management tools (list, search, browse, create, update, delete)
- S3 operations (list objects, get info, read text, upload, download)
- System tools (auth check, filesystem check)
- JWT authentication for secure data access
- 4-phase deployment pipeline (app, build-docker, catalog-push, deploy-aws)
- SPEC-compliant validation workflow
- Port-isolated testing (8000-8002 for phases 1-3, 443/80 for phase 4)
