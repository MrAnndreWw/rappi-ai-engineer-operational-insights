from __future__ import annotations

import json
from pathlib import Path

from competitive_intel.analysis.insights import load_normalized_table, top_actionable_insights
from competitive_intel.config import resolve_data_paths
from competitive_intel.utils.paths import project_paths


def run_report_pipeline(*, input_path: Path | None = None) -> int:
    _, outputs_dir = resolve_data_paths()
    reports_dir = outputs_dir / "reports"
    figures_dir = outputs_dir / "figures"
    reports_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    default_input = project_paths().data_processed / "offers_normalized.jsonl"
    path = input_path or default_input

    if not path.exists():
        stub = {"status": "no_input", "expected": str(default_input)}
        out = reports_dir / "report_stub.json"
        out.write_text(json.dumps(stub, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Sin datos de entrada. Escrito: {out}")
        return 0

    df = load_normalized_table(path)
    insights = top_actionable_insights(df, n=5)
    summary = reports_dir / "insights_summary.json"
    summary.write_text(json.dumps(insights, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Escrito: {summary}")
    return 0
