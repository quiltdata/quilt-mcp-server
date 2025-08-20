"""Tests for enhanced S3-to-package creation functionality."""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from quilt_mcp.tools.s3_package import (
    package_create_from_s3,
    _validate_bucket_access,
    _discover_s3_objects,
    _should_include_object,
    _suggest_target_registry,
    _organize_file_structure,
    _generate_readme_content,
    _generate_package_metadata,
)
from quilt_mcp.utils import validate_package_name, format_error_response
from quilt_mcp.validators import (
    validate_package_structure,
    validate_metadata_compliance,
    validate_package_naming,
)


class TestPackageCreateFromS3:
    """Test cases for the package_create_from_s3 function."""

    @pytest.mark.asyncio
    async def test_invalid_package_name(self):
        """Test that invalid package names are rejected."""
        result = await package_create_from_s3(
            source_bucket="test-bucket",
            package_name="invalid-name",  # Missing namespace
        )
        
        assert result["success"] is False
        assert "Invalid package name format" in result["error"]

    @pytest.mark.asyncio
    async def test_missing_required_params(self):
        """Test that missing required parameters are handled."""
        result = await package_create_from_s3(
            source_bucket="",  # Empty bucket
            package_name="test/package",
        )
        
        assert result["success"] is False
        assert "source_bucket is required" in result["error"]

    @pytest.mark.asyncio
    @patch('quilt_mcp.tools.s3_package.get_s3_client')
    @patch('quilt_mcp.tools.s3_package._validate_bucket_access')
    @patch('quilt_mcp.tools.s3_package._discover_s3_objects')
    async def test_no_objects_found(self, mock_discover, mock_validate, mock_s3_client):
        """Test handling when no objects are found."""
        # Setup mocks
        mock_s3_client.return_value = Mock()
        mock_validate.return_value = None
        mock_discover.return_value = []  # No objects found
        
        result = await package_create_from_s3(
            source_bucket="test-bucket",
            package_name="test/package",
        )
        
        assert result["success"] is False
        assert "No objects found" in result["error"]

    @pytest.mark.asyncio
    @patch('quilt_mcp.tools.s3_package.get_s3_client')
    @patch('quilt_mcp.tools.s3_package._validate_bucket_access')
    @patch('quilt_mcp.tools.s3_package._discover_s3_objects')
    @patch('quilt_mcp.tools.s3_package._create_package_from_objects')
    async def test_successful_package_creation(self, mock_create, mock_discover, mock_validate, mock_s3_client):
        """Test successful package creation."""
        # Setup mocks
        mock_s3_client.return_value = Mock()
        mock_validate.return_value = None
        mock_discover.return_value = [
            {"Key": "file1.txt", "Size": 100},
            {"Key": "file2.txt", "Size": 200},
        ]
        mock_create.return_value = {"top_hash": "test_hash_123"}
        
        result = await package_create_from_s3(
            source_bucket="test-bucket",
            package_name="test/package",
            description="Test package",
        )
        
        assert result["success"] is True
        assert result["package_name"] == "test/package"
        assert result["objects_count"] == 2
        assert result["total_size"] == 300
        assert result["package_hash"] == "test_hash_123"
        assert result["description"] == "Test package"


class TestUtilityFunctions:
    """Test cases for utility functions."""

    def test_should_include_object_no_patterns(self):
        """Test object inclusion with no patterns."""
        assert _should_include_object("test.txt", None, None) is True

    def test_should_include_object_include_patterns(self):
        """Test object inclusion with include patterns."""
        assert _should_include_object("test.txt", ["*.txt"], None) is True
        assert _should_include_object("test.pdf", ["*.txt"], None) is False

    def test_should_include_object_exclude_patterns(self):
        """Test object inclusion with exclude patterns."""
        assert _should_include_object("test.txt", None, ["*.tmp"]) is True
        assert _should_include_object("test.tmp", None, ["*.tmp"]) is False

    def test_should_include_object_both_patterns(self):
        """Test object inclusion with both include and exclude patterns."""
        # Should exclude even if it matches include pattern
        assert _should_include_object("test.tmp", ["*.txt", "*.tmp"], ["*.tmp"]) is False
        # Should include if matches include and doesn't match exclude
        assert _should_include_object("test.txt", ["*.txt"], ["*.tmp"]) is True


class TestValidation:
    """Test cases for validation functions."""

    def test_validate_package_name_valid(self):
        """Test valid package names."""
        assert validate_package_name("namespace/package") is True
        assert validate_package_name("my-ns/my-pkg") is True
        assert validate_package_name("ns123/pkg456") is True

    def test_validate_package_name_invalid(self):
        """Test invalid package names."""
        assert validate_package_name("invalid") is False  # No slash
        assert validate_package_name("ns/pkg/extra") is False  # Too many parts
        assert validate_package_name("/package") is False  # Empty namespace
        assert validate_package_name("namespace/") is False  # Empty package name
        assert validate_package_name("") is False  # Empty string

    def test_format_error_response(self):
        """Test error response formatting."""
        result = format_error_response("Test error message")
        
        assert result["success"] is False
        assert result["error"] == "Test error message"
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_dry_run_preview(self):
        """Test dry run functionality returns preview without creating package."""
        with patch('quilt_mcp.tools.s3_package.get_s3_client'), \
             patch('quilt_mcp.tools.s3_package._validate_bucket_access'), \
             patch('quilt_mcp.tools.s3_package._discover_s3_objects') as mock_discover:
            
            mock_discover.return_value = [
                {"Key": "data.csv", "Size": 1000},
                {"Key": "readme.md", "Size": 500},
            ]
            
            result = await package_create_from_s3(
                source_bucket="test-bucket",
                package_name="test/package", 
                dry_run=True
            )
            
            assert result["success"] is True
            assert result["action"] == "preview"
            assert "structure_preview" in result
            assert "readme_preview" in result
            assert "metadata_preview" in result

    @pytest.mark.asyncio
    async def test_auto_registry_suggestion(self):
        """Test automatic registry suggestion based on source patterns."""
        with patch('quilt_mcp.tools.s3_package.get_s3_client'), \
             patch('quilt_mcp.tools.s3_package._validate_bucket_access'), \
             patch('quilt_mcp.tools.s3_package._discover_s3_objects') as mock_discover, \
             patch('quilt_mcp.tools.s3_package._create_enhanced_package') as mock_create:
            
            mock_discover.return_value = [{"Key": "model.pkl", "Size": 1000}]
            mock_create.return_value = {"top_hash": "test_hash"}
            
            result = await package_create_from_s3(
                source_bucket="ml-training-data",
                package_name="test/package",
                # No target_registry specified - should be auto-suggested
            )
            
            assert result["success"] is True
            assert "ml-packages" in result["registry"]


class TestEnhancedFunctionality:
    """Test cases for enhanced S3-to-package functionality."""

    def test_suggest_target_registry(self):
        """Test registry suggestion algorithm."""
        # ML patterns
        assert _suggest_target_registry("ml-data", "models") == "s3://ml-packages"
        assert _suggest_target_registry("training-data", "") == "s3://ml-packages"
        
        # Analytics patterns  
        assert _suggest_target_registry("analytics-reports", "") == "s3://analytics-packages"
        assert _suggest_target_registry("data", "dashboard") == "s3://analytics-packages"
        
        # Default fallback
        assert _suggest_target_registry("random-bucket", "") == "s3://data-packages"

    def test_organize_file_structure(self):
        """Test smart file organization."""
        objects = [
            {"Key": "data.csv"},
            {"Key": "config.yml"},
            {"Key": "readme.md"},
            {"Key": "model.pkl"},
            {"Key": "image.png"},
        ]
        
        organized = _organize_file_structure(objects, auto_organize=True)
        
        assert "data/processed" in organized
        assert "metadata" in organized  
        assert "docs" in organized
        assert "data/misc" in organized
        assert "data/media" in organized
        
        # Test flat organization
        flat = _organize_file_structure(objects, auto_organize=False)
        assert "" in flat
        assert len(flat[""]) == 5

    def test_generate_readme_content(self):
        """Test README generation."""
        organized_structure = {
            "data/processed": [{"Key": "data.csv"}],
            "docs": [{"Key": "readme.md"}],
        }
        
        readme = _generate_readme_content(
            package_name="test/package",
            description="Test package",
            organized_structure=organized_structure,
            total_size=1000000,
            source_info={"bucket": "test-bucket"},
            metadata_template="standard"
        )
        
        assert "# test/package" in readme
        assert "Test package" in readme
        assert "data/processed" in readme
        assert "Usage" in readme
        assert "quilt3.Package.browse" in readme

    def test_generate_package_metadata(self):
        """Test metadata generation."""
        organized_structure = {
            "data/processed": [{"Key": "data.csv", "Size": 1000}],
        }
        
        metadata = _generate_package_metadata(
            package_name="test/package",
            source_info={"bucket": "test-bucket", "prefix": "data/"},
            organized_structure=organized_structure,
            metadata_template="ml",
            user_metadata={"tags": ["test"]}
        )
        
        assert "quilt" in metadata
        assert "ml" in metadata
        assert "user_metadata" in metadata
        assert metadata["quilt"]["source"]["bucket"] == "test-bucket"
        assert metadata["user_metadata"]["tags"] == ["test"]


class TestValidationUtilities:
    """Test cases for validation utilities."""

    def test_package_structure_validation(self):
        """Test package structure validation."""
        good_structure = {
            "data/processed": [{"Key": "data.csv"}],
            "docs": [{"Key": "readme.md"}],
        }
        
        is_valid, warnings, recommendations = validate_package_structure(good_structure)
        assert is_valid is True
        
        # Test problematic structure
        bad_structure = {
            "temp": [{"Key": "file1.txt"}] * 60,  # Too many files, bad folder name
        }
        
        is_valid, warnings, recommendations = validate_package_structure(bad_structure)
        assert len(warnings) > 0

    def test_metadata_compliance_validation(self):
        """Test metadata compliance validation."""
        good_metadata = {
            "quilt": {
                "created_by": "test",
                "creation_date": "2024-01-01T00:00:00Z",
                "source": {"type": "s3_bucket", "bucket": "test"}
            }
        }
        
        is_compliant, errors, warnings = validate_metadata_compliance(good_metadata)
        assert is_compliant is True
        assert len(errors) == 0

    def test_package_naming_validation(self):
        """Test package naming validation."""
        is_valid, errors, suggestions = validate_package_naming("test/package")
        assert is_valid is True
        assert len(errors) == 0
        
        is_valid, errors, suggestions = validate_package_naming("invalid-name")
        assert is_valid is False
        assert len(errors) > 0
