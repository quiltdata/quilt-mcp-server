# Issue #89: DXT Testing Strategy

## Deep Analysis: Testing Pre-bundled DXT Sources

The `ModuleNotFoundError: No module named 'quilt_mcp'` in issue #89 indicates a failure in the DXT package's module resolution or bootstrap process. To diagnose this systematically, we need multi-layered testing in isolated environments that replicate the DXT runtime conditions.

## Core Testing Challenges

### 1. **Environment Isolation**
- DXT packages run in Claude Desktop's controlled environment
- Need to replicate Python path manipulation and virtual environment creation
- Must test without pre-existing `quilt_mcp` installations that could mask bundling issues

### 2. **Bootstrap Process Verification**
- The two-stage bootstrap (`bootstrap.py` → `dxt_main.py`) creates complex dependency chains
- Virtual environment creation can fail silently in restricted environments
- Python path modifications may not work consistently across platforms

### 3. **Module Resolution Complexity**
- Bundled packages in `build/lib/` must be discoverable
- Import order matters when both bundled and system packages exist
- Platform-specific binary dependencies may fail in DXT context

## Comprehensive Testing Strategy

### **Level 1: Static Package Validation**

Test the DXT package structure without execution:

```bash
# Extract and inspect DXT contents
unzip -l quilt-mcp-0.5.9.dxt
unzip quilt-mcp-0.5.9.dxt -d test-extract/

# Verify expected structure
test -f test-extract/bootstrap.py
test -f test-extract/dxt_main.py
test -f test-extract/manifest.json
test -d test-extract/lib/
test -d test-extract/quilt_mcp/

# Check bundled dependencies
ls test-extract/lib/ | grep -E "(quilt3|fastmcp|mcp|boto3)"
```

**Purpose**: Verify package assembly before testing runtime behavior.

### **Level 2: Bootstrap Process Testing**

Test the bootstrap sequence in isolated environments:

#### **2.1 Clean Environment Bootstrap Test**

```bash
# Create completely clean test environment
docker run --rm -it -v $(pwd)/test-extract:/app python:3.13-slim bash

# Inside container - test bootstrap.py directly
cd /app
python bootstrap.py &
# Should create .venv/ and install dependencies
# Monitor for module import errors during setup
```

#### **2.2 Bootstrap Component Testing**

```python
# test_bootstrap_components.py
import tempfile
import subprocess
import sys
from pathlib import Path

def test_venv_creation():
    """Test virtual environment creation in isolation"""
    with tempfile.TemporaryDirectory() as tmpdir:
        venv_path = Path(tmpdir) / ".venv"
        result = subprocess.run([
            sys.executable, "-m", "venv", str(venv_path)
        ], capture_output=True, text=True)
        assert result.returncode == 0
        assert venv_path.exists()

def test_dependency_installation():
    """Test pip install of bundled requirements"""
    # Test with extracted DXT contents
    pass
```

### **Level 3: Module Import Resolution Testing**

Test the critical import path that's failing:

#### **3.1 Path Manipulation Verification**

```python
# test_import_resolution.py
import os
import sys
from pathlib import Path

def test_dxt_path_setup():
    """Replicate dxt_main.py path setup"""
    # Simulate the path setup from dxt_main.py:8-10
    base_dir = Path(__file__).parent / "test-extract"
    sys.path.insert(0, str(base_dir / 'lib'))
    sys.path.insert(0, str(base_dir))
    
    # Attempt the critical import
    try:
        from quilt_mcp.utils import run_server
        print("✅ Import successful")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False
```

#### **3.2 Dependency Chain Analysis**

```python
def test_dependency_chain():
    """Verify all import dependencies are satisfied"""
    import importlib.util
    
    # Test each critical module in the dependency chain
    modules_to_test = [
        'quilt_mcp',
        'quilt_mcp.utils', 
        'fastmcp',
        'mcp',
        'quilt3',
        'boto3'
    ]
    
    for module_name in modules_to_test:
        try:
            spec = importlib.util.find_spec(module_name)
            if spec is None:
                print(f"❌ Module {module_name} not found")
            else:
                print(f"✅ Module {module_name} found at {spec.origin}")
        except Exception as e:
            print(f"❌ Error checking {module_name}: {e}")
```

### **Level 4: Full Runtime Testing**

Test the complete DXT execution flow:

#### **4.1 Server Startup Testing**

```python
# test_server_startup.py
import subprocess
import time
import signal
import os

def test_dxt_server_startup():
    """Test complete server startup sequence"""
    
    # Set environment to match DXT conditions
    env = os.environ.copy()
    env.update({
        'FASTMCP_TRANSPORT': 'stdio',
        'LOG_LEVEL': 'DEBUG',
        'PYTHONNOUSERSITE': '1'
    })
    
    # Start server process
    proc = subprocess.Popen([
        'python', 'bootstrap.py'
    ], 
    cwd='test-extract',
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
    )
    
    # Give it time to start
    time.sleep(5)
    
    # Check if process is running
    if proc.poll() is None:
        print("✅ Server started successfully")
        proc.terminate()
        return True
    else:
        stdout, stderr = proc.communicate()
        print(f"❌ Server failed to start")
        print(f"STDOUT: {stdout}")
        print(f"STDERR: {stderr}")
        return False
```

#### **4.2 MCP Protocol Testing**

```python
def test_mcp_protocol():
    """Test basic MCP protocol communication"""
    import json
    
    # Send initialize request
    initialize_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"}
        }
    }
    
    # Test stdio communication with server
    # This requires more complex process management
    pass
```

### **Level 5: Environment-Specific Testing**

#### **5.1 Multi-Python Version Testing**

```yaml
# docker-compose.test.yml
version: '3.8'
services:
  python311:
    image: python:3.11-slim
    volumes:
      - ./test-extract:/app
    command: python /app/bootstrap.py
    
  python312:
    image: python:3.12-slim  
    volumes:
      - ./test-extract:/app
    command: python /app/bootstrap.py
    
  python313:
    image: python:3.13-slim
    volumes:
      - ./test-extract:/app  
    command: python /app/bootstrap.py
```

#### **5.2 Platform Testing Matrix**

| Platform | Python Version | Test Environment | Status |
|----------|----------------|------------------|--------|
| macOS | 3.11, 3.12, 3.13 | Native + Docker | |
| Linux | 3.11, 3.12, 3.13 | Docker | |  
| Windows | 3.11, 3.12, 3.13 | Docker + WSL | |

## Automated Test Implementation

### **Test Suite Structure**

```
tests/dxt/
├── test_static_validation.py    # Level 1: Package structure
├── test_bootstrap_process.py    # Level 2: Bootstrap testing  
├── test_import_resolution.py    # Level 3: Module imports
├── test_server_runtime.py       # Level 4: Full server testing
├── test_cross_platform.py       # Level 5: Platform testing
├── fixtures/
│   ├── clean_environments/      # Docker configs
│   └── sample_dxt_packages/     # Test DXT files
└── conftest.py                  # Pytest configuration
```

### **Integration with Build System**

Add to `tools/dxt/Makefile`:

```makefile
test-isolated: build
	@echo "Running isolated DXT tests..."
	@mkdir -p temp-test
	@unzip -q $(PACKAGE_NAME) -d temp-test/
	@python -m pytest tests/dxt/ -v --dxt-path=temp-test/
	@rm -rf temp-test/

test-platforms: build
	@echo "Running cross-platform DXT tests..."
	@docker-compose -f tests/dxt/docker-compose.test.yml up --abort-on-container-exit
```

## Success Criteria

### **Immediate Goals (Issue #89 Diagnosis)**
- [ ] Identify exact point of failure in bootstrap → import chain
- [ ] Reproduce the `ModuleNotFoundError` in controlled environment  
- [ ] Verify package integrity and structure
- [ ] Test import resolution in isolation

### **Long-term Quality Assurance**
- [ ] Automated testing for every DXT build
- [ ] Cross-platform compatibility validation
- [ ] Performance benchmarking for startup time
- [ ] Integration testing with actual Claude Desktop

## Implementation Priority

1. **Immediate** (Week 1): Implement Level 1-3 tests to diagnose Issue #89
2. **Short-term** (Week 2): Add Level 4 runtime testing to prevent regressions
3. **Medium-term** (Month 1): Implement comprehensive Level 5 platform testing
4. **Long-term** (Ongoing): Integrate with CI/CD for continuous validation

This testing strategy provides systematic isolation of the DXT execution environment to identify the root cause of the module import failure while establishing a framework for preventing similar issues in the future.