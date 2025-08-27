# README Auto-Testing Specification

## Problem Statement

The README.md contains bash installation instructions that users follow to set up the project. Currently, there's no verification that these commands actually work, which leads to:

- **Broken user experience** when installation steps fail
- **Documentation drift** as code changes but README doesn't update
- **Manual verification burden** on maintainers

## Core Insight

**Test the ACTUAL bash code blocks in the README, not separate test code that duplicates the logic.**

The goal is NOT to build complex testing infrastructure, but to extract and validate the literal bash commands written in README.md.

## Solution Approach

### 1. Direct Code Block Testing
- **Extract bash code blocks** from README.md using regex parsing
- **Test syntax validity** using `bash -n` (parse without execute)  
- **Validate referenced files exist** (env.example, scripts/, etc.)
- **Verify expected commands are present** in installation instructions

### 2. Minimal Implementation
- **Single test file** that parses README and validates bash blocks
- **No external dependencies** beyond pytest and standard library
- **Fast execution** - syntax checking only, no server startup
- **CI integration** via existing pytest infrastructure

### 3. What NOT to Build
- ❌ Complex validation frameworks with multiple components
- ❌ Self-validating README with ✅/❌ output
- ❌ Server startup and endpoint testing in README validation
- ❌ Heavy external dependencies (markdown-pytest is Python-only)

## Technical Requirements

### Functional Requirements

**FR1: Bash Code Extraction**
- Parse README.md and extract all `bash` code blocks
- Handle multi-line bash scripts with proper regex matching
- Support standard markdown fenced code block format: ````bash ... ````

**FR2: Syntax Validation**  
- Test each extracted bash block for valid syntax using `bash -n`
- Report specific syntax errors with block numbers
- Fail fast on syntax errors to catch issues immediately

**FR3: Path Validation**
- Verify that files referenced in bash code actually exist in repository
- Check critical paths: `env.example`, `shared/test-endpoint.sh`, `Makefile`
- Ensure executable permissions on scripts

**FR4: Command Validation**
- Verify "Option B: Local Development" contains expected installation commands
- Check for presence of: `git clone`, `uv sync`, `make app`, etc.
- Validate logical command sequence makes sense

### Non-Functional Requirements

**NFR1: Simplicity**
- Single test file under 100 lines of code
- No external dependencies beyond pytest
- Clear error messages when validation fails

**NFR2: Performance** 
- Complete validation in under 5 seconds
- No actual command execution (syntax check only)
- Lightweight regex parsing

**NFR3: CI Integration**
- Integrate with existing `make test-readme` target
- Run as part of GitHub Actions workflow
- Fail CI if README bash code has issues

**NFR4: Maintainability**
- Self-documenting code with clear function names
- Easy to extend for additional validation rules
- No complex configuration or setup required

## Implementation Details

### File Structure
```
tests/
├── test_readme_bash_validation.py    # Single test file
└── conftest.py                       # Existing pytest config
```

### Core Functions
1. **`extract_bash_blocks(readme_path)`** - Parse README and return bash code blocks
2. **`validate_bash_syntax(code)`** - Check syntax with `bash -n`  
3. **`validate_file_references(code, project_root)`** - Check referenced files exist
4. **`validate_installation_commands(code)`** - Check expected commands present

### Test Structure
```python
def test_readme_bash_syntax():
    """Test all bash blocks have valid syntax"""
    
def test_readme_file_references():  
    """Test referenced files exist in repository"""
    
def test_installation_commands():
    """Test Option B contains expected commands"""
```

### Integration Points
- **Makefile**: `make test-readme` runs the validation
- **CI**: GitHub Actions includes README validation step  
- **Local development**: Developers can run `pytest tests/test_readme_bash_validation.py`

## Acceptance Criteria

1. **✅ Syntax Validation**: All bash code blocks in README have valid bash syntax
2. **✅ File References**: All referenced files (env.example, scripts) exist and are accessible
3. **✅ Installation Commands**: Option B section contains all required installation commands
4. **✅ CI Integration**: README validation runs in GitHub Actions and fails CI on errors
5. **✅ Local Testing**: Developers can run `make test-readme` locally to validate changes
6. **✅ Fast Execution**: Validation completes in under 5 seconds
7. **✅ Clear Errors**: When validation fails, error messages clearly indicate which bash block and what the issue is

## Success Metrics

- **Zero false positives**: Tests only fail when there are actual README issues
- **Complete coverage**: All bash blocks in README are validated
- **Developer adoption**: Developers use `make test-readme` before committing README changes
- **User experience**: New users can successfully follow README instructions without errors

## Future Considerations

- Could extend to validate other code blocks (Python, JSON, etc.)
- Could add optional execution testing in isolated environments
- Could integrate with documentation generation tools
- Could add spell-checking for documentation text

The key principle: **Keep it simple and test the actual README content, not duplicated logic.**