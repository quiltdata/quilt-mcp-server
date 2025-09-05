"""
Main Visualization Engine for Quilt Packages

This module provides the core visualization engine that analyzes package contents
and automatically generates appropriate visualizations.
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .analyzers.file_analyzer import FileAnalyzer
from .analyzers.data_analyzer import DataAnalyzer
from .analyzers.genomic_analyzer import GenomicAnalyzer
from .generators.echarts import EChartsGenerator
from .generators.vega_lite import VegaLiteGenerator
from .generators.igv import IGVGenerator
from .generators.matplotlib import MatplotlibGenerator
from .generators.perspective import PerspectiveGenerator
from .layouts.grid_layout import GridLayout
from .utils.data_processing import DataProcessor


@dataclass
class PackageAnalysis:
    """Results of package content analysis"""

    package_path: str
    file_types: Dict[str, List[str]]
    data_files: List[str]
    genomic_files: List[str]
    image_files: List[str]
    text_files: List[str]
    metadata: Dict[str, Any]
    suggested_visualizations: List[str]


@dataclass
class Visualization:
    """Represents a generated visualization"""

    id: str
    type: str
    title: str
    description: str
    file_path: str
    config: Dict[str, Any]
    thumbnail_path: Optional[str] = None


class VisualizationEngine:
    """
    Main engine for automatic visualization generation in Quilt packages.

    This engine analyzes package contents and generates appropriate visualizations
    based on file types and data structures.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the visualization engine with configuration."""
        self.config = config or self._get_default_config()

        # Initialize analyzers
        self.file_analyzer = FileAnalyzer()
        self.data_analyzer = DataAnalyzer()
        self.genomic_analyzer = GenomicAnalyzer()

        # Initialize generators
        self.echarts_generator = EChartsGenerator()
        self.vega_generator = VegaLiteGenerator()
        self.igv_generator = IGVGenerator()
        self.matplotlib_generator = MatplotlibGenerator()
        self.perspective_generator = PerspectiveGenerator()

        # Initialize utilities
        self.data_processor = DataProcessor()
        self.layout_manager = GridLayout()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for visualization engine."""
        return {
            "default_chart_types": {
                "csv": "bar_chart",
                "tsv": "bar_chart",
                "json": "line_chart",
                "xlsx": "scatter_plot",
                "parquet": "heatmap",
            },
            "color_schemes": {
                "default": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"],
                "genomics": ["#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00"],
                "scientific": ["#2e8b57", "#4682b4", "#cd853f", "#8b4513", "#4169e1"],
            },
            "chart_sizes": {
                "small": {"width": "300px", "height": "200px"},
                "medium": {"width": "500px", "height": "300px"},
                "large": {"width": "800px", "height": "500px"},
            },
            "grid_columns": 2,
            "responsive_breakpoints": {"mobile": 768, "tablet": 1024, "desktop": 1200},
            "spacing": {"row": "20px", "column": "20px"},
            "max_data_points": 10000,
            "sampling_strategy": "random",
            "cache_enabled": True,
            "default_genome": "hg38",
            "track_colors": {
                "coverage": "#1f77b4",
                "variants": "#ff7f0e",
                "annotations": "#2ca02c",
                "sequences": "#d62728",
            },
            "annotation_sources": ["refseq", "ensembl", "ucsc"],
            "coverage_thresholds": {"min": 10, "max": 1000},
        }

    def analyze_package_contents(self, package_path: str) -> PackageAnalysis:
        """
        Analyze the contents of a Quilt package to determine what visualizations to generate.

        Args:
            package_path: Path to the package directory

        Returns:
            PackageAnalysis object with analysis results
        """
        package_path = Path(package_path)
        if not package_path.exists():
            raise ValueError(f"Package path does not exist: {package_path}")

        # Analyze file types and structure
        file_types = self.file_analyzer.analyze_file_types(package_path)
        data_files = self.file_analyzer.find_data_files(package_path)
        genomic_files = self.file_analyzer.find_genomic_files(package_path)
        image_files = self.file_analyzer.find_image_files(package_path)
        text_files = self.file_analyzer.find_text_files(package_path)

        # Analyze data content
        metadata = self.data_analyzer.analyze_package_metadata(package_path)

        # Analyze genomic content if present
        if genomic_files:
            genomic_metadata = self.genomic_analyzer.analyze_genomic_content(genomic_files)
            metadata.update(genomic_metadata)

        # Suggest visualizations based on content
        suggested_visualizations = self._suggest_visualizations(file_types, data_files, genomic_files, metadata)

        return PackageAnalysis(
            package_path=str(package_path),
            file_types=file_types,
            data_files=data_files,
            genomic_files=genomic_files,
            image_files=image_files,
            text_files=text_files,
            metadata=metadata,
            suggested_visualizations=suggested_visualizations,
        )

    def _suggest_visualizations(
        self,
        file_types: Dict[str, List[str]],
        data_files: List[str],
        genomic_files: List[str],
        metadata: Dict[str, Any],
    ) -> List[str]:
        """Suggest appropriate visualizations based on package content."""
        suggestions = []

        # Data file visualizations
        for file_type, files in file_types.items():
            if file_type in ["csv", "tsv", "xlsx", "parquet"] and files:
                suggestions.extend(["bar_chart", "line_chart", "scatter_plot", "heatmap"])
            elif file_type == "json" and files:
                suggestions.extend(["line_chart", "scatter_plot", "tree_map"])

        # Genomic visualizations
        if genomic_files:
            suggestions.extend(
                [
                    "genome_track",
                    "sequence_view",
                    "variant_view",
                    "expression_profile",
                    "coverage_plot",
                ]
            )

        # Image visualizations
        if metadata.get("image_count", 0) > 0:
            suggestions.append("image_gallery")

        # Text visualizations
        if metadata.get("text_count", 0) > 0:
            suggestions.append("text_summary")

        return list(set(suggestions))  # Remove duplicates

    def generate_visualizations(self, analysis: PackageAnalysis) -> List[Visualization]:
        """
        Generate visualizations based on package analysis.

        Args:
            analysis: PackageAnalysis object from analyze_package_contents

        Returns:
            List of generated Visualization objects
        """
        visualizations = []

        # Create visualization directory
        viz_dir = Path(analysis.package_path) / "visualizations"
        viz_dir.mkdir(exist_ok=True)

        # Generate data visualizations
        for data_file in analysis.data_files:
            viz = self._generate_data_visualization(data_file, viz_dir)
            if viz:
                visualizations.append(viz)

        # Generate genomic visualizations
        if analysis.genomic_files:
            genomic_viz = self._generate_genomic_visualizations(analysis.genomic_files, viz_dir, analysis.metadata)
            visualizations.extend(genomic_viz)

        # Generate summary visualizations
        summary_viz = self._generate_summary_visualizations(analysis, viz_dir)
        visualizations.extend(summary_viz)

        return visualizations

    def _generate_data_visualization(self, data_file: str, viz_dir: Path) -> Optional[Visualization]:
        """Generate visualization for a single data file."""
        try:
            file_path = Path(data_file)
            file_type = file_path.suffix.lower().lstrip(".")

            if file_type in ["csv", "tsv"]:
                return self._generate_csv_visualization(data_file, viz_dir)
            elif file_type == "json":
                return self._generate_json_visualization(data_file, viz_dir)
            elif file_type in ["xlsx", "xls"]:
                return self._generate_excel_visualization(data_file, viz_dir)
            elif file_type == "parquet":
                return self._generate_parquet_visualization(data_file, viz_dir)

        except Exception as e:
            print(f"Error generating visualization for {data_file}: {e}", file=sys.stderr)
            return None

    def _generate_csv_visualization(self, csv_file: str, viz_dir: Path) -> Optional[Visualization]:
        """Generate visualization for CSV file."""
        try:
            # Load and analyze data
            data = self.data_processor.load_csv(csv_file)
            if data is None or data.empty:
                return None

            # Analyze data structure
            analysis = self.data_analyzer.analyze_dataframe(data)

            # Generate appropriate chart
            if analysis["has_categorical"] and analysis["has_numerical"]:
                chart_config = self.echarts_generator.create_bar_chart(
                    data, analysis["categorical_cols"][0], analysis["numerical_cols"][0]
                )
                chart_type = "bar_chart"
            elif analysis["has_temporal"] and analysis["has_numerical"]:
                chart_config = self.echarts_generator.create_line_chart(
                    data, analysis["temporal_cols"][0], analysis["numerical_cols"][0]
                )
                chart_type = "line_chart"
            elif len(analysis["numerical_cols"]) >= 2:
                chart_config = self.echarts_generator.create_scatter_plot(
                    data, analysis["numerical_cols"][0], analysis["numerical_cols"][1]
                )
                chart_type = "scatter_plot"
            else:
                return None

            # Save chart configuration
            chart_file = viz_dir / f"{Path(csv_file).stem}_{chart_type}.json"
            with open(chart_file, "w") as f:
                json.dump(chart_config, f, indent=2)

            return Visualization(
                id=f"viz_csv_{chart_type}",
                type=chart_type,
                title=f"{Path(csv_file).stem} Visualization",
                description=f"Automatically generated {chart_type} for {Path(csv_file).name}",
                file_path=str(chart_file),
                config=chart_config,
            )

        except Exception as e:
            print(f"Error generating CSV visualization: {e}", file=sys.stderr)
            return None

    def _generate_json_visualization(self, json_file: str, viz_dir: Path) -> Optional[Visualization]:
        """Generate visualization for JSON file."""
        # Placeholder for JSON visualization
        return None

    def _generate_excel_visualization(self, excel_file: str, viz_dir: Path) -> Optional[Visualization]:
        """Generate visualization for Excel file."""
        # Placeholder for Excel visualization
        return None

    def _generate_parquet_visualization(self, parquet_file: str, viz_dir: Path) -> Optional[Visualization]:
        """Generate visualization for Parquet file."""
        # Placeholder for Parquet visualization
        return None

    def _generate_genomic_visualizations(
        self, genomic_files: List[str], viz_dir: Path, metadata: Dict[str, Any]
    ) -> List[Visualization]:
        """Generate genomic visualizations using IGV."""
        visualizations = []

        try:
            # Create genomics directory
            genomics_dir = viz_dir / "genomics"
            genomics_dir.mkdir(exist_ok=True)

            # Generate IGV session
            igv_session = self.igv_generator.create_igv_session(
                genomic_files,
                metadata.get("genome_assembly", self.config["default_genome"]),
            )

            session_file = genomics_dir / "igv_session.json"
            with open(session_file, "w") as f:
                json.dump(igv_session, f, indent=2)

            # Generate individual track visualizations
            for genomic_file in genomic_files:
                track_viz = self._generate_genomic_track(genomic_file, genomics_dir)
                if track_viz:
                    visualizations.append(track_viz)

            # Add IGV session visualization
            visualizations.append(
                Visualization(
                    id="igv_session",
                    type="igv_session",
                    title="IGV Session",
                    description="Complete IGV session for genomic analysis",
                    file_path=str(session_file),
                    config=igv_session,
                )
            )

        except Exception as e:
            print(f"Error generating genomic visualizations: {e}", file=sys.stderr)

        return visualizations

    def _generate_genomic_track(self, genomic_file: str, genomics_dir: Path) -> Optional[Visualization]:
        """Generate visualization for a single genomic file."""
        try:
            file_path = Path(genomic_file)
            file_type = file_path.suffix.lower().lstrip(".")

            if file_type in ["bam", "sam"]:
                track_config = self.igv_generator.create_coverage_plot(genomic_file, regions=[])
                track_type = "coverage_plot"
            elif file_type == "vcf":
                track_config = self.igv_generator.create_variant_view(genomic_file, reference="")
                track_type = "variant_view"
            elif file_type in ["bed", "gtf", "gff"]:
                track_config = self.igv_generator.create_genome_track(genomic_file, "annotation", {})
                track_type = "annotation_track"
            else:
                return None

            # Save track configuration
            track_file = genomics_dir / f"{file_path.stem}_{track_type}.json"
            with open(track_file, "w") as f:
                json.dump(track_config, f, indent=2)

            return Visualization(
                id=f"genomic_{track_type}_{file_path.stem}",
                type=track_type,
                title=f"{file_path.stem} {track_type.replace('_', ' ').title()}",
                description=f"IGV track for {file_path.name}",
                file_path=str(track_file),
                config=track_config,
            )

        except Exception as e:
            print(f"Error generating genomic track: {e}", file=sys.stderr)
            return None

    def _generate_summary_visualizations(self, analysis: PackageAnalysis, viz_dir: Path) -> List[Visualization]:
        """Generate summary and overview visualizations."""
        visualizations = []

        try:
            # Package overview chart
            overview_data = {
                "file_types": list(analysis.file_types.keys()),
                "counts": [len(files) for files in analysis.file_types.values()],
            }

            overview_config = self.echarts_generator.create_pie_chart(overview_data, "file_types", "counts")

            overview_file = viz_dir / "package_overview.json"
            with open(overview_file, "w") as f:
                json.dump(overview_config, f, indent=2)

            visualizations.append(
                Visualization(
                    id="package_overview",
                    type="pie_chart",
                    title="Package Overview",
                    description="Distribution of file types in package",
                    file_path=str(overview_file),
                    config=overview_config,
                )
            )

        except Exception as e:
            print(f"Error generating summary visualizations: {e}", file=sys.stderr)

        return visualizations

    def create_quilt_summarize(self, visualizations: List[Visualization]) -> str:
        """
        Create quilt_summarize.json configuration for the package.

        Args:
            visualizations: List of generated visualizations

        Returns:
            JSON string for quilt_summarize.json
        """
        try:
            # Group visualizations by type
            grouped_viz = {}
            for viz in visualizations:
                if viz.type not in grouped_viz:
                    grouped_viz[viz.type] = []
                grouped_viz[viz.type].append(viz)

            # Create quilt_summarize.json structure
            summary_config = []

            # Add package overview first
            overview_viz = next((v for v in visualizations if v.id == "package_overview"), None)
            if overview_viz:
                summary_config.append(
                    {
                        "path": f"visualizations/{Path(overview_viz.file_path).name}",
                        "title": "Package Overview",
                        "description": "Distribution of file types in this package",
                        "types": ["echarts"],
                    }
                )

            # Add data visualizations
            for viz in visualizations:
                if viz.type in ["bar_chart", "line_chart", "scatter_plot", "heatmap"]:
                    summary_config.append(
                        {
                            "path": f"visualizations/{Path(viz.file_path).name}",
                            "title": viz.title,
                            "description": viz.description,
                            "types": ["echarts"],
                        }
                    )

            # Add genomic visualizations
            genomic_viz = [v for v in visualizations if v.type.startswith("genomic") or v.type == "igv_session"]
            if genomic_viz:
                summary_config.append(
                    {
                        "path": "visualizations/genomics/igv_session.json",
                        "title": "Genomic Analysis",
                        "description": "Interactive genomic visualization with IGV",
                        "types": ["igv"],
                    }
                )

            # Add image gallery if images exist
            image_viz = next((v for v in visualizations if v.type == "image_gallery"), None)
            if image_viz:
                summary_config.append(
                    {
                        "path": f"visualizations/{Path(image_viz.file_path).name}",
                        "title": "Image Gallery",
                        "description": "Images and visual content in this package",
                        "types": ["html"],
                    }
                )

            return json.dumps(summary_config, indent=2)

        except Exception as e:
            print(f"Error creating quilt_summarize.json: {e}", file=sys.stderr)
            return "[]"

    def optimize_layout(self, visualizations: List[Visualization]) -> Dict[str, Any]:
        """
        Optimize the layout of visualizations for the best user experience.

        Args:
            visualizations: List of visualizations to layout

        Returns:
            Layout configuration
        """
        return self.layout_manager.optimize_layout(visualizations, self.config)

    def generate_package_visualizations(self, package_path: str) -> Dict[str, Any]:
        """
        Complete workflow to generate visualizations for a package.

        Args:
            package_path: Path to the package directory

        Returns:
            Dictionary with results including visualizations and quilt_summarize.json
        """
        try:
            # Analyze package contents
            analysis = self.analyze_package_contents(package_path)

            # Generate visualizations
            visualizations = self.generate_visualizations(analysis)

            # Create quilt_summarize.json
            quilt_summary = self.create_quilt_summarize(visualizations)

            # Optimize layout
            layout = self.optimize_layout(visualizations)

            return {
                "success": True,
                "package_path": package_path,
                "analysis": analysis,
                "visualizations": visualizations,
                "quilt_summarize": quilt_summary,
                "layout": layout,
                "visualization_count": len(visualizations),
            }

        except Exception as e:
            return {"success": False, "error": str(e), "package_path": package_path}
