"""Orchestrate candidate evaluation, artifact writing, and batch summaries."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import pandas as pd

from factor_autoresearch import __version__
from factor_autoresearch.artifacts import ArtifactWriter
from factor_autoresearch.calculator import ExpressionValidationError, FactorCalc
from factor_autoresearch.candidates import Candidate, InvalidCandidateRecord, load_candidate_batch
from factor_autoresearch.config import ExperimentConfig
from factor_autoresearch.context import EvaluationContext
from factor_autoresearch.data_loader import DataLoader, DatasetBundle
from factor_autoresearch.diagnostics import DIAGNOSTIC_COLUMNS, build_candidate_diagnostics
from factor_autoresearch.gate import GateDecision, apply_candidate_gate
from factor_autoresearch.logging_config import configure_logging
from factor_autoresearch.metrics import MetricsResult, compute_candidate_metrics
from factor_autoresearch.preprocess import preprocess_factor
from factor_autoresearch.registry import RegistryWriter

LOGGER = logging.getLogger(__name__)

RESULT_TOP_LEVEL_KEYS = [
    "id",
    "status",
    "failure_bucket",
    "failed_rules",
    "best_horizon",
    "best_horizon_score",
    "signal_direction",
    "details",
    "metrics",
]


@dataclass(frozen=True)
class EvaluationArtifacts:
    run_dir: Path
    results: list[dict[str, Any]]


def _sha256_file(path: Path) -> str:
    return f"sha256:{sha256(path.read_bytes()).hexdigest()}"


def _hash_gate_config(config: ExperimentConfig) -> str:
    payload = {"gate": config.gate.as_dict()}
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return f"sha256:{sha256(canonical.encode('utf-8')).hexdigest()}"


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
    calc = FactorCalc(config)
    candidates, invalid_records = load_candidate_batch(candidates_path, config)
    results = _invalid_results_from_records(invalid_records)
    for candidate in candidates:
        try:
            metadata = calc.validate_candidate(candidate)
        except ExpressionValidationError as exc:
            results.append(
                _normalize_result(
                    {
                        "id": candidate.candidate_id,
                        "status": "invalid",
                        "failure_bucket": "validate_failed",
                        "details": {"message": str(exc)},
                    }
                )
            )
            continue
        results.append(
            _normalize_result(
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
        )
    return results


class Evaluator:
    def __init__(self, context: EvaluationContext) -> None:
        self.context = context
        self.factor_calc = FactorCalc(context.config)
        self.loader = DataLoader(config=context.config, dataset_path=context.dataset_path)
        self.registry = RegistryWriter(context.registry_path)
        self.artifacts = ArtifactWriter(context)

    def evaluate_batch(self) -> EvaluationArtifacts:
        dataset = self.loader.load()
        candidates, invalid_records = load_candidate_batch(
            self.context.candidates_path, self.context.config
        )
        self.artifacts.prepare_run_dir()
        configure_logging(
            run_dir=self.context.run_dir,
            verbose=self.context.verbose,
            quiet=self.context.quiet,
        )
        LOGGER.info(
            "starting evaluation batch",
            extra={"run_id": self.context.run_id, "stage": "batch"},
        )

        manifest = self._build_run_manifest(len(candidates) + len(invalid_records), dataset.manifest)
        self.artifacts.write_manifest(manifest)

        results = self._collect_invalid_results(invalid_records)
        metric_frames: list[pd.DataFrame] = []
        ic_frames: list[pd.DataFrame] = []
        diagnostics_frames: list[pd.DataFrame] = []

        for candidate in candidates:
            LOGGER.info(
                "evaluating candidate",
                extra={
                    "run_id": self.context.run_id,
                    "candidate_id": candidate.candidate_id,
                    "stage": "candidate",
                },
            )
            result, metrics_result, diagnostics_frame = self.evaluate_candidate(candidate, dataset)
            results.append(result)
            self._append_metrics_frames(metrics_result, metric_frames, ic_frames)
            if diagnostics_frame is not None and not diagnostics_frame.empty:
                diagnostics_frames.append(diagnostics_frame)

        metrics_frame, ic_series_frame = self._combine_metric_frames(metric_frames, ic_frames)
        diagnostics_frame = (
            pd.concat(diagnostics_frames, ignore_index=True)
            if diagnostics_frames
            else pd.DataFrame(columns=DIAGNOSTIC_COLUMNS)
        )
        self._write_batch_outputs(
            results=results,
            metrics_frame=metrics_frame,
            ic_series_frame=ic_series_frame,
            diagnostics_frame=diagnostics_frame,
            dataset_manifest=dataset.manifest,
        )
        LOGGER.info(
            "evaluation batch completed",
            extra={"run_id": self.context.run_id, "stage": "batch"},
        )
        return EvaluationArtifacts(run_dir=self.context.run_dir, results=results)

    def evaluate_candidate(
        self,
        candidate: Candidate,
        dataset: DatasetBundle,
    ) -> tuple[dict[str, Any], MetricsResult | None, pd.DataFrame | None]:
        try:
            metadata = self.factor_calc.validate_candidate(candidate)
        except ExpressionValidationError as exc:
            return (
                _normalize_result(
                    {
                        "id": candidate.candidate_id,
                        "status": "invalid",
                        "failure_bucket": "validate_failed",
                        "details": {"message": str(exc)},
                    }
                ),
                None,
                None,
            )

        try:
            raw_factor = self.factor_calc.calculate(candidate, dataset)
            processed_factor = preprocess_factor(raw_factor, dataset, self.context.config)
            metrics_result = compute_candidate_metrics(
                candidate_id=candidate.candidate_id,
                factor=processed_factor,
                dataset=dataset,
                config=self.context.config,
                complexity_score=metadata.complexity_score,
                expected_direction=candidate.expected_direction,
            )
            diagnostics_frame = build_candidate_diagnostics(
                candidate_id=candidate.candidate_id,
                factor=processed_factor,
                dataset=dataset,
                config=self.context.config,
            )
            decision = apply_candidate_gate(candidate, metrics_result, self.context.config)
            factor_values_path = self.artifacts.write_factor_values(
                candidate.candidate_id,
                raw_factor,
                processed_factor,
            )
            if decision.passed:
                self.registry.append_passed(
                    candidate=candidate,
                    decision=decision,
                    metrics_result=metrics_result,
                    context=self.context,
                    factor_values_path=factor_values_path,
                )
            return (
                self._result_from_decision(candidate, decision, metrics_result),
                metrics_result,
                diagnostics_frame,
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception(
                "candidate runtime error",
                extra={
                    "run_id": self.context.run_id,
                    "candidate_id": candidate.candidate_id,
                    "stage": "candidate",
                },
            )
            return (
                _normalize_result(
                    {
                        "id": candidate.candidate_id,
                        "status": "error",
                        "failure_bucket": "runtime_error",
                        "details": {"message": str(exc)},
                    }
                ),
                None,
                None,
            )

    def _build_run_manifest(
        self, candidate_count: int, dataset_manifest: dict[str, Any]
    ) -> dict[str, Any]:
        gate_config_hash = getattr(self.context.config, "gate_config_hash", None) or _hash_gate_config(
            self.context.config
        )
        return {
            "run_id": self.context.run_id,
            "experiment_id": self.context.config.experiment_id,
            "dataset_id": self.context.config.dataset_id,
            "config_hash": self.context.config.config_hash,
            "gate_config_hash": gate_config_hash,
            "gate_version": self.context.config.gate.version,
            "candidate_file_hash": _sha256_file(self.context.candidates_path),
            "tool_version": __version__,
            "candidate_count": candidate_count,
            "dataset_manifest": dataset_manifest,
            "preprocess": {
                "winsorize_mad_scale": self.context.config.preprocess.winsorize_mad_scale,
                "size_exposure": self.context.config.preprocess.size_exposure,
            },
        }

    def _result_from_decision(
        self,
        candidate: Candidate,
        decision: GateDecision,
        metrics_result: MetricsResult,
    ) -> dict[str, Any]:
        return _normalize_result(
            {
                "id": candidate.candidate_id,
                "status": decision.status,
                "failure_bucket": decision.failure_bucket,
                "failed_rules": decision.failed_rules,
                "best_horizon": decision.best_horizon,
                "best_horizon_score": decision.best_horizon_score,
                "signal_direction": decision.signal_direction,
                "details": decision.details,
                "metrics": metrics_result.aggregate,
            }
        )

    def _collect_invalid_results(
        self, invalid_records: list[InvalidCandidateRecord]
    ) -> list[dict[str, Any]]:
        return _invalid_results_from_records(invalid_records)

    def _append_metrics_frames(
        self,
        metrics_result: MetricsResult | None,
        metric_frames: list[pd.DataFrame],
        ic_frames: list[pd.DataFrame],
    ) -> None:
        if metrics_result is None:
            return
        metric_frames.append(metrics_result.horizon_rows)
        ic_frames.append(metrics_result.ic_series)

    def _combine_metric_frames(
        self,
        metric_frames: list[pd.DataFrame],
        ic_frames: list[pd.DataFrame],
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        metrics_frame = pd.concat(metric_frames, ignore_index=True) if metric_frames else pd.DataFrame()
        ic_series_frame = pd.concat(ic_frames, ignore_index=True) if ic_frames else pd.DataFrame()
        return metrics_frame, ic_series_frame

    def _write_batch_outputs(
        self,
        *,
        results: list[dict[str, Any]],
        metrics_frame: pd.DataFrame,
        ic_series_frame: pd.DataFrame,
        diagnostics_frame: pd.DataFrame,
        dataset_manifest: dict[str, Any],
    ) -> None:
        self.artifacts.write_results(results, metrics_frame, ic_series_frame, diagnostics_frame)
        summary_text = self._render_summary(results, dataset_manifest)
        self.artifacts.write_summary(summary_text)

    def _render_summary(
        self,
        results: list[dict[str, Any]],
        dataset_manifest: dict[str, Any],
    ) -> str:
        counts = {
            "evaluated": len(results),
            "passed": sum(item["status"] == "candidate_pass" for item in results),
            "failed": sum(item["status"] == "candidate_fail" for item in results),
            "invalid": sum(item["status"] == "invalid" for item in results),
            "errors": sum(item["status"] == "error" for item in results),
        }
        failed_rule_counts: dict[str, int] = {}
        for result in results:
            for rule in result.get("failed_rules", []):
                failed_rule_counts[rule] = failed_rule_counts.get(rule, 0) + 1

        passed_results = [item for item in results if item["status"] == "candidate_pass"]

        lines = [
            f"# Run {self.context.run_id} Summary",
            "",
            "## Dataset",
            f"- dataset_id: {dataset_manifest['dataset_id']}",
            f"- experiment_id: {dataset_manifest['experiment_id']}",
            f"- universe: {dataset_manifest['universe']}",
            f"- date_range: {dataset_manifest['date_start']} to {dataset_manifest['date_end']}",
            "",
            "## Batch Result",
            *(f"- {key}: {value}" for key, value in counts.items()),
            "",
            "## Candidate Results",
            "| id | status | best_horizon | score | failed_rules | failure_bucket |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for result in results:
            failed_rules = ",".join(result.get("failed_rules", [])) or "-"
            score = result.get("best_horizon_score")
            score_text = "-" if score is None else str(score)
            lines.append(
                "| {id} | {status} | {best_horizon} | {score} | {failed_rules} | {failure_bucket} |".format(
                    id=result["id"],
                    status=result["status"],
                    best_horizon=result.get("best_horizon") or "-",
                    score=score_text,
                    failed_rules=failed_rules,
                    failure_bucket=result.get("failure_bucket") or "-",
                )
            )

        lines.extend(["", "## Failed Rules Summary"])
        if failed_rule_counts:
            lines.append("| rule | count |")
            lines.append("| --- | --- |")
            for rule, count in sorted(failed_rule_counts.items(), key=lambda item: (-item[1], item[0])):
                lines.append(f"| {rule} | {count} |")
        else:
            lines.append("- none")

        lines.extend(["", "## Passed Candidates"])
        if passed_results:
            lines.append("| id | best_horizon | score | signal_direction |")
            lines.append("| --- | --- | --- | --- |")
            for result in passed_results:
                lines.append(
                    "| {id} | {best_horizon} | {score} | {signal_direction} |".format(
                        id=result["id"],
                        best_horizon=result.get("best_horizon") or "-",
                        score=result.get("best_horizon_score"),
                        signal_direction=result.get("signal_direction") or "-",
                    )
                )
        else:
            lines.append("- none")

        lines.extend(
            [
                "",
                "## Diagnostics",
                f"- {self.context.diagnostics_path}",
            ]
        )
        return "\n".join(lines) + "\n"


def _normalize_result(payload: dict[str, Any]) -> dict[str, Any]:
    result = {key: None for key in RESULT_TOP_LEVEL_KEYS}
    result["failed_rules"] = []
    result["details"] = {}
    result["metrics"] = {}
    result.update(payload)
    if result["failed_rules"] is None:
        result["failed_rules"] = []
    if result["details"] is None:
        result["details"] = {}
    if result["metrics"] is None:
        result["metrics"] = {}
    return result


def _invalid_results_from_records(invalid_records: list[InvalidCandidateRecord]) -> list[dict[str, Any]]:
    return [
        _normalize_result(
            {
                "id": record.candidate_id,
                "status": "invalid",
                "failure_bucket": record.failure_bucket,
                "details": record.details,
            }
        )
        for record in invalid_records
    ]
