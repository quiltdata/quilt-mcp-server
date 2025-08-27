# Pull Request

## Description

Brief description of changes made in this PR.

## Type of Change

- [ ] 🐛 Bug fix (non-breaking change that fixes an issue)
- [ ] ✨ New feature (non-breaking change that adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 📚 Documentation update
- [ ] 🧪 Test improvements
- [ ] 🔧 Refactoring (no functional changes)
- [ ] ⚡ Performance improvement
- [ ] 🔒 Security improvement

## Related Issues

Fixes #(issue number)
Relates to #(issue number)

## Changes Made

### Added
- List new features or functionality added

### Changed
- List changes to existing functionality

### Fixed
- List bug fixes

### Removed
- List deprecated or removed functionality

## Testing

### Test Coverage
- [ ] Unit tests added/updated (maintain 85%+ coverage)
- [ ] Integration tests added/updated
- [ ] Real-world test scenarios added/updated
- [ ] Manual testing completed

### Test Results
```bash
# Include relevant test output
make coverage
# Coverage: 87% (target: 85%+)

make test-app
# All integration tests pass

python test_cases/sail_user_stories_real_test.py
# Real-world validation: 100% success
```

### Performance Impact
- [ ] No performance regression
- [ ] Performance improvement (include benchmarks)
- [ ] Performance impact acceptable (explain why)

## Documentation

- [ ] Code is self-documenting with clear function/class names
- [ ] Docstrings added/updated for new functions
- [ ] README.md updated (if needed)
- [ ] API documentation updated (if needed)
- [ ] User guide updated (if needed)

## Code Quality

- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] No linting errors
- [ ] No security vulnerabilities introduced

## Breaking Changes

If this PR introduces breaking changes, describe them here and provide migration instructions:

```python
# Before (old API)
result = old_function(param1, param2)

# After (new API)
result = new_function(param1, param2, new_param)
```

## Deployment Notes

Any special deployment considerations:
- [ ] No special deployment steps required
- [ ] Environment variables need to be updated
- [ ] Database migrations required
- [ ] Configuration changes required

## Screenshots (if applicable)

Include screenshots for UI changes or visual improvements.

## Checklist

- [ ] I have performed a self-review of my code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings or errors
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] Any dependent changes have been merged and published

## Additional Notes

Any additional information that reviewers should know:
- Implementation decisions and trade-offs
- Areas that need special attention during review
- Future improvements planned
- Known limitations or technical debt

---

**For Reviewers:**
- Focus on code quality, security, and maintainability
- Verify test coverage and documentation completeness
- Check for breaking changes and backward compatibility
- Validate that real-world scenarios are tested
