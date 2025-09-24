"""Tests for JWT decompression utilities."""

import pytest
from quilt_mcp.jwt_utils.jwt_decompression import (
    decompress_permissions,
    decompress_buckets,
    process_compressed_jwt,
    safe_decompress_jwt,
    is_compressed_jwt,
    PERMISSION_ABBREVIATIONS
)


class TestPermissionDecompression:
    """Test permission decompression functionality."""
    
    def test_decompress_basic_permissions(self):
        """Test decompression of basic permissions."""
        abbreviated = ['g', 'p', 'd', 'l', 'la']
        result = decompress_permissions(abbreviated)
        expected = ['s3:GetObject', 's3:PutObject', 's3:DeleteObject', 's3:ListBucket', 's3:ListAllMyBuckets']
        assert result == expected
    
    def test_decompress_unknown_permissions(self):
        """Test handling of unknown permission abbreviations."""
        abbreviated = ['g', 'unknown', 'p']
        result = decompress_permissions(abbreviated)
        expected = ['s3:GetObject', 'unknown', 's3:PutObject']
        assert result == expected
    
    def test_decompress_empty_permissions(self):
        """Test decompression of empty permission list."""
        result = decompress_permissions([])
        assert result == []
    
    def test_decompress_invalid_input(self):
        """Test handling of invalid input types."""
        result = decompress_permissions("not a list")
        assert result == []
        
        result = decompress_permissions(None)
        assert result == []


class TestBucketDecompression:
    """Test bucket decompression functionality."""
    
    def test_decompress_groups(self):
        """Test decompression of grouped bucket data."""
        bucket_data = {
            "_type": "groups",
            "_data": {
                "quilt": ["sandbox-bucket", "sales-raw"],
                "cell": ["cellpainting-gallery"]
            }
        }
        result = decompress_buckets(bucket_data)
        expected = ["quilt-sandbox-bucket", "quilt-sales-raw", "cell-cellpainting-gallery"]
        assert result == expected
    
    def test_decompress_patterns(self):
        """Test decompression of pattern-based bucket data."""
        bucket_data = {
            "_type": "patterns",
            "_data": {
                "quilt": ["sandbox-bucket", "sales-raw"],
                "other": ["data-drop-off-bucket"]
            }
        }
        result = decompress_buckets(bucket_data)
        expected = ["quilt-sandbox-bucket", "quilt-sales-raw", "data-drop-off-bucket"]
        assert result == expected
    
    def test_decompress_uncompressed(self):
        """Test handling of uncompressed bucket data."""
        bucket_data = ["quilt-sandbox-bucket", "quilt-sales-raw"]
        result = decompress_buckets(bucket_data)
        assert result == bucket_data
    
    def test_decompress_invalid_data(self):
        """Test handling of invalid bucket data."""
        # Invalid type
        result = decompress_buckets("not a dict or list")
        assert result == []
        
        # Missing _type
        result = decompress_buckets({"_data": {"quilt": ["bucket"]}})
        assert result == []
        
        # Unknown compression type
        result = decompress_buckets({"_type": "unknown", "_data": {}})
        assert result == []


class TestJWTProcessing:
    """Test complete JWT processing functionality."""
    
    def test_process_compressed_jwt(self):
        """Test processing of a complete compressed JWT."""
        compressed_jwt = {
            "s": "w",
            "p": ["g", "p", "d", "l"],
            "r": ["ReadWriteQuiltV2-sales-prod"],
            "b": {
                "_type": "groups",
                "_data": {
                    "quilt": ["sandbox-bucket", "sales-raw"]
                }
            },
            "l": "write",
            "iss": "quilt-frontend",
            "aud": "quilt-mcp-server",
            "sub": "user-123",
            "iat": 1758740633,
            "exp": 1758827033,
            "jti": "abc123"
        }
        
        result = process_compressed_jwt(compressed_jwt)
        
        assert result["scope"] == "w"
        assert len(result["permissions"]) == 4
        assert "s3:GetObject" in result["permissions"]
        assert "s3:PutObject" in result["permissions"]
        assert result["roles"] == ["ReadWriteQuiltV2-sales-prod"]
        assert len(result["buckets"]) == 2
        assert "quilt-sandbox-bucket" in result["buckets"]
        assert "quilt-sales-raw" in result["buckets"]
        assert result["level"] == "write"
        assert result["iss"] == "quilt-frontend"
        assert result["aud"] == "quilt-mcp-server"
        assert result["sub"] == "user-123"
        assert result["iat"] == 1758740633
        assert result["exp"] == 1758827033
        assert result["jti"] == "abc123"
    
    def test_safe_decompress_with_errors(self):
        """Test safe decompression with error handling."""
        malformed_jwt = {
            "s": "w",
            "p": None,  # Invalid data
            "r": ["ReadWriteQuiltV2-sales-prod"],
            "b": "invalid",  # Invalid data
            "l": "write"
        }
        
        result = safe_decompress_jwt(malformed_jwt)
        
        # Should return fallback values without throwing
        assert result["scope"] == "w"
        assert isinstance(result["permissions"], list)
        assert isinstance(result["buckets"], list)
        assert result["level"] == "write"
        assert result["roles"] == ["ReadWriteQuiltV2-sales-prod"]

    def test_safe_decompress_prefers_explicit_fields(self):
        """Explicit arrays should be preserved even when compressed metadata is present."""
        explicit_buckets = [f"quilt-bucket-{i:02d}" for i in range(32)]
        payload = {
            "scope": "write",
            "permissions": ["s3:GetObject"],
            "roles": ["ReadOnlyQuilt"],
            "buckets": explicit_buckets,
            "level": "read",
            "p": ["g"],  # Compressed metadata still provided
            "b": {"_type": "groups", "_data": {"quilt": ["demo"]}},
        }

        result = safe_decompress_jwt(payload)

        assert result["permissions"] == ["s3:GetObject"]
        assert result["buckets"] == explicit_buckets
        assert result["scope"] == "write"
        assert result["level"] == "read"


class TestCompressionDetection:
    """Test JWT compression detection."""
    
    def test_detect_compressed_jwt(self):
        """Test detection of compressed JWT."""
        compressed_jwt = {
            "s": "w",
            "p": ["g", "p"],
            "r": ["role"],
            "b": {"_type": "groups", "_data": {}},
            "l": "write"
        }
        
        assert is_compressed_jwt(compressed_jwt) is True
    
    def test_detect_uncompressed_jwt(self):
        """Test detection of uncompressed JWT."""
        uncompressed_jwt = {
            "scope": "write",
            "permissions": ["s3:GetObject", "s3:PutObject"],
            "roles": ["role"],
            "buckets": ["bucket1", "bucket2"],
            "level": "write"
        }
        
        assert is_compressed_jwt(uncompressed_jwt) is False
    
    def test_detect_mixed_jwt(self):
        """Test detection of JWT with mixed compressed/uncompressed fields."""
        mixed_jwt = {
            "s": "w",  # Compressed
            "permissions": ["s3:GetObject"],  # Uncompressed
            "r": ["role"],  # Compressed
            "buckets": ["bucket1"],  # Uncompressed
            "l": "write"  # Compressed
        }
        
        # Should detect as NOT compressed since it has standard fields
        # The detection logic requires compressed fields but NO standard fields
        assert is_compressed_jwt(mixed_jwt) is False
    
    def test_detect_empty_jwt(self):
        """Test detection with empty JWT."""
        empty_jwt = {}
        assert is_compressed_jwt(empty_jwt) is False


class TestPermissionAbbreviations:
    """Test permission abbreviation mappings."""
    
    def test_permission_abbreviations_completeness(self):
        """Test that all common S3 permissions have abbreviations."""
        common_permissions = [
            's3:GetObject',
            's3:PutObject', 
            's3:DeleteObject',
            's3:ListBucket',
            's3:ListAllMyBuckets'
        ]
        
        for permission in common_permissions:
            # Find the abbreviation for this permission
            abbrev = None
            for abbr, full_perm in PERMISSION_ABBREVIATIONS.items():
                if full_perm == permission:
                    abbrev = abbr
                    break
            
            assert abbrev is not None, f"No abbreviation found for permission: {permission}"
    
    def test_permission_abbreviations_consistency(self):
        """Test that abbreviations are consistent."""
        # Check that each abbreviation maps to exactly one permission
        abbreviations = list(PERMISSION_ABBREVIATIONS.keys())
        permissions = list(PERMISSION_ABBREVIATIONS.values())
        
        # No duplicate abbreviations
        assert len(abbreviations) == len(set(abbreviations))
        
        # No duplicate permissions
        assert len(permissions) == len(set(permissions))


if __name__ == "__main__":
    pytest.main([__file__])
