"""区块3产物测试: 只验证 JSONL 写入与字段瘦身。"""

from __future__ import annotations

import json

from factor_autoresearch.block3_screening import Block3GateDecision
from factor_autoresearch.block3_screening_artifacts import Block3ScreeningWriter


# ============== 测试辅助 ==============
def _build_run_payload() -> dict[str, object]:
    """构造运行追溯字段: 覆盖日志和因子库需要的最小字段。"""

    return {
        "run_id": "screen_run_001",
        "source_universe_key": "univ_trade_zz500",
        "forward_return_definition": "next_open_to_open_v1",
        "sample_protocol_id": "sample_protocol_v1",
        "sample_protocol_hash": "sha256:sample",
        "admission_horizon": "5d",
        "preprocess_config_hash": "sha256:prep",
        "engine_version": "compute_engine_v1",
        "created_at": "2026-06-28T14:00:00+08:00",
    }


def _build_candidate_payload() -> dict[str, object]:
    """构造候选 payload: 故意混入诊断字段，验证 writer 会瘦身。"""

    return {
        "candidate_id": "fa_block3_001",
        "expression": "cs_rank(close_hfq / open_hfq)",
        "category": "intraday",
        "economic_rationale": "开盘到收盘的强弱可能反映日内资金偏好。",
        "metrics": {
            "expression_depth": 4,
            "coverage_mean": 0.91,
            "median_valid_stock_count": 320,
            "directional_rankic_mean": 0.07,
            "max_abs_corr_to_library": 0.18,
            "correlated_factor_count": 0,
            "matched_factor_id": None,
            "directional_long_short_sharpe": 1.42,
            "long_short_effective_days": 96,
            "pearson_ic_mean": 0.55,
            "positive_ratio": 0.73,
            "spread_return_mean": 0.12,
            "node_count": 17,
        },
        "matched_factor": {
            "factor_id": "rf_legacy_001",
            "metrics": {"directional_rankic_mean": 0.05, "positive_ratio": 0.61},
        },
        "agent_note": "候选来自日内价格行为方向。",
    }


def _build_decision(decision: str, *, matched_factor_id: str | None = None) -> Block3GateDecision:
    """构造决策对象: 只包含 writer 需要的状态和替换信息。"""

    metrics = {
        "expression_depth": 4,
        "coverage_mean": 0.91,
        "median_valid_stock_count": 320,
        "directional_rankic_mean": 0.07,
        "max_abs_corr_to_library": 0.18,
        "correlated_factor_count": 0,
        "matched_factor_id": matched_factor_id,
        "directional_long_short_sharpe": 1.42,
        "long_short_effective_days": 96,
    }
    return Block3GateDecision(
        decision=decision,
        gate0_status="pass",
        gate1_status="pass",
        gate2_status="replace_candidate" if decision == "replace_candidate" else "pass",
        gate3_status="pass",
        reject_reason=None,
        matched_factor_id=matched_factor_id,
        metrics=metrics,
        existing_metrics={"directional_rankic_mean": 0.05} if matched_factor_id else None,
        metrics_delta={"improvement_ratio": 1.4} if matched_factor_id else None,
    )


def _read_jsonl(path) -> list[dict[str, object]]:
    """读取 JSONL: 返回便于断言的对象列表。"""

    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# ============== JSONL 写入 ==============
def test_block3_screening_writer_routes_admitted_into_evaluation_log_and_library(tmp_path) -> None:
    writer = Block3ScreeningWriter(tmp_path)
    candidate_payload = _build_candidate_payload()
    decision = _build_decision("admitted")

    writer.write(decision, candidate_payload, _build_run_payload())

    evaluation_rows = _read_jsonl(tmp_path / "evaluation_log.jsonl")
    library_rows = _read_jsonl(tmp_path / "research_factor_library.jsonl")

    assert len(evaluation_rows) == 1
    assert len(library_rows) == 1
    assert (tmp_path / "replacement_queue.jsonl").exists() is False

    evaluation_row = evaluation_rows[0]
    library_row = library_rows[0]
    assert evaluation_row["decision"] == "admitted"
    assert evaluation_row["economic_rationale"] == candidate_payload["economic_rationale"]
    assert library_row["admission_decision"] == "admitted"
    assert library_row["economic_rationale"] == candidate_payload["economic_rationale"]
    assert library_row["source_run_id"] == "screen_run_001"


def test_block3_screening_writer_routes_replace_candidate_into_replacement_queue(tmp_path) -> None:
    writer = Block3ScreeningWriter(tmp_path)
    candidate_payload = _build_candidate_payload()
    decision = _build_decision("replace_candidate", matched_factor_id="rf_legacy_001")

    writer.write(decision, candidate_payload, _build_run_payload())

    evaluation_rows = _read_jsonl(tmp_path / "evaluation_log.jsonl")
    replacement_rows = _read_jsonl(tmp_path / "replacement_queue.jsonl")

    assert len(evaluation_rows) == 1
    assert len(replacement_rows) == 1
    assert (tmp_path / "research_factor_library.jsonl").exists() is False

    replacement_row = replacement_rows[0]
    assert replacement_row["candidate_factor_id"] == "fa_block3_001"
    assert replacement_row["matched_factor_id"] == "rf_legacy_001"
    assert replacement_row["status"] == "pending"
    assert replacement_row["metrics_delta"]["improvement_ratio"] == 1.4


def test_block3_screening_writer_keeps_only_gate_metrics_and_blocks_diagnostic_fields(tmp_path) -> None:
    writer = Block3ScreeningWriter(tmp_path)

    writer.write(_build_decision("admitted"), _build_candidate_payload(), _build_run_payload())

    evaluation_row = _read_jsonl(tmp_path / "evaluation_log.jsonl")[0]
    library_row = _read_jsonl(tmp_path / "research_factor_library.jsonl")[0]

    assert set(evaluation_row["metrics"]) == {
        "expression_depth",
        "coverage_mean",
        "median_valid_stock_count",
        "directional_rankic_mean",
        "max_abs_corr_to_library",
        "correlated_factor_count",
        "matched_factor_id",
        "directional_long_short_sharpe",
        "long_short_effective_days",
    }
    assert "pearson_ic_mean" not in evaluation_row["metrics"]
    assert "positive_ratio" not in evaluation_row["metrics"]
    assert "spread_return_mean" not in evaluation_row["metrics"]
    assert "node_count" not in evaluation_row["metrics"]
    assert "pearson_ic_mean" not in library_row["prediction_metrics"]
    assert "positive_ratio" not in library_row["prediction_metrics"]


def test_block3_screening_writer_persists_traceability_fields_in_evaluation_log(tmp_path) -> None:
    writer = Block3ScreeningWriter(tmp_path)

    writer.write(_build_decision("admitted"), _build_candidate_payload(), _build_run_payload())

    evaluation_row = _read_jsonl(tmp_path / "evaluation_log.jsonl")[0]
    assert evaluation_row["run_id"] == "screen_run_001"
    assert evaluation_row["source_universe_key"] == "univ_trade_zz500"
    assert evaluation_row["forward_return_definition"] == "next_open_to_open_v1"
    assert evaluation_row["sample_protocol_id"] == "sample_protocol_v1"
    assert evaluation_row["sample_protocol_hash"] == "sha256:sample"
    assert evaluation_row["preprocess_config_hash"] == "sha256:prep"
    assert evaluation_row["engine_version"] == "compute_engine_v1"
    assert evaluation_row["created_at"] == "2026-06-28T14:00:00+08:00"
