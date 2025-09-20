<!-- markdownlint-disable MD013 -->
# Analysis - Tool Inventory Audit

**Reference**: Requirements in `spec/170-tool-audit/01-requirements.md`

## Current Architecture

1. MCP tools live under `src/quilt_mcp/tools/`, grouped by domain (auth, buckets, packages, permissions, workflow orchestration, etc.) with dozens of exported functions per module.
2. `src/quilt_mcp/__init__.py` re-exports a curated subset of tool functions, but many additional functions remain module-local or only documented elsewhere.
3. `docs/api/TOOLS.md` serves as narrative documentation and categorizes ~80 tools into thematic sections that do not necessarily match module boundaries.
4. `quilt_mcp_tools.csv` contains a tabular listing of tool metadata (module, function name, signature, description) but appears to be manually curated and not obviously generated from code.
5. Tests, fixtures, and simulation scripts reference tool names directly (e.g., `tests/integration/test_integration.py`, `tests/fixtures/data/*.json`), implying backwards compatibility requirements for existing identifiers.

## Implementation Idioms & Conventions

1. Most tools are synchronous functions returning JSON-serializable dictionaries; behavior often wraps Quilt services (`QuiltService`, `generate_signed_url`, etc.) with additional formatting.
2. Naming patterns vary: some use noun-first (`package_browse`), others verb-first (`create_package_enhanced`), some include domains twice (`packages_list` vs. `package_list_package_names`).
3. Modules frequently expose related verbs with shared prefixes (`bucket_object_*`, `package_create*`) but other domains split similar verbs across multiple modules (`package_ops`, `package_management`, `unified_package`).
4. Workflow orchestration tools maintain in-memory state (`_workflows` dict) and return structured responses with status/next steps, showing that side effects exist beyond stateless queries.
5. Documentation, CSV, and exports are not clearly tied together via a single source of truth; updates require touching multiple locations manually.

## System Constraints & Limitations

1. Tool names act as public API identifiers for MCP clients; renames or removals will break automation, recorded fixtures, and documentation unless migration paths exist.
2. Tests patch concrete module paths (`@patch("quilt_mcp.tools.buckets.get_s3_client")`, etc.), constraining refactors that move or rename tool implementations.
3. Some tools depend on AWS services (Athena, S3) and integration tests rely on cached fixtures; any audit must respect existing service abstractions and auth flows.
4. The CSV inventory currently resides at repo root and may be consumed by external tooling (unknown); restructuring it demands coordination with downstream consumers.
5. Maintaining alphabetical order within large documents is currently manual, increasing drift risk when multiple contributors touch similar sections.

## Technical Debt & Refactoring Opportunities

1. Multiple modules expose overlapping capabilities (e.g., `package_ops` vs. `package_management` vs. `unified_package`) without a clear differentiation strategy, driving cognitive load.
2. Function names mix singular/plural (`package_browse` vs. `packages_list`) and action verbs, making scanning the inventory inconsistent.
3. Some modules export long lists of similar utilities (e.g., workflow orchestration) where not all variants are documented or surfaced in the CSV, hinting at doc/code drift.
4. There is no automated process to regenerate `quilt_mcp_tools.csv` or verify alphabetical ordering in documentation, so drift accumulates silently.
5. Tool descriptions vary in verbosity and tone across modules and docs, reducing predictability for AI agents that rely on textual hints.

## Gaps Between Current State & Requirements

1. No consolidated, authoritative catalog exists—engineers must cross-reference CSV, module exports, and docs to understand the full inventory.
2. Overlaps and redundancies are undocumented; there is no living record of why similar tools coexist or which should be preferred.
3. Naming conventions are implicit and unenforced, so new tools can introduce further inconsistency without immediate feedback.
4. Alphabetical sorting is not guaranteed across CSV or markdown documentation, violating the requirement for easy scanning.
5. Guidelines for adding future tools are scattered (if they exist); contributors lack a single checklist to keep the catalog healthy.

## Architectural Challenges

1. Creating a canonical list without breaking compatibility requires mapping each tool to its consumer set and planning deprecation paths.
2. Aligning names, docs, and CSV entries demands coordination between code generation, documentation, and release workflows to avoid triple maintenance.
3. Introducing enforcement (linting, generators) must integrate with existing `make` targets and CI without causing unacceptable friction.
4. Any restructuring must consider integration tests and recorded fixtures that rely on current tool names, requiring migration strategies and broad regression coverage.
