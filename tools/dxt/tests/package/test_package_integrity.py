"""
Test Package Integrity
Tests DXT package checksums and structure validation.
"""

import hashlib
import pytest
import zipfile
import tempfile
import os
from pathlib import Path


class TestPackageIntegrity:
    """Test DXT package integrity and checksums."""
    
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
    
    def test_package_file_integrity(self, dxt_package_path):
        """Test that the DXT package file is not corrupted."""
        if not os.path.exists(dxt_package_path):
            pytest.skip("DXT package not built yet")
        
        # Test that file can be read
        with open(dxt_package_path, 'rb') as f:
            file_data = f.read()
        
        assert len(file_data) > 0, "Package file should not be empty"
        
        # Test that it's a valid zip file
        try:
            with zipfile.ZipFile(dxt_package_path, 'r') as zip_ref:
                # Test integrity
                bad_files = zip_ref.testzip()
                assert bad_files is None, f"Package contains corrupted files: {bad_files}"
        except zipfile.BadZipFile:
            pytest.fail("DXT package is not a valid zip file")
    
    def test_package_checksum_consistency(self, dxt_package_path):
        """Test that package checksum is consistent across reads."""
        if not os.path.exists(dxt_package_path):
            pytest.skip("DXT package not built yet")
        
        # Calculate checksum twice
        def calculate_checksum():
            sha256_hash = hashlib.sha256()
            with open(dxt_package_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        
        checksum1 = calculate_checksum()
        checksum2 = calculate_checksum()
        
        assert checksum1 == checksum2, "Package checksum should be consistent"
        assert len(checksum1) == 64, "SHA256 checksum should be 64 characters"
    
    def test_package_required_files_present(self, dxt_package_path):
        """Test that all required files are present in the package."""
        if not os.path.exists(dxt_package_path):
            pytest.skip("DXT package not built yet")
        
        required_files = {
            "manifest.json": {"min_size": 50, "content_check": "version"},
            "bootstrap.py": {"min_size": 100, "content_check": "import"},
            "dxt_main.py": {"min_size": 100, "content_check": "def"},
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(dxt_package_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            extracted_path = Path(temp_dir)
            
            for filename, requirements in required_files.items():
                file_path = extracted_path / filename
                
                assert file_path.exists(), f"Required file {filename} not found"
                
                file_size = file_path.stat().st_size
                assert file_size >= requirements["min_size"], \
                    f"File {filename} too small: {file_size} bytes"
                
                # Content validation
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                content_check = requirements["content_check"]
                assert content_check in content, \
                    f"File {filename} should contain '{content_check}'"
    
    def test_package_no_unauthorized_files(self, dxt_package_path):
        """Test that package doesn't contain unauthorized or sensitive files."""
        if not os.path.exists(dxt_package_path):
            pytest.skip("DXT package not built yet")
        
        # Files that should NOT be in the package
        forbidden_patterns = [
            ".pyc", "__pycache__", ".git", ".env", 
            ".secret", "password", ".key", ".pem"
        ]
        
        with zipfile.ZipFile(dxt_package_path, 'r') as zip_ref:
            file_list = zip_ref.namelist()
        
        for file_path in file_list:
            for pattern in forbidden_patterns:
                assert pattern not in file_path.lower(), \
                    f"Package contains forbidden file pattern '{pattern}': {file_path}"
    
    def test_package_size_reasonable(self, dxt_package_path):
        """Test that package size is within reasonable bounds."""
        if not os.path.exists(dxt_package_path):
            pytest.skip("DXT package not built yet")
        
        file_size = os.path.getsize(dxt_package_path)
        
        # Should be larger than minimum (has actual content)
        assert file_size > 1024, f"Package too small: {file_size} bytes"
        
        # Should not be excessively large (no huge files accidentally included)
        max_size = 100 * 1024 * 1024  # 100MB
        assert file_size < max_size, f"Package too large: {file_size} bytes"
    
    def test_package_compression_effective(self, dxt_package_path):
        """Test that package compression is working effectively."""
        if not os.path.exists(dxt_package_path):
            pytest.skip("DXT package not built yet")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(dxt_package_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Calculate uncompressed size
            uncompressed_size = 0
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    uncompressed_size += os.path.getsize(file_path)
        
        compressed_size = os.path.getsize(dxt_package_path)
        
        # Should have some compression (at least 10%)
        compression_ratio = compressed_size / uncompressed_size
        assert compression_ratio < 0.9, f"Poor compression ratio: {compression_ratio:.2%}"