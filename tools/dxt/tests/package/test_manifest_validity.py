"""
Test DXT Manifest Validation
Tests that the bundled manifest.json is valid and properly configured.
"""

import json
import pytest
import tempfile
import zipfile
from pathlib import Path


class TestManifestValidity:
    """Test DXT manifest.json validation."""
    
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
    def extracted_manifest(self, dxt_package_path):
        """Extract and return the manifest.json from the DXT package."""
        if not Path(dxt_package_path).exists():
            pytest.skip("DXT package not built yet")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(dxt_package_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            manifest_path = Path(temp_dir) / "manifest.json"
            if not manifest_path.exists():
                pytest.fail("manifest.json not found in DXT package")
            
            with open(manifest_path, 'r') as f:
                return json.load(f)
    
    def test_manifest_json_structure(self, extracted_manifest):
        """Test that manifest.json has the required structure."""
        required_fields = ["name", "version", "description"]
        
        for field in required_fields:
            assert field in extracted_manifest, f"Required field '{field}' missing from manifest"
            assert extracted_manifest[field], f"Field '{field}' is empty"
    
    def test_manifest_mcp_configuration(self, extracted_manifest):
        """Test that manifest.json has correct MCP server configuration."""
        # Should have MCP server configuration
        assert "mcpServers" in extracted_manifest or "mcp" in extracted_manifest, \
            "Manifest should contain MCP server configuration"
        
        # Check for expected name pattern
        assert "quilt" in extracted_manifest.get("name", "").lower(), \
            "Manifest name should contain 'quilt'"
    
    def test_manifest_version_format(self, extracted_manifest):
        """Test that manifest version follows semantic versioning."""
        version = extracted_manifest.get("version", "")
        
        # Basic version format check (major.minor.patch or dev)
        assert version, "Version field is required"
        
        if version != "dev":
            # Should follow semantic versioning pattern
            import re
            semver_pattern = r'^\d+\.\d+\.\d+(-\w+)?$'
            assert re.match(semver_pattern, version), \
                f"Version '{version}' should follow semantic versioning"
    
    def test_manifest_bootstrap_configuration(self, extracted_manifest):
        """Test that manifest references bootstrap.py correctly."""
        # Check for bootstrap configuration
        # This might be in different fields depending on the exact structure
        
        manifest_str = json.dumps(extracted_manifest)
        assert "bootstrap" in manifest_str.lower(), \
            "Manifest should reference bootstrap configuration"
    
    def test_manifest_no_sensitive_data(self, extracted_manifest):
        """Test that manifest doesn't contain sensitive information."""
        manifest_str = json.dumps(extracted_manifest).lower()
        
        sensitive_patterns = [
            "password", "secret", "key", "token", "credential",
            "aws_access", "aws_secret", "private"
        ]
        
        for pattern in sensitive_patterns:
            assert pattern not in manifest_str, \
                f"Manifest should not contain sensitive data pattern: {pattern}"