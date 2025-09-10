"""
Genomic Analyzer for Quilt Package Visualization

This module analyzes genomic files to understand their structure, content types,
and biological context for automatic IGV visualization generation.
"""

import os
from pathlib import Path
from typing import Dict, List, Any, Optional
import json


class GenomicAnalyzer:
    """Analyzes genomic files to determine appropriate IGV visualizations."""

    # Genome assembly mappings
    GENOME_ASSEMBLIES = {
        "hg38": "Human (GRCh38)",
        "hg19": "Human (GRCh37)",
        "mm10": "Mouse (GRCm38)",
        "mm9": "Mouse (GRCm37)",
        "rn6": "Rat (Rnor_6.0)",
        "dm6": "Fruit Fly (BDGP6)",
        "ce11": "Worm (WBcel235)",
        "sacCer3": "Yeast (R64-1-1)",
    }

    def __init__(self):
        """Initialize the genomic analyzer."""
        pass

    def analyze_genomic_content(self, genomic_files: List[str]) -> Dict[str, Any]:
        """
        Analyze genomic files to understand their content and structure.

        Args:
            genomic_files: List of paths to genomic files

        Returns:
            Dictionary with genomic analysis results
        """
        analysis = {
            "genomic_file_count": len(genomic_files),
            "file_types": {},
            "genome_assembly": None,
            "has_sequence_data": False,
            "has_variant_data": False,
            "has_annotation_data": False,
            "has_coverage_data": False,
            "sample_count": 0,
            "chromosomes": set(),
            "regions": [],
            "biological_context": {},
        }

        for file_path in genomic_files:
            file_analysis = self._analyze_genomic_file(file_path)
            if file_analysis:
                # Aggregate file types
                file_type = file_analysis.get("file_type", "unknown")
                if file_type not in analysis["file_types"]:
                    analysis["file_types"][file_type] = []
                analysis["file_types"][file_type].append(file_path)

                # Update flags
                if file_analysis.get("has_sequence_data"):
                    analysis["has_sequence_data"] = True
                if file_analysis.get("has_variant_data"):
                    analysis["has_variant_data"] = True
                if file_analysis.get("has_annotation_data"):
                    analysis["has_annotation_data"] = True
                if file_analysis.get("has_coverage_data"):
                    analysis["has_coverage_data"] = True

                # Aggregate chromosomes and regions
                if "chromosomes" in file_analysis:
                    analysis["chromosomes"].update(file_analysis["chromosomes"])
                if "regions" in file_analysis:
                    analysis["regions"].extend(file_analysis["regions"])

                # Update sample count
                if "sample_count" in file_analysis:
                    analysis["sample_count"] = max(analysis["sample_count"], file_analysis["sample_count"])

                # Detect genome assembly
                if not analysis["genome_assembly"] and "genome_assembly" in file_analysis:
                    analysis["genome_assembly"] = file_analysis["genome_assembly"]

        # Convert set to list for JSON serialization
        analysis["chromosomes"] = list(analysis["chromosomes"])

        # Determine biological context
        analysis["biological_context"] = self._determine_biological_context(analysis)

        return analysis

    def _analyze_genomic_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Analyze a single genomic file.

        Args:
            file_path: Path to the genomic file

        Returns:
            Dictionary with file analysis results or None if analysis fails
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return None

            file_analysis = {
                "file_path": str(file_path),
                "file_name": path.name,
                "file_size": path.stat().st_size,
                "file_type": self._detect_genomic_file_type(path),
                "analysis_timestamp": None,
            }

            # Analyze based on file type
            if file_analysis["file_type"] == "fasta":
                file_analysis.update(self._analyze_fasta_file(path))
            elif file_analysis["file_type"] == "fastq":
                file_analysis.update(self._analyze_fastq_file(path))
            elif file_analysis["file_type"] == "vcf":
                file_analysis.update(self._analyze_vcf_file(path))
            elif file_analysis["file_type"] == "bed":
                file_analysis.update(self._analyze_bed_file(path))
            elif file_analysis["file_type"] == "gtf":
                file_analysis.update(self._analyze_gtf_file(path))
            elif file_analysis["file_type"] == "bam":
                file_analysis.update(self._analyze_bam_file(path))

            return file_analysis

        except Exception as e:
            return {"error": str(e), "file_path": file_path}

    def _detect_genomic_file_type(self, file_path: Path) -> str:
        """
        Detect the type of genomic file based on extension and content.

        Args:
            file_path: Path to the file

        Returns:
            Detected file type
        """
        extension = file_path.suffix.lower().lstrip(".")

        # Map extensions to file types
        extension_mapping = {
            "fasta": "fasta",
            "fa": "fasta",
            "fastq": "fastq",
            "fq": "fastq",
            "vcf": "vcf",
            "bed": "bed",
            "gtf": "gtf",
            "gff": "gtf",
            "gff3": "gtf",
            "bam": "bam",
            "sam": "sam",
            "bw": "bigwig",
            "bigwig": "bigwig",
            "bb": "bigbed",
            "bigbed": "bigbed",
        }

        if extension in extension_mapping:
            return extension_mapping[extension]

        # Try to detect from content
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                first_line = f.readline().strip()

                if first_line.startswith(">"):
                    return "fasta"
                elif first_line.startswith("@"):
                    return "fastq"
                elif first_line.startswith("##"):
                    return "vcf"
                elif first_line.startswith("track"):
                    return "bed"
                elif "\t" in first_line and len(first_line.split("\t")) >= 3:
                    return "gtf"
                else:
                    return "unknown"
        except (UnicodeDecodeError, PermissionError, OSError):
            # Binary file
            if extension in ["bam", "sam", "bw", "bb"]:
                return extension
            else:
                return "unknown"

    def _analyze_fasta_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze a FASTA file."""
        analysis = {
            "has_sequence_data": True,
            "sequence_count": 0,
            "total_length": 0,
            "average_length": 0,
            "gc_content": 0,
            "genome_assembly": None,
        }

        try:
            with open(file_path, "r") as f:
                sequences = []
                current_seq = ""
                current_header = ""

                for line in f:
                    line = line.strip()
                    if line.startswith(">"):
                        if current_seq:
                            sequences.append((current_header, current_seq))
                        current_header = line[1:]
                        current_seq = ""
                    else:
                        current_seq += line

                # Add the last sequence
                if current_seq:
                    sequences.append((current_header, current_seq))

                analysis["sequence_count"] = len(sequences)
                analysis["total_length"] = sum(len(seq) for _, seq in sequences)
                if sequences:
                    analysis["average_length"] = analysis["total_length"] / len(sequences)

                # Calculate GC content
                if analysis["total_length"] > 0:
                    total_gc = sum(seq.count("G") + seq.count("C") for _, seq in sequences)
                    analysis["gc_content"] = total_gc / analysis["total_length"]

                # Try to detect genome assembly from headers
                for header, _ in sequences[:10]:  # Check first 10 sequences
                    if any(assembly in header.upper() for assembly in self.GENOME_ASSEMBLIES.keys()):
                        for assembly in self.GENOME_ASSEMBLIES.keys():
                            if assembly.upper() in header.upper():
                                analysis["genome_assembly"] = assembly
                                break
                        if analysis["genome_assembly"]:
                            break

        except Exception as e:
            analysis["error"] = str(e)

        return analysis

    def _analyze_fastq_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze a FASTQ file."""
        analysis = {
            "has_sequence_data": True,
            "sequence_count": 0,
            "total_length": 0,
            "average_length": 0,
            "quality_scores": {"min": 0, "max": 0, "average": 0},
        }

        try:
            with open(file_path, "r") as f:
                line_count = 0
                sequences = []
                qualities = []

                for line in f:
                    line = line.strip()
                    line_count += 1

                    if line_count % 4 == 2:  # Sequence line
                        sequences.append(line)
                    elif line_count % 4 == 0:  # Quality line
                        qualities.append(line)

                analysis["sequence_count"] = len(sequences)
                analysis["total_length"] = sum(len(seq) for seq in sequences)
                if sequences:
                    analysis["average_length"] = analysis["total_length"] / len(sequences)

                # Analyze quality scores
                if qualities:
                    all_quals = []
                    for qual in qualities:
                        all_quals.extend([ord(c) - 33 for c in qual])  # Convert ASCII to quality scores

                    if all_quals:
                        analysis["quality_scores"]["min"] = min(all_quals)
                        analysis["quality_scores"]["max"] = max(all_quals)
                        analysis["quality_scores"]["average"] = sum(all_quals) / len(all_quals)

        except Exception as e:
            analysis["error"] = str(e)

        return analysis

    def _analyze_vcf_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze a VCF file."""
        analysis = {
            "has_variant_data": True,
            "variant_count": 0,
            "chromosomes": set(),
            "sample_count": 0,
            "variant_types": set(),
            "genome_assembly": None,
        }

        try:
            with open(file_path, "r") as f:
                for line in f:
                    line = line.strip()

                    if line.startswith("##"):
                        # Header line
                        if "assembly=" in line:
                            for assembly in self.GENOME_ASSEMBLIES.keys():
                                if assembly in line:
                                    analysis["genome_assembly"] = assembly
                                    break
                    elif line.startswith("#CHROM"):
                        # Column header
                        parts = line.split("\t")
                        analysis["sample_count"] = max(0, len(parts) - 9)  # VCF has 9 fixed columns
                    elif not line.startswith("#"):
                        # Variant line
                        parts = line.split("\t")
                        if len(parts) >= 8:
                            chrom = parts[0]
                            ref = parts[3]
                            alt = parts[4]

                            analysis["chromosomes"].add(chrom)
                            analysis["variant_count"] += 1

                            # Determine variant type
                            if len(ref) == 1 and len(alt) == 1:
                                analysis["variant_types"].add("SNP")
                            elif len(ref) != len(alt):
                                analysis["variant_types"].add("INDEL")
                            else:
                                analysis["variant_types"].add("SUBSTITUTION")

                # Convert set to list for JSON serialization
                analysis["variant_types"] = list(analysis["variant_types"])

        except Exception as e:
            analysis["error"] = str(e)

        return analysis

    def _analyze_bed_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze a BED file."""
        analysis = {
            "has_annotation_data": True,
            "region_count": 0,
            "chromosomes": set(),
            "regions": [],
            "genome_assembly": None,
        }

        try:
            with open(file_path, "r") as f:
                for line in f:
                    line = line.strip()

                    if line.startswith("track"):
                        # Track header
                        if "genome=" in line:
                            for assembly in self.GENOME_ASSEMBLIES.keys():
                                if assembly in line:
                                    analysis["genome_assembly"] = assembly
                                    break
                    elif not line.startswith("#"):
                        # Region line
                        parts = line.split("\t")
                        if len(parts) >= 3:
                            chrom = parts[0]
                            start = int(parts[1])
                            end = int(parts[2])

                            analysis["chromosomes"].add(chrom)
                            analysis["region_count"] += 1
                            analysis["regions"].append({"chromosome": chrom, "start": start, "end": end})

        except Exception as e:
            analysis["error"] = str(e)

        return analysis

    def _analyze_gtf_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze a GTF file."""
        analysis = {
            "has_annotation_data": True,
            "feature_count": 0,
            "chromosomes": set(),
            "feature_types": set(),
            "genes": set(),
            "genome_assembly": None,
        }

        try:
            with open(file_path, "r") as f:
                for line in f:
                    line = line.strip()

                    if line.startswith("#"):
                        # Comment line
                        if "genome=" in line:
                            for assembly in self.GENOME_ASSEMBLIES.keys():
                                if assembly in line:
                                    analysis["genome_assembly"] = assembly
                                    break
                    else:
                        # Feature line
                        parts = line.split("\t")
                        if len(parts) >= 9:
                            chrom = parts[0]
                            feature_type = parts[2]

                            analysis["chromosomes"].add(chrom)
                            analysis["feature_count"] += 1
                            analysis["feature_types"].add(feature_type)

                            # Extract gene information from attributes
                            attributes = parts[8]
                            if "gene_id" in attributes:
                                gene_id = attributes.split('gene_id "')[1].split('"')[0]
                                analysis["genes"].add(gene_id)

                # Convert sets to lists for JSON serialization
                analysis["feature_types"] = list(analysis["feature_types"])
                analysis["genes"] = list(analysis["genes"])

        except Exception as e:
            analysis["error"] = str(e)

        return analysis

    def _analyze_bam_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze a BAM file."""
        analysis = {
            "has_coverage_data": True,
            "read_count": 0,
            "chromosomes": set(),
            "genome_assembly": None,
            "note": "BAM file analysis requires pysam library",
        }

        # Note: Full BAM analysis would require pysam library
        # This is a placeholder for basic file information

        try:
            # Try to get basic file info
            analysis["file_size"] = file_path.stat().st_size

            # Try to detect genome assembly from filename
            filename = file_path.name.lower()
            for assembly in self.GENOME_ASSEMBLIES.keys():
                if assembly in filename:
                    analysis["genome_assembly"] = assembly
                    break

        except Exception as e:
            analysis["error"] = str(e)

        return analysis

    def _determine_biological_context(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determine the biological context of the genomic data.

        Args:
            analysis: Genomic analysis results

        Returns:
            Dictionary with biological context information
        """
        context = {
            "organism": "Unknown",
            "data_type": "Unknown",
            "analysis_type": "Unknown",
            "complexity": "Low",
        }

        # Determine organism from genome assembly
        if analysis.get("genome_assembly"):
            assembly = analysis["genome_assembly"]
            if assembly.startswith("hg"):
                context["organism"] = "Human"
            elif assembly.startswith("mm"):
                context["organism"] = "Mouse"
            elif assembly.startswith("rn"):
                context["organism"] = "Rat"
            elif assembly.startswith("dm"):
                context["organism"] = "Fruit Fly"
            elif assembly.startswith("ce"):
                context["organism"] = "Worm"
            elif assembly.startswith("sac"):
                context["organism"] = "Yeast"

        # Determine data type
        if analysis.get("has_sequence_data"):
            context["data_type"] = "Sequencing Data"
        elif analysis.get("has_variant_data"):
            context["data_type"] = "Variant Data"
        elif analysis.get("has_annotation_data"):
            context["data_type"] = "Annotation Data"
        elif analysis.get("has_coverage_data"):
            context["data_type"] = "Coverage Data"

        # Determine analysis type
        if analysis.get("has_variant_data") and analysis.get("has_annotation_data"):
            context["analysis_type"] = "Variant Analysis"
        elif analysis.get("has_sequence_data") and analysis.get("has_coverage_data"):
            context["analysis_type"] = "Expression Analysis"
        elif analysis.get("has_annotation_data"):
            context["analysis_type"] = "Annotation Analysis"
        elif analysis.get("has_sequence_data"):
            context["analysis_type"] = "Sequence Analysis"

        # Determine complexity
        file_count = analysis.get("genomic_file_count", 0)
        if file_count > 10:
            context["complexity"] = "High"
        elif file_count > 5:
            context["complexity"] = "Medium"
        else:
            context["complexity"] = "Low"

        return context

    def get_genomic_summary(self, genomic_files: List[str]) -> Dict[str, Any]:
        """
        Get a comprehensive summary of genomic files.

        Args:
            genomic_files: List of paths to genomic files

        Returns:
            Dictionary with genomic summary
        """
        analysis = self.analyze_genomic_content(genomic_files)

        summary = {
            "summary": analysis,
            "recommendations": self._generate_recommendations(analysis),
            "visualization_suggestions": self._suggest_visualizations(analysis),
        }

        return summary

    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on genomic analysis."""
        recommendations = []

        if analysis.get("has_variant_data"):
            recommendations.append("Consider creating variant tracks for IGV visualization")

        if analysis.get("has_coverage_data"):
            recommendations.append("Coverage plots would be useful for this dataset")

        if analysis.get("has_annotation_data"):
            recommendations.append("Gene annotation tracks will enhance the visualization")

        if analysis.get("has_sequence_data"):
            recommendations.append("Sequence views can help with quality assessment")

        if not analysis.get("genome_assembly"):
            recommendations.append("Genome assembly information would improve visualization accuracy")

        return recommendations

    def _suggest_visualizations(self, analysis: Dict[str, Any]) -> List[str]:
        """Suggest appropriate visualizations based on genomic content."""
        suggestions = []

        if analysis.get("has_variant_data"):
            suggestions.extend(["variant_view", "coverage_plot"])

        if analysis.get("has_coverage_data"):
            suggestions.append("coverage_plot")

        if analysis.get("has_annotation_data"):
            suggestions.append("genome_track")

        if analysis.get("has_sequence_data"):
            suggestions.append("sequence_view")

        if len(analysis.get("chromosomes", [])) > 1:
            suggestions.append("multi_chromosome_view")

        return list(set(suggestions))  # Remove duplicates
