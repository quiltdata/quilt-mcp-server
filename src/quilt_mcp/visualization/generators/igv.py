"""
IGV Generator for Quilt Package Visualization

This module generates IGV (Integrative Genomics Viewer) configurations
for genomic data visualization including tracks, sessions, and views.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import json


class IGVGenerator:
    """Generates IGV configurations for genomic visualization."""

    # Supported genome assemblies
    GENOME_ASSEMBLIES = {
        "hg38": "https://s3.amazonaws.com/igv.broadinstitute.org/genomes/seq/hg38/hg38.fa",
        "hg19": "https://s3.amazonaws.com/igv.broadinstitute.org/genomes/seq/hg19/hg19.fa",
        "mm10": "https://s3.amazonaws.com/igv.broadinstitute.org/genomes/seq/mm10/mm10.fa",
        "mm9": "https://s3.amazonaws.com/igv.broadinstitute.org/genomes/seq/mm9/mm9.fa",
        "rn6": "https://s3.amazonaws.com/igv.broadinstitute.org/genomes/seq/rn6/rn6.fa",
        "dm6": "https://s3.amazonaws.com/igv.broadinstitute.org/genomes/seq/dm6/dm6.fa",
        "ce11": "https://s3.amazonaws.com/igv.broadinstitute.org/genomes/seq/ce11/ce11.fa",
        "sacCer3": "https://s3.amazonaws.com/igv.broadinstitute.org/genomes/seq/sacCer3/sacCer3.fa",
    }

    def __init__(self):
        """Initialize the IGV generator."""
        self.default_track_colors = {
            "coverage": "#1f77b4",
            "variants": "#ff7f0e",
            "annotations": "#2ca02c",
            "sequences": "#d62728",
            "expression": "#9467bd",
            "methylation": "#8c564b",
        }

    def create_genome_track(self, data_file: str, track_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a genome track configuration.

        Args:
            data_file: Path to the genomic data file
            track_type: Type of track (coverage, annotation, etc.)
            config: Additional configuration options

        Returns:
            IGV track configuration dictionary
        """
        track_config = {
            "name": Path(data_file).stem,
            "url": data_file,
            "type": track_type,
            "height": config.get("height", 50),
            "color": config.get("color", self.default_track_colors.get(track_type, "#1f77b4")),
            "visibilityWindow": config.get("visibility_window", -1),
            "autoScale": config.get("auto_scale", True),
            "displayMode": config.get("display_mode", "COLLAPSED"),
        }

        # Add type-specific configurations
        if track_type == "coverage":
            track_config.update(
                {
                    "type": "COVERAGE",
                    "height": 100,
                    "autoScale": True,
                    "color": config.get("color", self.default_track_colors["coverage"]),
                }
            )
        elif track_type == "annotation":
            track_config.update(
                {
                    "type": "ANNOTATION",
                    "height": 80,
                    "autoScale": False,
                    "color": config.get("color", self.default_track_colors["annotations"]),
                }
            )
        elif track_type == "sequence":
            track_config.update(
                {
                    "type": "SEQUENCE",
                    "height": 60,
                    "autoScale": False,
                    "color": config.get("color", self.default_track_colors["sequences"]),
                }
            )

        return track_config

    def create_sequence_view(self, fasta_file: str, annotations: List[str]) -> Dict[str, Any]:
        """
        Create a sequence view configuration.

        Args:
            fasta_file: Path to FASTA file
            annotations: List of annotation files

        Returns:
            IGV sequence view configuration
        """
        config = {
            "name": "Sequence View",
            "type": "sequence",
            "url": fasta_file,
            "height": 60,
            "autoScale": False,
            "color": self.default_track_colors["sequences"],
        }

        # Add annotation tracks if provided
        if annotations:
            config["annotationTracks"] = []
            for ann_file in annotations:
                config["annotationTracks"].append(
                    {
                        "name": Path(ann_file).stem,
                        "url": ann_file,
                        "type": "annotation",
                        "height": 40,
                        "color": self.default_track_colors["annotations"],
                    }
                )

        return config

    def create_variant_view(self, vcf_file: str, reference: str) -> Dict[str, Any]:
        """
        Create a variant view configuration.

        Args:
            vcf_file: Path to VCF file
            reference: Reference genome file

        Returns:
            IGV variant view configuration
        """
        config = {
            "name": "Variant View",
            "type": "variant",
            "url": vcf_file,
            "height": 80,
            "autoScale": False,
            "color": self.default_track_colors["variants"],
            "displayMode": "EXPANDED",
            "visibilityWindow": -1,
        }

        # Add reference sequence if provided
        if reference:
            config["referenceSequence"] = {
                "name": "Reference",
                "url": reference,
                "type": "sequence",
                "height": 40,
            }

        return config

    def create_expression_profile(self, expression_data: str, gene_annotations: str) -> Dict[str, Any]:
        """
        Create an expression profile configuration.

        Args:
            expression_data: Path to expression data file
            gene_annotations: Path to gene annotation file

        Returns:
            IGV expression profile configuration
        """
        config = {
            "name": "Expression Profile",
            "type": "heatmap",
            "url": expression_data,
            "height": 120,
            "autoScale": True,
            "color": self.default_track_colors["expression"],
            "displayMode": "EXPANDED",
            "visibilityWindow": -1,
        }

        # Add gene annotations if provided
        if gene_annotations:
            config["geneAnnotations"] = {
                "name": "Gene Annotations",
                "url": gene_annotations,
                "type": "annotation",
                "height": 60,
                "color": self.default_track_colors["annotations"],
            }

        return config

    def create_coverage_plot(self, bam_file: str, regions: List[str]) -> Dict[str, Any]:
        """
        Create a coverage plot configuration.

        Args:
            bam_file: Path to BAM file
            regions: List of genomic regions

        Returns:
            IGV coverage plot configuration
        """
        config = {
            "name": "Coverage Plot",
            "type": "coverage",
            "url": bam_file,
            "height": 100,
            "autoScale": True,
            "color": self.default_track_colors["coverage"],
            "displayMode": "EXPANDED",
            "visibilityWindow": -1,
        }

        # Add regions if specified
        if regions:
            config["regions"] = regions

        return config

    def create_igv_session(self, tracks: List[Dict[str, Any]], genome: str) -> Dict[str, Any]:
        """
        Create a complete IGV session configuration.

        Args:
            tracks: List of track configurations
            genome: Genome assembly identifier

        Returns:
            Complete IGV session configuration
        """
        # Get genome URL
        genome_url = self.GENOME_ASSEMBLIES.get(genome, self.GENOME_ASSEMBLIES["hg38"])

        session_config = {
            "version": "1.0",
            "genome": genome,
            "genomeURL": genome_url,
            "tracks": tracks,
            "locus": self._get_default_locus(genome),
            "panelHeight": 400,
            "panelWidth": 1200,
            "preferences": {
                "SAM_SHOW_REFERENCE_SEQUENCE": "true",
                "SAM_SHOW_CONSISTENCY": "true",
                "SAM_SHOW_ALIGNMENT_TRACKS": "true",
                "SAM_SHOW_COVERAGE": "true",
            },
        }

        return session_config

    def _get_default_locus(self, genome: str) -> str:
        """Get default locus for a genome assembly."""
        default_loci = {
            "hg38": "chr1:1-1000000",
            "hg19": "chr1:1-1000000",
            "mm10": "chr1:1-1000000",
            "mm9": "chr1:1-1000000",
            "rn6": "chr1:1-1000000",
            "dm6": "chr2L:1-1000000",
            "ce11": "I:1-1000000",
            "sacCer3": "chrI:1-100000",
        }

        return default_loci.get(genome, "chr1:1-1000000")

    def create_multi_track_view(self, track_files: List[str], track_types: List[str], genome: str) -> Dict[str, Any]:
        """
        Create a multi-track view configuration.

        Args:
            track_files: List of track file paths
            track_types: List of track types
            genome: Genome assembly identifier

        Returns:
            Multi-track view configuration
        """
        tracks = []

        for i, (file_path, track_type) in enumerate(zip(track_files, track_types)):
            track_config = self.create_genome_track(
                file_path,
                track_type,
                {
                    "height": 60,
                    "color": self.default_track_colors.get(track_type, self.default_track_colors["coverage"]),
                },
            )
            tracks.append(track_config)

        return self.create_igv_session(tracks, genome)

    def create_genomic_dashboard(
        self, genomic_files: List[str], genome: str, title: str = "Genomic Dashboard"
    ) -> Dict[str, Any]:
        """
        Create a comprehensive genomic dashboard configuration.

        Args:
            genomic_files: List of genomic file paths
            genome: Genome assembly identifier
            title: Dashboard title

        Returns:
            Genomic dashboard configuration
        """
        tracks = []

        # Automatically determine track types based on file extensions
        for file_path in genomic_files:
            file_ext = Path(file_path).suffix.lower().lstrip(".")

            if file_ext in ["bam", "sam"]:
                track_type = "coverage"
            elif file_ext in ["vcf"]:
                track_type = "variant"
            elif file_ext in ["bed", "gtf", "gff"]:
                track_type = "annotation"
            elif file_ext in ["fasta", "fa"]:
                track_type = "sequence"
            else:
                track_type = "annotation"  # Default

            track_config = self.create_genome_track(
                file_path,
                track_type,
                {
                    "height": 80,
                    "color": self.default_track_colors.get(track_type, self.default_track_colors["coverage"]),
                },
            )
            tracks.append(track_config)

        # Create session with dashboard title
        session_config = self.create_igv_session(tracks, genome)
        session_config["title"] = title

        return session_config

    def optimize_track_layout(self, tracks: List[Dict[str, Any]], max_height: int = 800) -> List[Dict[str, Any]]:
        """
        Optimize track layout for better visualization.

        Args:
            tracks: List of track configurations
            max_height: Maximum total height for all tracks

        Returns:
            Optimized track configurations
        """
        if not tracks:
            return tracks

        # Calculate optimal heights
        total_height = sum(track.get("height", 50) for track in tracks)

        if total_height <= max_height:
            return tracks

        # Scale down heights proportionally
        scale_factor = max_height / total_height

        optimized_tracks = []
        for track in tracks:
            optimized_track = track.copy()
            optimized_track["height"] = max(30, int(track.get("height", 50) * scale_factor))
            optimized_tracks.append(optimized_track)

        return optimized_tracks

    def create_track_summary(self, tracks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create a summary of track configurations.

        Args:
            tracks: List of track configurations

        Returns:
            Track summary information
        """
        summary = {
            "total_tracks": len(tracks),
            "track_types": {},
            "total_height": 0,
            "file_sizes": {},
            "genome_assemblies": set(),
        }

        for track in tracks:
            track_type = track.get("type", "unknown")
            if track_type not in summary["track_types"]:
                summary["track_types"][track_type] = 0
            summary["track_types"][track_type] += 1

            summary["total_height"] += track.get("height", 50)

            # Get file size if possible
            file_path = track.get("url", "")
            if file_path and os.path.exists(file_path):
                try:
                    file_size = os.path.getsize(file_path)
                    summary["file_sizes"][file_path] = file_size
                except (OSError, PermissionError):
                    pass

        # Convert set to list for JSON serialization
        summary["genome_assemblies"] = list(summary["genome_assemblies"])

        return summary

    def export_session_file(self, session_config: Dict[str, Any], output_path: str) -> bool:
        """
        Export IGV session configuration to a file.

        Args:
            session_config: IGV session configuration
            output_path: Output file path

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(output_path, "w") as f:
                json.dump(session_config, f, indent=2)
            return True
        except Exception as e:
            print(f"Error exporting IGV session: {e}", file=sys.stderr)
            return False

    def validate_session_config(self, session_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate IGV session configuration.

        Args:
            session_config: IGV session configuration to validate

        Returns:
            Validation results
        """
        validation = {"valid": True, "errors": [], "warnings": [], "suggestions": []}

        # Check required fields
        required_fields = ["version", "genome", "tracks"]
        for field in required_fields:
            if field not in session_config:
                validation["valid"] = False
                validation["errors"].append(f"Missing required field: {field}")

        # Validate genome
        if "genome" in session_config:
            genome = session_config["genome"]
            if genome not in self.GENOME_ASSEMBLIES:
                validation["warnings"].append(f"Unknown genome assembly: {genome}")
                validation["suggestions"].append(f"Consider using one of: {list(self.GENOME_ASSEMBLIES.keys())}")

        # Validate tracks
        if "tracks" in session_config:
            tracks = session_config["tracks"]
            if not isinstance(tracks, list):
                validation["valid"] = False
                validation["errors"].append("Tracks must be a list")
            else:
                for i, track in enumerate(tracks):
                    if not isinstance(track, dict):
                        validation["valid"] = False
                        validation["errors"].append(f"Track {i} must be a dictionary")
                    else:
                        # Check track required fields
                        if "name" not in track:
                            validation["warnings"].append(f"Track {i} missing name")
                        if "url" not in track:
                            validation["warnings"].append(f"Track {i} missing URL")
                        if "type" not in track:
                            validation["warnings"].append(f"Track {i} missing type")

        return validation
