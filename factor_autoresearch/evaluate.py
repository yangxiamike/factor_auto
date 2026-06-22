from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import pandas as pd

from factor_autoresearch import __version__
from factor_autoresearch.calculator import ExpressionValidationError, FactorCalc
from factor_autoresearch.candidates import Candidate, load_candidate_batch
from factor_autoresearch.config import ExperimentConfig
from factor_autoresearch.data_loader import DataLoader, DatasetBundle
from factor_autoresearch.gate import GateDecision, apply_candidate_gate
from factor_autoresearch.logging_config import configure_logging
from factor_autoresearch.metrics import MetricsResult, compute_candidate_metrics
from factor_autoresearch.preprocess import preprocess_factor
from factor_autoresearch.registry import append_registry_record

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class EvaluationArtifacts:
    run_dir: Path
    results: list[dict[str, Any]]


def _sha256_file(path: Path) -> str:
    return f"sha256:{sha256(path.read_bytes()).hexdigest()}"


def validate_dataset_contract(dataset_path: str | Path, config: ExperimentConfig) -> None:
    manifest_path = Path(dataset_path) / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"dataset manifest not found: {manifest_path}")
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("dataset_id") != config.dataset_id:
        raise ValueError("dataset manifest dataset_id does not match experiment config")
    if manifest.get("experiment_id") != config.experiment_id:
        raise ValueError("dataset manifest experiment_id does not match experiment config")


def run_static_validation(
    *,
    candidates_path: str | Path,
    dataset_path: str | Path,
    config: ExperimentConfig,
) -> list[dict[str, Any]]:
    validate_dataset_contract(dataset_path, config)
    calc = FactorCalc()
    candidates, invalid_records = load_candidate_batch(candidates_path, config)
    results: list[dict[str, Any]] = [
        {
            "id": record.candidate_id,
            "status": "invalid",
            "failure_bucket": record.failure_bucket,
            "details": record.details,
        }
        for record in invalid_records
    ]
    for candidate in candidates:
        try:
            metadata = calc.validate_candidate(candidate, config)
        except ExpressionValidationError as exc:
            results.append(
                {
                    "id": candidate.candidate_id,
                    "status": "invalid",
                    "failure_bucket": "validate_failed",
                    "details": {"message": str(exc)},
                }
            )
            continue
        results.append(
            {
                "id": candidate.candidate_id,
                "status": "valid",
                "failure_bucket": None,
                "details": {
                    "complexity_score": metadata.complexity_score,
                    "inferred_lookback": metadata.inferred_lookback,
                },
            }
        )
    return results


class Evaluator:
    def __init__(
        self,
        *,
        config: ExperimentConfig,
        dataset_path: str | Path,
        candidates_path: str | Path,
        registry_path: str | Path,
        runs_dir: str | Path,
        run_id: str,
        verbose: bool,
        quiet: bool = False,
    ) -> None:
        self.config = config
        self.dataset_path = Path(dataset_path)
        self.candidates_path = Path(candidates_path)
        self.registry_path = Path(registry_path)
        self.runs_dir = Path(runs_dir)
        self.run_id = run_id
        self.verbose = verbose
        self.quiet = quiet
        self.run_dir = self.runs_dir / run_id
        self.factor_calc = FactorCalc()
        self.loader = DataLoader()

    def evaluate_batch(self) -> EvaluationArtifacts:
        dataset = self.loader.load(self.dataset_path, self.config)
        candidates, invalid_records = load_candidate_batch(self.candidates_path, self.config)
        self._prepare_run_dir()
        configure_logging(run_dir=self.run_dir, verbose=self.verbose, quiet=self.quiet)
        LOGGER.info(
            "starting evaluation batch",
            extra={"run_id": self.run_id, "stage": "batch"},
        )

        manifest = self._build_run_manifest(len(candidates) + len(invalid_records), dataset.manifest)
        self._write_json(self.run_dir / "manifest.json", manifest)

        results: list[dict[str, Any]] = []
        metric_frames: list[pd.DataFrame] = []
        ic_frames: list[pd.DataFrame] = []

        for record in invalid_records:
            results.append(
                {
                    "id": record.candidate_id,
                    "status": "invalid",
                    "failure_bucket": record.failure_bucket,
                    "details": record.details,
                }
            )

        for candidate in candidates:
            LOGGER.info(
                "evaluating candidate",
                extra={
                    "run_id": self.run_id,
                    "candidate_id": candidate.candidate_id,
                    "stage": "candidate",
                },
            )
            result, metrics_result = self.evaluate_candidate(candidate, dataset)
            results.append(result)
            if metrics_result is not None:
                metric_frames.append(metrics_result.horizon_rows)
                ic_frames.append(metrics_result.ic_series)

        metrics_frame = pd.concat(metric_frames, ignore_index=True) if metric_frames else pd.DataFrame()
        ic_series_frame = pd.concat(ic_frames, ignore_index=True) if ic_frames else pd.DataFrame()
        self._write_results(results, metrics_frame, ic_series_frame)
        summary_text = self._render_summary(results, metrics_frame, dataset.manifest)
        (self.run_dir / "summary.md").write_text(summary_text, encoding="utf-8")
        LOGGER.info(
            "evaluation batch completed",
            extra={"run_id": self.run_id, "stage": "batch"},
        )
        return EvaluationArtifacts(run_dir=self.run_dir, results=results)

    def evaluate_candidate(self, candidate: Candidate, dataset: DatasetBundle) -> tuple[dict[str, Any], MetricsResult | None]:
        try:
            metadata = self.factor_calc.validate_candidate(candidate, self.config)
        except ExpressionValidationError as exc:
            return (
                {
                    "id": candidate.candidate_id,
                    "status": "invalid",
                    "failure_bucket": "validate_failed",
                    "details": {"message": str(exc)},
                },
                None,
            )

        try:
            raw_factor = self.factor_calc.calculate(candidate, dataset, self.config)
            processed_factor = preprocess_factor(raw_factor, dataset, self.config)
            metrics_result = compute_candidate_metrics(
                candidate_id=candidate.candidate_id,
                factor=processed_factor,
                dataset=dataset,
                config=self.config,
                complexity_score=metadata.complexity_score,
            )
            decision = apply_candidate_gate(candidate, metrics_result, self.config)
            factor_values_path = self._write_factor_values(candidate, raw_factor, processed_factor)
            if decision.passed:
                append_registry_record(
                    registry_path=self.registry_path,
                    candidate=candidate,
                    config=self.config,
                    decision=decision,
                    metrics_result=metrics_result,
                    run_id=self.run_id,
                    factor_values_path=str(factor_values_path),
                    summary_path=str(self.run_dir / "summary.md"),
                )
            return self._result_from_decision(candidate, decision, metrics_result), metrics_result
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception(
                "candidate runtime error",
                extra={
                    "run_id": self.run_id,
                    "candidate_id": candidate.candidate_id,
                    "stage": "candidate",
                },
            )
            return (
                {
                    "id": candidate.candidate_id,
                    "status": "error",
                    "failure_bucket": "runtime_error",
                    "details": {"message": str(exc)},
                },
                None,
            )

    def _prepare_run_dir(self) -> None:
        (self.run_dir / "factors").mkdir(parents=True, exist_ok=True)
        (self.run_dir / "results").mkdir(parents=True, exist_ok=True)
        (self.run_dir / "logs").mkdir(parents=True, exist_ok=True)

    def _build_run_manifest(self, candidate_count: int, dataset_manifest: dict[str, Any]) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "experiment_id": self.config.experiment_id,
            "dataset_id": self.config.dataset_id,
            "config_hash": self.config.config_hash,
            "candidate_file_hash": _sha256_file(self.candidates_path),
            "gate_version": self.config.gate.version,
            "tool_version": __version__,
            "candidate_count": candidate_count,
            "dataset_manifest": dataset_manifest,
            "preprocess": {
                "winsorize_mad_scale": self.config.preprocess.winsorize_mad_scale,
                "size_exposure": self.config.preprocess.size_exposure,
            },
        }

    def _write_factor_values(
        self,
        candidate: Candidate,
        raw_factor: pd.Series,
        processed_factor: pd.Series,
    ) -> Path:
        factor_frame = pd.DataFrame(
            {
                "trade_date": raw_factor.index.get_level_values("trade_date"),
                "ts_code": raw_factor.index.get_level_values("ts_code"),
                "raw_factor": raw_factor.to_numpy(),
                "factor": processed_factor.to_numpy(),
            }
        )
        output_path = self.run_dir / "factors" / f"{candidate.candidate_id}.parquet"
        factor_frame.to_parquet(output_path, index=False)
        return output_path

    def _result_from_decision(self, candidate: Candidate, decision: GateDecision, metrics_result: MetricsResult) -> dict[str, Any]:
        return {
            "id": candidate.candidate_id,
            "status": decision.status,
            "failure_bucket": decision.failure_bucket,
            "best_horizon": decision.best_horizon,
            "best_horizon_score": decision.best_horizon_score,
            "signal_direction": decision.signal_direction,
            "details": decision.details,
            "metrics": metrics_result.aggregate,
        }

    def _write_results(self, results: list[dict[str, Any]], metrics_frame: pd.DataFrame, ic_series_frame: pd.DataFrame) -> None:
        results_path = self.run_dir / "results" / "candidate_results.jsonl"
        with results_path.open("w", encoding="utf-8") as handle:
            for result in results:
                handle.write(json.dumps(result, ensure_ascii=False) + "\n")
        metrics_frame.to_parquet(self.run_dir / "results" / "metrics.parquet", index=False)
        ic_series_frame.to_parquet(self.run_dir / "results" / "ic_series.parquet", index=False)

    def _render_summary(
        self,
        results: list[dict[str, Any]],
        metrics_frame: pd.DataFrame,
        dataset_manifest: dict[str, Any],
    ) -> str:
        counts = {
            "evaluated": len(results),
            "passed": sum(item["status"] == "candidate_pass" for item in results),
            "failed": sum(item["status"] == "candidate_fail" for item in results),
            "invalid": sum(item["status"] == "invalid" for item in results),
            "errors": sum(item["status"] == "error" for item in results),
        }
        lines = [
            f"# Run {self.run_id} Summary",
            "",
            "## Dataset",
            f"dataset_id: {dataset_manifest['dataset_id']}",
            f"experiment_id: {dataset_manifest['experiment_id']}",
            f"universe: {dataset_manifest['universe']}",
            f"date_range: {dataset_manifest['date_start']} to {dataset_manifest['date_end']}",
            f"features: {', '.join(dataset_manifest['features'])}",
            f"adjustment: {dataset_manifest['adjustment']}",
            f"forward_return_definition: {dataset_manifest['forward_return_definition']}",
            "",
            "## Batch Result",
            *(f"{key}: {value}" for key, value in counts.items()),
            "",
            "## Candidate Results",
            "| id | status | best_horizon | score | failure_bucket | details |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for result in results:
            candidate_line = "| {id} | {status} | {best_horizon} | {score} | {failure_bucket} | {details} |".format(
                id=result["id"],
                status=result["status"],
                best_horizon=result.get("best_horizon", "-"),
                score=result.get("best_horizon_score", "-"),
                failure_bucket=result.get("failure_bucket") or "-",
                details=json.dumps(result.get("details", {}), ensure_ascii=False),
            )
            lines.append(candidate_line)
        if not metrics_frame.empty:
            top = metrics_frame.sort_values("rankic_mean", ascending=False).head(5)
            lines.extend(
                [
                    "",
                    "## Top Horizon Rows",
                    "| id | horizon | ic_mean | rankic_mean | monotonicity | coverage_mean | complexity |",
                    "| --- | --- | --- | --- | --- | --- | --- |",
                ]
            )
            for _, row in top.iterrows():
                top_line = (
                    "| {candidate_id} | {horizon} | {ic_mean:.6f} | {rankic_mean:.6f} | "
                    "{monotonicity:.6f} | {coverage_mean:.6f} | {complexity_score} |"
                )
                lines.append(top_line.format(**row.fillna(0).to_dict()))
        return "\n".join(lines) + "\n"

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
