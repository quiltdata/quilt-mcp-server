"""Tests for enhanced package management functionality."""

import time
import uuid
from contextlib import contextmanager

import pytest
from unittest.mock import Mock, patch

from quilt_mcp import DEFAULT_BUCKET, DEFAULT_REGISTRY
from quilt_mcp.tools.package_management import (
    create_package_enhanced,
    package_update_metadata,
    package_validate,
    list_package_tools,
)
from quilt_mcp.tools.metadata_templates import (
    get_metadata_template,
    list_metadata_templates,
    validate_metadata_structure,
)
from quilt_mcp.tools.packages import package_browse
from quilt_mcp.tools.package_ops import package_delete
from quilt_mcp.tools.buckets import bucket_objects_put


# Performance measurement utilities
@contextmanager
def measure_performance(operation_name: str):
    """Context manager to measure and report operation performance."""
    start_time = time.perf_counter()
    metrics = {"operation": operation_name, "start_time": start_time}

    try:
        yield metrics
    finally:
        end_time = time.perf_counter()
        duration = end_time - start_time
        metrics["end_time"] = end_time
        metrics["duration_seconds"] = duration

        print(f"\n{'=' * 60}")
        print(f"Performance Metrics: {operation_name}")
        print(f"{'=' * 60}")
        print(f"Duration: {duration:.3f}s")
        print(f"{'=' * 60}\n")


# Test fixtures
@pytest.fixture
def unique_package_name():
    """Generate a unique package name for testing."""
    return f"test/e2e-package-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_s3_objects(unique_package_name):
    """Create test S3 objects and clean them up after the test."""
    # Normalize bucket name (remove s3:// prefix if present)
    test_bucket = DEFAULT_BUCKET.replace("s3://", "") if DEFAULT_BUCKET else ""
    if not test_bucket:
        pytest.fail("DEFAULT_BUCKET not configured")

    test_prefix = f"test-data/e2e-{uuid.uuid4().hex[:8]}"

    # Create test data
    test_items = [
        {
            "key": f"{test_prefix}/data.csv",
            "text": "id,name,value\n1,test,100\n2,sample,200\n",
            "content_type": "text/csv",
            "metadata": {"created_by": "e2e_test", "test": "true"},
        },
        {
            "key": f"{test_prefix}/config.json",
            "text": '{"version": "1.0", "description": "E2E test configuration"}',
            "content_type": "application/json",
        },
    ]

    # Upload test objects (bucket_objects_put expects bucket name without s3:// prefix)
    result = bucket_objects_put(test_bucket, test_items)
    if result.get("uploaded", 0) < len(test_items):
        pytest.fail("Failed to create test S3 objects - check AWS permissions")

    # Return S3 URIs (with s3:// prefix)
    s3_uris = [f"s3://{test_bucket}/{item['key']}" for item in test_items]

    yield {
        "bucket": test_bucket,
        "prefix": test_prefix,
        "s3_uris": s3_uris,
        "items": test_items,
    }

    # Cleanup is best-effort (S3 objects will be cleaned up by lifecycle policies)


class TestCreatePackageEnhanced:
    """Test cases for enhanced package creation."""

    def test_invalid_package_name(self):
        """Test validation of invalid package names."""
        result = create_package_enhanced(
            name="invalid-name",  # Missing namespace
            files=["s3://bucket/file.csv"],
        )

        assert result["success"] is False
        assert "Invalid package name format" in result["error"]
        assert "examples" in result
        assert "tip" in result

    def test_invalid_files_parameter(self):
        """Test validation of invalid files parameter."""
        result = create_package_enhanced(
            name="team/dataset",
            files=[],  # Empty list
        )

        assert result["success"] is False
        assert "Invalid files parameter" in result["error"]
        assert "examples" in result

    def test_invalid_s3_uris(self):
        """Test validation of invalid S3 URIs."""
        result = create_package_enhanced(
            name="team/dataset",
            files=["invalid-uri", "s3://bucket-only"],  # Invalid URIs
        )

        assert result["success"] is False
        assert "Invalid S3 URIs detected" in result["error"]
        assert "invalid_uris" in result
        assert len(result["invalid_uris"]) == 2

    def test_dry_run_preview(self):
        """Test dry run functionality."""
        result = create_package_enhanced(
            name="team/dataset",
            files=["s3://bucket/file.csv"],
            description="Test dataset",
            metadata_template="genomics",
            dry_run=True,
        )

        assert result["success"] is True
        assert result["action"] == "preview"
        assert "metadata_preview" in result
        assert "next_steps" in result
        assert result["metadata_template"] == "genomics"

    def test_json_string_metadata_handling(self):
        """Test handling of metadata as JSON string."""
        # This would test the JSON parsing logic
        # In a full test, we'd mock the base package creation
        result = create_package_enhanced(
            name="team/dataset",
            files=["s3://bucket/file.csv"],
            metadata='{"custom": "value"}',  # JSON string
            dry_run=True,
        )

        assert result["success"] is True
        assert "custom" in result["metadata_preview"]

    def test_readme_content_extraction_from_metadata(self):
        """Test that README content is automatically extracted from metadata."""
        # Mock the base package creation function
        with patch("quilt_mcp.tools.package_management._base_package_create") as mock_base_create:
            mock_base_create.return_value = {
                "status": "success",
                "entries_added": 1,
                "package_name": "team/dataset",
            }

            # Test metadata with README content
            test_metadata = {
                "description": "Test dataset",
                "readme_content": "# Test Dataset\n\nThis is a test dataset with README content.",
                "tags": ["test", "example"],
            }

            result = create_package_enhanced(
                name="team/dataset",
                files=["s3://bucket/file.csv"],
                metadata=test_metadata,
                dry_run=True,
            )

            # Verify success
            assert result["success"] is True

            # Verify that README content was extracted and stored in metadata
            # In dry_run mode, the function returns early and doesn't call _base_package_create
            # but we can verify the metadata processing worked correctly
            assert "metadata_preview" in result

            # Verify README content was removed from the processed metadata
            processed_metadata = result["metadata_preview"]
            assert "readme_content" not in processed_metadata
            assert "readme" not in processed_metadata

            # Verify other metadata was preserved
            assert "description" in processed_metadata
            assert "tags" in processed_metadata

            # Verify that README content was extracted and stored
            assert "_extracted_readme" in processed_metadata
            assert (
                processed_metadata["_extracted_readme"]
                == "# Test Dataset\n\nThis is a test dataset with README content."
            )

    def test_both_readme_fields_extraction(self):
        """Test that both 'readme_content' and 'readme' fields are extracted."""
        # Mock the base package creation function
        with patch("quilt_mcp.tools.package_management._base_package_create") as mock_base_create:
            mock_base_create.return_value = {
                "status": "success",
                "entries_added": 1,
                "package_name": "team/dataset",
            }

            # Test metadata with both README fields
            test_metadata = {
                "description": "Test dataset",
                "readme_content": "# Priority README",
                "readme": "This should be ignored",
                "version": "1.0.0",
            }

            result = create_package_enhanced(
                name="team/dataset",
                files=["s3://bucket/file.csv"],
                metadata=test_metadata,
                dry_run=True,
            )

            # Verify success
            assert result["success"] is True

            # Verify that README content was extracted and stored in metadata
            # In dry_run mode, the function returns early and doesn't call _base_package_create
            # but we can verify the metadata processing worked correctly
            assert "metadata_preview" in result

            # Verify that README content was extracted and stored (priority to readme_content)
            processed_metadata = result["metadata_preview"]
            assert "readme_content" not in processed_metadata  # This should be removed
            assert "readme" in processed_metadata  # This remains since we only extract one field
            assert "_extracted_readme" in processed_metadata

            # Verify that readme_content took priority
            assert processed_metadata["_extracted_readme"] == "# Priority README"

            # Verify other metadata was preserved
            assert "description" in processed_metadata
            assert "version" in processed_metadata

    def test_no_readme_content_in_metadata(self):
        """Test that packages without README content work normally."""
        # Mock the base package creation function
        with patch("quilt_mcp.tools.package_management._base_package_create") as mock_base_create:
            mock_base_create.return_value = {
                "status": "success",
                "entries_added": 1,
                "package_name": "team/dataset",
            }

            # Test metadata without README content
            test_metadata = {
                "description": "Test dataset",
                "tags": ["test", "example"],
                "version": "1.0.0",
            }

            result = create_package_enhanced(
                name="team/dataset",
                files=["s3://bucket/file.csv"],
                metadata=test_metadata,
                dry_run=True,
            )

            # Verify success
            assert result["success"] is True

            # Verify that no README fields are in the processed metadata
            # In dry_run mode, the function returns early and doesn't call _base_package_create
            # but we can verify the metadata processing worked correctly
            assert "metadata_preview" in result

            # Verify no README fields in the processed metadata
            processed_metadata = result["metadata_preview"]
            assert "readme_content" not in processed_metadata
            assert "readme" not in processed_metadata
            assert "_extracted_readme" not in processed_metadata

            # Verify other metadata was preserved
            assert "description" in processed_metadata
            assert "tags" in processed_metadata
            assert "version" in processed_metadata


class TestMetadataTemplates:
    """Test cases for metadata templates."""

    def test_get_standard_template(self):
        """Test getting standard metadata template."""
        metadata = get_metadata_template("standard")

        assert "description" in metadata
        assert "created_by" in metadata
        assert "creation_date" in metadata
        assert "package_type" in metadata

    def test_get_genomics_template(self):
        """Test getting genomics metadata template."""
        metadata = get_metadata_template("genomics", {"organism": "human"})

        assert metadata["package_type"] == "genomics"
        assert metadata["organism"] == "human"
        assert "genome_build" in metadata

    def test_list_metadata_templates(self):
        """Test listing available templates."""
        result = list_metadata_templates()

        assert "available_templates" in result
        assert "usage_examples" in result
        assert "genomics" in result["available_templates"]
        assert "ml" in result["available_templates"]

    def test_validate_metadata_structure(self):
        """Test metadata structure validation."""
        # Valid metadata
        valid_metadata = {"description": "Test dataset", "version": "1.0"}
        result = validate_metadata_structure(valid_metadata)

        assert result["valid"] is True

        # Invalid metadata (not a dict)
        invalid_result = validate_metadata_structure("not a dict")  # type: ignore
        assert invalid_result["valid"] is False


class TestEnhancedPackageBrowsing:
    """Test cases for enhanced package browsing."""

    @patch("quilt3.Package.browse")
    def test_package_browse_enhanced(self, mock_browse):
        """Test enhanced package browsing with file tree."""
        # Mock package with nested structure
        mock_pkg = Mock()
        mock_pkg.keys.return_value = [
            "data/file1.csv",
            "docs/readme.md",
            "analysis/script.py",
        ]

        # Mock individual entries
        mock_entry1 = Mock()
        mock_entry1.size = 1000
        mock_entry1.hash = "hash1"
        mock_entry1.physical_key = "s3://bucket/data/file1.csv"

        mock_entry2 = Mock()
        mock_entry2.size = 500
        mock_entry2.hash = "hash2"
        mock_entry2.physical_key = "s3://bucket/docs/readme.md"

        # Configure the mock to handle __getitem__ calls
        mock_pkg.__getitem__ = Mock(
            side_effect=lambda key: {
                "data/file1.csv": mock_entry1,
                "docs/readme.md": mock_entry2,
                "analysis/script.py": mock_entry1,
            }[key]
        )

        mock_browse.return_value = mock_pkg

        result = package_browse("test/package", recursive=True, include_file_info=True)

        assert result["success"] is True
        assert result["view_type"] == "recursive"
        assert "file_tree" in result
        assert "summary" in result
        assert result["summary"]["total_files"] > 0

    @patch("quilt3.Package.browse")
    def test_package_browse_error_handling(self, mock_browse):
        """Test package browsing error handling."""
        mock_browse.side_effect = Exception("Package not found")

        result = package_browse("nonexistent/package")

        assert result["success"] is False
        assert "Failed to browse package" in result["error"]
        assert "possible_fixes" in result
        assert "suggested_actions" in result


class TestPackageValidation:
    """Test cases for package validation."""

    @patch("quilt_mcp.tools.package_management.package_browse")
    def test_package_validate_success(self, mock_browse):
        """Test successful package validation."""
        mock_browse.return_value = {
            "success": True,
            "entries": [
                {"logical_key": "file1.csv", "physical_key": "s3://bucket/file1.csv"},
                {"logical_key": "file2.json", "physical_key": "s3://bucket/file2.json"},
            ],
            "summary": {"total_size": 1500},
        }

        result = package_validate("test/package")

        assert result["success"] is True
        assert "validation" in result
        assert result["validation"]["accessible_files"] == 2

    @patch("quilt_mcp.tools.package_management.package_browse")
    def test_package_validate_browse_failure(self, mock_browse):
        """Test package validation when browsing fails."""
        mock_browse.return_value = {"success": False, "error": "Package not found"}

        result = package_validate("nonexistent/package")

        assert result["success"] is False
        assert "Cannot validate package" in result["error"]


class TestToolDocumentation:
    """Test cases for tool documentation and guidance."""

    def test_list_package_tools(self):
        """Test package tools listing."""
        result = list_package_tools()

        assert "primary_tools" in result
        assert "specialized_tools" in result
        assert "workflow_guide" in result
        assert "tips" in result

        # Check that main tools are documented
        assert "create_package_enhanced" in result["primary_tools"]
        assert "package_browse" in result["primary_tools"]
        assert "package_validate" in result["primary_tools"]


@pytest.mark.aws
class TestPackageManagementE2E:
    """True end-to-end tests for package management with real AWS operations.

    These tests exercise the complete package lifecycle:
    - Create test data in S3
    - Create packages with metadata templates
    - Verify package persistence and metadata
    - Browse and validate packages
    - Clean up test artifacts

    Performance is measured for regression detection.

    Note: For fast unit tests without AWS operations,
    see tests/unit/test_package_management_integration.py
    """

    def test_create_package_workflow_e2e(self, unique_package_name, test_s3_objects):
        """E2E: Verify create → browse → validate workflow with metadata templates.

        This test validates the package management workflow:
        1. Creates real S3 objects
        2. Creates a Quilt package with genomics metadata template
        3. Verifies the package was created successfully
        4. Browses the package to retrieve persisted metadata
        5. Validates that template fields were applied and persisted correctly
        6. Validates the package structure and accessibility
        7. Cleans up test artifacts

        This tests the core workflow: create → browse → validate.
        Performance target: <30s for complete workflow
        """
        # Fail if bucket/registry not configured
        if not DEFAULT_BUCKET or not DEFAULT_REGISTRY:
            pytest.fail("DEFAULT_BUCKET/DEFAULT_REGISTRY not configured - set QUILT_DEFAULT_BUCKET in .env")

        # Normalize registry to ensure s3:// prefix
        registry = DEFAULT_REGISTRY if DEFAULT_REGISTRY.startswith("s3://") else f"s3://{DEFAULT_REGISTRY}"

        package_name = unique_package_name
        s3_uris = test_s3_objects["s3_uris"]
        workflow_metrics = {}

        try:
            # ACT 1: Create package with genomics template
            with measure_performance("Create Package with Genomics Template") as create_metrics:
                result = create_package_enhanced(
                    name=package_name,
                    files=s3_uris,
                    description="E2E genomics metadata test",
                    metadata_template="genomics",
                    metadata={
                        "organism": "human",
                        "genome_build": "GRCh38",
                        "study_type": "WGS",
                        "test_type": "e2e",
                    },
                    registry=registry,
                )

            workflow_metrics["create"] = create_metrics

            # ASSERT: Package created successfully
            if "status" in result:
                assert result["status"] == "success", f"Package creation failed: {result}"
            elif "success" in result:
                assert result["success"] is True, f"Package creation failed: {result}"
            else:
                pytest.fail(f"Unexpected result format (no status/success field): {result}")

            # ASSERT: Entries were added
            entries = result.get("entries_added") or result.get("entries") or 0
            assert entries > 0, f"Expected entries to be added, got: {entries}"

            # ACT 2: Browse package to retrieve metadata
            with measure_performance("Browse Package and Retrieve Metadata") as browse_metrics:
                browse_result = package_browse(package_name, registry=registry)

            workflow_metrics["browse"] = browse_metrics

            # ASSERT: Browse succeeded
            assert browse_result.get("success") is True, f"Browse failed: {browse_result}"

            # ASSERT: Package has files
            files = browse_result.get("files", []) or browse_result.get("entries", [])
            assert len(files) > 0, "Package should contain files"

            # ACT 3: Verify metadata template was applied and persisted
            pkg_metadata = browse_result.get("metadata", {})

            # Debug output
            print(f"\n{'=' * 60}")
            print("Retrieved Package Metadata:")
            print(f"{'=' * 60}")
            import json

            print(json.dumps(pkg_metadata, indent=2, default=str))
            print(f"{'=' * 60}\n")

            # ASSERT: Template-specific fields are present and correct
            assert pkg_metadata.get("package_type") == "genomics", (
                f"Expected package_type='genomics', got: {pkg_metadata.get('package_type')}"
            )
            assert pkg_metadata.get("organism") == "human", (
                f"Expected organism='human', got: {pkg_metadata.get('organism')}"
            )
            assert pkg_metadata.get("genome_build") == "GRCh38", (
                f"Expected genome_build='GRCh38', got: {pkg_metadata.get('genome_build')}"
            )
            assert pkg_metadata.get("study_type") == "WGS", (
                f"Expected study_type='WGS', got: {pkg_metadata.get('study_type')}"
            )
            assert pkg_metadata.get("test_type") == "e2e", (
                f"Expected test_type='e2e', got: {pkg_metadata.get('test_type')}"
            )

            # ASSERT: Template default fields exist
            assert "created_by" in pkg_metadata, "Template should include 'created_by'"
            assert "creation_date" in pkg_metadata, "Template should include 'creation_date'"

            # ACT 3: Validate the package
            with measure_performance("Validate Package") as validate_metrics:
                validate_result = package_validate(package_name, registry=registry)

            workflow_metrics["validate"] = validate_metrics

            # ASSERT: Validation passed
            assert (
                validate_result.get("valid") is True
                or validate_result.get("status") == "success"
                or validate_result.get("success") is True
            ), f"Validation failed: {validate_result}"

            # Print performance metrics
            total_duration = sum(m["duration_seconds"] for m in workflow_metrics.values())
            print(f"\n{'=' * 60}")
            print("Create → Browse → Validate E2E Performance")
            print(f"{'=' * 60}")
            print(f"Total Duration: {total_duration:.3f}s")
            print(f"  - Create: {workflow_metrics['create']['duration_seconds']:.3f}s")
            print(f"  - Browse: {workflow_metrics['browse']['duration_seconds']:.3f}s")
            print(f"  - Validate: {workflow_metrics['validate']['duration_seconds']:.3f}s")
            print(f"{'=' * 60}\n")

        finally:
            # Cleanup: Delete the test package
            try:
                delete_result = package_delete(
                    package_name=package_name,
                    registry=registry,
                )
                print(f"Cleanup: Package deletion status: {delete_result.get('status', 'unknown')}")
            except Exception as e:
                print(f"Warning: Failed to clean up test package {package_name}: {e}")

    @pytest.mark.slow
    def test_update_package_workflow_e2e(self, unique_package_name, test_s3_objects):
        """E2E: Verify update → browse → validate workflow for existing packages.

        This test validates the package UPDATE workflow:
        1. Creates an initial package with test data
        2. Creates additional S3 objects
        3. Updates the existing package with new files (package_update)
        4. Browses the updated package to verify files were added
        5. Updates package metadata only (package_update_metadata)
        6. Browses to verify metadata was updated
        7. Validates the updated package structure
        8. Cleans up test artifacts

        This tests the core UPDATE workflow: update files → update metadata → validate.
        Performance target: <40s for complete workflow
        """
        from quilt_mcp.tools.package_ops import package_update

        # Fail if bucket/registry not configured
        if not DEFAULT_BUCKET or not DEFAULT_REGISTRY:
            pytest.fail("DEFAULT_BUCKET/DEFAULT_REGISTRY not configured - set QUILT_DEFAULT_BUCKET in .env")

        # Normalize registry and bucket
        registry = DEFAULT_REGISTRY if DEFAULT_REGISTRY.startswith("s3://") else f"s3://{DEFAULT_REGISTRY}"
        test_bucket = DEFAULT_BUCKET.replace("s3://", "") if DEFAULT_BUCKET else ""

        package_name = unique_package_name
        initial_s3_uris = test_s3_objects["s3_uris"]
        test_prefix = test_s3_objects["prefix"]
        workflow_metrics = {}

        try:
            # ACT 1: Create initial package
            with measure_performance("Create Initial Package") as create_metrics:
                result = create_package_enhanced(
                    name=package_name,
                    files=initial_s3_uris,
                    description="E2E update workflow test - initial version",
                    metadata_template="standard",
                    metadata={
                        "version": "1.0",
                        "test_type": "e2e_update",
                        "status": "initial",
                    },
                    registry=registry,
                )

            workflow_metrics["create"] = create_metrics

            # ASSERT: Initial package created successfully
            if "status" in result:
                assert result["status"] == "success", f"Initial package creation failed: {result}"
            elif "success" in result:
                assert result["success"] is True, f"Initial package creation failed: {result}"
            else:
                pytest.fail(f"Unexpected result format: {result}")

            initial_entries = result.get("entries_added") or result.get("entries") or 0
            assert initial_entries > 0, f"Expected entries in initial package, got: {initial_entries}"

            # ACT 2: Create additional S3 objects to add to package
            with measure_performance("Create Additional S3 Objects") as s3_create_metrics:
                additional_items = [
                    {
                        "key": f"{test_prefix}/additional_data.json",
                        "text": '{"additional": true, "version": "2.0"}',
                        "content_type": "application/json",
                    },
                    {
                        "key": f"{test_prefix}/extra_file.txt",
                        "text": "This is additional content for the updated package",
                        "content_type": "text/plain",
                    },
                ]

                upload_result = bucket_objects_put(test_bucket, additional_items)
                assert upload_result.get("uploaded", 0) == len(additional_items), (
                    "Failed to create additional S3 objects"
                )

                additional_s3_uris = [f"s3://{test_bucket}/{item['key']}" for item in additional_items]

            workflow_metrics["s3_create"] = s3_create_metrics

            # ACT 3: Update package with additional files
            with measure_performance("Update Package with New Files") as update_metrics:
                update_result = package_update(
                    package_name=package_name,
                    s3_uris=additional_s3_uris,
                    registry=registry,
                    metadata={"version": "2.0", "status": "updated"},
                    message="E2E test: Added additional files",
                )

            workflow_metrics["update_files"] = update_metrics

            # ASSERT: Package update succeeded
            assert update_result.get("status") == "success", f"Package update failed: {update_result}"

            files_added = update_result.get("files_added") or update_result.get("files") or []
            files_added_count = len(files_added) if isinstance(files_added, list) else files_added
            assert files_added_count == len(additional_s3_uris), (
                f"Expected {len(additional_s3_uris)} files added, got: {files_added_count}"
            )

            # ACT 4: Browse updated package to verify files were added
            with measure_performance("Browse Updated Package") as browse1_metrics:
                browse_result = package_browse(package_name, registry=registry)

            workflow_metrics["browse_after_update"] = browse1_metrics

            # ASSERT: Browse succeeded and has all files
            assert browse_result.get("success") is True, f"Browse after update failed: {browse_result}"

            all_files = browse_result.get("files", []) or browse_result.get("entries", [])
            total_expected_files = initial_entries + len(additional_s3_uris)
            assert len(all_files) == total_expected_files, (
                f"Expected {total_expected_files} files after update, got: {len(all_files)}"
            )

            # ACT 5: Update package metadata only (no file changes)
            with measure_performance("Update Package Metadata Only") as metadata_update_metrics:
                metadata_result = package_update_metadata(
                    package_name=package_name,
                    metadata={
                        "analysis_complete": True,
                        "reviewed_by": "e2e_test",
                        "review_date": "2025-01-11",
                    },
                    registry=registry,
                    merge_with_existing=True,
                )

            workflow_metrics["update_metadata"] = metadata_update_metrics

            # ASSERT: Metadata update succeeded
            assert metadata_result.get("success") is True, f"Metadata update failed: {metadata_result}"
            assert metadata_result.get("merge_applied") is True, "Metadata should have been merged"

            # ACT 6: Browse to verify metadata was updated
            with measure_performance("Browse After Metadata Update") as browse2_metrics:
                browse_result2 = package_browse(package_name, registry=registry)

            workflow_metrics["browse_after_metadata"] = browse2_metrics

            # ASSERT: Metadata fields present
            pkg_metadata = browse_result2.get("metadata", {})

            print(f"\n{'=' * 60}")
            print("Updated Package Metadata:")
            print(f"{'=' * 60}")
            import json

            print(json.dumps(pkg_metadata, indent=2, default=str))
            print(f"{'=' * 60}\n")

            # Verify new metadata fields
            assert pkg_metadata.get("analysis_complete") is True, "Missing analysis_complete field"
            assert pkg_metadata.get("reviewed_by") == "e2e_test", "Missing reviewed_by field"
            assert pkg_metadata.get("review_date") == "2025-01-11", "Missing review_date field"

            # Verify original metadata was preserved (merge=True)
            assert "version" in pkg_metadata, "Original version field should be preserved"
            assert "test_type" in pkg_metadata, "Original test_type field should be preserved"

            # ACT 7: Validate the updated package
            with measure_performance("Validate Updated Package") as validate_metrics:
                validate_result = package_validate(package_name, registry=registry)

            workflow_metrics["validate"] = validate_metrics

            # ASSERT: Validation passed
            assert (
                validate_result.get("valid") is True
                or validate_result.get("status") == "success"
                or validate_result.get("success") is True
            ), f"Validation of updated package failed: {validate_result}"

            # Print performance metrics
            total_duration = sum(m["duration_seconds"] for m in workflow_metrics.values())
            print(f"\n{'=' * 60}")
            print("Update → Browse → Validate E2E Performance")
            print(f"{'=' * 60}")
            print(f"Total Duration: {total_duration:.3f}s")
            print(f"  - Create Initial: {workflow_metrics['create']['duration_seconds']:.3f}s")
            print(f"  - Create S3 Objects: {workflow_metrics['s3_create']['duration_seconds']:.3f}s")
            print(f"  - Update Files: {workflow_metrics['update_files']['duration_seconds']:.3f}s")
            print(f"  - Browse After Update: {workflow_metrics['browse_after_update']['duration_seconds']:.3f}s")
            print(f"  - Update Metadata: {workflow_metrics['update_metadata']['duration_seconds']:.3f}s")
            print(f"  - Browse After Metadata: {workflow_metrics['browse_after_metadata']['duration_seconds']:.3f}s")
            print(f"  - Validate: {workflow_metrics['validate']['duration_seconds']:.3f}s")
            print(f"{'=' * 60}\n")

        finally:
            # Cleanup: Delete the test package
            try:
                delete_result = package_delete(
                    package_name=package_name,
                    registry=registry,
                )
                print(f"Cleanup: Package deletion status: {delete_result.get('status', 'unknown')}")
            except Exception as e:
                print(f"Warning: Failed to clean up test package {package_name}: {e}")
