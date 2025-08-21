## Enhancement Issues: Quilt Features Missing MCP Counterparts

Below are proposed enhancement issues to close feature gaps between Quilt (docs.quilt.bio, quiltdata/quilt) and this MCP server. Each entry includes a title, rationale, proposed API, and acceptance criteria to facilitate implementation.

### 1) Package install/materialize to local filesystem
- Rationale: Quilt CLI supports installing/materializing packages locally; MCP lacks an equivalent.
- Proposed API: `packages.package_install(package_name, dest_dir, registry?, top_hash?, tag?, include?, exclude?, overwrite=false)`
- Acceptance criteria:
  - Downloads all package objects to `dest_dir` (supports include/exclude globs).
  - Supports selecting a specific `top_hash` or `tag`.
  - Idempotent with `overwrite` control; returns manifest with bytes written and file list.

### 2) Package export with copy/symlink modes
- Rationale: Quilt CLI can export packages using symlinks or copies.
- Proposed API: `packages.package_export(package_name, dest_dir, registry?, top_hash?, mode="copy"|"symlink")`
- Acceptance criteria:
  - Creates local view of package contents using selected mode.
  - Returns manifest, errors, and skipped items.

### 3) Build package from YAML/manifest (build.yml) and from local dir
- Rationale: `quilt3 build` supports building from a configuration; MCP does not.
- Proposed API:
  - `package_ops.package_build_from_yaml(package_name, build_yaml_text|s3_uri, registry?, message?)`
  - `package_ops.package_build_from_dir(package_name, local_dir, registry?, include?, exclude?, message?)`
- Acceptance criteria:
  - Parse build.yml mapping logical->physical keys, set metadata, push package.
  - Directory build respects include/exclude; returns push hash and summary.

### 4) Package version history and manifests
- Rationale: Users need to list historical versions and inspect manifests.
- Proposed API:
  - `packages.package_versions_list(package_name, registry?, limit?, include_tags=false)`
  - `packages.package_manifest(package_name, registry?, top_hash?)`
- Acceptance criteria:
  - Lists top hashes with timestamps and messages; optional tag mapping.
  - Returns normalized manifest (logical->physical, sizes, hashes) for a version.

### 5) Package tagging: create, delete, list
- Rationale: Quilt supports tagging versions; MCP lacks it.
- Proposed API:
  - `packages.tags_list(package_name, registry?)`
  - `packages.tag_add(package_name, tag, top_hash, registry?)`
  - `packages.tag_delete(package_name, tag, registry?)`
- Acceptance criteria:
  - Can add/remove tags and list current tag->top_hash map with audit info.

### 6) Package verify/integrity check
- Rationale: Beyond access checks, verify object hashes and completeness.
- Proposed API: `package_management.package_verify(package_name, registry?, top_hash?, deep_hash=false)`
- Acceptance criteria:
  - Compares stored hashes vs object ETags/content; reports mismatches and missing objects.

### 7) Cross-registry/package promotion (copy between buckets)
- Rationale: Common workflow to promote packages across environments.
- Proposed API: `package_ops.package_copy(package_name, src_registry, dst_registry, top_hash?, rewrite_physical=false)`
- Acceptance criteria:
  - Copies package metadata and objects (server-side S3 copy) between registries.
  - Preserves logical keys; supports object rewrite or reference.

### 8) Auth helpers: login/logout wrappers
- Rationale: Simplify auth flows via MCP.
- Proposed API:
  - `auth.login_start(catalog_url?) -> {login_url, instructions}`
  - `auth.logout() -> status`
- Acceptance criteria:
  - Exposes a login URL and guidance; logout clears current session via quilt3.

### 9) JSON Schema metadata validation
- Rationale: Quilt emphasizes JSON Schema-based metadata; MCP has custom validators only.
- Proposed API: `validators.metadata_validate_jsonschema(metadata, schema_json|schema_s3_uri)`
- Acceptance criteria:
  - Validates against Draft-07+; returns errors, warnings, and paths; supports remote refs.

### 10) Metadata import helpers (CSV/XLSX to JSON)
- Rationale: Quilt docs describe spreadsheet-driven metadata; MCP lacks import tools.
- Proposed API: `metadata_templates.import_tabular_metadata(file_s3_uri|base64, mapping_spec)`
- Acceptance criteria:
  - Converts tabular rows/columns into per-object or package-level JSON per mapping.

### 11) Event-Driven Packaging (EDP) scaffolding
- Rationale: Quilt supports EDP via S3 events; MCP should scaffold infra and rules.
- Proposed API:
  - `edp.generate_stack(config) -> IaC artifact (CDK/CFN)`
  - `edp.preview(config) -> simulated package plans`
- Acceptance criteria:
  - Produces deployable infra spec and deterministic preview of triggers and outputs.

### 12) Tabulator/Athena queries across packages
- Rationale: Quilt Tabulator aggregates tabulars with Athena.
- Proposed API:
  - `tabulator.query(sql, workgroup?, output_s3?, catalog_db?)`
  - `tabulator.prepare(package_names[], registry?, infer_tables=true)`
- Acceptance criteria:
  - Executes queries and returns result sets; can infer Glue/Athena tables from package contents.

### 13) Bookmarks and multi-select for package creation
- Rationale: Catalog supports bookmarking files across buckets; MCP can mirror this.
- Proposed API:
  - `buckets.bookmarks_add(items[])`
  - `buckets.bookmarks_list()`
  - `buckets.bookmarks_clear()`
- Acceptance criteria:
  - Server-side persisted bookmark set; integrates with `create_package_enhanced` as `files`.

### 14) Package diff: enrich output parity with CLI
- Rationale: Current diff exists; align structure and provide human/JSON modes.
- Proposed API: `packages.package_diff(..., output="structured"|"summary"|"unified")`
- Acceptance criteria:
  - Supports multiple renderings and exit codes in summary mode.

### 15) Bucket lifecycle utilities (promote/archive)
- Rationale: Common workflows to move data between prefixes/stages.
- Proposed API: `buckets.objects_copy(src_uris[], dst_prefix, preserve_metadata=true)`
- Acceptance criteria:
  - Batch copy/move with retries, manifests, and dry-run.

### 16) Registry/config management parity
- Rationale: Extend beyond `configure_catalog/switch_catalog` to full config.
- Proposed API: `auth.config_get()`, `auth.config_set(key, value)`, `auth.config_list()`
- Acceptance criteria:
  - Read/write Quilt config keys safely with validation and audit output.

### 17) Package search facets and advanced filters
- Rationale: Expose richer search options (metadata facets) akin to catalog.
- Proposed API: `packages.packages_search(query, limit?, filters?)`
- Acceptance criteria:
  - Filter by namespace, tags, file types, size ranges when supported by backend.

---

References
- Quilt docs: `https://docs.quilt.bio`
- Quilt repo: `https://github.com/quiltdata/quilt`
- Quilt3 Python/CLI parity targets: install/materialize, export, build from YAML, tagging, version history, JSON Schema metadata validation, EDP, Tabulator.

Notes
- Some entries (EDP, Tabulator) may span infra; initial scope can provide scaffolding/clients under feature flags.
- Where Quilt APIs are not public, implement best-effort wrappers around `quilt3` or document constraints.

