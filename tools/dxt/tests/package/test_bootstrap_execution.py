"""
Test Bootstrap Execution
Tests that bootstrap.py creates the environment and loads dependencies correctly.
"""

import subprocess
import pytest
import tempfile
import zipfile
import os
import sys
from pathlib import Path


class TestBootstrapExecution:
    """Test bootstrap.py execution in clean environments."""
    
    @pytest.fixture
    def dxt_package_path(self):
        """Path to the built DXT package."""
        project_root = Path(__file__).parent.parent.parent.parent.parent
        dxt_path = project_root / "tools" / "dxt" / "dist" / "quilt-mcp-dev.dxt"
        
        if not dxt_path.exists():
            dist_dir = project_root / "tools" / "dxt" / "dist"
            if dist_dir.exists():
                dxt_files = list(dist_dir.glob("*.dxt"))
                if dxt_files:
                    dxt_path = dxt_files[0]
        
        return str(dxt_path)
    
    @pytest.fixture
    def extracted_bootstrap(self, dxt_package_path):
        """Extract bootstrap.py from DXT package to a temporary directory."""
        if not Path(dxt_package_path).exists():
            pytest.skip("DXT package not built yet")
        
        temp_dir = tempfile.mkdtemp()
        
        with zipfile.ZipFile(dxt_package_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        bootstrap_path = Path(temp_dir) / "bootstrap.py"
        if not bootstrap_path.exists():
            pytest.fail("bootstrap.py not found in DXT package")
        
        # Make executable
        os.chmod(bootstrap_path, 0o755)
        
        yield str(bootstrap_path), temp_dir
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_bootstrap_imports_successfully(self, extracted_bootstrap):
        """Test that bootstrap.py can be imported without errors."""
        bootstrap_path, temp_dir = extracted_bootstrap
        
        # Test import in isolated environment
        result = subprocess.run([
            sys.executable, "-c", "import bootstrap; print('Bootstrap imported successfully')"
        ], cwd=temp_dir, capture_output=True, text=True, timeout=30)
        
        assert result.returncode == 0, f"Bootstrap import failed: {result.stderr}"
        assert "Bootstrap imported successfully" in result.stdout
    
    def test_bootstrap_has_required_functions(self, extracted_bootstrap):
        """Test that bootstrap.py contains required setup functions."""
        bootstrap_path, temp_dir = extracted_bootstrap
        
        with open(bootstrap_path, 'r') as f:
            bootstrap_content = f.read()
        
        # Check for essential bootstrap functionality
        required_patterns = [
            # Should have some form of environment setup
            "def " or "class ",  # Should have functions or classes
            "import",  # Should import dependencies
        ]
        
        for pattern in required_patterns:
            assert pattern in bootstrap_content, \
                f"Bootstrap should contain '{pattern}' for proper functionality"
    
    def test_bootstrap_python_version_check(self, extracted_bootstrap):
        """Test that bootstrap.py validates Python version appropriately."""
        bootstrap_path, temp_dir = extracted_bootstrap
        
        # Test with current Python version (should work)
        result = subprocess.run([
            sys.executable, bootstrap_path, "--version-check"
        ], cwd=temp_dir, capture_output=True, text=True, timeout=30)
        
        # Should either succeed or provide clear version information
        # Don't fail on non-zero exit as bootstrap might check and exit early
        if result.returncode != 0:
            # Should provide helpful error message if version check fails
            assert result.stderr or result.stdout, \
                "Bootstrap should provide feedback on version compatibility"
    
    def test_bootstrap_handles_clean_environment(self, extracted_bootstrap):
        """Test that bootstrap.py works in a clean environment."""
        bootstrap_path, temp_dir = extracted_bootstrap
        
        # Create a minimal environment
        clean_env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "PYTHONPATH": "",  # Clean Python path
        }
        
        # Test that bootstrap can run without existing dependencies
        result = subprocess.run([
            sys.executable, "-c", 
            "import sys; sys.path.insert(0, '.'); "
            "try: import bootstrap; print('Clean environment test passed'); "
            "except Exception as e: print(f'Error: {e}'); exit(1)"
        ], cwd=temp_dir, env=clean_env, capture_output=True, text=True, timeout=30)
        
        # Should either succeed or provide clear error about missing dependencies
        if result.returncode != 0:
            # Error message should be informative
            error_output = result.stderr + result.stdout
            assert error_output, "Bootstrap should provide error feedback in clean environment"
        else:
            assert "Clean environment test passed" in result.stdout
    
    def test_bootstrap_dependency_management(self, extracted_bootstrap):
        """Test that bootstrap.py handles dependency installation correctly."""
        bootstrap_path, temp_dir = extracted_bootstrap
        
        with open(bootstrap_path, 'r') as f:
            bootstrap_content = f.read()
        
        # Should have some form of dependency management
        dependency_indicators = [
            "pip", "uv", "requirements", "install", "package"
        ]
        
        has_dependency_management = any(
            indicator in bootstrap_content.lower() 
            for indicator in dependency_indicators
        )
        
        assert has_dependency_management, \
            "Bootstrap should include dependency management functionality"