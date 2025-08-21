---
name: Package Tagging: Create, Delete, List
about: Add support for Quilt package version tagging operations
title: 'Feature: Package Tagging Operations'
labels: ['enhancement', 'packages', 'tagging']
assignees: ''
---

**Is your feature request related to a problem? Please describe.**
Quilt supports tagging package versions for easier reference and version management, but the MCP server currently lacks the ability to create, delete, and list tags. Users need these operations to maintain organized package versioning and create human-readable references to specific package versions.

**Describe the solution you'd like**
Add three new API endpoints to the packages module:

1. `packages.tags_list(package_name, registry?)`
   - Lists current tag->top_hash mapping
   - Includes audit information (who created tag, when)
   - Returns empty list for packages with no tags

2. `packages.tag_add(package_name, tag, top_hash, registry?)`
   - Creates a new tag pointing to a specific top_hash
   - Validates tag format and uniqueness
   - Returns success confirmation with tag details

3. `packages.tag_delete(package_name, tag, registry?)`
   - Removes an existing tag from a package
   - Requires appropriate permissions
   - Returns confirmation of deletion

**Describe alternatives you've considered**
- Using descriptive commit messages instead of tags
- Implementing tag-like functionality through metadata
- Creating external tag management systems

**Additional context**
Tagging is a core Quilt feature that enables semantic versioning and human-readable references. This functionality is essential for production environments where packages need stable, memorable identifiers.

**Acceptance Criteria**
- [ ] Can add/remove tags and list current tag->top_hash map
- [ ] Includes audit information for tag operations
- [ ] Validates tag format and prevents duplicate tags
- [ ] Handles permission checks appropriately
- [ ] Provides clear error messages for invalid operations
- [ ] Supports tag operations across different registries

**Implementation Notes**
- Tags should follow Quilt naming conventions
- Consider implementing tag validation rules
- Ensure tag operations are atomic and consistent
- Add appropriate logging for audit trails
- Consider rate limiting for tag creation to prevent abuse
