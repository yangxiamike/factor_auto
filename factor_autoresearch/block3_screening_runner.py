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

from factor_autoresearch.block3_screening import Block3GateInputs, apply_block3_screening_gate
from factor_autoresearch.block3_screening_artifacts import Block3ScreeningWriter
from factor_autoresearch.candidates import load_candidate_batch
from factor_autoresearch.compute_v1.screening import Block3ScreeningMetricBundle, compute_block3_screening_metrics
from factor_autoresearch.config import (
    Block3ScreeningConfig,
    ExperimentConfig,
    load_block3_screening_config,
    load_experiment_config,
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


def _build_candidate_payload(candidate: Any, bundle: Block3ScreeningMetricBundle) -> dict[str, object]:
    """候选 payload: 统一 writer 所需的基础字段和 Gate 指标。"""

    return {
        "candidate_id": candidate.candidate_id,
        "name": candidate.name,
        "expression": candidate.expression,
        "expected_direction": candidate.expected_direction,
        "category": candidate.category,
        "economic_rationale": getattr(candidate, "economic_rationale", ""),
        "metrics": _flatten_metric_bundle(bundle),
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
) -> dict[str, object]:
    """运行 payload: 统一产物追溯字段。"""

    return {
        "run_id": f"block3_screening_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "source_universe_key": getattr(sample_view, "source_universe_key", experiment_config.source_universe_key),
        "forward_return_definition": getattr(sample_view, "forward_return_definition", experiment_config.forward_return_definition),
        "sample_protocol_id": getattr(sample_view, "sample_protocol_id", experiment_config.sample_protocol_id),
        "sample_protocol_hash": getattr(sample_view, "sample_protocol_hash", ""),
        "admission_horizon": screening_config.admission_horizon,
        "preprocess_config_hash": _hash_preprocess_config(experiment_config),
        "engine_version": bundle.engine_version,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "dataset_id": getattr(sample_view, "dataset_id", experiment_config.dataset_id),
    }


# ============== 主入口 ==============
def run_block3_screening(
    *,
    config_path: str | Path,
    candidates_path: str | Path,
    dataset_path: str | Path,
    output_dir: str | Path,
    screening_gate_config_path: str | Path,
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

    for candidate in candidates:
        total_candidates += 1
        bundle = compute_block3_screening_metrics(
            candidate=candidate,
            sample_view=sample_view,
            config=runtime_config,
        )
        decision = apply_block3_screening_gate(
            Block3GateInputs(
                config=screening_config,
                metrics=bundle,
            )
        )
        writer.write(
            decision,
            _build_candidate_payload(candidate, bundle),
            _build_run_payload(
                experiment_config=experiment_config,
                sample_view=sample_view,
                screening_config=screening_config,
                bundle=bundle,
            ),
        )
        counts[decision.decision] += 1

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

