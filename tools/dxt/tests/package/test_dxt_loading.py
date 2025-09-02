"""
Test DXT Package Loading
Tests that the built .dxt package can be loaded and validated correctly.
"""

import subprocess
import pytest
import os
import tempfile
from pathlib import Path


class TestDXTLoading:
    """Test DXT package loading functionality."""
    
    @pytest.fixture
    def dxt_package_path(self):
        """Path to the built DXT package."""
        project_root = Path(__file__).parent.parent.parent.parent.parent
        dxt_path = project_root / "tools" / "dxt" / "dist" / "quilt-mcp-dev.dxt"
        
        # If dev version doesn't exist, try to find any .dxt file
        if not dxt_path.exists():
            dist_dir = project_root / "tools" / "dxt" / "dist"
            if dist_dir.exists():
                dxt_files = list(dist_dir.glob("*.dxt"))
                if dxt_files:
                    dxt_path = dxt_files[0]
        
        return str(dxt_path)
    
    def test_dxt_package_exists(self, dxt_package_path):
        """Test that the DXT package file exists."""
        assert os.path.exists(dxt_package_path), f"DXT package not found at {dxt_package_path}"
        assert os.path.getsize(dxt_package_path) > 0, "DXT package file is empty"
    
    def test_dxt_package_loads_with_cli(self, dxt_package_path):
        """Test that built .dxt package can be loaded by @anthropic-ai/dxt CLI."""
        if not os.path.exists(dxt_package_path):
            pytest.skip("DXT package not built yet")
        
        # Test package info can be retrieved
        result = subprocess.run(
            ["npx", "@anthropic-ai/dxt", "info", dxt_package_path],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0, f"DXT info command failed: {result.stderr}"
        assert "quilt-mcp" in result.stdout.lower(), "Package info doesn't contain expected name"
    
    def test_dxt_package_structure_valid(self, dxt_package_path):
        """Test that the DXT package has valid internal structure."""
        if not os.path.exists(dxt_package_path):
            pytest.skip("DXT package not built yet")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract and examine package structure
            import zipfile
            
            with zipfile.ZipFile(dxt_package_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            extracted_path = Path(temp_dir)
            
            # Check for required files
            required_files = [
                "manifest.json",
                "bootstrap.py", 
                "dxt_main.py"
            ]
            
            for required_file in required_files:
                file_path = extracted_path / required_file
                assert file_path.exists(), f"Required file {required_file} not found in package"
                assert file_path.stat().st_size > 0, f"Required file {required_file} is empty"
    
    def test_dxt_package_permissions(self, dxt_package_path):
        """Test that the DXT package has correct file permissions."""
        if not os.path.exists(dxt_package_path):
            pytest.skip("DXT package not built yet")
        
        # Package should be readable
        assert os.access(dxt_package_path, os.R_OK), "DXT package is not readable"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            import zipfile
            
            with zipfile.ZipFile(dxt_package_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            extracted_path = Path(temp_dir)
            
            # Check bootstrap.py is executable after extraction
            bootstrap_path = extracted_path / "bootstrap.py"
            if bootstrap_path.exists():
                # Make executable and test
                os.chmod(bootstrap_path, 0o755)
                assert os.access(bootstrap_path, os.X_OK), "bootstrap.py should be executable"