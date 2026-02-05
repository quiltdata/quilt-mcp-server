# Test Suite Improvement Plan

**Status:** Proposal
**Date:** 2026-02-04
**Related:** [01-testing-issues.md](01-testing-issues.md), [02-testing-refactor.md](02-testing-refactor.md), [a16 Multiuser Test Reuse](../a16-multiuser/05-multiuser-test-reuse.md)
**Goal:** Improve test quality, maintainability, and coverage from 55.7% to 75%

---

## Executive Summary

The test suite is comprehensive (1,181 tests, 30K lines) but suffers from excessive mocking, fixture complexity, and
organizational ambiguity. This creates maintenance burden and false confidence. This plan delivers three strategic
initiatives over 8 weeks to achieve 75% coverage, <0.5 mock density, and 20-30% faster execution.

**Note:** Some improvements are already implemented (backend_mode fixture, JWT generation, platform skip logic).
This plan completes the migration and addresses remaining issues.

---

## Core Problems

### 1. Test Structure Ambiguity

**Problem:** Unclear boundaries between test types. "Integration" tests are ambiguous (multi-module? real AWS? both?), and E2E tests are faster than integration tests (contradiction).

**Impact:** Developers unsure where to add tests, duplicated effort, tests may not run in appropriate CI stages.

### 2. Excessive Mocking

**Problem:** 1,889 lines of mock/patch usage. Tests verify mocks were called, not that real code works correctly.

**Impact:** False confidence, tests pass while production code fails, refactoring is risky.

### 3. Fixture Complexity

**Problem:** Autouse fixtures run for every test, session-scoped state creates interdependencies, 40-line pytest_configure with global side effects.

**Impact:** Hidden dependencies, slow startup, hard to debug, tests can't run in isolation.

### 4. Backend Mode Duplication

**Problem:** Tests parametrized with backend_mode run twice (quilt3 + platform), but 76 tests skip when platform disabled.

**Impact:** Nearly 2x test time, confusion about which mode is being tested.

---

## Strategic Design Decisions

### Decision 1: Test Categorization by Directory + Minimal Markers

**Approach:** Use directory structure for test types, markers only for CI control.

**Directory structure:**

```
tests/
├── unit/          # Single module, no network, all mocks
├── func/          # Multi-module, no network, functional logic (renamed from integration/)
├── e2e/           # Real AWS/network, no mocks, full workflows
└── fixtures/      # Shared test data and helpers
```

**Pytest markers (only 2):**

- `@pytest.mark.platform` - Requires platform authentication
- `@pytest.mark.slow` - Tests taking >1 second

**Rationale:** Simplicity. Test type determined by location, not by remembering which marker to use. Markers only for CI filtering.

---

### Decision 2: Eliminate mock-centric tests, refactor code instead

**Approach:** Don't replace mocks with fakes. Refactor code to be testable without mocks.

- Eliminate tests that only verify mock interactions
- Extract business logic from I/O operations
- Test business logic directly without mocks
- Keep minimal mocks only for external services (AWS SDK calls)

---

### Decision 3: Fixture Simplification

**Approach:** Remove autouse fixtures, minimize pytest_configure, make fixtures opt-in.

**Current State:**

- ❌ `reset_runtime_auth_state` autouse fixture exists ([conftest.py:199-234](../tests/conftest.py#L199-L234)) - runs for EVERY test
- ❌ `cached_athena_service_constructor` session autouse fixture exists ([conftest.py:314-339](../tests/conftest.py#L314-L339))
- ❌ `pytest_configure` has 40+ lines of global config ([conftest.py:158-197](../tests/conftest.py#L158-L197))
- ✅ `backend_mode` fixture is parametrized, not autouse (good pattern)

**Changes needed:**

- Remove autouse from `reset_runtime_auth_state`, make it opt-in as `clean_auth` fixture
- Consider keeping or simplifying Athena caching (performance optimization)
- Move pytest_configure configuration to explicit fixtures

**Rationale:** Explicit is better than implicit. Tests declare exactly what they need.

---

---

## Implementation Phases

### Phase 1: Foundation + Speed (Weeks 1-2)

Set up structure and accelerate test suite for faster iteration.

**Tasks:**

1. Migrate existing pytest markers to only 'platform' and 'slow'
2. Update CI to use directories + markers
3. Remove autouse from reset_runtime_auth_state → make opt-in clean_auth fixture
4. Simplify pytest_configure → move config to opt-in fixtures
5. Document structure in TESTING.md

**Success:** All tests pass, 20-30% faster, new structure documented.

---

### Phase 2: Quick Wins (Weeks 3-4)

Target: Coverage 65-70% (from 55.7%)

**Tasks:**

1. Audit visualization module (1,296 lines, 0% coverage) - test or exempt
2. Remove dead code (95+ lines, 0% coverage)
3. Fix failing tests - add skip conditions
4. Split large test files (target <500 lines)

**Success:** All tests green, coverage 65-70%.

---

### Phase 3: Reduce Over-Mocking (Weeks 5-6)

Target: Coverage 70-75%, mock density <0.5

**Tasks:**

1. Eliminate mock-verification tests (tests that only check mocks were called)
2. Refactor code to separate business logic from I/O:
   - test_quilt_service.py (109 mocks) → extract logic, test directly
   - test_utils.py (48 mocks) → separate pure functions from I/O
   - test_tabulator.py (31 mocks) → extract data processing logic
3. Migrate multi-module tests from unit/ to func/

**Success:** Coverage 70-75%, 60% fewer mocks.

---

### Phase 4: Strategic Integration (Weeks 7-8)

Target: Coverage 75%+, both backends tested

**Tasks:**

1. Create explicit quilt3_backend and platform_backend fixtures
2. Expand backend_mode parametrization to remaining integration tests
3. Add E2E error recovery tests (S3 throttling, network timeout, auth failure)
4. Add cross-service functional tests (workflows, governance)
5. Enable PLATFORM_TEST_ENABLED in CI

**Success:** Coverage 75%+, both backends tested.

---

## Anti-Patterns

### Don't Mock What You're Testing

- ❌ Mock all methods, verify mocks called
- ✅ Extract business logic, test directly without mocks

### Don't Over-Parametrize

- ❌ backend × mode × region = 8 runs
- ✅ Test common case + critical edge cases

### Don't Test Implementation Details

- ❌ Assert cache state, request counts
- ✅ Assert observable behavior

### Don't Create Test Dependencies

- ❌ test_b assumes test_a ran
- ✅ Each test creates/cleans own resources

### Don't Write Mega-Fixtures

- ❌ 200-line fixture with 50 keys
- ✅ Small composable fixtures

---

## Success Metrics

**Coverage:**

- Combined: 75%+ (from 55.7%)
- Per-file minimum: 50%+
- No 0% modules (except exempted)

**Quality:**

- Mock density: <0.5 per test (from 1.4)
- All tests: passing or properly skipped
- Execution time: <120s unit+func (from 171s)
- Max file size: <500 lines (from 997)

**Developer Experience:**

- Clear unit/func/e2e boundaries
- `make test` completes in <30s
- Single test runs without complex setup
- docs/TESTING.md answers common questions

---

## Risk Mitigation

**Breaking tests:** Refactor incrementally, run full suite after each change, use feature branches.

**Slower suite:** Mark slow tests, run in CI only, parallelize where possible.

**Coverage stalls:** Track after each phase, adjust strategy if missing targets.

**Team resistance:** Document clearly, provide examples, enforce in code review.

---

## Rollout Timeline

**Weeks 1-2:** Foundation + Speed - structure setup, fixture refactoring, 20-30% faster
**Weeks 3-4:** Quick wins - dead code removal, coverage 65-70%
**Weeks 5-6:** Code refactoring - eliminate mock-centric tests, extract business logic, coverage 70-75%
**Weeks 7-8:** Integration - backend fixtures, E2E tests, backend parametrization, coverage 75%+

---

## Implementation Guidance

**Fixture Refactoring (Early):** Do this first to accelerate all subsequent work. Remove one autouse at a time, update
tests, verify, commit.

**Code Refactoring:** Extract business logic from I/O operations. Test logic directly without mocks.

**Directory Migration:** Start with clear cases (S3 → e2e/, pure functions → unit/), defer ambiguous.

**Backend Parametrization:** Start with obviously agnostic tests (packages, buckets), expand gradually.

**Coverage Tracking:** Check after each phase, adjust strategy if off-track.

---

## Out of Scope

- Performance optimization (except as side effect)
- New test frameworks (keep pytest)
- 100% coverage (target is 75%)
- Rewriting working, non-problematic tests

---

## Implementation Status

**Done:**

- ✅ backend_mode fixture ([conftest.py:237-273](../tests/conftest.py#L237-L273))
- ✅ JWT generation ([conftest.py:53-67](../tests/conftest.py#L53-67))
- ✅ Platform test skip logic (PLATFORM_TEST_ENABLED)
- ✅ 6/~20 integration tests parametrized
- ✅ Test bucket fixtures, cached Athena service

**Todo:**

- 🔲 Create func/ directory
- 🔲 Expand backend_mode to remaining tests
- 🔲 Remove autouse from reset_runtime_auth_state
- 🔲 Simplify pytest_configure
- 🔲 Eliminate mock-verification tests
- 🔲 Refactor code to separate business logic from I/O
- 🔲 Migrate high-mock tests to func/
- 🔲 Enable PLATFORM_TEST_ENABLED in CI

---

## Approval

Ready when:

1. ✅ Team agrees on directory structure
2. ✅ Team commits to fixture simplification
3. ✅ CI updated for new markers
4. ✅ TESTING.md drafted

---

**Effort:** 8 weeks (1 developer)
**Outcome:** 75%+ coverage, <0.5 mock density, 20-30% faster, clear organization
