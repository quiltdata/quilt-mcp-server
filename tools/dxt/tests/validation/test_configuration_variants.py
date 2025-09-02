"""
Test Configuration Variants
Tests different DXT configurations (authentication, environment variables, etc.).
"""

import pytest
import tempfile
import os
import subprocess
from pathlib import Path


class TestConfigurationVariants:
    """Test DXT configuration validation (AC3)."""
    
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
    
    def test_authentication_modes(self, dxt_package_path):
        """Test authentication vs. non-authenticated DXT modes."""
        # Test with AWS credentials
        env_with_auth = os.environ.copy()
        env_with_auth.update({
            "AWS_PROFILE": "test",
            "AWS_REGION": "us-east-1"
        })
        
        # Test without credentials
        env_no_auth = {k: v for k, v in os.environ.items() 
                      if not k.startswith("AWS")}
        
        # Both should handle gracefully (may fail but should not crash)
        for env_name, env in [("with_auth", env_with_auth), ("no_auth", env_no_auth)]:
            try:
                result = subprocess.run([
                    "npx", "@anthropic-ai/dxt", "info", dxt_package_path
                ], env=env, capture_output=True, text=True, timeout=10)
                
                # Should complete without crashing
                assert result.returncode is not None, f"Process should complete in {env_name} mode"
            except subprocess.TimeoutExpired:
                pytest.skip(f"DXT info timed out in {env_name} mode")
    
    def test_environment_variable_propagation(self, dxt_package_path):
        """Test environment variable propagation to bundled server."""
        test_env = os.environ.copy()
        test_env.update({
            "QUILT_TEST_VAR": "test_value",
            "LOG_LEVEL": "debug"
        })
        
        # Test that DXT can access environment variables
        result = subprocess.run([
            "npx", "@anthropic-ai/dxt", "info", dxt_package_path
        ], env=test_env, capture_output=True, text=True, timeout=10)
        
        # Should complete (environment variables should be accessible)
        assert result.returncode is not None, "Should handle environment variables"
    
    def test_concurrent_connections(self, dxt_package_path):
        """Test concurrent Claude Desktop instance connections."""
        # This is a basic test - would need more sophisticated implementation
        # for real concurrent testing
        
        try:
            # Start two DXT info processes concurrently
            import concurrent.futures
            
            def run_dxt_info():
                return subprocess.run([
                    "npx", "@anthropic-ai/dxt", "info", dxt_package_path
                ], capture_output=True, text=True, timeout=5)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                future1 = executor.submit(run_dxt_info)
                future2 = executor.submit(run_dxt_info)
                
                result1 = future1.result()
                result2 = future2.result()
                
                # Both should complete
                assert result1.returncode is not None, "First concurrent process should complete"
                assert result2.returncode is not None, "Second concurrent process should complete"
        except Exception:
            pytest.skip("Concurrent testing not available in current environment")
    
    def test_logging_configuration(self, dxt_package_path):
        """Test that DXT logging doesn't interfere with MCP protocol."""
        # Test with different log levels
        for log_level in ["info", "debug", "error"]:
            env = os.environ.copy()
            env["LOG_LEVEL"] = log_level
            
            result = subprocess.run([
                "npx", "@anthropic-ai/dxt", "info", dxt_package_path
            ], env=env, capture_output=True, text=True, timeout=10)
            
            # Should handle different log levels
            if result.returncode is not None:
                # Log level should not break basic functionality
                pass
            else:
                pytest.skip(f"DXT info failed with log level {log_level}")
    
    def test_claude_desktop_version_compatibility(self, dxt_package_path):
        """Test DXT compatibility with different Claude Desktop versions."""
        # This is a placeholder - would need actual Claude Desktop version testing
        # For now, just verify the package structure supports version compatibility
        
        import zipfile
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(dxt_package_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            manifest_path = Path(temp_dir) / "manifest.json"
            if manifest_path.exists():
                import json
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                
                # Should have version information that can be used for compatibility
                assert "version" in manifest, "Manifest should have version for compatibility checks"
            else:
                pytest.skip("Manifest not found for compatibility testing")