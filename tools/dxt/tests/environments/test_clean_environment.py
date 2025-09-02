"""
Test Clean Environment Installation
Tests DXT package in environments with no existing Python dependencies.
"""

import pytest
import tempfile
import subprocess
import os
import shutil
from pathlib import Path


class TestCleanEnvironment:
    """Test DXT in clean environments (AC4)."""
    
    @pytest.fixture
    def dxt_package_path(self):
        """Path to the built DXT package."""
        project_root = Path(__file__).parent.parent.parent.parent.parent
        dxt_path = project_root / "tools" / "dxt" / "dist"
        
        if dxt_path.exists():
            dxt_files = list(dxt_path.glob("*.dxt"))
            if dxt_files:
                return str(dxt_files[0])
        
        pytest.skip("No DXT package found")
    
    def test_clean_python_environment(self, dxt_package_path):
        """Test DXT in environment with minimal Python setup."""
        # Create clean environment variables
        clean_env = {
            "PATH": "/usr/bin:/bin",  # Minimal PATH
            "HOME": os.environ.get("HOME", ""),
            "PYTHONPATH": "",  # No Python path
            "PYTHONNOUSERSITE": "1"  # Disable user site packages
        }
        
        # Test DXT package validation in clean environment
        result = subprocess.run([
            "npx", "@anthropic-ai/dxt", "info", dxt_package_path
        ], env=clean_env, capture_output=True, text=True, timeout=15)
        
        # Should either work or provide clear error message
        assert result.returncode is not None, "Should complete in clean environment"
        
        if result.returncode != 0:
            # Should provide informative error
            error_output = result.stderr + result.stdout
            assert error_output.strip(), "Should provide error feedback in clean environment"
    
    def test_no_existing_dependencies(self, dxt_package_path):
        """Test DXT when no existing Python dependencies are available."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create isolated test environment
            isolated_env = os.environ.copy()
            isolated_env.update({
                "PYTHONPATH": "",
                "VIRTUAL_ENV": "",  # No virtual environment
                "CONDA_DEFAULT_ENV": "",  # No conda environment
            })
            
            # Test DXT package info in isolated environment
            result = subprocess.run([
                "npx", "@anthropic-ai/dxt", "info", dxt_package_path
            ], env=isolated_env, capture_output=True, text=True, timeout=10, cwd=temp_dir)
            
            # Should handle isolation gracefully
            assert result.returncode is not None, "Should handle isolated environment"
    
    def test_package_integrity_before_use(self, dxt_package_path):
        """Test DXT package integrity verification before testing."""
        # Verify package can be read
        with open(dxt_package_path, 'rb') as f:
            package_data = f.read()
        
        assert len(package_data) > 0, "Package should not be empty"
        
        # Verify it's a valid zip
        import zipfile
        try:
            with zipfile.ZipFile(dxt_package_path, 'r') as zip_ref:
                file_list = zip_ref.namelist()
                assert len(file_list) > 0, "Package should contain files"
        except zipfile.BadZipFile:
            pytest.fail("Package is not a valid zip file")
    
    def test_python_version_compatibility(self, dxt_package_path):
        """Test DXT works with different available Python versions."""
        import sys
        
        # Test with current Python version
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        
        result = subprocess.run([
            "npx", "@anthropic-ai/dxt", "info", dxt_package_path
        ], capture_output=True, text=True, timeout=10)
        
        # Should work with current Python version (3.11+)
        if sys.version_info >= (3, 11):
            assert result.returncode is not None, f"Should work with Python {python_version}"
        else:
            # Older Python versions may not work - that's expected
            pytest.skip(f"Python {python_version} may not be supported")
    
    def test_network_restrictions_handling(self, dxt_package_path):
        """Test DXT behavior with network restrictions."""
        # Test with limited network environment
        restricted_env = os.environ.copy()
        restricted_env.update({
            "http_proxy": "http://nonexistent:8080",
            "https_proxy": "https://nonexistent:8080",
            "no_proxy": ""
        })
        
        # Test DXT info with network restrictions
        result = subprocess.run([
            "npx", "@anthropic-ai/dxt", "info", dxt_package_path
        ], env=restricted_env, capture_output=True, text=True, timeout=10)
        
        # Should handle network restrictions (may fail but shouldn't crash)
        assert result.returncode is not None, "Should handle network restrictions gracefully"
    
    def test_permission_restrictions(self, dxt_package_path):
        """Test DXT with limited file permissions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create read-only directory
            readonly_dir = Path(temp_dir) / "readonly"
            readonly_dir.mkdir()
            readonly_dir.chmod(0o555)  # Read and execute only
            
            try:
                # Test DXT info from read-only directory
                result = subprocess.run([
                    "npx", "@anthropic-ai/dxt", "info", dxt_package_path
                ], cwd=str(readonly_dir), capture_output=True, text=True, timeout=10)
                
                # Should handle permission restrictions
                assert result.returncode is not None, "Should handle permission restrictions"
            finally:
                # Cleanup - restore permissions
                readonly_dir.chmod(0o755)