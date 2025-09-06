"""
Data Analyzer for Quilt Package Visualization

This module analyzes data files to understand their structure, content types,
and relationships for automatic visualization generation.
"""

import pandas as pd
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
import numpy as np
from datetime import datetime


class DataAnalyzer:
    """Analyzes data files to determine appropriate visualizations."""

    def __init__(self):
        """Initialize the data analyzer."""
        pass

    def analyze_package_metadata(self, package_path: Path) -> Dict[str, Any]:
        """
        Analyze package metadata and structure.

        Args:
            package_path: Path to the package directory

        Returns:
            Dictionary with package metadata
        """
        metadata = {
            "package_name": package_path.name,
            "package_path": str(package_path),
            "analysis_timestamp": datetime.now().isoformat(),
            "file_count": 0,
            "data_count": 0,
            "genomic_count": 0,
            "image_count": 0,
            "text_count": 0,
            "total_size": 0,
            "has_readme": False,
            "has_metadata": False,
        }

        try:
            # Count files and calculate sizes
            for file_path in package_path.rglob("*"):
                if file_path.is_file():
                    metadata["file_count"] += 1
                    try:
                        metadata["total_size"] += file_path.stat().st_size
                    except (OSError, PermissionError):
                        pass

                    # Check for specific file types
                    if file_path.name.lower() == "readme.md":
                        metadata["has_readme"] = True
                    elif file_path.name.lower() in [
                        "metadata.json",
                        "quilt_summarize.json",
                    ]:
                        metadata["has_metadata"] = True

            # Analyze data files
            data_files = list(package_path.rglob("*.csv")) + list(package_path.rglob("*.tsv"))
            metadata["data_count"] = len(data_files)

            # Analyze genomic files
            genomic_extensions = {
                ".bam",
                ".sam",
                ".vcf",
                ".bed",
                ".gtf",
                ".gff",
                ".fasta",
                ".fastq",
            }
            genomic_files = [f for f in package_path.rglob("*") if f.suffix.lower() in genomic_extensions]
            metadata["genomic_count"] = len(genomic_files)

            # Analyze image files
            image_extensions = {
                ".png",
                ".jpg",
                ".jpeg",
                ".gif",
                ".bmp",
                ".tiff",
                ".svg",
            }
            image_files = [f for f in package_path.rglob("*") if f.suffix.lower() in image_extensions]
            metadata["image_count"] = len(image_files)

            # Analyze text files
            text_extensions = {".txt", ".md", ".rst", ".log", ".py", ".r", ".sql"}
            text_files = [f for f in package_path.rglob("*") if f.suffix.lower() in text_extensions]
            metadata["text_count"] = len(text_files)

        except Exception as e:
            metadata["error"] = str(e)

        return metadata

    def analyze_dataframe(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze a pandas DataFrame to determine visualization options.

        Args:
            df: Pandas DataFrame to analyze

        Returns:
            Dictionary with analysis results
        """
        if df is None or df.empty:
            return {}

        analysis = {
            "shape": df.shape,
            "columns": list(df.columns),
            "dtypes": df.dtypes.to_dict(),
            "has_categorical": False,
            "has_numerical": False,
            "has_temporal": False,
            "has_text": False,
            "categorical_cols": [],
            "numerical_cols": [],
            "temporal_cols": [],
            "text_cols": [],
            "missing_data": df.isnull().sum().to_dict(),
            "unique_counts": {},
            "numerical_stats": {},
            "correlations": {},
        }

        # Analyze each column
        for col in df.columns:
            col_type = df[col].dtype

            # Check for categorical data
            if col_type == "object" or col_type == "category":
                unique_count = df[col].nunique()
                analysis["unique_counts"][col] = unique_count

                if unique_count <= 50:  # Reasonable number for categorical visualization
                    analysis["has_categorical"] = True
                    analysis["categorical_cols"].append(col)
                else:
                    analysis["has_text"] = True
                    analysis["text_cols"].append(col)

            # Check for numerical data
            elif pd.api.types.is_numeric_dtype(col_type):
                analysis["has_numerical"] = True
                analysis["numerical_cols"].append(col)

                # Calculate basic statistics
                col_stats = df[col].describe()
                analysis["numerical_stats"][col] = {
                    "mean": col_stats["mean"],
                    "std": col_stats["std"],
                    "min": col_stats["min"],
                    "max": col_stats["max"],
                    "median": col_stats["50%"],
                }

            # Check for temporal data
            elif pd.api.types.is_datetime64_any_dtype(col_type):
                analysis["has_temporal"] = True
                analysis["temporal_cols"].append(col)

        # Calculate correlations for numerical columns
        if len(analysis["numerical_cols"]) > 1:
            try:
                corr_matrix = df[analysis["numerical_cols"]].corr()
                analysis["correlations"] = corr_matrix.to_dict()
            except Exception:
                pass

        return analysis

    def analyze_csv_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Analyze a CSV file to understand its structure.

        Args:
            file_path: Path to the CSV file

        Returns:
            Dictionary with analysis results or None if analysis fails
        """
        try:
            # Try to read the CSV file
            df = pd.read_csv(file_path, nrows=1000)  # Read first 1000 rows for analysis
            return self.analyze_dataframe(df)
        except Exception as e:
            return {"error": str(e)}

    def analyze_json_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Analyze a JSON file to understand its structure.

        Args:
            file_path: Path to the JSON file

        Returns:
            Dictionary with analysis results or None if analysis fails
        """
        try:
            with open(file_path, "r") as f:
                data = json.load(f)

            analysis = {
                "type": type(data).__name__,
                "size": len(str(data)),
                "has_nested": False,
                "max_depth": 0,
                "key_count": 0,
                "array_length": 0,
            }

            if isinstance(data, dict):
                analysis["key_count"] = len(data)
                analysis["keys"] = list(data.keys())
                analysis["max_depth"] = self._get_max_depth(data)
                analysis["has_nested"] = analysis["max_depth"] > 1

                # Check if it's chartable data
                if self._is_chartable_dict(data):
                    analysis["chartable"] = True
                    analysis["chart_type"] = self._suggest_chart_type(data)
                else:
                    analysis["chartable"] = False

            elif isinstance(data, list):
                analysis["array_length"] = len(data)
                if data and isinstance(data[0], dict):
                    analysis["has_nested"] = True
                    analysis["sample_keys"] = list(data[0].keys()) if data else []

                    # Check if it's chartable data
                    if self._is_chartable_list(data):
                        analysis["chartable"] = True
                        analysis["chart_type"] = self._suggest_chart_type(data)
                    else:
                        analysis["chartable"] = False

            return analysis

        except Exception as e:
            return {"error": str(e)}

    def _get_max_depth(self, obj: Any, current_depth: int = 1) -> int:
        """Calculate the maximum depth of a nested object."""
        if isinstance(obj, dict):
            if not obj:
                return current_depth
            return max(self._get_max_depth(v, current_depth + 1) for v in obj.values())
        elif isinstance(obj, list):
            if not obj:
                return current_depth
            return max(self._get_max_depth(item, current_depth + 1) for item in obj)
        else:
            return current_depth

    def _is_chartable_dict(self, data: Dict[str, Any]) -> bool:
        """Check if a dictionary contains chartable data."""
        if not data:
            return False

        # Check if it's a simple key-value structure
        values = list(data.values())
        if len(values) == 0:
            return False

        # Check if values are numeric
        numeric_count = sum(1 for v in values if isinstance(v, (int, float)) and not isinstance(v, bool))
        return numeric_count >= len(values) * 0.5  # At least 50% numeric

    def _is_chartable_list(self, data: List[Any]) -> bool:
        """Check if a list contains chartable data."""
        if not data or len(data) < 2:
            return False

        # Check if it's a list of dictionaries with consistent structure
        if isinstance(data[0], dict):
            keys = set(data[0].keys())
            if len(keys) >= 2:  # Need at least 2 columns for a chart
                # Check if most items have numeric values for the same keys
                numeric_keys = set()
                for item in data[:100]:  # Check first 100 items
                    if isinstance(item, dict):
                        for key, value in item.items():
                            if isinstance(value, (int, float)) and not isinstance(value, bool):
                                numeric_keys.add(key)

                return len(numeric_keys) >= 2

        return False

    def _suggest_chart_type(self, data: Any) -> str:
        """Suggest an appropriate chart type for the data."""
        if isinstance(data, dict):
            values = list(data.values())
            if len(values) <= 10:
                return "bar_chart"
            else:
                return "line_chart"
        elif isinstance(data, list) and len(data) > 0:
            if isinstance(data[0], dict):
                keys = list(data[0].keys())
                if len(keys) >= 3:
                    return "scatter_plot"
                else:
                    return "line_chart"

        return "bar_chart"

    def get_data_summary(self, file_path: str) -> Dict[str, Any]:
        """
        Get a comprehensive summary of a data file.

        Args:
            file_path: Path to the data file

        Returns:
            Dictionary with data summary
        """
        file_path = Path(file_path)
        if not file_path.exists():
            return {"error": "File does not exist"}

        summary = {
            "file_path": str(file_path),
            "file_name": file_path.name,
            "file_size": file_path.stat().st_size,
            "file_type": file_path.suffix.lower().lstrip("."),
            "analysis_timestamp": datetime.now().isoformat(),
        }

        # Analyze based on file type
        if file_path.suffix.lower() in [".csv", ".tsv"]:
            analysis = self.analyze_csv_file(str(file_path))
            if analysis:
                summary.update(analysis)
        elif file_path.suffix.lower() == ".json":
            analysis = self.analyze_json_file(str(file_path))
            if analysis:
                summary.update(analysis)

        return summary
