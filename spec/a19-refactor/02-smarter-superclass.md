# Better Solution: Template Method Pattern with Concrete Base Class

## The Core Insight

**Current Problem:** High-level business logic (validation, orchestration, transformation) is duplicated across both backend implementations because the base class is purely abstract.

**Better Solution:** Move the business logic INTO the QuiltOps base class as concrete methods, and extract only the truly backend-specific operations as abstract primitives.

## Why This Is Better Than Shared Validators

### Shared Validators Approach (Previous Proposal)

- Creates a separate utility module
- Both backends still have identical orchestration logic
- Still duplicates the workflow/algorithm in each backend
- Reduces duplication but doesn't eliminate it
- Backends still responsible for calling validators in correct order

### Template Method Pattern (This Proposal)

- Base class implements the complete workflow once
- Backends implement only primitive operations (no orchestration)
- Zero duplication of business logic
- Single source of truth for algorithms
- Impossible to have divergent behavior

## Design Pattern: Template Method

**Principle:** Abstract class defines the algorithm skeleton, concrete subclasses implement specific steps.

**Applied Here:**

- QuiltOps defines complete package creation workflow as concrete method
- Quilt3_Backend implements backend-specific primitives (call quilt3 library)
- Platform_Backend implements backend-specific primitives (execute GraphQL)
- All validation, transformation, orchestration happens once in base class

## Concrete vs Abstract Responsibility Split

### What Stays Concrete in QuiltOps Base Class

**Package Operations:**

- Full create_package_revision() workflow
- Full update_package_revision() workflow
- Full diff_packages() workflow
- Input validation for all operations
- Logical key extraction algorithms
- Catalog URL construction
- Result object creation
- Error handling and transformation

**Content Operations:**

- browse_content() orchestration
- get_content_url() orchestration
- Content transformation logic

**Session Operations:**

- get_auth_status() orchestration
- Catalog config validation
- Registry URL normalization

**Bucket Operations:**

- list_buckets() orchestration
- Bucket transformation logic

### What Becomes Abstract (Backend Primitives)

**Package Backend Primitives:**

- _backend_search_packages(query, registry) - Execute backend-specific search
- _backend_get_package(name, registry, top_hash) - Fetch package from backend
- _backend_create_empty_package() - Create package object
- _backend_add_file_to_package(package, s3_uri, logical_key) - Add file reference
- _backend_set_package_metadata(package, metadata) - Set metadata
- _backend_push_package(package, message, registry) - Push to backend
- _backend_diff_packages(pkg1, pkg2) - Backend-specific diff

**Content Backend Primitives:**

- _backend_browse_package_content(package, path) - List package contents
- _backend_get_file_url(package, path) - Generate download URL

**Session Backend Primitives:**

- _backend_get_session_info() - Backend-specific session data
- _backend_get_catalog_config(url) - Fetch catalog config
- _backend_get_graphql_endpoint() - Backend-specific GraphQL URL
- _backend_get_auth_headers() - Backend-specific auth headers

**Bucket Backend Primitives:**

- _backend_list_buckets() - Backend-specific bucket enumeration

**AWS Backend Primitives:**

- _backend_get_boto3_session() - Backend-specific AWS credentials

## Refactoring Task List

### Phase 1: Analyze Current Implementation

**Task 1.1: Document Current Workflows**

- Map out complete create_package_revision() workflow in both backends
- Map out complete update_package_revision() workflow in both backends
- Identify common steps vs backend-specific steps
- Document all validation points in current implementations

**Task 1.2: Identify Primitive Operations**

- List all quilt3 library calls in Quilt3_Backend
- List all GraphQL mutations/queries in Platform_Backend
- Identify minimum set of primitives needed
- Ensure primitives are truly atomic (no business logic)

**Task 1.3: Analyze Dependencies**

- Identify which mixins can be eliminated (logic moves to base)
- Determine if TabulatorMixin can use same pattern
- Check AdminOps for similar opportunities

### Phase 2: Design New Abstract Interface

**Task 2.1: Define Backend Primitives**

- Create list of all abstract primitive methods needed
- Define method signatures with clear contracts
- Document what each primitive should/shouldn't do
- Specify return types and error handling expectations

**Task 2.2: Design Concrete Workflows**

- Design create_package_revision() algorithm in base class
- Design update_package_revision() algorithm in base class
- Design browse_content() algorithm in base class
- Design search_packages() orchestration in base class

**Task 2.3: Plan Validation Strategy**

- All validation happens in base class concrete methods
- Define validation methods (can be private to base class)
- Define transformation utilities (private to base class)
- No validation in backend implementations

**Task 2.4: Error Handling Strategy**

- Base class handles all domain exception translation
- Primitives throw backend-specific exceptions
- Base class wraps primitive exceptions into domain exceptions
- Consistent error context across all operations

### Phase 3: Implement New QuiltOps Base Class

**Task 3.1: Add Validation Methods to Base**

- _validate_package_name(name) - Check format
- _validate_s3_uris(uris) - Check URI list
- _validate_s3_uri(uri) - Check single URI
- _validate_registry(registry) - Check registry format
- _validate_package_creation_inputs(name, uris) - Composite validation
- _validate_package_update_inputs(name, uris, registry) - Composite validation

**Task 3.2: Add Transformation Methods to Base**

- _extract_logical_key(s3_uri, auto_organize) - Path extraction
- _extract_bucket_from_registry(registry) - Bucket extraction
- _normalize_registry(bucket_or_uri) - Registry normalization
- _build_catalog_url(registry, bucket, top_hash, package_name) - URL construction

**Task 3.3: Implement Concrete create_package_revision()**

- Validate all inputs using validation methods
- Extract bucket from registry
- Create empty package via _backend_create_empty_package()
- Iterate through S3 URIs, extract logical keys, add via _backend_add_file_to_package()
- Set metadata via _backend_set_package_metadata()
- Push package via _backend_push_package()
- Build catalog URL using transformation method
- Return Package_Creation_Result
- All error handling in this method

**Task 3.4: Implement Concrete update_package_revision()**

- Validate all inputs
- Get existing package via _backend_get_package()
- Add new files via _backend_add_file_to_package()
- Merge metadata via _backend_set_package_metadata()
- Push updated package via _backend_push_package()
- Build catalog URL
- Return Package_Creation_Result

**Task 3.5: Implement Concrete browse_content()**

- Validate inputs
- Get package via _backend_get_package()
- Browse content via _backend_browse_package_content()
- Transform results to domain objects
- Return Content_Info list

**Task 3.6: Implement Concrete search_packages()**

- Validate query input
- Execute search via _backend_search_packages()
- Transform results to domain objects
- Return Package_Info list

**Task 3.7: Implement Other Concrete Methods**

- get_package_info() orchestration
- diff_packages() orchestration
- get_content_url() orchestration
- list_buckets() orchestration
- get_auth_status() orchestration

**Task 3.8: Define All Abstract Primitives**

- Add @abstractmethod decorators
- Add comprehensive docstrings with contracts
- Specify what exceptions primitives should raise
- Document threading/async requirements if any

### Phase 4: Refactor Quilt3_Backend

**Task 4.1: Remove High-Level Methods**

- Delete create_package_revision() implementation
- Delete update_package_revision() implementation
- Delete browse_content() implementation
- Delete search_packages() implementation
- Keep only primitive implementations

**Task 4.2: Implement Backend Primitives**

- Implement _backend_create_empty_package() using quilt3.Package()
- Implement _backend_add_file_to_package() using package.set()
- Implement _backend_set_package_metadata() using package.set_meta()
- Implement _backend_push_package() using package.push()
- Implement _backend_get_package() using quilt3.Package.browse()
- Implement _backend_search_packages() using Elasticsearch via quilt3
- Implement _backend_browse_package_content() using package.walk()
- Implement _backend_get_file_url() using package.get_url()

**Task 4.3: Remove Validation Logic**

- Delete _validate_package_creation_inputs()
- Delete _validate_package_update_inputs()
- Delete all input validation (now in base class)

**Task 4.4: Remove Transformation Logic**

- Delete _extract_logical_key()
- Delete _build_catalog_url()
- Delete _extract_bucket_from_registry()
- All transformation now in base class

**Task 4.5: Simplify Mixins**

- Evaluate if mixins are still needed
- Consider flattening into single implementation file
- Remove redundant base class methods

**Task 4.6: Update Error Handling**

- Primitives throw quilt3-specific exceptions
- Remove domain exception translation (base class does this)
- Keep only quilt3 library call error catching

### Phase 5: Refactor Platform_Backend

**Task 5.1: Remove High-Level Methods**

- Delete create_package_revision() implementation
- Delete update_package_revision() implementation
- Delete browse_content() implementation
- Delete search_packages() implementation

**Task 5.2: Implement Backend Primitives**

- Implement _backend_create_empty_package() as GraphQL package creation
- Implement _backend_add_file_to_package() as GraphQL add file mutation
- Implement _backend_set_package_metadata() as GraphQL metadata mutation
- Implement _backend_push_package() as GraphQL push mutation
- Implement _backend_get_package() as GraphQL package query
- Implement _backend_search_packages() as GraphQL search query
- Implement _backend_browse_package_content() as GraphQL content query
- Implement _backend_get_file_url() as GraphQL presigned URL query

**Task 5.3: Remove Validation Logic**

- Delete _validate_package_creation_inputs()
- Delete _validate_package_update_inputs()
- Delete all input validation

**Task 5.4: Remove Transformation Logic**

- Delete _extract_logical_key()
- Delete _build_catalog_url()
- Delete _extract_bucket_from_registry()

**Task 5.5: Simplify GraphQL Operations**

- Keep only GraphQL mutation/query execution
- Remove orchestration logic
- Focus on GraphQL <-> Python translation

**Task 5.6: Update Error Handling**

- Primitives throw GraphQL-specific exceptions
- Remove domain exception translation
- Keep only GraphQL error parsing

### Phase 6: Update Tests

**Task 6.1: Create Base Class Tests**

- Create tests/unit/ops/test_quilt_ops_concrete.py
- Test all concrete workflow methods with mocked primitives
- Test validation methods
- Test transformation methods
- Test error handling in workflows
- Test edge cases in orchestration logic

**Task 6.2: Update Quilt3_Backend Tests**

- Focus tests on primitive implementations only
- Remove tests for high-level workflows (now in base tests)
- Test quilt3 library integration
- Test error translation from quilt3 exceptions

**Task 6.3: Update Platform_Backend Tests**

- Focus tests on primitive implementations only
- Remove tests for high-level workflows
- Test GraphQL query/mutation execution
- Test error translation from GraphQL responses

**Task 6.4: Integration Tests**

- Verify full workflows with both backends
- Test that backends produce identical results
- Test error messages are consistent
- Verify catalog URLs are correct

### Phase 7: Update Tools Layer

**Task 7.1: Remove Utility Functions**

- Remove _normalize_registry() from packages.py
- Remove any backend-related utilities
- Clean up imports

**Task 7.2: Verify Tool Behavior**

- Tools should work identically
- No changes needed (QuiltOps interface unchanged)
- Verify authorization flow still works

### Phase 8: Documentation & Cleanup

**Task 8.1: Update Architecture Documentation**

- Document Template Method pattern usage
- Explain concrete vs abstract split
- Document primitive contracts
- Update developer guide

**Task 8.2: Add Docstrings**

- Comprehensive docstrings for all concrete methods in base
- Clear contracts for all abstract primitives
- Examples of primitive usage patterns

**Task 8.3: Code Review Checklist**

- No business logic in backend implementations
- All validation in base class
- All transformation in base class
- Primitives are truly atomic
- No duplication anywhere

### Phase 9: Verification & Testing

**Task 9.1: Unit Test Coverage**

- Base class concrete methods: 100% coverage
- Quilt3_Backend primitives: 100% coverage
- Platform_Backend primitives: 100% coverage

**Task 9.2: Integration Testing**

- Run full test suite: make test-all
- Test with MCP Inspector
- Test both backend modes
- Verify error messages

**Task 9.3: Performance Testing**

- Ensure no performance degradation
- Verify template method overhead is negligible
- Test with realistic workloads

**Task 9.4: Manual Testing**

- Package creation workflows
- Package update workflows
- Content browsing
- Search operations
- Error scenarios

## Benefits Over Shared Validators Approach

### Elimination of Duplication

- **Shared validators:** Reduces duplication, doesn't eliminate it
- **Template method:** Zero duplication, impossible to diverge

### Maintenance

- **Shared validators:** Both backends still orchestrate workflows
- **Template method:** One workflow implementation, maintained in one place

### Correctness

- **Shared validators:** Backends can still call validators wrong
- **Template method:** Workflow guaranteed identical, enforced by inheritance

### Simplicity

- **Shared validators:** Three locations (validators, quilt3, platform)
- **Template method:** Two locations (base class, backend primitives)

### Backend Implementation

- **Shared validators:** Backends still complex, full workflows
- **Template method:** Backends simple, just primitive operations

### Testing

- **Shared validators:** Test validators + both workflows
- **Template method:** Test base workflow once + primitives

## Risks & Mitigation

### Risk 1: Base Class Becomes Too Large

**Mitigation:** Keep workflows focused, extract helpers as private methods

### Risk 2: Primitives Too Granular

**Mitigation:** Find right abstraction level, allow primitives to be slightly higher-level if needed

### Risk 3: Backend-Specific Optimizations Limited

**Mitigation:** Primitives can be smart, base class just orchestrates; backends control their own optimization

### Risk 4: Breaking Changes During Refactor

**Mitigation:** Incremental approach, comprehensive test coverage, one operation at a time

## Success Criteria

1. Zero duplicated business logic between backends
2. All high-level workflows implemented exactly once (in base class)
3. Backend implementations contain only primitive operations
4. No validation logic in backend implementations
5. No transformation logic in backend implementations
6. All existing tests pass
7. Base class has 100% test coverage for concrete methods
8. Backends simple enough to understand at a glance
9. Impossible to have divergent behavior between backends
10. New backends easy to implement (just primitives)

## Impact Comparison

| Metric | Current | Shared Validators | Template Method |
|--------|---------|-------------------|-----------------|
| Duplicated workflows | 2 | 2 | 1 |
| Duplicated validation | 2 | 0 (shared) | 0 (base) |
| Duplicated transformation | 2 | 0 (shared) | 0 (base) |
| Workflow maintenance points | 2 | 2 | 1 |
| Backend complexity | High | Medium | Low |
| Lines in backends | ~1500 each | ~1200 each | ~500 each |
| Risk of divergence | High | Medium | Zero |

## Conclusion

The Template Method pattern is architecturally superior to the shared validators approach. It eliminates ALL duplication, not just validation, and makes backend implementations trivial. This is the textbook use case for this pattern: multiple implementations of the same algorithm with different low-level operations.

**Recommendation: Implement Template Method pattern by moving business logic to concrete base class methods.**
