"""Tests for S3 package creation utilities and validators."""

from tests.conftest import KNOWN_TEST_PACKAGE
from quilt_mcp.tools.packages import (
    _should_include_object,
    _suggest_target_registry,
    _organize_file_structure,
    _generate_readme_content,
    _generate_package_metadata,
)
from quilt_mcp.utils.common import validate_package_name, format_error_response
from quilt_mcp.utils.structure_validator import validate_package_structure
from quilt_mcp.utils.metadata_validator import validate_metadata_compliance
from quilt_mcp.utils.naming_validator import validate_package_naming

TEST_BUCKET = "test-bucket"


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
        assert _should_include_object("test.tmp", ["*.txt", "*.tmp"], ["*.tmp"]) is False
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
        assert validate_package_name("invalid") is False
        assert validate_package_name("ns/pkg/extra") is False
        assert validate_package_name("/package") is False
        assert validate_package_name("namespace/") is False
        assert validate_package_name("") is False

    def test_format_error_response(self):
        """Test error response formatting."""
        result = format_error_response("Test error message")

        assert result["success"] is False
        assert result["error"] == "Test error message"
        assert "timestamp" in result


class TestEnhancedFunctionality:
    """Test cases for enhanced S3-to-package functionality."""

    def test_suggest_target_registry(self):
        """Test registry suggestion algorithm."""
        assert _suggest_target_registry("ml-data", "models") == "s3://ml-packages"
        assert _suggest_target_registry("training-data", "") == "s3://ml-packages"

        assert _suggest_target_registry("analytics-reports", "") == "s3://analytics-packages"
        assert _suggest_target_registry("data", "dashboard") == "s3://analytics-packages"

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
            package_name=KNOWN_TEST_PACKAGE,
            description="Test package",
            organized_structure=organized_structure,
            total_size=1000000,
            source_info={"bucket": TEST_BUCKET},
            metadata_template="standard",
        )

        assert f"# {KNOWN_TEST_PACKAGE}" in readme
        assert "Test package" in readme
        assert "data/processed" in readme
        assert "Usage" in readme
        assert "Package.browse" in readme

    def test_generate_package_metadata(self):
        """Test metadata generation."""
        organized_structure = {
            "data/processed": [{"Key": "data.csv", "Size": 1000}],
        }

        metadata = _generate_package_metadata(
            package_name=KNOWN_TEST_PACKAGE,
            source_info={"bucket": TEST_BUCKET, "prefix": "data/"},
            organized_structure=organized_structure,
            metadata_template="ml",
            user_metadata={"tags": ["test"]},
        )

        assert "quilt" in metadata
        assert "ml" in metadata
        assert "user_metadata" in metadata
        assert metadata["quilt"]["source"]["bucket"] == TEST_BUCKET
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

        bad_structure = {
            "temp": [{"Key": "file1.txt"}] * 60,
        }

        is_valid, warnings, recommendations = validate_package_structure(bad_structure)
        assert len(warnings) > 0

    def test_metadata_compliance_validation(self):
        """Test metadata compliance validation."""
        good_metadata = {
            "quilt": {
                "created_by": "test",
                "creation_date": "2024-01-01T00:00:00Z",
                "source": {"type": "s3_bucket", "bucket": "test"},
            }
        }

        is_compliant, errors, warnings = validate_metadata_compliance(good_metadata)
        assert is_compliant is True
        assert len(errors) == 0

    def test_package_naming_validation(self):
        """Test package naming validation."""
        is_valid, errors, suggestions = validate_package_naming(KNOWN_TEST_PACKAGE)
        assert is_valid is True
        assert len(errors) == 0

        is_valid, errors, suggestions = validate_package_naming("invalid-name")
        assert is_valid is False
        assert len(errors) > 0
