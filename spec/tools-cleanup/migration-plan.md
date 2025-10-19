# Tools Cleanup Plan: Resource Inline Migration

## Objective

- Inline the read-only logic that still lives under `quilt_mcp.tools.*` directly into their corresponding `quilt_mcp.resources.*` modules.
- Delete the legacy tool modules once their functionality is owned by resources, including all exports, registrations, and doc references.
- Restore or replace the skipped tests with resource-focused coverage so that the migration does not regress behaviour.

## References

- Current resources implementation: `src/quilt_mcp/resources/`
- Current tools that still power resources (must be fully migrated):  
  `auth`, `governance`, `athena_glue`, `metadata_examples`, `metadata_templates`, `permissions`, `tabulator`, `workflow_orchestration`
- Legacy patterns to borrow from: `legacy_0_7_2:src/quilt_mcp/resources/` (direct service usage, resource registry wiring, response shaping).

## High-Level Approach

1. **Inventory & Contract Freeze**
   - Record the input parameters, return payloads, and error semantics for each tool function used by a resource.
   - Identify shared helpers (`GovernanceService`, `format_users_as_table`, etc.) that should stay reusable (likely move to `services/` or keep as module-level helpers inside the resource).
   - Confirm no other parts of the codebase depend on those tool entry points (scan with `rg "quilt_mcp.tools.<module>"`).
2. **Extract Service Logic**
   - For each domain (auth, governance, athena, metadata, permissions, tabulator, workflow), move the core implementation from the tool into either:
     - A dedicated helper class or function colocated within the resource module; or
     - An existing `services.*` module if it already encapsulates the Quilt/ AWS interaction (following `legacy_0_7_2` style).
   - Maintain async boundaries: resources should call synchronous helpers via `asyncio.to_thread` only when truly blocking.
3. **Update Resources to be Self-Sufficient**
   - Replace `from quilt_mcp.tools...` imports with the new helper(s).
   - Preserve the existing `ResourceResponse` structure and metadata fields.
   - Ensure parameter validation that currently lives in the tools is replicated in the resources (e.g., governance user lookup).
4. **Delete Tool Modules**
   - Remove the migrated files from `src/quilt_mcp/tools/`.
   - Update `src/quilt_mcp/tools/__init__.py` to drop the module name from `_MODULE_PATHS`.
   - Remove any unit tests that only exercised the tool shim; replace with resource-level tests.
5. **Documentation & Examples**
   - Search `docs/` and `spec/` for references to the removed tools and update them to point to resources or higher-level workflows.
   - Update CLI or integration guides if they currently instruct users to call the tool directly.
6. **Testing & Validation**
   - Re-enable the skipped tests by porting them to exercise the resource endpoints (`ResourceRegistry.read_resource` or direct resource instances).
   - Add regression tests where the tools previously contained nuanced formatting or error handling (e.g., governance table formatting, Athena suggestion text).
   - Run targeted service mocks for admin/Athena permissions so tests remain hermetic.
7. **Clean-Up & Verification**
   - Ensure the repo passes `ruff`, type checks, and the reinstated unit/e2e suites.
   - Perform a grep to confirm no `quilt_mcp.tools.<migrated>` references remain.
   - Update `CHANGELOG.md` with the removal notice and migration guidance.

## Domain-Specific Tasks

- **Authentication (`resources/auth.py`)**
  - Inline `auth_status`, `catalog_info`, `catalog_name`, `filesystem_status` logic.
  - Validate dependency on `QuiltConfig`, `os`, and filesystem helpers once moved.
- **Governance (`resources/admin.py`)**
  - Relocate `GovernanceService` and associated async functions.
  - Mirror the legacy resource approach of instantiating the admin service on demand while keeping table formatting utilities.
- **Athena (`resources/athena.py`)**
  - Move `AthenaQueryService` calls in-line (reuse `services/athena_service` directly).
  - Decide how to expose `athena_tables_list`—add a new parameterized resource or keep as helper for schema discovery.
- **Metadata (`resources/metadata.py`)**
  - Inline template loading and example generation while sharing validation helpers.
- **Permissions (`resources/permissions.py`)**
  - Embed `aws_permissions_discover`, `bucket_recommendations_get`, `bucket_access_check` logic, ensuring boto clients remain mockable.
- **Tabulator (`resources/tabulator.py`)**
  - Inline `tabulator_buckets_list` / `tabulator_tables_list` using `services.tabulator`.
  - Keep pagination semantics consistent with tool output.
- **Workflow (`resources/workflow.py`)**
  - Inline `workflow_list_all`, `workflow_get_status`, leveraging any orchestration services.

## Deliverables

- Updated resource modules with embedded logic and helper abstractions.
- Deleted tool modules and cleaned `__init__` exports.
- Revised tests (unit + e2e) that cover the resource behaviour.
- Documentation updates describing the resource URIs instead of tool entry points.
- Validation checklist proving no stale tool references remain.

## Open Questions

- Should any of the migrated helpers become shared utilities (`quilt_mcp/services` or `utils`) to avoid circular imports?
- Do we need compatibility shims for third-party consumers that might still import the tools package?
- Are there additional read-only tools (e.g., search explain/suggest) that should also be folded into resources during this cleanup?
