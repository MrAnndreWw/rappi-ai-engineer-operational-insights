from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    config: Path
    data_raw: Path
    data_processed: Path
    outputs_exports: Path
    outputs_reports: Path
    outputs_figures: Path


def project_paths() -> ProjectPaths:
    root = Path(__file__).resolve().parents[3]
    data = root / "data"
    outputs = root / "outputs"
    return ProjectPaths(
        root=root,
        config=root / "config",
        data_raw=data / "raw",
        data_processed=data / "processed",
        outputs_exports=outputs / "exports",
        outputs_reports=outputs / "reports",
        outputs_figures=outputs / "figures",
    )
