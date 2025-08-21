---
name: JSON Schema Metadata Validation
about: Add JSON Schema-based metadata validation to complement existing custom validators
title: 'Feature: JSON Schema Metadata Validation'
labels: ['enhancement', 'validation', 'metadata', 'json-schema']
assignees: ''
---

**Is your feature request related to a problem? Please describe.**
Quilt emphasizes JSON Schema-based metadata validation as a best practice, but the MCP server currently only has custom validators. Users need the ability to validate metadata against standard JSON Schema definitions to ensure compliance with organizational standards and data governance requirements.

**Describe the solution you'd like**
Add a new API endpoint to the validators module:

`validators.metadata_validate_jsonschema(metadata, schema_json|schema_s3_uri)`

This endpoint should:
- Accept metadata as a JSON object
- Accept schema as either inline JSON or S3 URI reference
- Validate against JSON Schema Draft-07 or later
- Return detailed validation results including errors, warnings, and paths
- Support remote schema references and $ref resolution

**Describe alternatives you've considered**
- Extending existing custom validators with schema-like rules
- Creating custom validation DSL
- Using external validation services

**Additional context**
JSON Schema validation is a standard approach that enables:
- Reusable validation rules across organizations
- Integration with existing data governance tools
- Standard compliance reporting
- Automated metadata quality checks

**Acceptance Criteria**
- [ ] Validates against Draft-07+ JSON Schema standards
- [ ] Returns comprehensive error and warning information with paths
- [ ] Supports remote schema references via S3 URIs
- [ ] Handles complex schema structures including nested objects and arrays
- [ ] Provides clear error messages for validation failures
- [ ] Supports both inline and remote schema definitions
- [ ] Includes performance optimizations for large schemas

**Implementation Notes**
- Use a robust JSON Schema library (e.g., jsonschema, fastjsonschema)
- Implement schema caching for frequently used schemas
- Consider async validation for large metadata objects
- Add schema version compatibility checking
- Ensure proper error handling for malformed schemas
- Consider implementing schema validation result caching
