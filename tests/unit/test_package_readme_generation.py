"""BDD tests for automatic README.md and quilt_summarize.json generation in packages.

These tests verify that package creation automatically includes:
1. README.md file with comprehensive package documentation
2. quilt_summarize.json file with package summary and metadata

Per user requirements:
- README contents should be added as actual files in the package (not package metadata)
- Every package should include a quilt_summarize.json file containing at least the README
  and, if relevant, a visualization
"""

import json
from unittest.mock import Mock, patch

import pytest

from quilt_mcp.services.quilt_service import QuiltService


class TestAutomaticREADMEGeneration:
    """Test automatic README.md generation during package creation."""

    def test_create_package_includes_readme_by_default(self):
        """Given I create a package with files,
        When the package is created,
        Then README.md should be automatically added to the package."""
        service = QuiltService()

        mock_package = Mock()
        mock_package.set = Mock()
        mock_package.set_meta = Mock()
        mock_package.push = Mock(return_value="test-hash-123")

        with (
            patch('quilt3.Package', return_value=mock_package),
            patch('quilt_mcp.services.quilt_service.QuiltService._organize_s3_files_smart', return_value={}),
            patch(
                'quilt_mcp.services.quilt_service.QuiltService._normalize_registry', return_value="s3://test-bucket"
            ),
        ):
            result = service.create_package_revision(
                package_name="test/dataset",
                s3_uris=["s3://source/data.csv"],
                metadata={"description": "Test dataset"},
                registry="s3://test-bucket",
                message="Test message",
            )

            # Verify README.md was added to package
            readme_calls = [call for call in mock_package.set.call_args_list if 'README.md' in str(call)]
            assert len(readme_calls) > 0, "README.md should be added to package"

            # Verify README.md content was generated
            readme_call = readme_calls[0]
            readme_content = readme_call[0][1]  # Second argument is the content
            assert isinstance(readme_content, str)
            assert "test/dataset" in readme_content
            assert "Test dataset" in readme_content

    def test_readme_contains_package_metadata(self):
        """Given I create a package with metadata,
        When README.md is generated,
        Then it should contain package name, description, and metadata information."""
        service = QuiltService()

        mock_package = Mock()
        mock_package.set = Mock()
        mock_package.set_meta = Mock()
        mock_package.push = Mock(return_value="test-hash-123")

        test_metadata = {
            "description": "Comprehensive test dataset",
            "version": "1.0.0",
            "license": "MIT",
            "tags": ["test", "example"],
        }

        with (
            patch('quilt3.Package', return_value=mock_package),
            patch('quilt_mcp.services.quilt_service.QuiltService._organize_s3_files_smart', return_value={}),
            patch(
                'quilt_mcp.services.quilt_service.QuiltService._normalize_registry', return_value="s3://test-bucket"
            ),
        ):
            result = service.create_package_revision(
                package_name="test/comprehensive-dataset",
                s3_uris=["s3://source/data.csv"],
                metadata=test_metadata,
                registry="s3://test-bucket",
            )

            # Find README.md call
            readme_calls = [call for call in mock_package.set.call_args_list if 'README.md' in str(call)]
            assert len(readme_calls) > 0
            readme_content = readme_calls[0][0][1]

            # Verify metadata is in README
            assert "Comprehensive test dataset" in readme_content
            assert "version" in readme_content.lower() or "1.0.0" in readme_content
            assert "license" in readme_content.lower() or "MIT" in readme_content

    def test_readme_contains_file_listing(self):
        """Given I create a package with multiple files,
        When README.md is generated,
        Then it should contain a listing of all files in the package."""
        service = QuiltService()

        mock_package = Mock()
        mock_package.set = Mock()
        mock_package.set_meta = Mock()
        mock_package.push = Mock(return_value="test-hash-123")

        with (
            patch('quilt3.Package', return_value=mock_package),
            patch(
                'quilt_mcp.services.quilt_service.QuiltService._organize_s3_files_smart',
                return_value={
                    "data": [
                        {"Key": "file1.csv", "Size": 1000},
                        {"Key": "file2.csv", "Size": 2000},
                    ]
                },
            ),
            patch(
                'quilt_mcp.services.quilt_service.QuiltService._normalize_registry', return_value="s3://test-bucket"
            ),
        ):
            result = service.create_package_revision(
                package_name="test/multi-file",
                s3_uris=["s3://source/file1.csv", "s3://source/file2.csv"],
                metadata={"description": "Multi-file dataset"},
                registry="s3://test-bucket",
            )

            # Find README.md call
            readme_calls = [call for call in mock_package.set.call_args_list if 'README.md' in str(call)]
            assert len(readme_calls) > 0
            readme_content = readme_calls[0][0][1]

            # Verify files are mentioned in README
            assert "file1.csv" in readme_content or "file" in readme_content.lower()

    def test_readme_contains_usage_examples(self):
        """Given I create a package,
        When README.md is generated,
        Then it should contain Python code examples showing how to use the package."""
        service = QuiltService()

        mock_package = Mock()
        mock_package.set = Mock()
        mock_package.set_meta = Mock()
        mock_package.push = Mock(return_value="test-hash-123")

        with (
            patch('quilt3.Package', return_value=mock_package),
            patch('quilt_mcp.services.quilt_service.QuiltService._organize_s3_files_smart', return_value={}),
            patch(
                'quilt_mcp.services.quilt_service.QuiltService._normalize_registry', return_value="s3://test-bucket"
            ),
        ):
            result = service.create_package_revision(
                package_name="test/example-package",
                s3_uris=["s3://source/data.csv"],
                metadata={"description": "Example dataset"},
                registry="s3://test-bucket",
            )

            # Find README.md call
            readme_calls = [call for call in mock_package.set.call_args_list if 'README.md' in str(call)]
            assert len(readme_calls) > 0
            readme_content = readme_calls[0][0][1]

            # Verify usage examples are present
            assert "```python" in readme_content or "import" in readme_content
            assert "quilt3" in readme_content.lower() or "package" in readme_content.lower()


class TestAutomaticQuiltSummarizeGeneration:
    """Test automatic quilt_summarize.json generation during package creation."""

    def test_create_package_includes_quilt_summarize_by_default(self):
        """Given I create a package with files,
        When the package is created,
        Then quilt_summarize.json should be automatically added to the package."""
        service = QuiltService()

        mock_package = Mock()
        mock_package.set = Mock()
        mock_package.set_meta = Mock()
        mock_package.push = Mock(return_value="test-hash-123")

        with (
            patch('quilt3.Package', return_value=mock_package),
            patch('quilt_mcp.services.quilt_service.QuiltService._organize_s3_files_smart', return_value={}),
            patch(
                'quilt_mcp.services.quilt_service.QuiltService._normalize_registry', return_value="s3://test-bucket"
            ),
        ):
            result = service.create_package_revision(
                package_name="test/dataset",
                s3_uris=["s3://source/data.csv"],
                metadata={"description": "Test dataset"},
                registry="s3://test-bucket",
            )

            # Verify quilt_summarize.json was added to package
            summary_calls = [call for call in mock_package.set.call_args_list if 'quilt_summarize.json' in str(call)]
            assert len(summary_calls) > 0, "quilt_summarize.json should be added to package"

            # Verify content is valid JSON
            summary_call = summary_calls[0]
            summary_content = summary_call[0][1]  # Second argument is the content
            summary_data = json.loads(summary_content)
            assert isinstance(summary_data, dict)

    def test_quilt_summarize_contains_readme(self):
        """Given I create a package,
        When quilt_summarize.json is generated,
        Then it should contain the full README content."""
        service = QuiltService()

        mock_package = Mock()
        mock_package.set = Mock()
        mock_package.set_meta = Mock()
        mock_package.push = Mock(return_value="test-hash-123")

        with (
            patch('quilt3.Package', return_value=mock_package),
            patch('quilt_mcp.services.quilt_service.QuiltService._organize_s3_files_smart', return_value={}),
            patch(
                'quilt_mcp.services.quilt_service.QuiltService._normalize_registry', return_value="s3://test-bucket"
            ),
        ):
            result = service.create_package_revision(
                package_name="test/dataset",
                s3_uris=["s3://source/data.csv"],
                metadata={"description": "Test dataset"},
                registry="s3://test-bucket",
            )

            # Get README content
            readme_calls = [call for call in mock_package.set.call_args_list if 'README.md' in str(call)]
            readme_content = readme_calls[0][0][1]

            # Get quilt_summarize.json content
            summary_calls = [call for call in mock_package.set.call_args_list if 'quilt_summarize.json' in str(call)]
            summary_content = summary_calls[0][0][1]
            summary_data = json.loads(summary_content)

            # Verify README is in summary
            assert "readme" in summary_data
            assert summary_data["readme"] == readme_content

    def test_quilt_summarize_has_required_structure(self):
        """Given I create a package,
        When quilt_summarize.json is generated,
        Then it should have the required structure with summary, metadata, and readme."""
        service = QuiltService()

        mock_package = Mock()
        mock_package.set = Mock()
        mock_package.set_meta = Mock()
        mock_package.push = Mock(return_value="test-hash-123")

        with (
            patch('quilt3.Package', return_value=mock_package),
            patch('quilt_mcp.services.quilt_service.QuiltService._organize_s3_files_smart', return_value={}),
            patch(
                'quilt_mcp.services.quilt_service.QuiltService._normalize_registry', return_value="s3://test-bucket"
            ),
        ):
            result = service.create_package_revision(
                package_name="test/dataset",
                s3_uris=["s3://source/data.csv"],
                metadata={"description": "Test dataset"},
                registry="s3://test-bucket",
            )

            # Get quilt_summarize.json content
            summary_calls = [call for call in mock_package.set.call_args_list if 'quilt_summarize.json' in str(call)]
            summary_content = summary_calls[0][0][1]
            summary_data = json.loads(summary_content)

            # Verify required fields
            assert "summary" in summary_data
            assert "readme" in summary_data
            assert "metadata" in summary_data
            assert summary_data["metadata"]["package_name"] == "test/dataset"


class TestConfigurableREADMEGeneration:
    """Test configurable README and quilt_summarize.json generation."""

    def test_can_disable_readme_generation(self):
        """Given I create a package with include_readme=False,
        When the package is created,
        Then README.md should NOT be added to the package."""
        service = QuiltService()

        mock_package = Mock()
        mock_package.set = Mock()
        mock_package.set_meta = Mock()
        mock_package.push = Mock(return_value="test-hash-123")

        with (
            patch('quilt3.Package', return_value=mock_package),
            patch('quilt_mcp.services.quilt_service.QuiltService._organize_s3_files_smart', return_value={}),
            patch(
                'quilt_mcp.services.quilt_service.QuiltService._normalize_registry', return_value="s3://test-bucket"
            ),
        ):
            result = service.create_package_revision(
                package_name="test/dataset",
                s3_uris=["s3://source/data.csv"],
                metadata={"description": "Test dataset"},
                registry="s3://test-bucket",
                include_readme=False,
            )

            # Verify README.md was NOT added to package
            readme_calls = [call for call in mock_package.set.call_args_list if 'README.md' in str(call)]
            assert len(readme_calls) == 0, "README.md should not be added when include_readme=False"

    def test_can_provide_custom_readme_content(self):
        """Given I create a package with custom readme_content,
        When the package is created,
        Then the custom README content should be used instead of auto-generated."""
        service = QuiltService()

        mock_package = Mock()
        mock_package.set = Mock()
        mock_package.set_meta = Mock()
        mock_package.push = Mock(return_value="test-hash-123")

        custom_readme = "# Custom README\n\nThis is my custom README content."

        with (
            patch('quilt3.Package', return_value=mock_package),
            patch('quilt_mcp.services.quilt_service.QuiltService._organize_s3_files_smart', return_value={}),
            patch(
                'quilt_mcp.services.quilt_service.QuiltService._normalize_registry', return_value="s3://test-bucket"
            ),
        ):
            result = service.create_package_revision(
                package_name="test/dataset",
                s3_uris=["s3://source/data.csv"],
                metadata={"description": "Test dataset"},
                registry="s3://test-bucket",
                readme_content=custom_readme,
            )

            # Verify custom README content was used
            readme_calls = [call for call in mock_package.set.call_args_list if 'README.md' in str(call)]
            assert len(readme_calls) > 0
            readme_content = readme_calls[0][0][1]
            assert readme_content == custom_readme

    def test_can_disable_quilt_summarize_generation(self):
        """Given I create a package with include_quilt_summary=False,
        When the package is created,
        Then quilt_summarize.json should NOT be added to the package."""
        service = QuiltService()

        mock_package = Mock()
        mock_package.set = Mock()
        mock_package.set_meta = Mock()
        mock_package.push = Mock(return_value="test-hash-123")

        with (
            patch('quilt3.Package', return_value=mock_package),
            patch('quilt_mcp.services.quilt_service.QuiltService._organize_s3_files_smart', return_value={}),
            patch(
                'quilt_mcp.services.quilt_service.QuiltService._normalize_registry', return_value="s3://test-bucket"
            ),
        ):
            result = service.create_package_revision(
                package_name="test/dataset",
                s3_uris=["s3://source/data.csv"],
                metadata={"description": "Test dataset"},
                registry="s3://test-bucket",
                include_quilt_summary=False,
            )

            # Verify quilt_summarize.json was NOT added to package
            summary_calls = [call for call in mock_package.set.call_args_list if 'quilt_summarize.json' in str(call)]
            assert len(summary_calls) == 0, "quilt_summarize.json should not be added when include_quilt_summary=False"
