<!-- markdownlint-disable MD013 -->
# Story 2: Robust Environment Validation

## Story Summary

**As a** customer installing DXT  
**I want** comprehensive environment validation before installation  
**So that** I get clear guidance on fixing environment issues instead of cryptic failures

## Story Details

### Current State Analysis

**Existing Environment Validation:**

- Basic `tools/dxt/assets/check-prereqs.sh` script (4474 bytes)
- Manual execution required, not integrated into installation flow
- Limited error messaging and recovery guidance
- Focuses primarily on Python version and basic permissions

**Identified Gaps from brownfield-architecture.md:**

- Python version mismatches (user has 3.10, requires 3.11+)
- Permission issues in restricted environments  
- Network/firewall blocking pip installs
- AWS credential propagation to DXT environment
- PATH and environment variable propagation varies by OS

### Acceptance Criteria

#### AC1: Enhanced Prerequisites Check Script

- [ ] Expand `check-prereqs.sh` with comprehensive environment validation
- [ ] Check Python version accessibility via login shell (not just venv)
- [ ] Validate write permissions for virtual environment creation
- [ ] Test network connectivity for dependency installation
- [ ] Verify AWS credential availability and validity
- [ ] Provide actionable error messages with specific remediation steps

#### AC2: Automated Integration with DXT Installation

- [ ] Integrate prerequisites check into DXT installation workflow
- [ ] Run validation automatically during `bootstrap.py` execution
- [ ] Fail fast with clear error messages when environment is incompatible
- [ ] Provide option to bypass checks for advanced users (with warnings)

#### AC3: Cross-Platform Environment Compatibility

- [ ] Test and validate across macOS, Linux, and Windows environments
- [ ] Handle different shell environments (bash, zsh, fish, etc.)
- [ ] Account for different Python installation methods (homebrew, pyenv, system)
- [ ] Validate PATH and environment variable handling across platforms

#### AC4: Recovery and Fallback Strategies

- [ ] Detect common environment issues and suggest specific fixes
- [ ] Provide fallback options for restricted environments
- [ ] Create environment setup scripts for common scenarios
- [ ] Document workarounds for known customer environment patterns

### Technical Approach

#### Enhanced Prerequisites Architecture

```text
tools/dxt/assets/
├── check-prereqs.sh          # Enhanced main validation script
├── environment-setup/        # Environment-specific setup scripts
│   ├── macos-setup.sh       # macOS-specific environment setup
│   ├── linux-setup.sh       # Linux-specific environment setup  
│   └── windows-setup.ps1    # Windows PowerShell setup
├── validation/              # Modular validation components
│   ├── python-validation.sh # Python version and access validation
│   ├── permissions-check.sh # File system permission validation
│   ├── network-check.sh     # Network connectivity validation
│   └── aws-validation.sh    # AWS credential validation
└── recovery/                # Recovery and fix suggestion scripts
    ├── python-fixes.sh      # Python environment fixes
    ├── permission-fixes.sh  # Permission issue fixes
    └── network-fixes.sh     # Network connectivity fixes
```

#### Enhanced bootstrap.py Integration

```python
# Enhanced bootstrap.py workflow
def validate_environment():
    """Run comprehensive environment validation before setup"""
    prereq_script = get_prereq_script_path()
    result = run_subprocess([prereq_script, '--strict'])
    
    if result.returncode != 0:
        print("Environment validation failed:")
        print(result.stderr)
        
        # Offer recovery options
        if '--auto-fix' in sys.argv:
            attempt_environment_fixes()
        else:
            print("Run with --auto-fix to attempt automatic fixes")
            sys.exit(1)
    
    return True
```

### Implementation Details

#### Phase 1: Enhanced Prerequisites Script

1. **Expand check-prereqs.sh validation**:

   ```bash
   # Enhanced validation checks
   check_python_version_and_access() {
       # Test python3 accessible in login shell
       # Validate version 3.11+
       # Test import of critical modules
   }
   
   check_environment_permissions() {
       # Test write access for venv creation
       # Check executable permissions
       # Validate PATH access
   }
   
   check_network_connectivity() {
       # Test PyPI connectivity
       # Verify DNS resolution
       # Check for proxy configuration
   }
   
   check_aws_credentials() {
       # Validate AWS credential availability
       # Test basic AWS API access
       # Check credential format and permissions
   }
   ```

2. **Actionable error messaging**:
   - Specific error codes for different failure types
   - Clear remediation steps for each error
   - Links to documentation and troubleshooting guides

#### Phase 2: Integration with Installation Flow

1. **Bootstrap integration**:
   - Run prerequisites check before any installation steps
   - Provide clear progress indicators during validation
   - Support both interactive and automated modes

2. **Failure handling**:
   - Categorize failures as blocking vs. warning
   - Provide multiple resolution paths
   - Support graceful degradation where possible

#### Phase 3: Cross-Platform Support

1. **Platform detection and adaptation**:
   - Detect OS and shell environment
   - Adapt validation checks for platform specifics
   - Handle different Python installation patterns

2. **Environment variable handling**:
   - Test PATH propagation to DXT environment
   - Validate environment variable inheritance
   - Handle platform-specific environment setup

#### Phase 4: Recovery and Setup Automation

1. **Automated fix suggestions**:
   - Detect common issues and suggest specific commands
   - Provide copy-paste ready fix commands
   - Create setup scripts for common environments

2. **Documentation and troubleshooting**:
   - Comprehensive troubleshooting guide
   - Common environment patterns and solutions
   - Customer environment compatibility matrix

### Customer Environment Scenarios

#### Scenario 1: Corporate Restrictive Environment

- **Challenge**: Limited network access, restricted file permissions
- **Validation**: Check proxy settings, test network connectivity, validate permissions
- **Recovery**: Provide offline installation options, permission escalation guidance

#### Scenario 2: Multiple Python Versions

- **Challenge**: User has Python 3.10 system default, 3.11+ available via pyenv
- **Validation**: Find and test all available Python installations
- **Recovery**: Guide user to configure PATH or provide explicit Python path

#### Scenario 3: AWS Credential Complexity

- **Challenge**: Multiple AWS profiles, credential inheritance issues
- **Validation**: Test credential access and permissions
- **Recovery**: Guide credential configuration, test access to required services

### Dependencies

**External Dependencies:**

- Enhanced shell scripting capabilities
- Cross-platform testing environments
- AWS CLI tools for credential validation

**Internal Dependencies:**

- Existing `bootstrap.py` installation flow
- Current `check-prereqs.sh` script
- Integration with DXT build system

### Risks and Mitigations

**Risk 1: Prerequisites check becomes too strict or slow**

- **Mitigation**: Implement tiered validation (critical vs. optional checks)
- **Fallback**: Provide skip options for advanced users

**Risk 2: Cross-platform compatibility issues**

- **Mitigation**: Extensive testing across platforms, platform-specific implementations
- **Fallback**: Platform-specific validation scripts

**Risk 3: Network checks may fail in legitimate environments**

- **Mitigation**: Make network checks configurable, provide offline alternatives
- **Fallback**: Warning-only mode for network validation

### Definition of Done

- [ ] Enhanced `check-prereqs.sh` covers all critical environment validation
- [ ] Automated integration with `bootstrap.py` installation flow
- [ ] Cross-platform compatibility tested and validated
- [ ] Recovery scripts and troubleshooting documentation complete
- [ ] Customer environment scenarios tested and documented
- [ ] Backward compatibility with existing installation flow maintained

### Success Metrics

- **Environment Coverage**: >95% of customer environments pass validation
- **Error Clarity**: 100% of validation failures include actionable remediation steps
- **Installation Success**: 90% reduction in customer installation failures
- **Recovery Effectiveness**: 80% of failed environments can be automatically or easily fixed

### Integration with Story 1

This story's enhanced environment validation will be tested by Story 1's comprehensive testing framework, ensuring:

- All validation scenarios are covered by automated tests
- Environment validation failures are properly caught by the test suite
- Recovery mechanisms are validated through testing

### Integration with Story 3

This story's validation capabilities will be included in Story 3's standalone distribution:

- Prerequisites validation bundled in distribution package
- Environment setup scripts included in standalone zip
- Troubleshooting documentation included in customer package

---

**Story Type**: Enhancement  
**Epic**: DXT Reliability Enhancement  
**Estimate**: 8 story points  
**Priority**: High  
**Created**: 2025-01-02
