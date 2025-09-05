"""
File Analyzer for Quilt Package Visualization

This module analyzes package files to determine types, structure, and organization
for automatic visualization generation.
"""

import os
from pathlib import Path
from typing import List, Dict, Set
import mimetypes


class FileAnalyzer:
    """Analyzes file types and structure in Quilt packages."""

    # Data file extensions
    DATA_EXTENSIONS = {
        "csv",
        "tsv",
        "xlsx",
        "xls",
        "json",
        "parquet",
        "h5",
        "hdf5",
        "feather",
        "arrow",
        "pickle",
        "pkl",
        "npy",
        "npz",
    }

    # Genomic file extensions
    GENOMIC_EXTENSIONS = {
        "bam",
        "sam",
        "vcf",
        "bed",
        "gtf",
        "gff",
        "gff3",
        "fasta",
        "fa",
        "fastq",
        "fq",
        "bw",
        "bigwig",
        "bb",
        "bigbed",
        "maf",
        "ped",
        "map",
    }

    # Image file extensions
    IMAGE_EXTENSIONS = {
        "png",
        "jpg",
        "jpeg",
        "gif",
        "bmp",
        "tiff",
        "tif",
        "svg",
        "webp",
    }

    # Text file extensions
    TEXT_EXTENSIONS = {"txt", "md", "rst", "log", "out", "err", "sh", "py", "r", "sql"}

    def __init__(self):
        """Initialize the file analyzer."""
        # Initialize mimetypes
        mimetypes.init()

    def analyze_file_types(self, package_path: Path) -> Dict[str, List[str]]:
        """
        Analyze and categorize files by type in the package.

        Args:
            package_path: Path to the package directory

        Returns:
            Dictionary mapping file types to lists of file paths
        """
        file_types = {"data": [], "genomic": [], "image": [], "text": [], "other": []}

        for file_path in package_path.rglob("*"):
            if file_path.is_file():
                file_type = self._categorize_file(file_path)
                if file_type in file_types:
                    file_types[file_type].append(str(file_path))
                else:
                    file_types["other"].append(str(file_path))

        return file_types

    def find_data_files(self, package_path: Path) -> List[str]:
        """Find all data files in the package."""
        return self._find_files_by_extensions(package_path, self.DATA_EXTENSIONS)

    def find_genomic_files(self, package_path: Path) -> List[str]:
        """Find all genomic files in the package."""
        return self._find_files_by_extensions(package_path, self.GENOMIC_EXTENSIONS)

    def find_image_files(self, package_path: Path) -> List[str]:
        """Find all image files in the package."""
        return self._find_files_by_extensions(package_path, self.IMAGE_EXTENSIONS)

    def find_text_files(self, package_path: Path) -> List[str]:
        """Find all text files in the package."""
        return self._find_files_by_extensions(package_path, self.TEXT_EXTENSIONS)

    def _categorize_file(self, file_path: Path) -> str:
        """
        Categorize a file based on its extension and content.

        Args:
            file_path: Path to the file

        Returns:
            Category string: 'data', 'genomic', 'image', 'text', or 'other'
        """
        extension = file_path.suffix.lower().lstrip(".")

        if extension in self.DATA_EXTENSIONS:
            return "data"
        elif extension in self.GENOMIC_EXTENSIONS:
            return "genomic"
        elif extension in self.IMAGE_EXTENSIONS:
            return "image"
        elif extension in self.TEXT_EXTENSIONS:
            return "text"
        else:
            # Try to determine type from content
            return self._detect_file_type_by_content(file_path)

    def _detect_file_type_by_content(self, file_path: Path) -> str:
        """
        Detect file type by examining file content.

        Args:
            file_path: Path to the file

        Returns:
            Detected file type category
        """
        try:
            # Check if it's a text file by trying to read as text
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                first_line = f.readline().strip()

                # Check for common file signatures
                if first_line.startswith("@"):
                    return "genomic"  # FASTQ or similar
                elif first_line.startswith(">"):
                    return "genomic"  # FASTA
                elif first_line.startswith("##"):
                    return "genomic"  # VCF header
                elif first_line.startswith("track"):
                    return "genomic"  # BED track
                elif first_line.startswith("{") or first_line.startswith("["):
                    return "data"  # JSON
                elif "," in first_line or "\t" in first_line:
                    return "data"  # CSV/TSV
                else:
                    return "text"

        except (UnicodeDecodeError, PermissionError, OSError):
            # Binary file, check extension
            extension = file_path.suffix.lower().lstrip(".")
            if extension in ["bam", "sam", "bw", "bb"]:
                return "genomic"
            elif extension in ["png", "jpg", "jpeg", "gif", "bmp", "tiff"]:
                return "image"
            else:
                return "other"

    def _find_files_by_extensions(self, package_path: Path, extensions: Set[str]) -> List[str]:
        """
        Find files with specific extensions in the package.

        Args:
            package_path: Path to the package directory
            extensions: Set of file extensions to search for

        Returns:
            List of file paths matching the extensions
        """
        files = []
        for file_path in package_path.rglob("*"):
            if file_path.is_file():
                extension = file_path.suffix.lower().lstrip(".")
                if extension in extensions:
                    files.append(str(file_path))
        return files

    def get_file_metadata(self, file_path: str) -> Dict[str, any]:
        """
        Get metadata for a specific file.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary with file metadata
        """
        path = Path(file_path)
        if not path.exists():
            return {}

        try:
            stat = path.stat()
            return {
                "name": path.name,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "extension": path.suffix.lower().lstrip("."),
                "category": self._categorize_file(path),
                "mime_type": mimetypes.guess_type(str(path))[0] or "unknown",
            }
        except (OSError, PermissionError):
            return {}

    def analyze_package_structure(self, package_path: Path) -> Dict[str, any]:
        """
        Analyze the overall structure of the package.

        Args:
            package_path: Path to the package directory

        Returns:
            Dictionary with package structure information
        """
        file_types = self.analyze_file_types(package_path)

        # Count files by type
        counts = {k: len(v) for k, v in file_types.items()}

        # Find largest files
        largest_files = []
        for file_path in package_path.rglob("*"):
            if file_path.is_file():
                try:
                    size = file_path.stat().st_size
                    largest_files.append((str(file_path), size))
                except (OSError, PermissionError):
                    continue

        largest_files.sort(key=lambda x: x[1], reverse=True)

        # Analyze directory structure
        directories = [str(p) for p in package_path.rglob("*") if p.is_dir()]

        return {
            "file_counts": counts,
            "total_files": sum(counts.values()),
            "directories": directories,
            "largest_files": largest_files[:10],  # Top 10 largest files
            "has_data": counts.get("data", 0) > 0,
            "has_genomic": counts.get("genomic", 0) > 0,
            "has_images": counts.get("image", 0) > 0,
            "has_text": counts.get("text", 0) > 0,
        }
