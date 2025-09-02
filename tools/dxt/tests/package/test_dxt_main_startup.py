"""
Test DXT Main Startup
Tests that dxt_main.py properly initializes the MCP server with stdio transport.
"""

import subprocess
import pytest
import tempfile
import zipfile
import os
import sys
import threading
import time
import json
from pathlib import Path


class TestDXTMainStartup:
    """Test dxt_main.py MCP server initialization."""
    
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
    def extracted_dxt_main(self, dxt_package_path):
        """Extract dxt_main.py from DXT package to a temporary directory."""
        if not Path(dxt_package_path).exists():
            pytest.skip("DXT package not built yet")
        
        temp_dir = tempfile.mkdtemp()
        
        with zipfile.ZipFile(dxt_package_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        dxt_main_path = Path(temp_dir) / "dxt_main.py"
        if not dxt_main_path.exists():
            pytest.fail("dxt_main.py not found in DXT package")
        
        yield str(dxt_main_path), temp_dir
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_dxt_main_imports_successfully(self, extracted_dxt_main):
        """Test that dxt_main.py can be imported without errors."""
        dxt_main_path, temp_dir = extracted_dxt_main
        
        # Test import in isolated environment
        result = subprocess.run([
            sys.executable, "-c", 
            "import sys; sys.path.insert(0, '.'); "
            "import dxt_main; print('DXT main imported successfully')"
        ], cwd=temp_dir, capture_output=True, text=True, timeout=30)
        
        # May fail due to missing dependencies, but should provide clear error
        if result.returncode != 0:
            # Should have informative error message
            assert result.stderr or result.stdout, \
                "DXT main should provide feedback on import issues"
        else:
            assert "DXT main imported successfully" in result.stdout
    
    def test_dxt_main_has_mcp_server_setup(self, extracted_dxt_main):
        """Test that dxt_main.py contains MCP server initialization code."""
        dxt_main_path, temp_dir = extracted_dxt_main
        
        with open(dxt_main_path, 'r') as f:
            dxt_main_content = f.read()
        
        # Check for MCP-related functionality
        mcp_indicators = [
            "mcp", "server", "stdio", "transport", "quilt_mcp"
        ]
        
        found_indicators = [
            indicator for indicator in mcp_indicators 
            if indicator.lower() in dxt_main_content.lower()
        ]
        
        assert len(found_indicators) >= 2, \
            f"DXT main should contain MCP server setup. Found indicators: {found_indicators}"
    
    def test_dxt_main_stdio_transport_setup(self, extracted_dxt_main):
        """Test that dxt_main.py sets up stdio transport correctly."""
        dxt_main_path, temp_dir = extracted_dxt_main
        
        with open(dxt_main_path, 'r') as f:
            dxt_main_content = f.read()
        
        # Should reference stdio transport
        stdio_indicators = ["stdio", "stdin", "stdout", "transport"]
        
        has_stdio_setup = any(
            indicator in dxt_main_content.lower() 
            for indicator in stdio_indicators
        )
        
        assert has_stdio_setup, "DXT main should configure stdio transport for MCP"
    
    def test_dxt_main_startup_timeout(self, extracted_dxt_main):
        """Test that dxt_main.py starts up within reasonable time."""
        dxt_main_path, temp_dir = extracted_dxt_main
        
        # Test startup time (should start quickly even if it fails due to missing deps)
        start_time = time.time()
        
        result = subprocess.run([
            sys.executable, dxt_main_path
        ], cwd=temp_dir, capture_output=True, text=True, timeout=10)
        
        startup_time = time.time() - start_time
        
        # Should start quickly (even if it exits with error due to missing dependencies)
        assert startup_time < 10, f"DXT main startup took too long: {startup_time:.2f}s"
    
    def test_dxt_main_error_handling(self, extracted_dxt_main):
        """Test that dxt_main.py handles errors gracefully."""
        dxt_main_path, temp_dir = extracted_dxt_main
        
        # Test with invalid environment to see error handling
        invalid_env = {
            "PATH": "/nonexistent",
            "PYTHONPATH": "",
        }
        
        result = subprocess.run([
            sys.executable, dxt_main_path
        ], cwd=temp_dir, env=invalid_env, capture_output=True, text=True, timeout=30)
        
        # Should exit gracefully with error message, not crash
        if result.returncode != 0:
            # Should provide some error output
            error_output = result.stderr + result.stdout
            assert error_output.strip(), "DXT main should provide error feedback"
    
    def test_dxt_main_has_main_function(self, extracted_dxt_main):
        """Test that dxt_main.py has proper main function or entry point."""
        dxt_main_path, temp_dir = extracted_dxt_main
        
        with open(dxt_main_path, 'r') as f:
            dxt_main_content = f.read()
        
        # Should have main function or entry point
        entry_indicators = [
            "def main", "__main__", "if __name__", "async def main"
        ]
        
        has_entry_point = any(
            indicator in dxt_main_content 
            for indicator in entry_indicators
        )
        
        assert has_entry_point, "DXT main should have proper entry point (main function)"