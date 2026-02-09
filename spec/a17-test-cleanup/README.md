# A17: QuiltOps E2E Test Suite - Comprehensive Specification

**Initiative:** Test Cleanup & Quality Improvement
**Focus:** QuiltOps Abstract API End-to-End Testing
**Status:** Design Phase - Specification Complete
**Date:** 2026-02-05

---

## Overview

This specification defines a comprehensive end-to-end (e2e) test suite for the **QuiltOps abstract API**. The tests validate real-world functionality against live AWS infrastructure, ensuring both backend implementations (Quilt3_Backend and Platform_Backend) correctly honor the abstract interface contract.

### Key Objectives

1. **Complete API Coverage** - Test all 50+ QuiltOps methods
2. **Backend Agnostic** - Validate abstract interface, not implementation details
3. **Real-World Testing** - Run against live AWS (no mocks)
4. **Workflow-Focused** - Test complete user journeys, not just isolated methods
5. **Reproducible** - Deterministic test data with versioned datasets
6. **Cost-Effective** - Monthly AWS costs <$30
7. **CI/CD Integrated** - Automated nightly test runs

---

## Document Structure

This specification is divided into three comprehensive documents:

### 1. [Test Specification](01-quilt-ops-e2e-spec.md)

**Focus:** What to test and how to test it

**Contents:**
- Detailed test scenarios for all QuiltOps methods (100+ tests)
- Test organization (18 test files)
- Domain object validation patterns
- Exception handling verification
- Performance benchmarks
- Concurrency testing
- End-to-end workflows

**Key Sections:**
- API surface coverage (50+ methods)
- Test scenarios by category:
  - Authentication & Status
  - Package Discovery & Content
  - Package Creation & Updates
  - Admin Operations (User, Role, SSO)
  - Tabulator Operations
  - GraphQL & AWS Integration
  - Error Handling
  - Concurrency & Performance
  - Complete Workflows

### 2. [Infrastructure Setup](02-test-infrastructure-setup.md)

**Focus:** How to provision and configure the test environment

**Contents:**
- AWS resource provisioning (S3, IAM, Athena, Glue)
- Test data generation scripts (deterministic, versioned)
- Authentication setup (local + multiuser modes)
- CI/CD integration (GitHub Actions)
- Cost monitoring and cleanup automation

**Key Sections:**
- S3 buckets (data, scratch, packages)
- IAM roles and policies
- Athena/Glue configuration (Tabulator)
- Quilt Catalog instance setup (multiuser mode)
- Test data generation (8 datasets, 600 MB)
- Authentication automation
- CI/CD workflows
- Cost estimation ($25/month)

### 3. [Implementation Roadmap](03-implementation-roadmap.md)

**Focus:** How to implement the test suite (phased approach)

**Contents:**
- 7 implementation phases over 17 days
- Detailed task breakdowns per phase
- Dependencies and milestones
- Risk management and contingency plans
- Team responsibilities and review checkpoints
- Success metrics and validation criteria

**Key Phases:**
1. Infrastructure Setup (3 days)
2. Test Data Generation (2 days)
3. Test Framework Setup (2 days)
4. Core Test Implementation (4 days)
5. Admin & Tabulator Tests (2 days)
6. Performance, Concurrency, Workflows (2 days)
7. CI/CD Integration & Documentation (2 days)

---

## Quick Reference

### Test Suite Statistics

| Metric | Value |
|--------|-------|
| **Test Files** | 18 |
| **Total Tests** | 100+ |
| **QuiltOps Methods Covered** | 27 |
| **AdminOps Methods Covered** | 19 |
| **Tabulator Methods Covered** | 8 |
| **Domain Objects Validated** | 9 |
| **Exception Types Tested** | 5 |
| **Backends Validated** | 2 (Quilt3, Platform) |

### Test Organization

```
tests/e2e/quilt_ops/
├── test_01_authentication.py      # Auth flows (both modes)
├── test_02_package_discovery.py   # Search, list, metadata
├── test_03_package_content.py     # Browse, download URLs
├── test_04_package_creation.py    # Create packages
├── test_05_package_updates.py     # Update packages
├── test_06_package_diff.py        # Version comparison
├── test_07_catalog_config.py      # Catalog operations
├── test_08_graphql_queries.py     # GraphQL execution
├── test_09_aws_integration.py     # Boto3 clients, S3
├── test_10_admin_users.py         # User CRUD
├── test_11_admin_roles.py         # Role management
├── test_12_admin_sso.py           # SSO configuration
├── test_13_tabulator_tables.py    # Table operations
├── test_14_tabulator_queries.py   # Open query feature
├── test_15_error_handling.py      # Exception validation
├── test_16_concurrency.py         # Parallel operations
├── test_17_performance.py         # Benchmarks
└── test_18_end_to_end_workflows.py # Complete journeys
```

### Infrastructure Components

**AWS Resources:**
- 3 S3 Buckets (data, scratch, packages)
- IAM Role with granular permissions
- Athena Workgroup + Glue Data Catalog
- CloudWatch Billing Alarms
- Quilt Catalog Instance (multiuser mode)

**Test Data:**
- 8 deterministic datasets (600 MB total)
- Versioned with checksums
- Uploaded to S3 test bucket
- 9 baseline packages in registry

**Authentication:**
- Local mode: quilt3 CLI session
- Multiuser mode: JWT token + GraphQL endpoint
- Automated validation scripts

---

## Implementation Timeline

**Total Effort:** 17 days (12-16 days core + buffer)
**Target Timeline:** 4 weeks (accounting for reviews)

```
Week 1: Infrastructure & Data
Week 2: Test Framework & Core Tests
Week 3: Advanced Tests & Admin
Week 4: CI/CD & Documentation
```

### Key Milestones

| Milestone | Date | Deliverable |
|-----------|------|-------------|
| M1: Infrastructure Ready | End Week 1 | AWS resources, test data, auth |
| M2: Framework Complete | Day 7 | Pytest fixtures, markers |
| M3: Core Tests (50%) | Day 9 | Auth, discovery, content tests |
| M4: Core Tests (100%) | Day 11 | All core operations tested |
| M5: Admin/Tabulator Done | Day 13 | Admin & Tabulator tests |
| M6: Advanced Tests Done | Day 15 | Concurrency, performance, workflows |
| M7: CI/CD Integrated | Day 16 | GitHub Actions running |
| M8: Final Sign-Off | Day 17 | Documentation, ready for prod |

---

## Cost Analysis

### Monthly Recurring Costs

| Resource | Cost/Month |
|----------|-----------|
| S3 Storage | $0.04 |
| S3 Requests | $0.90 |
| Data Transfer | $0.90 |
| Athena Queries | $0.05 |
| Glue Catalog | $1.00 |
| CloudWatch Logs | $0.50 |
| **Subtotal (infrastructure)** | **~$3.39** |
| **Nightly Test Runs (30x)** | **~$15** |
| **Development Buffer** | **~$5** |
| **TOTAL** | **~$25/month** |

### Cost Optimization

- Lifecycle policies (auto-delete after 24h)
- Immutable reference data (no re-upload)
- Selective test execution
- Request batching
- 7-day log retention

---

## Key Principles

### 1. Backend Agnostic Testing

**DO:**
- Test the abstract QuiltOps interface
- Validate return types match domain objects
- Check exception types match hierarchy
- Verify behavior is consistent across backends

**DON'T:**
- Check backend implementation type
- Access private attributes or methods
- Test implementation-specific behavior
- Assume backend internals

### 2. Real AWS, No Mocks

**Rationale:**
- E2E tests must validate real-world behavior
- Mocks hide integration issues
- Real AWS tests catch permission problems
- Validates actual performance characteristics

**Trade-offs:**
- Higher cost (mitigated with cleanup)
- Slower execution (acceptable for nightly runs)
- Requires AWS credentials (documented setup)

### 3. Deterministic Test Data

**Benefits:**
- Reproducible test results
- Easy to debug failures
- Versioned for schema changes
- Validated with checksums

**Implementation:**
- Seeded random generation
- Fixed test datasets
- Immutable reference data
- Documented structure

### 4. Workflow-Focused Testing

**Approach:**
- Test complete user journeys, not just methods
- Validate multi-step operations
- Ensure state transitions work correctly
- Catch integration issues between components

**Examples:**
- Data scientist creates and shares package
- Collaborator updates shared package
- Admin onboards new user
- Analyst sets up Tabulator tables

---

## Success Criteria

### Quantitative Metrics

- ✅ **API Coverage:** 100% of QuiltOps abstract methods tested
- ✅ **Pass Rate:** 100% of tests passing on both backends
- ✅ **Flakiness:** <1% flaky test rate (3x retry validation)
- ✅ **Performance:** All benchmarks within defined thresholds
- ✅ **Cost:** Monthly AWS costs <$30
- ✅ **Execution Time:** Full suite <60 minutes

### Qualitative Metrics

- ✅ **Documentation:** New contributors can run tests without support
- ✅ **Maintainability:** Test code is readable and well-structured
- ✅ **Reliability:** Tests catch real bugs, not false positives
- ✅ **Coverage:** Tests validate real workflows, not just isolated methods

---

## Getting Started

### Prerequisites

1. **AWS Account** with permissions to provision resources
2. **AWS CLI** configured with test profile
3. **Python 3.12+** and `uv` package manager
4. **Quilt3 CLI** for local mode authentication
5. **Access to Quilt Catalog** for multiuser mode (optional)

### Quick Start

```bash
# 1. Clone repository
git clone https://github.com/quiltdata/quilt-mcp-server.git
cd quilt-mcp-server

# 2. Provision AWS infrastructure
cd infrastructure/cloudformation
aws cloudformation deploy \
  --template-file quilt-mcp-e2e-tests.yaml \
  --stack-name quilt-mcp-tests \
  --capabilities CAPABILITY_IAM

# 3. Generate test data
cd tests/e2e/fixtures
uv run python generate_test_data.py
aws s3 sync data/ s3://quilt-mcp-test-data/ --delete

# 4. Create baseline packages
uv run python create_baseline_packages.py

# 5. Configure authentication
cp .env.test.template .env.test
# Edit .env.test with your credentials
source .env.test

# 6. Validate authentication
uv run python setup_authentication.py

# 7. Run tests
cd ../quilt_ops
uv run pytest -v
```

### Documentation

- [Test Specification](01-quilt-ops-e2e-spec.md) - Detailed test scenarios
- [Infrastructure Setup](02-test-infrastructure-setup.md) - AWS provisioning guide
- [Implementation Roadmap](03-implementation-roadmap.md) - Phased implementation plan
- `tests/e2e/README.md` - Test execution guide (to be created)
- `tests/e2e/TROUBLESHOOTING.md` - Common issues (to be created)
- `tests/e2e/MAINTENANCE.md` - Maintenance checklist (to be created)

---

## Next Steps

### Immediate Actions (Week 1)

1. **Review & Approve Specification**
   - Technical review by backend team
   - Cost approval by finance/management
   - Timeline approval by project manager

2. **Assign Team Roles**
   - Lead Engineer (core implementation)
   - DevOps Engineer (infrastructure)
   - Backend Engineer (test data)
   - QA Engineer (validation)

3. **Begin Infrastructure Setup**
   - Provision AWS resources
   - Set up Athena/Glue
   - Configure Quilt Catalog (multiuser mode)
   - Create IAM roles and policies

### Follow-On Work (Weeks 2-4)

4. **Generate Test Data** (Week 2)
5. **Implement Test Framework** (Week 2)
6. **Build Core Tests** (Weeks 2-3)
7. **Build Admin/Tabulator Tests** (Week 3)
8. **Build Advanced Tests** (Week 3)
9. **Integrate CI/CD** (Week 4)
10. **Finalize Documentation** (Week 4)

---

## Related Initiatives

### Current Test Cleanup Work

- **A18: Valid JWT Tests** - JWT validation test infrastructure
- **Unit Test Improvements** - Backend-specific unit test coverage
- **Functional Test Refactoring** - Mocked integration tests

### Dependencies

- QuiltOps abstract interface (stable, no planned changes)
- Backend implementations (Quilt3_Backend, Platform_Backend)
- Domain objects (Package_Info, User, etc.)
- Test AWS account with provisioning permissions

### Downstream Impact

- **MCP Tool Tests** - Can use QuiltOps fixtures for tool testing
- **Integration Tests** - Can leverage test data and infrastructure
- **Performance Testing** - Baseline performance metrics established
- **Security Testing** - Authentication patterns validated

---

## Questions & Support

### Contacts

- **Specification Author:** [Your Name]
- **Backend Team:** [Backend Team Contact]
- **DevOps Team:** [DevOps Team Contact]
- **Project Manager:** [PM Contact]

### Review Schedule

- **Technical Review:** [Date]
- **Cost Review:** [Date]
- **Final Approval:** [Date]
- **Kickoff Meeting:** [Date]

---

## Appendices

### Appendix A: QuiltOps Method Reference

See [01-quilt-ops-e2e-spec.md § 9.1](01-quilt-ops-e2e-spec.md#91-quiltops-method-reference) for complete method list.

### Appendix B: Domain Object Schemas

See [01-quilt-ops-e2e-spec.md § 9.2](01-quilt-ops-e2e-spec.md#92-domain-object-schemas) for complete domain object definitions.

### Appendix C: Exception Hierarchy

See [01-quilt-ops-e2e-spec.md § 9.3](01-quilt-ops-e2e-spec.md#93-exception-hierarchy) for complete exception definitions.

### Appendix D: Environment Variables

See [02-test-infrastructure-setup.md § 9.4](02-test-infrastructure-setup.md#94-environment-variables-reference) for complete environment variable reference.

### Appendix E: Cost Breakdown

See [02-test-infrastructure-setup.md § 7](02-test-infrastructure-setup.md#7-cost-estimation) for detailed cost analysis.

### Appendix F: Implementation Timeline

See [03-implementation-roadmap.md § 5](03-implementation-roadmap.md#5-timeline-visualization) for visual timeline.

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-05 | [Your Name] | Initial specification |

---

**END OF SPECIFICATION**
