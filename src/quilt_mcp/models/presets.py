"""Parameter presets for common tool configurations.

This module provides named presets that bundle common parameter combinations
for complex tools, making it easier for LLMs and users to apply best practices
without specifying numerous individual parameters.
"""

from typing import Any


class PackageImportPresets:
    """Common parameter combinations for package creation from S3.

    These presets bundle frequently-used parameter configurations to simplify
    LLM tool calls and encode best practices for different use cases.

    Available Presets:
        - simple: Basic import with smart defaults (90% of use cases)
        - filtered-csv: Import only CSV files with analytics metadata
        - ml-experiment: Import ML artifacts (models, checkpoints, configs)
        - genomics-data: Import genomics data (FASTQ, BAM, VCF, H5AD)
        - analytics: Import analytics data (CSV, Parquet, JSON, Excel)

    Usage:
        Instead of specifying 7+ parameters, use a preset:

        package_create_from_s3(
            source_bucket="ml-experiments",
            package_name="team/model-v1",
            preset="ml-experiment",  # Automatically applies ML-specific settings
        )

        You can still override individual parameters:

        package_create_from_s3(
            source_bucket="ml-experiments",
            package_name="team/model-v1",
            preset="ml-experiment",
            description="Custom description",  # Override
        )
    """

    SIMPLE: dict[str, Any] = {
        "metadata_template": "standard",
        "copy_mode": "all",
    }

    FILTERED_CSV: dict[str, Any] = {
        "include_patterns": ["*.csv"],
        "metadata_template": "analytics",
        "copy_mode": "all",
    }

    ML_EXPERIMENT: dict[str, Any] = {
        "include_patterns": ["*.pkl", "*.h5", "*.json", "*.pt", "*.pth", "*.ckpt"],
        "exclude_patterns": ["*.tmp", "checkpoints/*", "*.log"],
        "metadata_template": "ml",
        "copy_mode": "all",
    }

    GENOMICS_DATA: dict[str, Any] = {
        "include_patterns": ["*.fastq", "*.fastq.gz", "*.bam", "*.vcf", "*.vcf.gz", "*.h5ad"],
        "metadata_template": "standard",
        "copy_mode": "same_bucket",  # Large genomics files - avoid copying
    }

    ANALYTICS: dict[str, Any] = {
        "include_patterns": ["*.csv", "*.parquet", "*.json", "*.xlsx"],
        "exclude_patterns": ["*.tmp", "*.log", "*_backup.*"],
        "metadata_template": "analytics",
        "copy_mode": "all",
    }

    @classmethod
    def get_preset(cls, preset_name: str) -> dict[str, Any]:
        """Get preset configuration by name.

        Args:
            preset_name: Name of the preset (case-insensitive, hyphens or underscores)

        Returns:
            Dictionary of parameter values for the preset

        Raises:
            ValueError: If preset_name is not a valid preset
        """
        preset_upper = preset_name.upper().replace("-", "_")
        if not hasattr(cls, preset_upper):
            available = cls.list_presets()
            raise ValueError(
                f"Unknown preset '{preset_name}'. Available presets: {', '.join(available)}"
            )
        return getattr(cls, preset_upper).copy()

    @classmethod
    def list_presets(cls) -> list[str]:
        """List all available preset names.

        Returns:
            List of preset names in lowercase with hyphens
        """
        return [
            name.lower().replace("_", "-")
            for name in dir(cls)
            if not name.startswith("_") and name.isupper() and isinstance(getattr(cls, name), dict)
        ]


class VisualizationPresets:
    """Common parameter combinations for data visualizations.

    These presets bundle visualization settings for different use cases,
    providing appropriate color schemes and templates.

    Available Presets:
        - basic-plot: Simple plots with default styling
        - publication-quality: Research-grade visualizations
        - interactive-dashboard: Analytics dashboards
        - genomics: Genomics-specific color schemes
        - ml-metrics: ML experiment metrics

    Usage:
        create_data_visualization(
            data=my_data,
            plot_type="scatter",
            x_column="gene",
            y_column="expression",
            preset="publication-quality",  # Applies publication-ready settings
        )
    """

    BASIC_PLOT: dict[str, Any] = {
        "color_scheme": "default",
        "template": "research",
        "title": "",
        "xlabel": "",
        "ylabel": "",
    }

    PUBLICATION_QUALITY: dict[str, Any] = {
        "color_scheme": "research",
        "template": "research",
        "title": "",
        "xlabel": "",
        "ylabel": "",
    }

    INTERACTIVE_DASHBOARD: dict[str, Any] = {
        "color_scheme": "analytics",
        "template": "analytics",
        "title": "",
        "xlabel": "",
        "ylabel": "",
    }

    GENOMICS: dict[str, Any] = {
        "color_scheme": "genomics",
        "template": "research",
        "title": "",
        "xlabel": "",
        "ylabel": "",
    }

    ML_METRICS: dict[str, Any] = {
        "color_scheme": "ml",
        "template": "ml",
        "title": "",
        "xlabel": "",
        "ylabel": "",
    }

    @classmethod
    def get_preset(cls, preset_name: str) -> dict[str, Any]:
        """Get preset configuration by name.

        Args:
            preset_name: Name of the preset (case-insensitive, hyphens or underscores)

        Returns:
            Dictionary of parameter values for the preset

        Raises:
            ValueError: If preset_name is not a valid preset
        """
        preset_upper = preset_name.upper().replace("-", "_")
        if not hasattr(cls, preset_upper):
            available = cls.list_presets()
            raise ValueError(
                f"Unknown preset '{preset_name}'. Available presets: {', '.join(available)}"
            )
        return getattr(cls, preset_upper).copy()

    @classmethod
    def list_presets(cls) -> list[str]:
        """List all available preset names.

        Returns:
            List of preset names in lowercase with hyphens
        """
        return [
            name.lower().replace("_", "-")
            for name in dir(cls)
            if not name.startswith("_") and name.isupper() and isinstance(getattr(cls, name), dict)
        ]


class WorkflowPresets:
    """Common parameter combinations for workflow creation.

    These presets bundle workflow settings for different pipeline types,
    providing appropriate descriptions and metadata.

    Available Presets:
        - simple-pipeline: Basic data processing
        - ml-workflow: Machine learning experiments
        - data-ingestion: Data loading and validation
        - analytics-pipeline: Analytics processing and reporting

    Usage:
        workflow_create(
            workflow_id="wf-123",
            name="Data Pipeline",
            preset="data-ingestion",  # Applies ingestion-specific settings
        )
    """

    SIMPLE_PIPELINE: dict[str, Any] = {
        "description": "Simple data processing pipeline",
        "metadata": {
            "type": "pipeline",
            "complexity": "simple",
        },
    }

    ML_WORKFLOW: dict[str, Any] = {
        "description": "Machine learning experiment workflow",
        "metadata": {
            "type": "ml_experiment",
            "complexity": "moderate",
            "domain": "machine_learning",
        },
    }

    DATA_INGESTION: dict[str, Any] = {
        "description": "Data ingestion and validation workflow",
        "metadata": {
            "type": "ingestion",
            "complexity": "simple",
            "domain": "data_engineering",
        },
    }

    ANALYTICS_PIPELINE: dict[str, Any] = {
        "description": "Analytics processing and reporting workflow",
        "metadata": {
            "type": "analytics",
            "complexity": "moderate",
            "domain": "analytics",
        },
    }

    @classmethod
    def get_preset(cls, preset_name: str) -> dict[str, Any]:
        """Get preset configuration by name.

        Args:
            preset_name: Name of the preset (case-insensitive, hyphens or underscores)

        Returns:
            Dictionary of parameter values for the preset

        Raises:
            ValueError: If preset_name is not a valid preset
        """
        preset_upper = preset_name.upper().replace("-", "_")
        if not hasattr(cls, preset_upper):
            available = cls.list_presets()
            raise ValueError(
                f"Unknown preset '{preset_name}'. Available presets: {', '.join(available)}"
            )
        return getattr(cls, preset_upper).copy()

    @classmethod
    def list_presets(cls) -> list[str]:
        """List all available preset names.

        Returns:
            List of preset names in lowercase with hyphens
        """
        return [
            name.lower().replace("_", "-")
            for name in dir(cls)
            if not name.startswith("_") and name.isupper() and isinstance(getattr(cls, name), dict)
        ]
