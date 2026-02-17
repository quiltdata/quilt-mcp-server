# Contributing to Quilt MCP Server

Thank you for your interest in contributing to the Quilt MCP Server! This guide will help you get started with
contributing code, documentation, bug reports, and feature requests.

## 🚀 Quick Start for Contributors

### 1. Development Setup

```bash
# Fork and clone the repository
git clone https://github.com/your-username/quilt-mcp-server.git
cd quilt-mcp-server

# Set up development environment
cp env.example .env
# Edit .env with your AWS credentials and Quilt settings

# Install dependencies
uv sync --group test

# Validate setup
make test
make coverage
```

### 2. Testing with Claude Desktop

To test your local changes with Claude Desktop, configure it to use your local development version:

**macOS/Linux:**
Edit `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "quilt-uvx": {
      "command": "uvx",
      "args": [
        "--from",
        "/absolute/path/to/your/quilt-mcp-server",
        "quilt-mcp"
      ]
    }
  }
}
```

**Windows:**
Edit `%APPDATA%\Claude\claude_desktop_config.json` with the same configuration.

**Activating changes:**
1. Save the configuration file
2. Quit Claude Desktop completely (Cmd+Q on macOS)
3. Restart Claude Desktop
4. Your local MCP server will initialize with your development code

**Testing workflow:**
1. Make code changes in your local repository
2. Restart Claude Desktop to pick up changes
3. Test the functionality in Claude Desktop
4. Iterate until satisfied
5. Run tests: `make test && make coverage`
6. Commit and push your changes

### 3. Branch Naming Convention

We use a structured branch naming system:

| Prefix | Purpose | Example |
|--------|---------|---------|
| `feature/` | New features | `feature/unified-search` |
| `fix/` | Bug fixes | `fix/athena-connection-timeout` |
| `docs/` | Documentation | `docs/api-reference-update` |
| `test/` | Test improvements | `test/real-world-scenarios` |
| `refactor/` | Code refactoring | `refactor/search-architecture` |
| `chore/` | Maintenance tasks | `chore/update-dependencies` |

### 4. Development Workflow

```bash
# 1. Create feature branch
git checkout -b feature/your-feature-name

# 2. Make changes
# ... edit files ...

# 3. Run tests
make coverage                    # Unit tests (must maintain 85%+ coverage)
make test               # Integration validation
python test_cases/sail_user_stories_real_test.py  # Real-world tests

# 4. Commit with descriptive message
git add .
git commit -m \"Add unified search across multiple backends

- Implement parallel search across GraphQL, Elasticsearch, and S3
- Add intelligent query parsing and result ranking
- Include comprehensive error handling and fallback mechanisms
- Add 15 new test cases covering edge cases

Fixes #123\"

# 5. Push and create PR
git push origin feature/your-feature-name
```

## 📋 Contribution Types

## Code Organization Guidelines

- Keep modules focused by responsibility; prefer extraction over adding unrelated concerns to large files.
- Prefer cohesive architecture over hard LOC thresholds; split when a module mixes concerns or has unclear boundaries.
- Avoid circular imports: move shared contracts/types into dedicated modules (`types/`, `protocols/`, shared helpers).
- For backend operations, keep orchestration in `QuiltOps` and implement backend-specific behavior in `_backend_*` primitives.
- Reuse shared helpers (`src/quilt_mcp/utils/helpers.py`, `src/quilt_mcp/backends/utils.py`) instead of duplicating registry/bucket parsing logic.

Good organization examples:
- Package CRUD APIs in `src/quilt_mcp/tools/package_crud.py`; S3 ingestion workflow in `src/quilt_mcp/tools/s3_package_ingestion.py`.
- GraphQL transport in `src/quilt_mcp/backends/platform_graphql_client.py`; operation text in `src/quilt_mcp/backends/graphql_queries.py`.

### 🐛 Bug Reports

When reporting bugs, please include:

**Required Information:**

- **Environment**: OS, Python version, MCP client (Claude Desktop, Cursor, etc.)
- **Configuration**: Relevant environment variables (redact sensitive info)
- **Steps to Reproduce**: Clear, numbered steps
- **Expected Behavior**: What should happen
- **Actual Behavior**: What actually happens
- **Error Messages**: Full error messages and stack traces
- **Minimal Example**: Smallest code example that reproduces the issue

### 🔧 Code Contributions

#### Adding New MCP Tools

When adding new tools, follow this structure:

```python
# app/quilt_mcp/tools/your_new_tool.py

from typing import Dict, Any, Optional
from ..validators import validate_required_params

async def your_new_tool(
    required_param: str,
    optional_param: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    \"\"\"
    Brief description of what this tool does.
    
    Args:
        required_param: Description of required parameter
        optional_param: Description of optional parameter
        
    Returns:
        Dict containing:
        - success: Whether operation succeeded
        - data: Tool-specific response data
        - message: Human-readable status message
        
    Raises:
        ValueError: When required parameters are invalid
        ConnectionError: When external service is unavailable
    \"\"\"
    # Validate inputs
    validate_required_params({'required_param': required_param})
    
    try:
        # Implementation here
        result = await some_async_operation(required_param)
        
        return {
            'success': True,
            'data': result,
            'message': f'Successfully processed {required_param}'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'message': f'Failed to process {required_param}: {str(e)}'
        }
```

**Tool Requirements:**

- **Async Support**: All tools must be async-compatible
- **Error Handling**: Graceful error handling with meaningful messages
- **Input Validation**: Validate all inputs using our validator functions
- **Documentation**: Comprehensive docstrings with examples
- **Testing**: Unit tests with 85%+ coverage
- **Real-World Testing**: Include in integration test scenarios

#### Testing Requirements

**Unit Tests:**

```python
# tests/test_your_new_tool.py

import pytest
from unittest.mock import AsyncMock, patch
from app.quilt_mcp.tools.your_new_tool import your_new_tool

class TestYourNewTool:
    @pytest.mark.asyncio
    async def test_successful_operation(self):
        \"\"\"Test successful tool execution\"\"\"
        result = await your_new_tool(required_param=\"test_value\")
        
        assert result['success'] is True
        assert 'data' in result
        assert result['message'].startswith('Successfully')
    
    @pytest.mark.asyncio
    async def test_invalid_input(self):
        \"\"\"Test error handling for invalid input\"\"\"
        with pytest.raises(ValueError):
            await your_new_tool(required_param=\"\")
    
    @pytest.mark.asyncio
    async def test_external_service_failure(self):
        \"\"\"Test graceful handling of external service failures\"\"\"
        with patch('app.quilt_mcp.tools.your_new_tool.some_async_operation') as mock_op:
            mock_op.side_effect = ConnectionError(\"Service unavailable\")
            
            result = await your_new_tool(required_param=\"test\")
            
            assert result['success'] is False
            assert 'Service unavailable' in result['error']
```

**Integration Tests:**

```python
# Add to test_cases/comprehensive_test_scenarios.json
{
  \"test_id\": \"your_new_tool_integration\",
  \"description\": \"Test your new tool with real data\",
  \"tool_name\": \"your_new_tool\",
  \"parameters\": {
    \"required_param\": \"real_test_value\"
  },
  \"expected_success\": true,
  \"validation_checks\": [
    \"response.success == True\",
    \"'data' in response\",
    \"len(response.data) > 0\"
  ]
}
```

### 📚 Documentation Contributions

We welcome improvements to:

- **API Documentation**: Tool descriptions and examples
- **User Guides**: Installation, configuration, and usage
- **Developer Guides**: Architecture and contribution instructions
- **Examples**: Real-world usage scenarios

**Documentation Standards:**

- Use clear, concise language
- Include code examples for all features
- Test all code examples to ensure they work
- Follow our markdown style guide
- Include screenshots for UI-related documentation

## 🧪 Testing Standards

### Coverage Requirements

- **Unit Tests**: Maintain 85%+ code coverage
- **Integration Tests**: All new tools must have integration tests
- **Real-World Tests**: Include scenarios in our real-world test suite
- **Performance Tests**: For tools that may impact performance

### Test Categories

```bash
# Unit tests (required for all contributions)
make coverage

# Integration tests (required for new tools)
make test

# Real-world scenarios (recommended for significant features)
python test_cases/sail_user_stories_real_test.py
python test_cases/ccle_computational_biology_test_runner.py

# Performance benchmarks (for performance-critical changes)
python test_cases/mcp_comprehensive_test_simulation.py
```

### Test Data

- **Use Real Data When Possible**: Our tests use actual Benchling and Quilt data
- **Mock External Services**: Mock AWS services for unit tests
- **Provide Test Fixtures**: Include sample data for complex scenarios
- **Document Test Setup**: Clear instructions for running tests

## 📝 Code Style and Standards

### Python Code Style

We follow PEP 8 with these specific guidelines:

```python
# Good: Clear function names and documentation
async def create_package_from_s3_objects(
    package_name: str,
    s3_uris: List[str],
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    \"\"\"
    Create a Quilt package from S3 objects with intelligent organization.
    
    Args:
        package_name: Name in namespace/package format
        s3_uris: List of S3 URIs to include
        metadata: Optional metadata dictionary
        
    Returns:
        Package creation result with status and details
    \"\"\"
    
# Good: Error handling with context
try:
    result = await quilt_operation()
except QuiltAPIError as e:
    logger.error(f\"Quilt API error in {operation_name}: {e}\")
    return {
        'success': False,
        'error': f\"Quilt API error: {e}\",
        'message': f\"Failed to {operation_name}. Please check your Quilt configuration.\"
    }

# Good: Input validation
if not package_name or '/' not in package_name:
    raise ValueError(\"Package name must be in 'namespace/package' format\")
```

### Commit Message Format

Use conventional commit format:

```commit
type(scope): brief description

Detailed explanation of changes, including:
- What was changed and why
- Any breaking changes
- Related issue numbers

Fixes #123
Closes #456
```

**Types:**

- `feat`: New features
- `fix`: Bug fixes  
- `docs`: Documentation changes
- `test`: Test additions/changes
- `refactor`: Code refactoring
- `chore`: Maintenance tasks

## 🔄 Pull Request Process

### PR Requirements

Before submitting a PR, ensure:

- [ ] **Tests Pass**: All tests pass with 85%+ coverage
- [ ] **Documentation Updated**: Relevant docs are updated
- [ ] **Real-World Testing**: Significant features tested with real data
- [ ] **Breaking Changes Documented**: Any breaking changes are clearly noted
- [ ] **Issue References**: PR references related issues

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing
- [ ] Unit tests pass (make coverage)
- [ ] Integration tests pass (make test)
- [ ] Real-world tests pass (if applicable)
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] No breaking changes (or clearly documented)

## Related Issues
Fixes #123
Relates to #456

## Screenshots (if applicable)
[Include screenshots for UI changes]

## Additional Notes
[Any additional information for reviewers]
```

### Review Process

1. **Automated Checks**: CI runs tests and coverage analysis
2. **Code Review**: Maintainers review code quality and design
3. **Testing**: Reviewers may test changes locally
4. **Documentation Review**: Ensure docs are accurate and complete
5. **Approval**: At least one maintainer approval required
6. **Merge**: Squash and merge to main branch

## 🏷️ Issue Labels and Project Management

### Issue Labels

| Label | Purpose |
|-------|---------|
| `bug` | Something isn't working |
| `enhancement` | New feature or request |
| `documentation` | Improvements to docs |
| `good first issue` | Good for newcomers |
| `help wanted` | Extra attention needed |
| `priority: high` | High priority issue |
| `priority: low` | Low priority issue |
| `status: blocked` | Blocked by external dependency |
| `status: in progress` | Currently being worked on |

### Milestones

We organize work into milestones:

- **v0.6.0**: Next minor release
- **v1.0.0**: Major release milestone
- **Backlog**: Future considerations

## 🤝 Community Guidelines

### Code of Conduct

- **Be Respectful**: Treat all community members with respect
- **Be Inclusive**: Welcome contributors from all backgrounds
- **Be Constructive**: Provide helpful feedback and suggestions
- **Be Patient**: Remember that everyone is learning

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General questions and community chat
- **Pull Requests**: Code review and collaboration

### Getting Help

- **Documentation**: Check [docs/](../docs/) first
- **Issues**: Search existing issues before creating new ones
- **Discussions**: Use GitHub Discussions for questions
- **Maintainers**: Tag maintainers for urgent issues

## 🎯 Contribution Ideas

Looking for ways to contribute? Here are some areas where we'd love help:

### High Priority

- **New MCP Tools**: Additional Quilt operations
- **Performance Optimization**: Faster search and data operations
- **Error Handling**: Better error messages and recovery
- **Documentation**: User guides and examples

### Medium Priority  

- **Testing**: Additional real-world test scenarios
- **Monitoring**: Observability and metrics
- **Security**: Security audits and improvements
- **Integrations**: Support for additional MCP clients

### Good First Issues

- **Documentation Fixes**: Typos and clarity improvements
- **Test Coverage**: Tests for existing functionality
- **Code Cleanup**: Refactoring and code organization
- **Examples**: Usage examples and tutorials

## 📞 Contact

- **Maintainers**: @maintainer1, @maintainer2
- **Issues**: [GitHub Issues](https://github.com/quiltdata/quilt-mcp-server/issues)
- **Discussions**: [GitHub Discussions](https://github.com/quiltdata/quilt-mcp-server/discussions)

Thank you for contributing to the Quilt MCP Server! 🙏
