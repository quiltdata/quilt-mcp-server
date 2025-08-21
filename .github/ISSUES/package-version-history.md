---
name: Package Version History and Manifests
about: Add support for listing historical versions and inspecting package manifests
title: 'Feature: Package Version History and Manifests'
labels: ['enhancement', 'packages', 'versioning']
assignees: ''
---

**Is your feature request related to a problem? Please describe.**
Users need to list historical versions and inspect manifests for Quilt packages. Currently, the MCP server lacks the ability to access package version history and detailed manifest information, which is essential for understanding package evolution and contents.

**Describe the solution you'd like**
Add two new API endpoints to the packages module:

1. `packages.package_versions_list(package_name, registry?, limit?, include_tags=false)`
   - Lists top hashes with timestamps and commit messages
   - Optional tag mapping when include_tags=true
   - Supports pagination via limit parameter

2. `packages.package_manifest(package_name, registry?, top_hash?)`
   - Returns normalized manifest for a specific version
   - Maps logical paths to physical S3 locations
   - Includes file sizes, hashes, and metadata

**Describe alternatives you've considered**
- Using existing package browsing tools with version filtering
- Implementing version history through S3 object listing
- Creating a separate versioning module

**Additional context**
This feature aligns with Quilt's versioning capabilities and provides users with essential package lifecycle information. The manifest functionality is particularly important for data lineage and reproducibility.

**Acceptance Criteria**
- [ ] Lists top hashes with timestamps and commit messages
- [ ] Optional tag mapping when requested
- [ ] Returns normalized manifest (logical->physical, sizes, hashes) for a version
- [ ] Supports pagination for large version histories
- [ ] Handles missing packages gracefully with appropriate error messages
- [ ] Includes comprehensive error handling for network and permission issues

**Implementation Notes**
- Should integrate with existing Quilt package browsing functionality
- Consider caching frequently accessed manifest data
- Ensure backward compatibility with existing package operations
