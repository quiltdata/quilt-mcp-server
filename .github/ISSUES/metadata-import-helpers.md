---
name: Metadata Import Helpers (CSV/XLSX to JSON)
about: Add tools for importing tabular metadata from spreadsheets into JSON format
title: 'Feature: Metadata Import Helpers for Tabular Data'
labels: ['enhancement', 'metadata', 'import', 'spreadsheets']
assignees: ''
---

**Is your feature request related to a problem? Please describe.**
Quilt documentation describes spreadsheet-driven metadata workflows, but the MCP server lacks tools for importing tabular data from CSV/XLSX files into JSON metadata format. Users need to convert spreadsheet-based metadata into structured JSON for package creation and updates, especially when working with large datasets that have metadata stored in tabular formats.

**Describe the solution you'd like**
Add a new API endpoint to the metadata_templates module:

`metadata_templates.import_tabular_metadata(file_s3_uri|base64, mapping_spec)`

This endpoint should:
- Accept tabular data from S3 URIs or base64-encoded content
- Support CSV and XLSX file formats
- Use mapping specifications to convert rows/columns into JSON
- Generate per-object or package-level metadata based on mapping
- Handle data type conversions and validation
- Support both simple and complex mapping scenarios

**Describe alternatives you've considered**
- Manual conversion of spreadsheets to JSON
- Using external ETL tools for data transformation
- Creating custom import scripts for each use case
- Extending existing metadata template functionality

**Additional context**
Spreadsheet-based metadata is common in research and data science workflows. This feature enables:
- Bulk metadata import for large datasets
- Integration with existing data management workflows
- Standardization of metadata across teams
- Reduced manual data entry errors

**Acceptance Criteria**
- [ ] Converts tabular rows/columns into per-object or package-level JSON
- [ ] Supports CSV and XLSX file formats
- [ ] Accepts flexible mapping specifications for data transformation
- [ ] Handles data type conversions (string, number, boolean, date)
- [ ] Provides validation and error reporting for malformed data
- [ ] Supports both S3 URIs and base64-encoded file content
- [ ] Generates appropriate error messages for mapping failures
- [ ] Includes data preview and validation before import

**Implementation Notes**
- Use pandas for robust CSV/XLSX parsing
- Implement flexible mapping DSL for complex transformations
- Consider memory efficiency for large files
- Add data validation and type checking
- Support incremental imports for large datasets
- Consider implementing mapping templates for common use cases
- Ensure proper error handling for file format issues
- Add support for custom data type converters
