"""
评估编排模块: 负责串联候选因子加载、静态校验、批量评估与结果落盘流程。
"""

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
from factor_autoresearch.candidates import Candidate, load_candidate_batch
from factor_autoresearch.compute_v1.calculator import V1FactorCalc
from factor_autoresearch.config import ExperimentConfig
from factor_autoresearch.context import EvaluationContext
from factor_autoresearch.data_loader import DataLoader, DatasetBundle
from factor_autoresearch.engine.parallel import run_ordered
from factor_autoresearch.gate import GateDecision, apply_candidate_gate
from factor_autoresearch.logging_config import configure_logging
from factor_autoresearch.metrics import MetricsResult, compute_candidate_metrics
from factor_autoresearch.preprocess import preprocess_factor
from factor_autoresearch.registry import RegistryWriter

LOGGER = logging.getLogger(__name__)


# ============== 评估结果结构 ==============
@dataclass(frozen=True)
class EvaluationArtifacts:
    """评估产物: 记录本次评估运行目录与候选结果列表。"""

    run_dir: Path
    results: list[dict[str, Any]]


@dataclass(frozen=True)
class CandidateEvaluation:
    """Single-candidate output before the coordinator writes artifacts."""

    candidate: Candidate
    result: dict[str, Any]
    metrics_result: MetricsResult | None
    raw_factor: pd.Series | None = None
    processed_factor: pd.Series | None = None
    decision: GateDecision | None = None


def _sha256_file(path: Path) -> str:
    """文件哈希: 计算文件内容的 sha256 标识。"""

    return f"sha256:{sha256(path.read_bytes()).hexdigest()}"


# ============== 静态校验入口 ==============
def validate_dataset_contract(dataset_path: str | Path, config: ExperimentConfig) -> None:
    """数据集契约校验: 确认 dataset manifest 与实验配置一致。"""

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
    """静态校验: 批量校验候选表达式并返回有效性结果。"""

    validate_dataset_contract(dataset_path, config)
    calc = FactorCalc(config)
    candidates, invalid_records = load_candidate_batch(candidates_path, config)
    results = _invalid_results_from_records(invalid_records)
    for candidate in candidates:
        try:
            metadata = calc.validate_candidate(candidate)
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


# ============== 评估编排器 ==============
class Evaluator:
    """评估器: 负责执行单个批次的候选评估与产物写出。"""

    def __init__(self, context: EvaluationContext) -> None:
        """初始化: 准备评估上下文依赖与落盘组件。"""

        self.context = context
        self.factor_calc = V1FactorCalc(context.config) if context.engine == "v1" else FactorCalc(context.config)
        self.loader = DataLoader(config=context.config, dataset_path=context.dataset_path)
        self.registry = RegistryWriter(context.registry_path)
        self.artifacts = ArtifactWriter(context)

    def evaluate_batch(self) -> EvaluationArtifacts:
        """批量评估: 执行整批候选因子的加载、评估、汇总与写出。"""

        dataset = self.loader.load()
        candidates, invalid_records = load_candidate_batch(self.context.candidates_path, self.context.config)
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

        for evaluation in self._evaluate_candidates(candidates, dataset):
            result, metrics_result = self._commit_candidate_evaluation(evaluation)
            results.append(result)
            self._append_metrics_frames(metrics_result, metric_frames, ic_frames)

        metrics_frame, ic_series_frame = self._combine_metric_frames(metric_frames, ic_frames)
        self._write_batch_outputs(results, metrics_frame, ic_series_frame, dataset.manifest)
        LOGGER.info(
            "evaluation batch completed",
            extra={"run_id": self.context.run_id, "stage": "batch"},
        )
        return EvaluationArtifacts(run_dir=self.context.run_dir, results=results)

    def _evaluate_candidates(
        self,
        candidates: list[Candidate],
        dataset: DatasetBundle,
    ) -> list[CandidateEvaluation]:
        """Evaluate candidates serially or with ordered candidate-level parallelism."""

        if self.context.engine == "legacy":
            return [self._evaluate_candidate_core(candidate, dataset) for candidate in candidates]

        jobs = int(self.context.jobs) if self.context.jobs != "auto" else "auto"
        ordered = run_ordered(candidates, lambda candidate: self._evaluate_candidate_core(candidate, dataset), jobs)
        evaluations: list[CandidateEvaluation] = []
        for item in ordered:
            if item.ok:
                evaluations.append(item.value)
                continue
            candidate = item.item
            evaluations.append(
                CandidateEvaluation(
                    candidate=candidate,
                    result={
                        "id": candidate.candidate_id,
                        "status": "error",
                        "failure_bucket": "runtime_error",
                        "details": {"message": str(item.error)},
                    },
                    metrics_result=None,
                )
            )
        return evaluations

    def _evaluate_candidate_core(
        self,
        candidate: Candidate,
        dataset: DatasetBundle,
    ) -> CandidateEvaluation:
        """Compute one candidate without writing artifacts or registry records."""

        LOGGER.info(
            "evaluating candidate",
            extra={
                "run_id": self.context.run_id,
                "candidate_id": candidate.candidate_id,
                "stage": "candidate",
            },
        )
        try:
            metadata = self.factor_calc.validate_candidate(candidate)
        except ExpressionValidationError as exc:
            return CandidateEvaluation(
                candidate=candidate,
                result={
                    "id": candidate.candidate_id,
                    "status": "invalid",
                    "failure_bucket": "validate_failed",
                    "details": {"message": str(exc)},
                },
                metrics_result=None,
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
            )
            decision = apply_candidate_gate(candidate, metrics_result, self.context.config)
            return CandidateEvaluation(
                candidate=candidate,
                result=self._result_from_decision(candidate, decision, metrics_result),
                metrics_result=metrics_result,
                raw_factor=raw_factor,
                processed_factor=processed_factor,
                decision=decision,
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
            return CandidateEvaluation(
                candidate=candidate,
                result={
                    "id": candidate.candidate_id,
                    "status": "error",
                    "failure_bucket": "runtime_error",
                    "details": {"message": str(exc)},
                },
                metrics_result=None,
            )

    def _commit_candidate_evaluation(
        self,
        evaluation: CandidateEvaluation,
    ) -> tuple[dict[str, Any], MetricsResult | None]:
        """Return a computed candidate result after coordinator-side artifact work."""

        if (
            evaluation.metrics_result is None
            or evaluation.raw_factor is None
            or evaluation.processed_factor is None
            or evaluation.decision is None
        ):
            return evaluation.result, evaluation.metrics_result

        factor_values_path = self.artifacts.write_factor_values(
            evaluation.candidate.candidate_id,
            evaluation.raw_factor,
            evaluation.processed_factor,
        )
        if evaluation.decision.passed:
            self.registry.append_passed(
                candidate=evaluation.candidate,
                decision=evaluation.decision,
                metrics_result=evaluation.metrics_result,
                context=self.context,
                factor_values_path=factor_values_path,
            )
        return evaluation.result, evaluation.metrics_result

    def evaluate_candidate(
        self,
        candidate: Candidate,
        dataset: DatasetBundle,
    ) -> tuple[dict[str, Any], MetricsResult | None]:
        """单因子评估: 返回候选评估结果，并隔离运行时异常。"""

        return self._commit_candidate_evaluation(self._evaluate_candidate_core(candidate, dataset))

    def _build_run_manifest(self, candidate_count: int, dataset_manifest: dict[str, Any]) -> dict[str, Any]:
        """运行清单: 组装本次评估批次的 manifest 内容。"""

        return {
            "run_id": self.context.run_id,
            "experiment_id": self.context.config.experiment_id,
            "dataset_id": self.context.config.dataset_id,
            "config_hash": self.context.config.config_hash,
            "candidate_file_hash": _sha256_file(self.context.candidates_path),
            "gate_version": self.context.config.gate.version,
            "tool_version": __version__,
            "engine": self.context.engine,
            "jobs": self.context.jobs,
            "candidate_count": candidate_count,
            "dataset_manifest": dataset_manifest,
            "preprocess": {
                "winsorize_mad_scale": self.context.config.preprocess.winsorize_mad_scale,
                "size_exposure": self.context.config.preprocess.size_exposure,
            },
        }

    def _result_from_decision(self, candidate: Candidate, decision: GateDecision, metrics_result: MetricsResult) -> dict[str, Any]:
        """评估结果组装: 把门禁决策与指标汇总成标准结果字典。"""

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

    def _collect_invalid_results(self, invalid_records: list[Any]) -> list[dict[str, Any]]:
        """无效记录收集: 把候选加载期的非法记录转成结果字典。"""

        return _invalid_results_from_records(invalid_records)

    def _append_metrics_frames(
        self,
        metrics_result: MetricsResult | None,
        metric_frames: list[pd.DataFrame],
        ic_frames: list[pd.DataFrame],
    ) -> None:
        """指标帧追加: 把单候选指标结果追加到批量聚合容器。"""

        if metrics_result is None:
            return
        metric_frames.append(metrics_result.horizon_rows)
        ic_frames.append(metrics_result.ic_series)

    def _combine_metric_frames(
        self,
        metric_frames: list[pd.DataFrame],
        ic_frames: list[pd.DataFrame],
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """指标帧合并: 合并批量评估过程中累积的指标明细。"""

        metrics_frame = pd.concat(metric_frames, ignore_index=True) if metric_frames else pd.DataFrame()
        ic_series_frame = pd.concat(ic_frames, ignore_index=True) if ic_frames else pd.DataFrame()
        return metrics_frame, ic_series_frame

    def _write_batch_outputs(
        self,
        results: list[dict[str, Any]],
        metrics_frame: pd.DataFrame,
        ic_series_frame: pd.DataFrame,
        dataset_manifest: dict[str, Any],
    ) -> None:
        """批量结果写出: 统一写出结果明细与 summary 文本。"""

        self.artifacts.write_results(results, metrics_frame, ic_series_frame)
        summary_text = self._render_summary(results, metrics_frame, dataset_manifest)
        self.artifacts.write_summary(summary_text)

    def _render_summary(
        self,
        results: list[dict[str, Any]],
        metrics_frame: pd.DataFrame,
        dataset_manifest: dict[str, Any],
    ) -> str:
        """摘要渲染: 生成评估批次的 markdown 总结文本。"""

        counts = {
            "evaluated": len(results),
            "passed": sum(item["status"] == "candidate_pass" for item in results),
            "failed": sum(item["status"] == "candidate_fail" for item in results),
            "invalid": sum(item["status"] == "invalid" for item in results),
            "errors": sum(item["status"] == "error" for item in results),
        }
        lines = [
            f"# Run {self.context.run_id} Summary",
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


# ============== 评估辅助函数 ==============
def _invalid_results_from_records(invalid_records: list[Any]) -> list[dict[str, Any]]:
    """无效结果转换: 把非法候选记录转换为统一结果结构。"""

    return [
        {
            "id": record.candidate_id,
            "status": "invalid",
            "failure_bucket": record.failure_bucket,
            "details": record.details,
        }
        for record in invalid_records
    ]
