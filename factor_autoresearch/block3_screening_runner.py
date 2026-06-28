"""
Block3 screening runner 模块
负责串联区块2样本视图、compute v1 指标、区块3 Gate 和产物写入。
不负责旧 Evaluator 链路，也不在命令层内拼装指标。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import pandas as pd

from factor_autoresearch.block3_screening import Block3GateInputs, apply_block3_screening_gate
from factor_autoresearch.block3_screening_artifacts import Block3ScreeningWriter
from factor_autoresearch.candidates import load_candidate_batch
from factor_autoresearch.compute_v1.calculator import V1FactorCalc
from factor_autoresearch.compute_v1.panel import PanelStore
from factor_autoresearch.compute_v1.preprocess import preprocess_factor_matrix
from factor_autoresearch.compute_v1.screening import Block3ScreeningMetricBundle, compute_block3_screening_metrics
from factor_autoresearch.config import (
    Block3ScreeningConfig,
    ExperimentConfig,
    load_block3_screening_config,
    load_experiment_config,
)
from factor_autoresearch.data_loader import DatasetBundle
from factor_autoresearch.factor_asset_values import load_library_factor_values, save_factor_values
from factor_autoresearch.factor_assets import (
    AssetCandidateRecord,
    get_existing_factor_metrics,
    ingest_block3_batch,
    register_factor_value_scope,
)
from factor_autoresearch.screening_sample import build_screening_sample_view


# ============== 数据结构 ==============
@dataclass(frozen=True)
class Block3ScreeningRunSummary:
    """Block3 运行摘要: 汇总产物路径和决策计数。"""

    output_dir: Path
    evaluation_log_path: Path
    research_factor_library_path: Path
    replacement_queue_path: Path
    total_candidates: int
    admitted_count: int
    reject_count: int
    duplicate_count: int
    replace_candidate_count: int


@dataclass(frozen=True)
class _RuntimeScreeningConfig:
    """运行期筛选配置: 给 compute v1 暴露实验配置，同时保留 Block3 阈值。"""

    experiment_config: ExperimentConfig
    screening_config: Block3ScreeningConfig

    def __getattr__(self, name: str) -> object:
        return getattr(self.screening_config, name)


# ============== 基础辅助函数 ==============
def _hash_preprocess_config(config: ExperimentConfig) -> str:
    """预处理哈希: 稳定追溯 screening 使用的 preprocess 口径。"""

    payload = json.dumps(asdict(config.preprocess), sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return f"sha256:{sha256(payload.encode('utf-8')).hexdigest()}"


def _flatten_metric_bundle(bundle: Block3ScreeningMetricBundle) -> dict[str, object]:
    """拉平 metric bundle: 便于 Gate 与产物层复用。"""

    return {
        **bundle.gate0_metrics,
        **bundle.gate1_metrics,
        **bundle.gate2_metrics,
        **bundle.gate3_metrics,
    }


def _build_candidate_payload(
    candidate: Any,
    bundle: Block3ScreeningMetricBundle,
    *,
    library_value_status: str | None,
) -> dict[str, object]:
    """候选 payload: 统一 writer 所需的基础字段和 Gate 指标。"""

    metrics = _flatten_metric_bundle(bundle)
    if library_value_status is not None:
        metrics["library_value_status"] = library_value_status
    return {
        "candidate_id": candidate.candidate_id,
        "name": candidate.name,
        "expression": candidate.expression,
        "expected_direction": candidate.expected_direction,
        "category": candidate.category,
        "economic_rationale": getattr(candidate, "economic_rationale", ""),
        "metrics": metrics,
        "library_value_status": library_value_status,
        "matched_factor": {
            "factor_id": bundle.gate2_metrics.get("matched_factor_id")
        } if bundle.gate2_metrics.get("matched_factor_id") else None,
    }


def _build_run_payload(
    *,
    experiment_config: ExperimentConfig,
    sample_view: Any,
    screening_config: Block3ScreeningConfig,
    bundle: Block3ScreeningMetricBundle,
    run_id: str,
    created_at: str,
) -> dict[str, object]:
    """运行 payload: 统一产物追溯字段。"""

    return {
        "run_id": run_id,
        "source_universe_key": getattr(sample_view, "source_universe_key", experiment_config.source_universe_key),
        "forward_return_definition": getattr(sample_view, "forward_return_definition", experiment_config.forward_return_definition),
        "sample_protocol_id": getattr(sample_view, "sample_protocol_id", experiment_config.sample_protocol_id),
        "sample_protocol_hash": getattr(sample_view, "sample_protocol_hash", ""),
        "admission_horizon": screening_config.admission_horizon,
        "preprocess_config_hash": _hash_preprocess_config(experiment_config),
        "engine_version": bundle.engine_version,
        "created_at": created_at,
        "dataset_id": getattr(sample_view, "dataset_id", experiment_config.dataset_id),
    }


def _dataset_from_sample_view(sample_view: Any) -> DatasetBundle:
    """样本视图转数据集: 复用 screening sample 切片作为计算输入。"""

    dataset = getattr(sample_view, "dataset", None)
    if dataset is None:
        raise ValueError("sample_view must expose dataset for asset persistence")
    panel_view = getattr(sample_view, "panel_view", None)
    forward_returns_view = getattr(sample_view, "forward_returns_view", None)
    if panel_view is None and forward_returns_view is None:
        return dataset
    if panel_view is None or forward_returns_view is None:
        raise ValueError("sample_view must expose both panel_view and forward_returns_view")
    return DatasetBundle(
        panel=panel_view,
        forward_returns=forward_returns_view,
        manifest=dataset.manifest,
    )


def _compute_candidate_factor_values(
    *,
    candidate: Any,
    sample_view: Any,
    experiment_config: ExperimentConfig,
) -> tuple[pd.Series, pd.Series]:
    """候选因子值: 为最终 active 因子重算 raw 与 preprocessed values。"""

    dataset = _dataset_from_sample_view(sample_view)
    panel = PanelStore.from_dataset(dataset)
    calculator = V1FactorCalc(experiment_config)
    raw_matrix = calculator.calculate_matrix(candidate, dataset, panel)
    preprocessed_matrix = preprocess_factor_matrix(
        raw_matrix,
        panel,
        experiment_config,
        dataset.panel["industry"],
    )
    return (
        panel.to_series(candidate.candidate_id, raw_matrix).rename(candidate.candidate_id),
        panel.to_series(candidate.candidate_id, preprocessed_matrix).rename(candidate.candidate_id),
    )


def _asset_scope_dates(sample_view: Any, experiment_config: ExperimentConfig) -> tuple[str, str]:
    """资产日期范围: 优先用 dataset manifest，缺失时退回实验配置。"""

    manifest = getattr(getattr(sample_view, "dataset", None), "manifest", {})
    date_start = str(manifest.get("date_start", getattr(experiment_config, "date_start", "")))
    date_end = str(manifest.get("date_end", getattr(experiment_config, "date_end", "")))
    return date_start, date_end


# ============== 主入口 ==============
def run_block3_screening(
    *,
    config_path: str | Path,
    candidates_path: str | Path,
    dataset_path: str | Path,
    output_dir: str | Path,
    screening_gate_config_path: str | Path,
    asset_store_dir: str | Path | None = None,
) -> Block3ScreeningRunSummary:
    """运行 Block3 screening: 调用区块2、compute v1、Gate 判定和产物写入。"""

    experiment_config = load_experiment_config(config_path)
    screening_config = load_block3_screening_config(screening_gate_config_path)
    runtime_config = _RuntimeScreeningConfig(
        experiment_config=experiment_config,
        screening_config=screening_config,
    )
    sample_view = build_screening_sample_view(
        config=experiment_config,
        dataset_path=dataset_path,
        screening_sample_roles=screening_config.screening_sample_roles,
    )
    candidates, invalid_records = load_candidate_batch(candidates_path, experiment_config)
    if invalid_records:
        raise ValueError(str(invalid_records[0].details["message"]))

    writer = Block3ScreeningWriter(output_dir)
    counts = {
        "admitted": 0,
        "reject": 0,
        "duplicate": 0,
        "replace_candidate": 0,
    }
    total_candidates = 0
    run_id = f"block3_screening_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")

    library_factors: dict[str, pd.Series] | None = None
    library_value_status: str | None = None
    if asset_store_dir is not None:
        date_start, date_end = _asset_scope_dates(sample_view, experiment_config)
        load_result = load_library_factor_values(
            asset_store_dir,
            source_universe_key=getattr(sample_view, "source_universe_key", experiment_config.source_universe_key),
            forward_return_definition=getattr(sample_view, "forward_return_definition", experiment_config.forward_return_definition),
            sample_protocol_hash=getattr(sample_view, "sample_protocol_hash", ""),
            preprocess_config_hash=_hash_preprocess_config(experiment_config),
            date_start=date_start,
            date_end=date_end,
        )
        library_factors = load_result.values or None
        library_value_status = "loaded" if load_result.values else "library_empty"

    asset_records: list[AssetCandidateRecord] = []
    active_candidates: dict[str, tuple[Any, dict[str, object], dict[str, object]]] = {}

    for candidate in candidates:
        total_candidates += 1
        bundle = compute_block3_screening_metrics(
            candidate=candidate,
            sample_view=sample_view,
            config=runtime_config,
            library_factors=library_factors,
        )
        matched_factor_id = bundle.gate2_metrics.get("matched_factor_id")
        existing_metrics = (
            get_existing_factor_metrics(asset_store_dir, str(matched_factor_id) if matched_factor_id else None)
            if asset_store_dir is not None
            else None
        )
        decision = apply_block3_screening_gate(
            Block3GateInputs(
                config=screening_config,
                metrics=bundle,
                existing_factor_metrics=existing_metrics,
            )
        )
        candidate_payload = _build_candidate_payload(
            candidate,
            bundle,
            library_value_status=library_value_status,
        )
        run_payload = _build_run_payload(
            experiment_config=experiment_config,
            sample_view=sample_view,
            screening_config=screening_config,
            bundle=bundle,
            run_id=run_id,
            created_at=created_at,
        )
        writer.write(decision, candidate_payload, run_payload)
        counts[decision.decision] += 1

        if asset_store_dir is not None:
            asset_records.append(
                AssetCandidateRecord(
                    decision=decision.decision,
                    candidate_payload=candidate_payload,
                    run_payload=run_payload,
                    matched_factor_id=decision.matched_factor_id,
                    reject_reason=decision.reject_reason,
                    existing_metrics=decision.existing_metrics,
                    metrics_delta=decision.metrics_delta,
                )
            )
            if decision.decision in {"admitted", "replace_candidate"}:
                active_candidates[candidate.candidate_id] = (candidate, candidate_payload, run_payload)

    if asset_store_dir is not None and asset_records:
        ingest_summary = ingest_block3_batch(
            asset_store_dir,
            records=asset_records,
            replacement_quality_metric=getattr(screening_config, "replacement_quality_metric", "directional_rankic_mean"),
        )
        for factor_id in ingest_summary.admitted_factor_ids:
            candidate_info = active_candidates.get(factor_id)
            if candidate_info is None:
                continue
            candidate, candidate_payload, run_payload = candidate_info
            raw_factor, preprocessed_factor = _compute_candidate_factor_values(
                candidate=candidate,
                sample_view=sample_view,
                experiment_config=experiment_config,
            )
            saved = save_factor_values(
                asset_store_dir,
                factor_id=factor_id,
                expression_hash=f"sha256:{sha256(str(candidate_payload['expression']).encode('utf-8')).hexdigest()}",
                source_run_id=str(run_payload["run_id"]),
                source_universe_key=run_payload["source_universe_key"],
                forward_return_definition=run_payload["forward_return_definition"],
                sample_protocol_hash=run_payload["sample_protocol_hash"],
                preprocess_config_hash=run_payload["preprocess_config_hash"],
                raw_factor=raw_factor,
                preprocessed_factor=preprocessed_factor,
                created_at=str(run_payload["created_at"]),
            )
            register_factor_value_scope(
                asset_store_dir,
                factor_id=factor_id,
                value_scope_hash=str(saved["value_scope_hash"]),
            )

    return Block3ScreeningRunSummary(
        output_dir=Path(output_dir),
        evaluation_log_path=writer.evaluation_log_path,
        research_factor_library_path=writer.research_factor_library_path,
        replacement_queue_path=writer.replacement_queue_path,
        total_candidates=total_candidates,
        admitted_count=counts["admitted"],
        reject_count=counts["reject"],
        duplicate_count=counts["duplicate"],
        replace_candidate_count=counts["replace_candidate"],
    )



