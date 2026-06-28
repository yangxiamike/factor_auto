"""
区块3产物模块
只负责把 Gate 决策写成 JSONL。
不负责计算指标，也不扩展诊断字段。
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from typing import Any

from factor_autoresearch.block3_screening import (
    BLOCK3_GATE_METRIC_FIELDS,
    CORRELATION_PROFILE_FIELDS,
    LIGHT_TRADING_PROFILE_FIELDS,
    PREDICTION_METRIC_FIELDS,
    Block3GateDecision,
)


# ============== 基础辅助函数 ==============
def _hash_expression(expression: str) -> str:
    """计算表达式哈希: 产出稳定 trace 字段。"""

    return f"sha256:{sha256(expression.encode('utf-8')).hexdigest()}"


def _select_fields(payload: Mapping[str, object], field_names: tuple[str, ...]) -> dict[str, object]:
    """按字段白名单瘦身: 只保留当前产物职责真正需要的指标。"""

    return {field_name: payload.get(field_name) for field_name in field_names if field_name in payload}


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    """追加 JSONL: 统一 UTF-8 和单行落盘格式。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


# ============== 产物写入 ==============
class Block3ScreeningWriter:
    """区块3 JSONL writer: 写 evaluation log、research library 和 replacement queue。"""

    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.evaluation_log_path = self.output_dir / "evaluation_log.jsonl"
        self.research_factor_library_path = self.output_dir / "research_factor_library.jsonl"
        self.replacement_queue_path = self.output_dir / "replacement_queue.jsonl"

    def write(
        self,
        decision: Block3GateDecision,
        candidate_payload: Mapping[str, object],
        run_payload: Mapping[str, object],
    ) -> None:
        """写区块3产物: 全量写 evaluation，按决策分流 admitted 和 replacement。"""

        metrics_source = candidate_payload.get("metrics", decision.metrics)
        if not isinstance(metrics_source, Mapping):
            metrics_source = decision.metrics
        gate_metrics = _select_fields(metrics_source, BLOCK3_GATE_METRIC_FIELDS)
        matched_factor = candidate_payload.get("matched_factor")
        matched_factor_id = decision.matched_factor_id
        if matched_factor_id is None and isinstance(matched_factor, Mapping):
            raw_factor_id = matched_factor.get("factor_id")
            matched_factor_id = str(raw_factor_id) if raw_factor_id is not None else None

        candidate_id = str(candidate_payload["candidate_id"])
        expression = str(candidate_payload["expression"])
        category = str(candidate_payload["category"])
        economic_rationale = candidate_payload.get("economic_rationale")
        created_at = run_payload["created_at"]

        evaluation_record = {
            "candidate_id": candidate_id,
            "expression": expression,
            "category": category,
            "economic_rationale": economic_rationale,
            "run_id": run_payload["run_id"],
            "source_universe_key": run_payload["source_universe_key"],
            "forward_return_definition": run_payload["forward_return_definition"],
            "sample_protocol_id": run_payload["sample_protocol_id"],
            "sample_protocol_hash": run_payload["sample_protocol_hash"],
            "admission_horizon": run_payload["admission_horizon"],
            "preprocess_config_hash": run_payload["preprocess_config_hash"],
            "engine_version": run_payload["engine_version"],
            "gate0_status": decision.gate0_status,
            "gate1_status": decision.gate1_status,
            "gate2_status": decision.gate2_status,
            "gate3_status": decision.gate3_status,
            "decision": decision.decision,
            "reject_reason": decision.reject_reason,
            "metrics": gate_metrics,
            "matched_factor_id": matched_factor_id,
            "agent_note": candidate_payload.get("agent_note"),
            "created_at": created_at,
        }
        _append_jsonl(self.evaluation_log_path, evaluation_record)

        if decision.decision == "admitted":
            library_record = {
                "factor_id": candidate_id,
                "expression": expression,
                "expression_hash": _hash_expression(expression),
                "category": category,
                "economic_rationale": economic_rationale,
                "source_run_id": run_payload["run_id"],
                "source_universe_key": run_payload["source_universe_key"],
                "forward_return_definition": run_payload["forward_return_definition"],
                "sample_protocol_id": run_payload["sample_protocol_id"],
                "sample_protocol_hash": run_payload["sample_protocol_hash"],
                "admission_horizon": run_payload["admission_horizon"],
                "preprocess_config_hash": run_payload["preprocess_config_hash"],
                "engine_version": run_payload["engine_version"],
                "prediction_metrics": _select_fields(gate_metrics, PREDICTION_METRIC_FIELDS),
                "correlation_profile": _select_fields(gate_metrics, CORRELATION_PROFILE_FIELDS),
                "light_trading_profile": _select_fields(gate_metrics, LIGHT_TRADING_PROFILE_FIELDS),
                "admission_decision": "admitted",
                "admission_reason": "admitted",
                "created_at": created_at,
            }
            _append_jsonl(self.research_factor_library_path, library_record)

        if decision.decision == "replace_candidate":
            replacement_record = {
                "candidate_factor_id": candidate_id,
                "matched_factor_id": matched_factor_id,
                "candidate_metrics": _select_fields(gate_metrics, PREDICTION_METRIC_FIELDS),
                "existing_metrics": decision.existing_metrics or {},
                "metrics_delta": decision.metrics_delta or {},
                "replacement_reason": "replacement_candidate",
                "status": "pending",
                "created_at": created_at,
            }
            _append_jsonl(self.replacement_queue_path, replacement_record)
