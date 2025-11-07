"""Tests for parameter presets functionality."""

import pytest
from quilt_mcp.models.inputs import (
    PackageCreateFromS3Params,
    DataVisualizationParams,
    WorkflowCreateParams,
)
from quilt_mcp.models.presets import (
    PackageImportPresets,
    VisualizationPresets,
    WorkflowPresets,
)


class TestPackageImportPresets:
    """Test PackageImportPresets class."""

    def test_list_presets(self):
        """Test listing all available presets."""
        presets = PackageImportPresets.list_presets()
        assert isinstance(presets, list)
        assert len(presets) == 5
        assert "simple" in presets
        assert "filtered-csv" in presets
        assert "ml-experiment" in presets
        assert "genomics-data" in presets
        assert "analytics" in presets

    def test_get_preset_simple(self):
        """Test getting simple preset."""
        config = PackageImportPresets.get_preset("simple")
        assert isinstance(config, dict)
        assert config["metadata_template"] == "standard"
        assert config["copy_mode"] == "all"

    def test_get_preset_ml_experiment(self):
        """Test getting ML experiment preset."""
        config = PackageImportPresets.get_preset("ml-experiment")
        assert isinstance(config, dict)
        assert config["metadata_template"] == "ml"
        assert "*.pkl" in config["include_patterns"]
        assert "*.h5" in config["include_patterns"]
        assert "*.tmp" in config["exclude_patterns"]

    def test_get_preset_invalid(self):
        """Test getting invalid preset raises ValueError."""
        with pytest.raises(ValueError, match="Unknown preset"):
            PackageImportPresets.get_preset("nonexistent")


class TestPackageCreateFromS3ParamsPresets:
    """Test preset application in PackageCreateFromS3Params."""

    def test_no_preset(self):
        """Test params without preset uses defaults."""
        params = PackageCreateFromS3Params(
            source_bucket="my-bucket",
            package_name="team/dataset",
        )
        assert params.preset is None
        assert params.metadata_template == "standard"  # Default
        assert params.copy_mode == "all"  # Default

    def test_simple_preset(self):
        """Test applying simple preset."""
        params = PackageCreateFromS3Params(
            source_bucket="my-bucket",
            package_name="team/dataset",
            preset="simple",
        )
        assert params.preset == "simple"
        assert params.metadata_template == "standard"
        assert params.copy_mode == "all"

    def test_ml_experiment_preset(self):
        """Test applying ML experiment preset."""
        params = PackageCreateFromS3Params(
            source_bucket="ml-bucket",
            package_name="team/model",
            preset="ml-experiment",
        )
        assert params.preset == "ml-experiment"
        assert params.include_patterns == ["*.pkl", "*.h5", "*.json", "*.pt", "*.pth", "*.ckpt"]
        assert params.exclude_patterns == ["*.tmp", "checkpoints/*", "*.log"]
        assert params.metadata_template == "ml"

    def test_genomics_data_preset(self):
        """Test applying genomics data preset."""
        params = PackageCreateFromS3Params(
            source_bucket="genomics-bucket",
            package_name="team/sequencing",
            preset="genomics-data",
        )
        assert params.preset == "genomics-data"
        assert "*.fastq" in params.include_patterns
        assert "*.bam" in params.include_patterns
        assert params.copy_mode == "same_bucket"  # Large files

    def test_preset_with_override(self):
        """Test that explicit parameters override preset values."""
        params = PackageCreateFromS3Params(
            source_bucket="my-bucket",
            package_name="team/dataset",
            preset="simple",
            metadata_template="ml",  # Override preset's "standard"
            description="Custom description",
        )
        assert params.preset == "simple"
        assert params.metadata_template == "ml"  # Overridden
        assert params.description == "Custom description"
        assert params.copy_mode == "all"  # From preset

    def test_invalid_preset(self):
        """Test that invalid preset name raises validation error."""
        # Pydantic validates Literal types before the model_validator runs
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            PackageCreateFromS3Params(
                source_bucket="my-bucket",
                package_name="team/dataset",
                preset="nonexistent",
            )


class TestVisualizationPresets:
    """Test VisualizationPresets class."""

    def test_list_presets(self):
        """Test listing all available presets."""
        presets = VisualizationPresets.list_presets()
        assert isinstance(presets, list)
        assert len(presets) == 5
        assert "basic-plot" in presets
        assert "publication-quality" in presets
        assert "genomics" in presets

    def test_get_preset_publication_quality(self):
        """Test getting publication quality preset."""
        config = VisualizationPresets.get_preset("publication-quality")
        assert isinstance(config, dict)
        assert config["color_scheme"] == "research"
        assert config["template"] == "research"


class TestDataVisualizationParamsPresets:
    """Test preset application in DataVisualizationParams."""

    def test_no_preset(self):
        """Test params without preset uses defaults."""
        params = DataVisualizationParams(
            data={"x": [1, 2], "y": [3, 4]},
            plot_type="scatter",
            x_column="x",
            y_column="y",
        )
        assert params.preset is None
        assert params.color_scheme == "genomics"  # Default

    def test_publication_quality_preset(self):
        """Test applying publication quality preset."""
        params = DataVisualizationParams(
            data={"x": [1, 2], "y": [3, 4]},
            plot_type="scatter",
            x_column="x",
            y_column="y",
            preset="publication-quality",
        )
        assert params.preset == "publication-quality"
        assert params.color_scheme == "research"
        assert params.template == "research"

    def test_ml_metrics_preset(self):
        """Test applying ML metrics preset."""
        params = DataVisualizationParams(
            data={"epoch": [1, 2, 3], "loss": [0.5, 0.3, 0.2]},
            plot_type="line",
            x_column="epoch",
            y_column="loss",
            preset="ml-metrics",
        )
        assert params.preset == "ml-metrics"
        assert params.color_scheme == "ml"
        assert params.template == "ml"

    def test_preset_with_override(self):
        """Test that explicit parameters override preset values."""
        params = DataVisualizationParams(
            data={"x": [1, 2], "y": [3, 4]},
            plot_type="scatter",
            x_column="x",
            y_column="y",
            preset="publication-quality",
            title="Custom Title",  # Override
        )
        assert params.preset == "publication-quality"
        assert params.title == "Custom Title"  # Overridden
        assert params.color_scheme == "research"  # From preset


class TestWorkflowPresets:
    """Test WorkflowPresets class."""

    def test_list_presets(self):
        """Test listing all available presets."""
        presets = WorkflowPresets.list_presets()
        assert isinstance(presets, list)
        assert len(presets) == 4
        assert "simple-pipeline" in presets
        assert "ml-workflow" in presets
        assert "data-ingestion" in presets

    def test_get_preset_ml_workflow(self):
        """Test getting ML workflow preset."""
        config = WorkflowPresets.get_preset("ml-workflow")
        assert isinstance(config, dict)
        assert "machine learning" in config["description"].lower()
        assert config["metadata"]["type"] == "ml_experiment"


class TestWorkflowCreateParamsPresets:
    """Test preset application in WorkflowCreateParams."""

    def test_no_preset(self):
        """Test params without preset uses defaults."""
        params = WorkflowCreateParams(
            workflow_id="wf-123",
            name="My Workflow",
        )
        assert params.preset is None
        assert params.description == ""  # Default
        assert params.metadata is None  # Default

    def test_ml_workflow_preset(self):
        """Test applying ML workflow preset."""
        params = WorkflowCreateParams(
            workflow_id="wf-ml-001",
            name="ML Experiment",
            preset="ml-workflow",
        )
        assert params.preset == "ml-workflow"
        assert "machine learning" in params.description.lower()
        assert params.metadata["type"] == "ml_experiment"
        assert params.metadata["domain"] == "machine_learning"

    def test_data_ingestion_preset(self):
        """Test applying data ingestion preset."""
        params = WorkflowCreateParams(
            workflow_id="wf-ingest-001",
            name="Data Ingestion",
            preset="data-ingestion",
        )
        assert params.preset == "data-ingestion"
        assert "ingestion" in params.description.lower()
        assert params.metadata["type"] == "ingestion"

    def test_preset_with_override(self):
        """Test that explicit parameters override preset values."""
        params = WorkflowCreateParams(
            workflow_id="wf-123",
            name="My Workflow",
            preset="simple-pipeline",
            description="Custom description",  # Override
        )
        assert params.preset == "simple-pipeline"
        assert params.description == "Custom description"  # Overridden
        # Metadata from preset should still apply since it wasn't overridden
        assert params.metadata["type"] == "pipeline"


class TestPresetIntegration:
    """Integration tests for preset system."""

    def test_all_package_presets_valid(self):
        """Test that all package presets can be applied successfully."""
        for preset_name in PackageImportPresets.list_presets():
            params = PackageCreateFromS3Params(
                source_bucket="test-bucket",
                package_name="team/test",
                preset=preset_name,
            )
            assert params.preset == preset_name
            # Should not raise any errors

    def test_all_visualization_presets_valid(self):
        """Test that all visualization presets can be applied successfully."""
        for preset_name in VisualizationPresets.list_presets():
            params = DataVisualizationParams(
                data={"x": [1, 2], "y": [3, 4]},
                plot_type="scatter",
                x_column="x",
                y_column="y",
                preset=preset_name,
            )
            assert params.preset == preset_name

    def test_all_workflow_presets_valid(self):
        """Test that all workflow presets can be applied successfully."""
        for preset_name in WorkflowPresets.list_presets():
            params = WorkflowCreateParams(
                workflow_id=f"wf-{preset_name}",
                name=f"Test {preset_name}",
                preset=preset_name,
            )
            assert params.preset == preset_name
