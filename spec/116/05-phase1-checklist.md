# Phase 1 Implementation Checklist: Utility Extraction Foundation

**Issue**: [#116 - Streamline tools directory structure](https://github.com/quiltdata/quilt-mcp-server/issues/116)  
**Phase**: 1 - Extract Composable Utilities  
**Document**: Implementation Checklist  
**Date**: 2025-01-08

## Overview

This checklist implements the IRS/DSCO methodology for Phase 1 of the tools directory streamlining initiative. The implementation follows a 5-stage approach over 10 days, extracting composable utilities from existing tools to create a foundation layer that eliminates duplication and enables consistent functionality.

**Reference Documents**:
- Requirements: [`spec/116/01-requirements.md`](./01-requirements.md)
- Technical Analysis: [`spec/116/02-analysis.md`](./02-analysis.md)
- Architecture: [`spec/116/03-specifications.md`](./03-specifications.md)
- Phase Design: [`spec/116/04-phase1-design.md`](./04-phase1-design.md)

## Success Criteria Summary

- [x] **FR-01**: AWS Operations Utilities fully implemented and tested
- [ ] **FR-02**: Package Operations Utilities fully implemented and tested
- [ ] **FR-03**: Object Operations Utilities fully implemented and tested
- [ ] **FR-04**: Data and Content Operations fully implemented and tested
- [ ] **FR-05**: Search and Query Utilities fully implemented and tested
- [x] **Significant Code Duplication Reduction**: Eliminate redundant implementations across tools (Stage 1)
- [x] **Comprehensive Test Coverage**: All utility functions covered by BDD tests (Stage 1)
- [x] **Performance Maintained**: No significant degradation in operations (Stage 1)
- [x] **Backward Compatibility**: All existing tool functionality preserved (Stage 1)

---

## Stage 1: AWS Operations Utilities (Days 1-2)

**Objective**: Extract AWS operations from existing tools into composable utilities.

### Stage 1.1: Foundation Setup

#### Infrastructure Tasks
- [x] Create directory structure `src/quilt_mcp/utilities/aws/`
- [x] Create `src/quilt_mcp/utilities/__init__.py`
- [x] Create `src/quilt_mcp/utilities/aws/__init__.py`
- [x] Setup test directory structure `tests/utilities/aws/`
- [x] Configure pytest for new module path

#### Documentation Tasks
- [x] Document AWS utilities API design
- [x] Create code examples for common usage patterns
- [x] Document dependency injection patterns

### Stage 1.2: Session Management Utilities

#### Implementation Tasks
- [x] Extract session creation logic from `tools/aws/`, `tools/dxt/`, and `aws/permission_discovery.py`
- [x] Create `src/quilt_mcp/utilities/aws/session.py`
- [x] Implement `create_session(prefer_quilt=True, profile_name=None, region=None)` function with dual credential support
- [x] Implement credential fallback logic: Quilt3 → AWS native → error with guidance
- [x] Implement `get_session_credentials(session)` function
- [x] Implement `validate_session(session)` function
- [x] Add environment variable support (`QUILT_DISABLE_QUILT3_SESSION`) for credential preference
- [x] Handle both `quilt3.get_boto3_session()` and `boto3.Session()` patterns
- [x] Add proper error handling and logging with credential-specific guidance

#### BDD Test Requirements
- [x] **Given** Quilt catalog login active, **When** creating session with prefer_quilt=True, **Then** Quilt3-backed session used
- [x] **Given** native AWS credentials configured, **When** creating session with prefer_quilt=False, **Then** standard boto3 session used
- [x] **Given** both credential types available, **When** creating session with default settings, **Then** Quilt3 session preferred
- [x] **Given** QUILT_DISABLE_QUILT3_SESSION=1 environment variable, **When** creating session, **Then** native AWS credentials used
- [x] **Given** AWS profile name provided, **When** creating session, **Then** session uses specified profile (native AWS only)
- [x] **Given** invalid Quilt3 credentials, **When** creating session, **Then** fallback to native AWS credentials attempted
- [x] **Given** no credentials configured, **When** creating session, **Then** appropriate error with setup guidance for both credential types
- [x] **Given** session timeout, **When** validating session, **Then** session refresh is handled appropriately for session type

#### Validation Tasks
- [x] Verify session creation works with both Quilt3 and native AWS credentials
- [x] Verify credential fallback logic works correctly (Quilt3 → native AWS → error)
- [x] Verify error handling provides clear guidance for both credential types
- [x] Verify environment variable control (QUILT_DISABLE_QUILT3_SESSION) works
- [x] Verify performance matches existing implementations for both session types
- [x] Verify memory usage is acceptable for both credential patterns

### Stage 1.3: S3 Operations Utilities

#### Implementation Tasks
- [x] Extract S3 operations from `tools/aws/`, `tools/dxt/`, and `tools/package_manifest/`
- [x] Create `src/quilt_mcp/utilities/aws/s3.py`
- [x] Implement `create_client(session, region=None)` function
- [x] Implement `list_objects(client, bucket, prefix="", **kwargs)` function
- [x] Implement `get_object(client, bucket, key)` function
- [x] Implement `put_object(client, bucket, key, data, **kwargs)` function
- [x] Implement `delete_object(client, bucket, key)` function
- [x] Implement `object_exists(client, bucket, key)` function
- [x] Add streaming support for large objects
- [x] Add retry logic with exponential backoff

#### BDD Test Requirements
- [x] **Given** valid S3 client, **When** listing objects with prefix, **Then** correct objects returned
- [x] **Given** existing S3 object, **When** getting object, **Then** object data retrieved correctly
- [x] **Given** object data, **When** putting object, **Then** object stored successfully in S3
- [x] **Given** existing S3 object, **When** deleting object, **Then** object removed from S3
- [x] **Given** large object (>1GB), **When** streaming object, **Then** memory usage remains constant
- [x] **Given** network failure, **When** performing S3 operation, **Then** retry with exponential backoff

#### Validation Tasks
- [x] Verify S3 operations work with real AWS S3 buckets
- [x] Verify streaming works with large objects (>1GB)
- [x] Verify retry logic handles transient failures
- [x] Verify performance matches existing implementations

### Stage 1.4: Registry Operations Utilities

#### Implementation Tasks
- [x] Extract registry operations from `tools/dxt/` and existing tools
- [x] Create `src/quilt_mcp/utilities/aws/registry.py`
- [x] Implement `get_registry_url(registry_name)` function
- [x] Implement `list_packages(s3_client, registry_url, **kwargs)` function
- [x] Implement `get_package_metadata(s3_client, registry_url, package_name)` function
- [x] Implement `validate_registry_access(s3_client, registry_url)` function
- [x] Add pagination support for large package lists

#### BDD Test Requirements
- [x] **Given** registry name, **When** getting registry URL, **Then** correct URL returned
- [x] **Given** valid registry, **When** listing packages, **Then** package list retrieved
- [x] **Given** package name, **When** getting package metadata, **Then** metadata retrieved correctly
- [x] **Given** invalid registry, **When** validating access, **Then** appropriate error raised
- [x] **Given** large registry, **When** listing packages, **Then** pagination works correctly

#### Validation Tasks
- [x] Verify registry operations work with real Quilt registries
- [x] Verify pagination handles large package lists
- [x] Verify access validation catches permission issues

### Stage 1.5: Authentication Utilities

#### Implementation Tasks
- [x] Extract authentication logic from existing tools (`auth.py`, `permission_discovery.py`)
- [x] Create `src/quilt_mcp/utilities/aws/auth.py`
- [x] Implement `get_credentials(prefer_quilt=True, profile_name=None)` function with dual credential support
- [x] Implement `validate_credentials(credentials, credential_type="auto")` function
- [x] Implement `get_caller_identity(session)` function for both session types
- [x] Implement `is_quilt_authenticated()` function to check Quilt3 login status
- [x] Implement `get_credential_type(session)` function to identify session source
- [x] Add credential caching and refresh logic for both credential types

#### BDD Test Requirements
- [x] **Given** Quilt catalog login, **When** getting credentials with prefer_quilt=True, **Then** Quilt3 credentials returned
- [x] **Given** AWS profile, **When** getting credentials with prefer_quilt=False, **Then** profile credentials returned
- [x] **Given** both credential types available, **When** getting credentials with default settings, **Then** Quilt3 credentials preferred
- [x] **Given** valid Quilt3 credentials, **When** validating, **Then** validation succeeds with Quilt3 identity
- [x] **Given** valid native AWS credentials, **When** validating, **Then** validation succeeds with native AWS identity
- [x] **Given** invalid credentials, **When** validating, **Then** validation fails with credential-type-specific error
- [x] **Given** expired Quilt3 token, **When** refreshing, **Then** appropriate re-authentication guidance provided
- [x] **Given** expired native AWS credentials, **When** refreshing, **Then** new credentials obtained via standard AWS flow

#### Validation Tasks
- [x] Verify authentication works with both Quilt3 and native AWS credential sources
- [x] Verify credential type detection accurately identifies session source
- [x] Verify credential caching improves performance for both credential types
- [x] Verify error messages are clear and actionable for both authentication methods
- [x] Verify fallback logic handles mixed authentication scenarios

### Stage 1 Quality Gates

#### Code Quality
- [x] All AWS utility modules have comprehensive test coverage
- [x] All functions have comprehensive type annotations
- [x] All functions have docstrings with examples
- [x] Linting passes without warnings
- [x] No circular dependencies between modules

#### Integration Quality
- [x] All utilities integrate with real AWS services
- [x] Performance benchmarks established and met
- [x] Memory usage profiled and acceptable
- [x] Error handling covers all edge cases

#### Architecture Quality
- [x] Dependency injection pattern consistently applied
- [x] Pure functions clearly separated from impure functions
- [x] Single responsibility principle maintained
- [x] Clear separation of concerns achieved
- [x] Dual credential pattern (Quilt3 + native AWS) properly abstracted across all utilities
- [x] Credential fallback logic consistent across all AWS operations
- [x] Session management utilities work seamlessly with both credential types

---

## Stage 2: Package Operations Utilities (Days 3-4)

**Objective**: Extract package operations from existing tools into composable utilities.

### Stage 2.1: Manifest Operations Utilities

#### Implementation Tasks
- [ ] Extract manifest operations from `tools/dxt/` and `tools/package_manifest/`
- [ ] Create `src/quilt/utilities/package/manifest.py`
- [ ] Implement `load_manifest(source)` function (supports file path or S3 object)
- [ ] Implement `save_manifest(manifest_data, destination)` function
- [ ] Implement `validate_manifest_format(manifest_data)` function
- [ ] Implement `merge_manifests(manifest_list)` function
- [ ] Implement `extract_manifest_metadata(manifest_data)` function
- [ ] Add support for both local files and S3 objects

#### BDD Test Requirements
- [ ] **Given** valid manifest file, **When** loading manifest, **Then** manifest data parsed correctly
- [ ] **Given** S3 manifest object, **When** loading manifest, **Then** manifest retrieved and parsed
- [ ] **Given** manifest data, **When** saving to file, **Then** file created with correct format
- [ ] **Given** invalid manifest format, **When** validating, **Then** validation errors returned
- [ ] **Given** multiple manifests, **When** merging, **Then** combined manifest created correctly
- [ ] **Given** large manifest (>100MB), **When** processing, **Then** memory usage remains reasonable

#### Validation Tasks
- [ ] Verify manifest operations work with real package manifests
- [ ] Verify S3 integration handles large manifests efficiently
- [ ] Verify validation catches all manifest format errors
- [ ] Verify performance with large manifest files

### Stage 2.2: Package Validation Utilities

#### Implementation Tasks
- [ ] Extract validation logic from multiple tools
- [ ] Create `src/quilt/utilities/package/validation.py`
- [ ] Implement `validate_package_structure(package_data)` function
- [ ] Implement `validate_package_integrity(package_data)` function
- [ ] Implement `validate_package_metadata(metadata)` function
- [ ] Implement `check_required_fields(package_data, requirements)` function
- [ ] Add comprehensive error reporting

#### BDD Test Requirements
- [ ] **Given** valid package structure, **When** validating, **Then** validation passes
- [ ] **Given** missing required fields, **When** validating, **Then** specific missing fields reported
- [ ] **Given** corrupted package data, **When** validating integrity, **Then** corruption detected
- [ ] **Given** invalid metadata format, **When** validating, **Then** format errors reported
- [ ] **Given** package with circular references, **When** validating, **Then** circular references detected

#### Validation Tasks
- [ ] Verify validation catches all common package errors
- [ ] Verify error messages are clear and actionable
- [ ] Verify validation performance is acceptable for large packages

### Stage 2.3: Package Metadata Utilities

#### Implementation Tasks
- [ ] Extract metadata handling from existing implementations
- [ ] Create `src/quilt/utilities/package/metadata.py`
- [ ] Implement `extract_metadata(package_data)` function
- [ ] Implement `update_metadata(package_data, new_metadata)` function
- [ ] Implement `serialize_metadata(metadata, format="json")` function
- [ ] Implement `deserialize_metadata(metadata_str, format="json")` function
- [ ] Support multiple metadata formats (JSON, YAML)

#### BDD Test Requirements
- [ ] **Given** package data, **When** extracting metadata, **Then** complete metadata returned
- [ ] **Given** new metadata, **When** updating package, **Then** metadata updated correctly
- [ ] **Given** metadata object, **When** serializing to JSON, **Then** valid JSON produced
- [ ] **Given** JSON metadata string, **When** deserializing, **Then** metadata object created
- [ ] **Given** metadata with special characters, **When** serializing, **Then** encoding handled correctly

#### Validation Tasks
- [ ] Verify metadata operations preserve all information
- [ ] Verify serialization/deserialization is lossless
- [ ] Verify performance with large metadata objects

### Stage 2.4: Package Compression Utilities

#### Implementation Tasks
- [ ] Extract compression logic from `tools/dxt/`
- [ ] Create `src/quilt/utilities/package/compression.py`
- [ ] Implement `create_dxt_package(source_dir, output_path)` function
- [ ] Implement `extract_dxt_package(dxt_path, output_dir)` function
- [ ] Implement `validate_dxt_format(dxt_path)` function
- [ ] Implement `get_dxt_metadata(dxt_path)` function
- [ ] Add progress tracking for large packages

#### BDD Test Requirements
- [ ] **Given** source directory, **When** creating DXT package, **Then** valid DXT file created
- [ ] **Given** DXT package, **When** extracting, **Then** original files restored correctly
- [ ] **Given** corrupted DXT file, **When** validating format, **Then** corruption detected
- [ ] **Given** DXT file, **When** getting metadata, **Then** package metadata returned
- [ ] **Given** large package (>1GB), **When** compressing, **Then** progress tracking works

#### Validation Tasks
- [ ] Verify DXT packages are compatible with existing tools
- [ ] Verify compression/extraction preserves file permissions and timestamps
- [ ] Verify performance with large packages

### Stage 2 Quality Gates

#### Code Quality
- [ ] All package utility modules have comprehensive test coverage
- [ ] All functions handle edge cases properly
- [ ] Error messages are clear and actionable
- [ ] Performance benchmarks established

#### Integration Quality
- [ ] Package utilities work with real Quilt packages
- [ ] S3 integration handles large packages efficiently
- [ ] DXT format compatibility maintained with existing tools

---

## Stage 3: Object Operations Utilities (Days 5-6)

**Objective**: Extract object operations into composable utilities.

### Stage 3.1: Object Metadata Utilities

#### Implementation Tasks
- [ ] Extract object metadata operations from existing tools
- [ ] Create `src/quilt/utilities/object/metadata.py`
- [ ] Implement `get_object_metadata(s3_client, bucket, key)` function
- [ ] Implement `extract_file_metadata(file_path)` function
- [ ] Implement `compare_metadata(metadata1, metadata2)` function
- [ ] Implement `validate_metadata_schema(metadata, schema)` function
- [ ] Support various metadata formats

#### BDD Test Requirements
- [ ] **Given** S3 object, **When** getting metadata, **Then** complete metadata returned
- [ ] **Given** local file, **When** extracting metadata, **Then** file metadata extracted
- [ ] **Given** two metadata objects, **When** comparing, **Then** differences identified
- [ ] **Given** metadata and schema, **When** validating, **Then** schema compliance verified
- [ ] **Given** object without metadata, **When** getting metadata, **Then** appropriate default returned

#### Validation Tasks
- [ ] Verify metadata extraction works with various object types
- [ ] Verify metadata comparison accurately identifies differences
- [ ] Verify schema validation catches all violations

### Stage 3.2: Object Retrieval Utilities

#### Implementation Tasks
- [ ] Extract object retrieval logic from existing implementations
- [ ] Create `src/quilt/utilities/object/retrieval.py`
- [ ] Implement `retrieve_object(s3_client, bucket, key, **options)` function
- [ ] Implement `retrieve_object_range(s3_client, bucket, key, start, end)` function
- [ ] Implement `stream_object(s3_client, bucket, key, chunk_size=8192)` function
- [ ] Implement `download_object(s3_client, bucket, key, local_path)` function
- [ ] Add progress tracking and cancellation support

#### BDD Test Requirements
- [ ] **Given** S3 object, **When** retrieving, **Then** object data returned correctly
- [ ] **Given** object range request, **When** retrieving range, **Then** correct range returned
- [ ] **Given** large object, **When** streaming, **Then** memory usage remains constant
- [ ] **Given** download request, **When** downloading, **Then** file saved to local path
- [ ] **Given** network interruption, **When** retrieving object, **Then** operation can be resumed

#### Validation Tasks
- [ ] Verify object retrieval works with objects of various sizes
- [ ] Verify streaming handles large objects efficiently
- [ ] Verify download progress tracking is accurate

### Stage 3.3: Object Validation Utilities

#### Implementation Tasks
- [ ] Extract object validation logic
- [ ] Create `src/quilt/utilities/object/validation.py`
- [ ] Implement `validate_object_integrity(s3_client, bucket, key)` function
- [ ] Implement `check_object_format(object_data, expected_format)` function
- [ ] Implement `validate_object_size(s3_client, bucket, key, max_size)` function
- [ ] Implement `scan_object_content(object_data, content_rules)` function
- [ ] Add checksum validation support

#### BDD Test Requirements
- [ ] **Given** S3 object with checksum, **When** validating integrity, **Then** integrity verified
- [ ] **Given** object data and format spec, **When** checking format, **Then** format compliance verified
- [ ] **Given** object size limits, **When** validating size, **Then** size compliance checked
- [ ] **Given** content scanning rules, **When** scanning object, **Then** content rules applied
- [ ] **Given** corrupted object, **When** validating integrity, **Then** corruption detected

#### Validation Tasks
- [ ] Verify object validation catches all common integrity issues
- [ ] Verify format checking works with various object types
- [ ] Verify content scanning performs efficiently

### Stage 3 Quality Gates

#### Code Quality
- [ ] All object utility modules have comprehensive test coverage
- [ ] Memory usage optimized for large objects
- [ ] Error handling comprehensive and clear
- [ ] Performance acceptable for production workloads

#### Integration Quality
- [ ] Object utilities work with real Quilt objects
- [ ] Streaming handles objects >1GB efficiently
- [ ] Validation catches real-world object issues

---

## Stage 4: Data and Content Operations (Days 7-8)

**Objective**: Extract data handling and content operations.

### Stage 4.1: Data Preview Utilities

#### Implementation Tasks
- [ ] Extract data preview functionality from existing tools
- [ ] Create `src/quilt/utilities/data/preview.py`
- [ ] Implement `generate_preview(data, format_type, **options)` function
- [ ] Implement `preview_csv(data, max_rows=100)` function
- [ ] Implement `preview_json(data, max_depth=5)` function
- [ ] Implement `preview_image(data, max_size=(800, 600))` function
- [ ] Implement `preview_parquet(data, max_rows=100)` function
- [ ] Support streaming previews for large datasets

#### BDD Test Requirements
- [ ] **Given** CSV data, **When** generating preview, **Then** formatted CSV preview returned
- [ ] **Given** JSON data, **When** generating preview, **Then** formatted JSON preview returned
- [ ] **Given** image data, **When** generating preview, **Then** resized image returned
- [ ] **Given** large dataset, **When** generating preview, **Then** preview generated without loading entire dataset
- [ ] **Given** unsupported format, **When** generating preview, **Then** appropriate error message returned

#### Validation Tasks
- [ ] Verify previews accurately represent source data
- [ ] Verify memory usage for large dataset previews
- [ ] Verify preview generation performance

### Stage 4.2: Format Handling Utilities

#### Implementation Tasks
- [ ] Extract format handling logic
- [ ] Create `src/quilt/utilities/data/formats.py`
- [ ] Implement `detect_format(data_sample)` function
- [ ] Implement `validate_format(data, format_spec)` function
- [ ] Implement `convert_format(data, from_format, to_format)` function
- [ ] Implement `get_format_info(format_type)` function
- [ ] Support extensible format registry

#### BDD Test Requirements
- [ ] **Given** data sample, **When** detecting format, **Then** correct format identified
- [ ] **Given** data and format spec, **When** validating format, **Then** format compliance verified
- [ ] **Given** data and target format, **When** converting format, **Then** data converted correctly
- [ ] **Given** format type, **When** getting format info, **Then** format information returned
- [ ] **Given** ambiguous data sample, **When** detecting format, **Then** best guess with confidence returned

#### Validation Tasks
- [ ] Verify format detection accuracy across various data types
- [ ] Verify format conversion preserves data integrity
- [ ] Verify format validation catches all violations

### Stage 4.3: Data Serialization Utilities

#### Implementation Tasks
- [ ] Extract serialization utilities from existing code
- [ ] Create `src/quilt/utilities/data/serialization.py`
- [ ] Implement `serialize_data(data, format="json", **options)` function
- [ ] Implement `deserialize_data(data_str, format="json", **options)` function
- [ ] Implement `stream_serialize(data_generator, format="json")` function
- [ ] Implement `stream_deserialize(data_stream, format="json")` function
- [ ] Support multiple serialization formats

#### BDD Test Requirements
- [ ] **Given** Python object, **When** serializing to JSON, **Then** valid JSON string produced
- [ ] **Given** JSON string, **When** deserializing, **Then** original Python object reconstructed
- [ ] **Given** data generator, **When** stream serializing, **Then** serialized data streamed
- [ ] **Given** data stream, **When** stream deserializing, **Then** objects yielded incrementally
- [ ] **Given** complex data types, **When** serializing, **Then** data types preserved correctly

#### Validation Tasks
- [ ] Verify serialization/deserialization is lossless where possible
- [ ] Verify streaming serialization handles large datasets efficiently
- [ ] Verify error handling for malformed data

### Stage 4 Quality Gates

#### Code Quality
- [ ] All data utility modules have comprehensive test coverage
- [ ] Streaming operations memory-efficient
- [ ] Format detection comprehensive and accurate
- [ ] Error messages clear and actionable

#### Integration Quality
- [ ] Data utilities work with real-world datasets
- [ ] Preview generation handles various data formats
- [ ] Format conversion maintains data quality

---

## Stage 5: Search and Query Utilities (Days 9-10)

**Objective**: Extract search and query operations.

### Stage 5.1: Registry Search Utilities

#### Implementation Tasks
- [ ] Extract registry search functionality
- [ ] Create `src/quilt/utilities/search/registry.py`
- [ ] Implement `search_packages(s3_client, registry_url, query, **options)` function
- [ ] Implement `search_by_metadata(s3_client, registry_url, metadata_filter)` function
- [ ] Implement `search_by_tags(s3_client, registry_url, tags)` function
- [ ] Implement `get_package_versions(s3_client, registry_url, package_name)` function
- [ ] Add pagination and sorting support

#### BDD Test Requirements
- [ ] **Given** registry and search query, **When** searching packages, **Then** matching packages returned
- [ ] **Given** metadata filter, **When** searching by metadata, **Then** packages with matching metadata returned
- [ ] **Given** tag list, **When** searching by tags, **Then** packages with all tags returned
- [ ] **Given** package name, **When** getting versions, **Then** all versions listed chronologically
- [ ] **Given** large result set, **When** searching, **Then** pagination works correctly

#### Validation Tasks
- [ ] Verify search accuracy with real registry data
- [ ] Verify search performance with large registries
- [ ] Verify pagination handles edge cases correctly

### Stage 5.2: Metadata Search Utilities

#### Implementation Tasks
- [ ] Extract metadata search operations
- [ ] Create `src/quilt/utilities/search/metadata.py`
- [ ] Implement `search_metadata(metadata_collection, query)` function
- [ ] Implement `filter_by_schema(metadata_collection, schema_filter)` function
- [ ] Implement `aggregate_metadata(metadata_collection, aggregation_spec)` function
- [ ] Implement `index_metadata(metadata_collection)` function for performance
- [ ] Add fuzzy search capabilities

#### BDD Test Requirements
- [ ] **Given** metadata collection and query, **When** searching, **Then** matching metadata returned
- [ ] **Given** schema filter, **When** filtering metadata, **Then** compliant metadata returned
- [ ] **Given** aggregation specification, **When** aggregating, **Then** aggregated results computed
- [ ] **Given** large metadata collection, **When** searching, **Then** search performance acceptable
- [ ] **Given** fuzzy query, **When** searching, **Then** approximate matches returned with scores

#### Validation Tasks
- [ ] Verify metadata search accuracy and relevance
- [ ] Verify aggregation calculations are correct
- [ ] Verify search performance scales with data size

### Stage 5.3: Filtering Utilities

#### Implementation Tasks
- [ ] Extract filtering utilities from various tools
- [ ] Create `src/quilt/utilities/search/filtering.py`
- [ ] Implement `apply_filters(data_collection, filter_spec)` function
- [ ] Implement `create_filter(filter_type, **parameters)` function
- [ ] Implement `combine_filters(filter_list, operator="AND")` function
- [ ] Implement `validate_filter(filter_spec)` function
- [ ] Support complex filtering expressions

#### BDD Test Requirements
- [ ] **Given** data collection and filter spec, **When** applying filters, **Then** filtered data returned
- [ ] **Given** filter parameters, **When** creating filter, **Then** valid filter object created
- [ ] **Given** multiple filters, **When** combining with AND, **Then** intersection of results returned
- [ ] **Given** multiple filters, **When** combining with OR, **Then** union of results returned
- [ ] **Given** invalid filter spec, **When** validating, **Then** validation errors returned

#### Validation Tasks
- [ ] Verify filtering accuracy with various data types
- [ ] Verify complex filter expressions work correctly
- [ ] Verify filter performance with large datasets

### Stage 5 Quality Gates

#### Code Quality
- [ ] All search utility modules have comprehensive test coverage
- [ ] Search performance optimized for large datasets
- [ ] Filter expressions handle edge cases correctly
- [ ] Pagination and sorting work reliably

#### Integration Quality
- [ ] Search utilities work with real registry data
- [ ] Metadata search handles various schema formats
- [ ] Filtering scales to production data volumes

---

## Final Phase 1 Validation

### Regression Testing
- [ ] **All existing tool functionality preserved**: Run comprehensive regression test suite
- [ ] **No breaking changes**: All existing APIs continue to work
- [ ] **Performance maintained**: No significant performance degradation in operations
- [ ] **Memory usage acceptable**: Large object operations don't exceed memory limits

### Integration Testing
- [ ] **AWS integration**: All utilities work with real AWS services
- [ ] **Package operations**: Real package files processed correctly
- [ ] **Object operations**: Large objects handled efficiently
- [ ] **Data operations**: Various data formats supported
- [ ] **Search operations**: Real registry data searchable

### Quality Assurance
- [ ] **Comprehensive Test Coverage**: All utility functions covered by BDD tests
- [ ] **Documentation Complete**: All utilities documented with examples
- [ ] **Code Quality**: Linting passes, type annotations complete
- [ ] **Architecture Compliance**: Dependency injection used consistently

### Success Metrics Validation
- [ ] **Code Duplication Reduction**: Measure and verify significant reduction achieved
- [ ] **Complexity Reduction**: Verify meaningful reduction in cyclomatic complexity
- [ ] **Performance Benchmarks**: All operations maintain acceptable performance
- [ ] **Test Coverage**: Achieve and maintain comprehensive coverage

### Acceptance Criteria Final Check

#### Functional Requirements Complete
- [ ] **FR-01**: AWS Operations Utilities ✓
- [ ] **FR-02**: Package Operations Utilities ✓  
- [ ] **FR-03**: Object Operations Utilities ✓
- [ ] **FR-04**: Data and Content Operations ✓
- [ ] **FR-05**: Search and Query Utilities ✓

#### Non-Functional Requirements Met
- [ ] **NFR-01**: Performance requirements met
- [ ] **NFR-02**: Reliability requirements met
- [ ] **NFR-03**: Maintainability requirements met
- [ ] **NFR-04**: Compatibility requirements met

#### Success Metrics Achieved
- [ ] **Quantitative Metrics**: All numerical targets met
- [ ] **Qualitative Metrics**: Developer experience improvements validated
- [ ] **Quality Gates**: All quality gates passed
- [ ] **Risk Mitigation**: All identified risks addressed

---

## Implementation Notes

### Development Workflow
1. **Follow TDD strictly**: Write failing tests before implementation code
2. **Use prefactoring**: Strengthen tests and clean existing code before adding features
3. **Commit frequently**: Each completed task should be committed
4. **Run diagnostics**: Fix all IDE diagnostics after each significant change
5. **Document learnings**: Update CLAUDE.md with useful discoveries

### Quality Standards
- Every utility function must have comprehensive type annotations
- Every utility function must have docstrings with usage examples
- All error conditions must be handled with clear, actionable error messages
- All external dependencies must be injected rather than imported globally
- Performance must be profiled and optimized for production workloads

### Testing Strategy
- Use BDD format: Given/When/Then for all test descriptions
- Test behavior, not implementation details
- Use real AWS services in integration tests where possible
- Mock external dependencies for unit tests
- Include edge cases, error conditions, and performance tests

**Phase 1 Complete**: All checklist items verified ✓  
**Ready for Phase 2**: High-level tool refactoring using new utilities