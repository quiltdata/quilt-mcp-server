<!-- markdownlint-disable MD013 -->
# A03: Release Version Management

## Problem Statement

The project has two version declarations that can become out of sync:

- `pyproject.toml` declares version `0.5.7` as the authoritative Python package version
- `tools/dxt/assets/manifest.json` declares version `0.4.0` for the Claude Desktop Extension

This version drift creates confusion during releases and can lead to mismatched package versions.

## Solution Overview

Implement automated version synchronization where `pyproject.toml` serves as the single source of truth, and `manifest.json` is generated from a template during the build process.

## Functional Requirements

### FR-1: Single Source of Truth

- `pyproject.toml` version field is the authoritative version for the entire project
- All other version declarations must derive from this source

### FR-2: Template-Based Generation

- `tools/dxt/assets/manifest.json` is generated from `tools/dxt/assets/manifest.json.j2` template
- Template uses Jinja2 syntax with `{{ version }}` placeholder
- Generated file preserves all other manifest properties unchanged

### FR-3: Build Integration

- Version sync occurs automatically during build process
- Sync can be triggered manually via `make sync-version`
- Build fails if versions are out of sync after generation

### FR-4: Validation

- Pre-commit validation ensures generated manifest matches template + pyproject version
- Release tagging reads version from pyproject.toml, not manifest.json

## Behavioral Specifications

### BS-1: Version Reading

```gherkin
Given a pyproject.toml with version "1.2.3"
When I read the project version
Then the returned version should be "1.2.3"
```

### BS-2: Template Processing

```gherkin
Given a manifest.json.j2 template with "{{ version }}" placeholder
And pyproject.toml version is "1.2.3"
When I generate the manifest from template
Then the manifest.json should contain version "1.2.3"
And all other fields should remain unchanged
```

### BS-3: Sync Detection

```gherkin
Given pyproject.toml version is "1.2.3"
And manifest.json version is "1.2.2"
When I check version sync status
Then sync should be required
```

### BS-4: Build Integration

```gherkin
Given pyproject.toml version is "1.2.3"
And manifest.json template exists
When I run the build process
Then manifest.json should be generated with version "1.2.3"
And build should succeed
```

## Technical Requirements

### TR-1: Dependencies

- Use existing Jinja2 dependency (already available)
- Use Python stdlib `tomllib` for TOML parsing
- No additional external dependencies

### TR-2: File Locations

- Template: `tools/dxt/assets/manifest.json.j2`
- Generated: `tools/dxt/assets/manifest.json`
- Source: `pyproject.toml`

### TR-3: Error Handling

- Clear error messages for missing files
- Validation of TOML and JSON syntax
- Graceful handling of template rendering errors

### TR-4: Makefile Integration

- `make sync-version` target for manual sync
- Integration with existing build targets
- Update `make tag` to read from pyproject.toml

## Implementation Approach

1. **Phase 1: Core Functionality**
   - Create version reading utility
   - Implement template-based generation
   - Add sync validation

2. **Phase 2: Build Integration**
   - Add Makefile targets
   - Integrate with existing build process
   - Update release tagging logic

3. **Phase 3: Validation**
   - Add pre-commit checks
   - Implement sync verification
   - Add error handling

## Acceptance Criteria

- [ ] `pyproject.toml` version can be read programmatically
- [ ] `manifest.json.j2` template renders correctly with version substitution
- [ ] Generated `manifest.json` has correct version and preserved fields
- [ ] `make sync-version` updates manifest from template
- [ ] `make tag` reads version from pyproject.toml instead of manifest.json
- [ ] Build process automatically syncs versions
- [ ] Validation detects version mismatches
- [ ] All existing functionality remains unaffected

## Testing Strategy

- **Unit Tests**: Version reading, template rendering, file operations
- **Integration Tests**: End-to-end sync process, build integration
- **BDD Tests**: User-facing behaviors for version management
- **Error Handling Tests**: Invalid files, missing dependencies, syntax errors

## Rollback Strategy

If implementation causes issues:

1. Revert to manual version management
2. Keep existing manifest.json as static file
3. Update versions manually during releases
4. Remove template and sync logic
