"""Artifact writing helpers for evaluation runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from factor_autoresearch.context import EvaluationContext


class ArtifactWriter:
    """Centralize run artifact directory preparation and file writes."""

    def __init__(self, context: EvaluationContext) -> None:
        self.context = context

    def prepare_run_dir(self) -> Path:
        self.context.factors_dir.mkdir(parents=True, exist_ok=True)
        self.context.results_dir.mkdir(parents=True, exist_ok=True)
        self.context.logs_dir.mkdir(parents=True, exist_ok=True)
        return self.context.run_dir

    def write_manifest(self, payload: dict[str, Any]) -> Path:
        self.context.run_dir.mkdir(parents=True, exist_ok=True)
        with self.context.manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        return self.context.manifest_path

    def write_summary(self, text: str) -> Path:
        self.context.run_dir.mkdir(parents=True, exist_ok=True)
        self.context.summary_path.write_text(text, encoding="utf-8")
        return self.context.summary_path

    def write_factor_values(
        self,
        candidate_id: str,
        raw_factor: pd.Series,
        processed_factor: pd.Series,
    ) -> Path:
        self.context.factors_dir.mkdir(parents=True, exist_ok=True)
        factor_frame = pd.DataFrame(
            {
                "trade_date": raw_factor.index.get_level_values("trade_date"),
                "ts_code": raw_factor.index.get_level_values("ts_code"),
                "raw_factor": raw_factor.to_numpy(),
                "factor": processed_factor.to_numpy(),
            }
        )
        output_path = self.context.factors_dir / f"{candidate_id}.parquet"
        factor_frame.to_parquet(output_path, index=False)
        return output_path

    def write_results(
        self,
        results: list[dict[str, Any]],
        metrics_frame: pd.DataFrame,
        ic_series_frame: pd.DataFrame,
    ) -> dict[str, Path]:
        self.context.results_dir.mkdir(parents=True, exist_ok=True)
        results_path = self.context.results_dir / "candidate_results.jsonl"
        with results_path.open("w", encoding="utf-8") as handle:
            for result in results:
                handle.write(json.dumps(result, ensure_ascii=False) + "\n")
        metrics_path = self.context.results_dir / "metrics.parquet"
        ic_series_path = self.context.results_dir / "ic_series.parquet"
        metrics_frame.to_parquet(metrics_path, index=False)
        ic_series_frame.to_parquet(ic_series_path, index=False)
        return {
            "results": results_path,
            "metrics": metrics_path,
            "ic_series": ic_series_path,
        }
