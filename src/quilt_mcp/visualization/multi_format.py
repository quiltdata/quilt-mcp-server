"""
Multi-format visualization orchestration helpers.

This module coordinates the existing visualization generators to produce
Quilt-ready artifacts (config files plus quilt_summarize entries) across
ECharts, Vega-Lite, Perspective, and IGV formats.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .generators.echarts import EChartsGenerator
from .generators.igv import IGVGenerator
from .generators.perspective import PerspectiveGenerator
from .generators.vega_lite import VegaLiteGenerator

GENOMIC_EXTENSIONS = {"bam", "sam", "vcf", "bcf", "bed", "gff", "gtf", "bigwig", "bw"}
TABULAR_EXTENSIONS = {"csv", "tsv", "parquet", "jsonl", "xlsx", "xls"}
HIERARCHICAL_EXTENSIONS = {"json"}


def _slugify(value: str) -> str:
    """Create filesystem-friendly slug."""
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "visualization"


def _folder_label(folder: Optional[str]) -> str:
    return folder or "root"


@dataclass
class FileRecord:
    key: str
    extension: str
    folder: str
    size: int


class MultiFormatVisualizationGenerator:
    """Orchestrates visualization generation across the supported formats."""

    def __init__(self, default_genome: str = "hg38") -> None:
        self.echarts = EChartsGenerator()
        self.vega = VegaLiteGenerator()
        self.igv = IGVGenerator()
        self.perspective = PerspectiveGenerator()
        self.default_genome = default_genome

    def generate(
        self,
        package_name: str,
        organized_structure: Dict[str, List[Dict[str, Any]]],
        file_types: Dict[str, Any],
        metadata_template: str = "standard",
        viz_preferences: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Generate visualization artifacts for the provided package metadata."""
        if not isinstance(organized_structure, dict):
            return {
                "success": False,
                "error": "organized_structure must be a dictionary of folder -> file list.",
                "visualizations": {},
                "count": 0,
                "quilt_summarize_entries": [],
                "files": {},
                "metadata": {"package_name": package_name},
            }

        records = self._flatten_structure(organized_structure)
        normalized_types = self._normalize_file_types(file_types, records)

        visualizations: Dict[str, Dict[str, Any]] = {}
        quilt_entries: List[Dict[str, Any]] = []
        files: Dict[str, str] = {}

        def add_artifact(
            identifier: str,
            title: str,
            description: str,
            viz_format: str,
            config: Dict[str, Any],
            path: str,
            types: Iterable[Any],
        ) -> None:
            artifact = {
                "id": identifier,
                "title": title,
                "description": description,
                "format": viz_format,
                "config": config,
                "path": path,
                "types": list(types),
            }
            visualizations[identifier] = artifact
            quilt_entries.append(
                {
                    "path": path,
                    "title": title,
                    "description": description,
                    "types": list(types),
                }
            )
            files[path] = json.dumps(config, indent=2)

        self._build_file_type_distribution(package_name, normalized_types, add_artifact)
        self._build_folder_size_chart(package_name, organized_structure, add_artifact)
        self._build_tabular_views(records, viz_preferences or {}, add_artifact)
        self._build_genomic_session(records, add_artifact)

        metadata = {
            "package_name": package_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "detected_file_types": normalized_types,
            "tabular_files": len([r for r in records if r.extension in TABULAR_EXTENSIONS]),
            "genomic_files": len([r for r in records if r.extension in GENOMIC_EXTENSIONS]),
            "metadata_template": metadata_template,
        }

        return {
            "success": True,
            "count": len(visualizations),
            "visualizations": visualizations,
            "quilt_summarize_entries": quilt_entries,
            "files": files,
            "metadata": metadata,
        }

    def _flatten_structure(self, organized_structure: Dict[str, List[Dict[str, Any]]]) -> List[FileRecord]:
        records: List[FileRecord] = []
        for folder, files in organized_structure.items():
            if not isinstance(files, list):
                continue
            for entry in files:
                key = (
                    entry.get("logicalKey")
                    or entry.get("LogicalKey")
                    or entry.get("Key")
                    or entry.get("key")
                )
                if not key:
                    continue
                extension = Path(str(key)).suffix.lstrip(".").lower()
                size = int(entry.get("Size") or entry.get("size") or 0)
                records.append(FileRecord(key=str(key), extension=extension, folder=_folder_label(folder), size=size))
        return records

    def _normalize_file_types(self, file_types: Dict[str, Any], records: List[FileRecord]) -> Dict[str, int]:
        normalized: Dict[str, int] = {}
        for ext, value in (file_types or {}).items():
            if isinstance(value, dict):
                count = value.get("count") or value.get("total")
            else:
                count = value
            if count is None:
                continue
            normalized[ext.lower()] = int(count)

        if not normalized:
            for record in records:
                if record.extension:
                    normalized[record.extension] = normalized.get(record.extension, 0) + 1
        return normalized

    def _build_file_type_distribution(
        self,
        package_name: str,
        file_type_counts: Dict[str, int],
        add_artifact,
    ) -> None:
        if not file_type_counts:
            return

        config = self.echarts.create_pie_chart(
            [{"extension": ext, "count": count} for ext, count in file_type_counts.items()],
            labels="extension",
            values="count",
            title=f"File Type Distribution - {package_name}",
        )
        add_artifact(
            identifier="file_type_distribution",
            title="File Type Distribution",
            description="Interactive breakdown of files by extension.",
            viz_format="echarts",
            config=config,
            path="visualizations/file_type_distribution.echarts.json",
            types=["echarts"],
        )

    def _build_folder_size_chart(
        self,
        package_name: str,
        organized_structure: Dict[str, List[Dict[str, Any]]],
        add_artifact,
    ) -> None:
        folder_stats: List[Dict[str, Any]] = []
        for folder, files in organized_structure.items():
            total_size = sum(int(entry.get("Size") or entry.get("size") or 0) for entry in files or [])
            if total_size <= 0:
                continue
            folder_stats.append(
                {
                    "folder": _folder_label(folder),
                    "size_mb": round(total_size / (1024 * 1024), 4),
                }
            )

        if not folder_stats:
            return

        config = self.vega.create_bar_chart(
            data=folder_stats,
            x_field="folder",
            y_field="size_mb",
            title=f"Folder Size Overview - {package_name}",
            description="Total size (MB) per folder.",
        )
        add_artifact(
            identifier="folder_size_overview",
            title="Folder Size Overview",
            description="Vega-Lite chart of total storage consumption per folder.",
            viz_format="vega-lite",
            config=config,
            path="visualizations/folder_size_overview.vega.json",
            types=["vega-lite"],
        )

    def _build_tabular_views(
        self,
        records: List[FileRecord],
        viz_preferences: Dict[str, Any],
        add_artifact,
    ) -> None:
        tabular_records = [record for record in records if record.extension in TABULAR_EXTENSIONS]
        for record in tabular_records[:3]:
            dataset_name = Path(record.key).name
            slug = _slugify(dataset_name)
            plugin = viz_preferences.get("tabular_plugin", "Datagrid")
            theme = viz_preferences.get("tabular_theme", "Material Light")
            config = self.perspective.create_grid_config(
                dataset_name=dataset_name,
                data_path=record.key,
                approx_size=record.size,
                plugin=plugin,
                theme=theme,
            )
            types = [
                {
                    "name": "perspective",
                    "config": {
                        "plugin": config["plugin"],
                        "settings": config["settings"],
                        "theme": config["theme"],
                    },
                }
            ]
            add_artifact(
                identifier=f"perspective_{slug}",
                title=f"Interactive Table - {dataset_name}",
                description="Interactive data grid with filtering, pivot, and aggregation controls.",
                viz_format="perspective",
                config=config,
                path=f"visualizations/{slug}.perspective.json",
                types=types,
            )

    def _build_genomic_session(self, records: List[FileRecord], add_artifact) -> None:
        genomic_records = [record for record in records if record.extension in GENOMIC_EXTENSIONS]
        if not genomic_records:
            return

        tracks = []
        for record in genomic_records:
            if record.extension in {"bam", "sam", "bigwig", "bw"}:
                tracks.append(self.igv.create_coverage_plot(record.key, regions=[]))
            elif record.extension in {"vcf", "bcf"}:
                tracks.append(self.igv.create_variant_view(record.key, reference=""))
            elif record.extension in {"bed", "gff", "gtf"}:
                tracks.append(self.igv.create_genome_track(record.key, "annotation", {}))

        if not tracks:
            return

        session_config = self.igv.create_igv_session(tracks=tracks, genome=self.default_genome)
        add_artifact(
            identifier="igv_session",
            title="Genomic Tracks Overview",
            description="IGV session including coverage and variant tracks for genomic assets.",
            viz_format="igv",
            config=session_config,
            path="visualizations/genomics_overview.igv.json",
            types=["igv"],
        )
