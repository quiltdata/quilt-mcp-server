# Coverage Improvement Specifications (Issue #235 / #238)

This directory contains specifications for improving test coverage from 55.7% to 75%+.

## Issue Context

- **Issue #235**: Integration test coverage gap: 28.4% vs 45% threshold
- **Issue #238**: Improve test coverage from 55.7% to 75%+ through strategic testing improvements
- **Branch**: `235-integration-test-coverage-gap`

## Three-Phase Approach

### Phase 1: Low-Hanging Fruit (Expected: +10-15% coverage)
Target untested modules with quick wins.

**Specifications**:
- Not yet created

**Targets**:
1. Test or remove `visualization/` module (1,296 lines, 0% coverage)
2. Test or remove `stack_buckets.py` (95 lines, 0% coverage)

### Phase 2: Reduce Over-Mocking (Expected: +5-10% coverage)
Refactor over-mocked unit tests to proper integration tests.

**Specifications**:
- [`phase2-reduce-over-mocking.md`](phase2-reduce-over-mocking.md) - **Current document**

**Targets**:
- `test_quilt_service.py` (109 mocks) → Service integration tests
- `test_utils.py` (48 mocks) → S3 and utility integration tests
- `test_tabulator.py` (31 mocks) → Tabulator integration tests
- `test_selector_fn.py` (23 mocks) → Package selector integration tests

**Key Problems Addressed**:
- Unit tests mock everything, testing mock interactions not real logic
- High unit coverage (82.6%) but low integration coverage (21.5%) indicates mocking bypasses real code
- ~1,500 lines of code with unit-only coverage that should be integration-tested

### Phase 3: Strategic Integration Tests (Expected: +5-10% coverage)
Add integration tests for modules with high unit-only coverage.

**Specifications**:
- Not yet created

**Targets**:
- `error_recovery.py` (59.9% unit, 0.0% integration)
- `workflow_service.py` (66.5% unit, 18.1% integration)
- `governance_service.py` (59.4% unit, 12.9% integration)
- `data_visualization.py` (55.6% unit, 13.1% integration)

## Current Status

### Overall Metrics
- **Combined Coverage**: 55.7% (target: 75%+)
- **Unit Tests**: 37.2% (3,576 lines)
- **Integration Tests**: 29.0% (2,831 lines)
- **E2E Tests**: 32.0% (3,501 lines)

### Critical Findings

1. **Entire modules untested**: ~1,400 lines (31% of gap)
   - `visualization/`: 1,296 lines, 0% coverage
   - `stack_buckets.py`: 95 lines, 0% coverage

2. **Over-mocking in unit tests**: ~1,500 lines (36% of gap)
   - 109 mocks in `test_quilt_service.py`
   - Tests verify mock interactions, not real logic
   - Example: 82.6% unit coverage but only 21.5% integration coverage

3. **Siloed test coverage**: Only 18.5% overlap between test suites
   - Different test types hit completely different code paths
   - Combined coverage barely exceeds individual suite coverage

## Documents in This Directory

### Phase 2 Specifications

- **[phase2-reduce-over-mocking.md](phase2-reduce-over-mocking.md)**: Comprehensive specification for analyzing and refactoring over-mocked tests

## How to Use These Specs

### For Analysis (Current Phase)
1. Read the Phase 2 specification
2. Follow the analysis sections (1-7) to understand WHAT needs to be done
3. Document findings in the spec or create analysis documents
4. Do NOT write code yet - focus on understanding the problem

### For Implementation (Future Phase)
1. Use completed analysis to guide refactoring
2. Follow categorization (A/B/C) to determine which tests to refactor vs. keep vs. delete
3. Create integration tests based on gap analysis
4. Refactor source code based on prerequisite analysis
5. Measure actual coverage impact against projections

## Philosophy: Analysis Before Implementation

These specifications focus on **WHAT needs to be done** and **WHY**, not **HOW to do it**.

The goal is to:
- ✅ Understand the root causes of low coverage
- ✅ Identify which tests are problematic and why
- ✅ Document what real logic is being bypassed
- ✅ Project coverage impact of fixes
- ✅ Identify prerequisites for refactoring

NOT to:
- ❌ Write new test code
- ❌ Refactor existing tests
- ❌ Fix source code issues
- ❌ Achieve coverage targets

## Success Metrics

- [ ] Combined coverage reaches 75%+
- [ ] No entire modules with 0% coverage (except marked as exempt)
- [ ] Reduced mocking ratio: <0.5 mocks per test function (currently 1.4)
- [ ] Individual test suite thresholds remain low (unit 30%, integration 25%, e2e 28%)

## Related Issues

- #232: Original coverage infrastructure PR
- #235: Integration test coverage gap
- #238: Overall coverage improvement strategy
