"""
Data Processing Utilities for Quilt Package Visualization

This module provides utilities for loading, preprocessing, and analyzing data
for automatic visualization generation.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import json


class DataProcessor:
    """Handles data loading and preprocessing for visualization."""

    def __init__(self):
        """Initialize the data processor."""
        self.supported_formats = {
            "csv",
            "tsv",
            "json",
            "xlsx",
            "xls",
            "parquet",
            "h5",
            "hdf5",
        }

    def load_csv(self, file_path: str) -> Optional[Any]:
        """
        Load CSV data from file.

        Args:
            file_path: Path to CSV file

        Returns:
            Pandas DataFrame or None if loading fails
        """
        try:
            import pandas as pd

            return pd.read_csv(file_path)
        except ImportError:
            print("pandas not available for CSV loading", file=sys.stderr)
            return None
        except Exception as e:
            print(f"Error loading CSV file {file_path}: {e}", file=sys.stderr)
            return None

    def load_json(self, file_path: str) -> Optional[Any]:
        """
        Load JSON data from file.

        Args:
            file_path: Path to JSON file

        Returns:
            Parsed JSON data or None if loading fails
        """
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading JSON file {file_path}: {e}", file=sys.stderr)
            return None

    def load_excel(self, file_path: str) -> Optional[Any]:
        """
        Load Excel data from file.

        Args:
            file_path: Path to Excel file

        Returns:
            Pandas DataFrame or None if loading fails
        """
        try:
            import pandas as pd

            return pd.read_excel(file_path)
        except ImportError:
            print("pandas not available for Excel loading", file=sys.stderr)
            return None
        except Exception as e:
            print(f"Error loading Excel file {file_path}: {e}", file=sys.stderr)
            return None

    def load_parquet(self, file_path: str) -> Optional[Any]:
        """
        Load Parquet data from file.

        Args:
            file_path: Path to Parquet file

        Returns:
            Pandas DataFrame or None if loading fails
        """
        try:
            import pandas as pd

            return pd.read_parquet(file_path)
        except ImportError:
            print("pandas not available for Parquet loading", file=sys.stderr)
            return None
        except Exception as e:
            print(f"Error loading Parquet file {file_path}: {e}", file=sys.stderr)
            return None

    def detect_file_format(self, file_path: str) -> Optional[str]:
        """
        Detect the format of a data file.

        Args:
            file_path: Path to the file

        Returns:
            Detected format string or None
        """
        if not os.path.exists(file_path):
            return None

        extension = Path(file_path).suffix.lower().lstrip(".")

        if extension in ["csv", "tsv"]:
            return "csv"
        elif extension in ["xlsx", "xls"]:
            return "excel"
        elif extension == "json":
            return "json"
        elif extension == "parquet":
            return "parquet"
        elif extension in ["h5", "hdf5"]:
            return "hdf5"

        # Try to detect from content
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                first_line = f.readline().strip()

                if first_line.startswith("{") or first_line.startswith("["):
                    return "json"
                elif "," in first_line:
                    return "csv"
                elif "\t" in first_line:
                    return "tsv"
                else:
                    return None
        except (UnicodeDecodeError, PermissionError, OSError):
            return None

    def load_data(self, file_path: str) -> Optional[Any]:
        """
        Load data from file with automatic format detection.

        Args:
            file_path: Path to the data file

        Returns:
            Loaded data or None if loading fails
        """
        file_format = self.detect_file_format(file_path)

        if file_format == "csv":
            return self.load_csv(file_path)
        elif file_format == "excel":
            return self.load_excel(file_path)
        elif file_format == "json":
            return self.load_json(file_path)
        elif file_format == "parquet":
            return self.load_parquet(file_path)
        else:
            print(f"Unsupported file format for {file_path}", file=sys.stderr)
            return None

    def preprocess_data(self, data: Any, max_rows: int = 10000) -> Any:
        """
        Preprocess data for visualization.

        Args:
            data: Input data
            max_rows: Maximum number of rows to keep

        Returns:
            Preprocessed data
        """
        if data is None:
            return None

        try:
            import pandas as pd

            if isinstance(data, pd.DataFrame):
                # Limit rows for performance
                if len(data) > max_rows:
                    data = data.sample(n=max_rows, random_state=42)

                # Remove completely empty rows and columns
                data = data.dropna(how="all").dropna(axis=1, how="all")

                # Fill missing values with appropriate defaults
                for col in data.columns:
                    if data[col].dtype == "object":
                        data[col] = data[col].fillna("Unknown")
                    else:
                        data[col] = data[col].fillna(data[col].median())

                return data
            else:
                return data

        except ImportError:
            # pandas not available, return data as-is
            return data
        except Exception as e:
            print(f"Error preprocessing data: {e}", file=sys.stderr)
            return data

    def sample_data(self, data: Any, sample_size: int = 1000) -> Any:
        """
        Sample data for visualization.

        Args:
            data: Input data
            sample_size: Number of samples to take

        Returns:
            Sampled data
        """
        if data is None:
            return None

        try:
            import pandas as pd

            if isinstance(data, pd.DataFrame):
                if len(data) > sample_size:
                    return data.sample(n=sample_size, random_state=42)
                else:
                    return data
            else:
                return data

        except ImportError:
            return data
        except Exception as e:
            print(f"Error sampling data: {e}", file=sys.stderr)
            return data

    def get_data_summary(self, data: Any) -> Dict[str, Any]:
        """
        Get a summary of the data.

        Args:
            data: Input data

        Returns:
            Dictionary with data summary
        """
        if data is None:
            return {"error": "No data provided"}

        try:
            import pandas as pd

            if isinstance(data, pd.DataFrame):
                summary = {
                    "shape": data.shape,
                    "columns": list(data.columns),
                    "dtypes": data.dtypes.to_dict(),
                    "memory_usage": data.memory_usage(deep=True).sum(),
                    "missing_values": data.isnull().sum().to_dict(),
                    "numeric_columns": list(data.select_dtypes(include=["number"]).columns),
                    "categorical_columns": list(data.select_dtypes(include=["object", "category"]).columns),
                    "datetime_columns": list(data.select_dtypes(include=["datetime"]).columns),
                }

                # Add basic statistics for numeric columns
                if summary["numeric_columns"]:
                    summary["numeric_stats"] = data[summary["numeric_columns"]].describe().to_dict()

                return summary
            else:
                return {
                    "type": type(data).__name__,
                    "length": len(data) if hasattr(data, "__len__") else "Unknown",
                    "note": "Non-DataFrame data type",
                }

        except ImportError:
            return {
                "type": type(data).__name__,
                "note": "pandas not available for detailed analysis",
            }
        except Exception as e:
            return {"error": str(e)}

    def validate_data(self, data: Any) -> Dict[str, Any]:
        """
        Validate data for visualization.

        Args:
            data: Input data

        Returns:
            Validation results
        """
        validation = {"valid": True, "errors": [], "warnings": [], "suggestions": []}

        if data is None:
            validation["valid"] = False
            validation["errors"].append("Data is None")
            return validation

        try:
            import pandas as pd

            if isinstance(data, pd.DataFrame):
                # Check if DataFrame is empty
                if data.empty:
                    validation["valid"] = False
                    validation["errors"].append("DataFrame is empty")
                    return validation

                # Check for too many columns
                if len(data.columns) > 100:
                    validation["warnings"].append("Data has many columns (>100), consider subsetting")

                # Check for too many rows
                if len(data) > 100000:
                    validation["warnings"].append("Data has many rows (>100,000), consider sampling")
                    validation["suggestions"].append("Use sample_data() to reduce data size")

                # Check for missing values
                missing_pct = data.isnull().sum().sum() / (len(data) * len(data.columns))
                if missing_pct > 0.5:
                    validation["warnings"].append("Data has many missing values (>50%)")
                    validation["suggestions"].append("Consider data cleaning or imputation")

                # Check for mixed data types
                mixed_types = []
                for col in data.columns:
                    if data[col].dtype == "object":
                        # Check if column contains mixed types
                        unique_types = set(type(val) for val in data[col].dropna())
                        if len(unique_types) > 1:
                            mixed_types.append(col)

                if mixed_types:
                    validation["warnings"].append(f"Columns with mixed data types: {mixed_types}")
                    validation["suggestions"].append("Consider standardizing data types")

            else:
                validation["warnings"].append("Data is not a pandas DataFrame")
                validation["suggestions"].append("Consider converting to DataFrame for better analysis")

        except ImportError:
            validation["warnings"].append("pandas not available for detailed validation")
        except Exception as e:
            validation["errors"].append(f"Validation error: {e}")

        return validation

    def create_sample_dataset(self, size: int = 100) -> Any:
        """
        Create a sample dataset for testing.

        Args:
            size: Number of rows to generate

        Returns:
            Sample DataFrame
        """
        try:
            import pandas as pd
            import numpy as np

            # Generate sample data
            np.random.seed(42)

            data = {
                "category": np.random.choice(["A", "B", "C", "D"], size),
                "value": np.random.normal(100, 20, size),
                "date": pd.date_range("2023-01-01", periods=size, freq="D"),
                "score": np.random.uniform(0, 100, size),
            }

            return pd.DataFrame(data)

        except ImportError:
            print(
                "pandas/numpy not available for sample dataset creation",
                file=sys.stderr,
            )
            return None
        except Exception as e:
            print(f"Error creating sample dataset: {e}", file=sys.stderr)
            return None
