"""
Evaluator 测试: 验证批量评估产物、摘要和 v1 benchmark 输出。
这里关注端到端产物契约，不重复底层指标计算细节。
"""

import json

import pandas as pd
import pytest

from factor_autoresearch.context import EvaluationContext
from factor_autoresearch.evaluate import Evaluator


# ============== 测试辅助 ==============
def _write_candidates(path):
    """写入候选样例: 同时包含可评估和非法候选。"""
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "fa_eval_pass",
                        "name": "eval pass",
                        "expression": "cs_rank((close_hfq - open_hfq) / open_hfq)",
                        "expected_direction": "positive",
                        "hypothesis": "eval pass",
                        "category": "intraday",
                        "lookback_days": 1,
                        "created_at": "2026-06-22",
                        "notes": "eval pass",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "id": "fa_eval_invalid",
                        "name": "eval invalid",
                        "expression": "cs_rank(close_hfq)",
                        "expected_direction": "positive",
                        "hypothesis": "eval invalid",
                        "category": "intraday",
                        "created_at": "2026-06-22",
                        "notes": "missing lookback",
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )


# ============== 评估产物 ==============
def test_evaluator_writes_artifacts(sample_dataset_dir, tmp_path, test_config) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    _write_candidates(candidates_path)
    context = EvaluationContext(
        config=test_config,
        dataset_path=sample_dataset_dir,
        candidates_path=candidates_path,
        registry_path=tmp_path / "registry.jsonl",
        runs_dir=tmp_path / "runs",
        run_id="smoke_001",
        verbose=False,
    )
    evaluator = Evaluator(context)
    artifacts = evaluator.evaluate_batch()

    assert (artifacts.run_dir / "summary.md").exists()
    assert (artifacts.run_dir / "logs" / "evaluate.log").exists()

    manifest = json.loads((artifacts.run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["gate_version"] == test_config.gate.version
    assert manifest["gate_config_hash"] == test_config.gate_config_hash

    results_path = artifacts.run_dir / "results" / "candidate_results.jsonl"
    results = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines()]
    assert all(
        set(result) == {
            "id",
            "status",
            "failure_bucket",
            "failed_rules",
            "best_horizon",
            "best_horizon_score",
            "signal_direction",
            "details",
            "metrics",
        }
        for result in results
    )

    passed = next(item for item in results if item["id"] == "fa_eval_pass")
    assert {
        "best_horizon_directional_ic_positive_ratio",
        "best_horizon_directional_rankic_positive_ratio",
        "best_horizon_ic_positive_ratio",
        "best_horizon_rankic_positive_ratio",
    }.issubset(passed["details"])

    invalid = next(item for item in results if item["id"] == "fa_eval_invalid")
    assert invalid["status"] == "invalid"
    assert invalid["failed_rules"] == []
    assert invalid["best_horizon"] is None
    assert invalid["metrics"] == {}

    diagnostics = pd.read_parquet(artifacts.run_dir / "results" / "diagnostics.parquet")
    assert not diagnostics.empty
    assert set(diagnostics["slice_type"]) == {"year", "industry"}

    summary = (artifacts.run_dir / "summary.md").read_text(encoding="utf-8")
    assert "## Failed Rules Summary" in summary
    assert "## Passed Candidates" in summary
    assert ("| rule | count |" in summary) or ("- none" in summary)
    assert "## Diagnostics" in summary
    assert "diagnostics.parquet" in summary


# ============== v1 benchmark ==============
def test_evaluator_writes_v1_benchmark(sample_dataset_dir, tmp_path, test_config) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    candidates_path.write_text(
        json.dumps(
            {
                "id": "fa_eval_v1",
                "name": "eval v1",
                "expression": "cs_rank(ts_return(close_hfq, 3))",
                "expected_direction": "positive",
                "hypothesis": "eval v1",
                "category": "momentum",
                "lookback_days": 3,
                "created_at": "2026-06-22",
                "notes": "eval v1",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    context = EvaluationContext(
        config=test_config,
        dataset_path=sample_dataset_dir,
        candidates_path=candidates_path,
        registry_path=tmp_path / "registry.jsonl",
        runs_dir=tmp_path / "runs",
        run_id="smoke_v1",
        engine="v1",
        jobs="auto",
        verbose=False,
    )
    artifacts = Evaluator(context).evaluate_batch()

    assert {path.name for path in (artifacts.run_dir / "results").iterdir() if path.is_file()} == {
        "candidate_results.jsonl",
        "metrics.parquet",
        "ic_series.parquet",
        "diagnostics.parquet",
    }
    benchmark = json.loads((artifacts.run_dir / "benchmark.json").read_text(encoding="utf-8"))
    assert benchmark["engine"] == "v1"
    assert benchmark["jobs"] == "auto"
    assert benchmark["candidate_count"] == 1
    assert benchmark["trade_days"] == 8
    assert benchmark["panel_rows"] == 32
    assert benchmark["universe_daily_mean"] == 4.0
    assert benchmark["dataset_id"] == "sandbox_v1"
    assert benchmark["universe"] == "csi500"
    assert benchmark["target_seconds_10y_30c"] == 300.0
    assert benchmark["classification"] in {"strong_green", "green", "yellow", "red"}
    assert isinstance(benchmark["should_trigger_optimization_loop"], bool)
    assert benchmark["top_bottleneck_stage"] in {
        "calculate_seconds",
        "preprocess_seconds",
        "metrics_seconds",
        "artifact_seconds",
    }
    for field in (
        "total_seconds",
        "calculate_seconds",
        "preprocess_seconds",
        "metrics_seconds",
        "artifact_seconds",
        "seconds_per_candidate",
        "seconds_per_candidate_day",
        "projected_seconds_8y_20c",
        "projected_seconds_8y_30c",
        "projected_seconds_10y_20c",
        "projected_seconds_10y_30c",
    ):
        assert isinstance(benchmark[field], float)
        assert benchmark[field] >= 0.0


def test_evaluator_rejects_dataset_manifest_filter_mismatch(sample_dataset_dir, tmp_path, test_config) -> None:
    manifest_path = sample_dataset_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["universe_filter"] = {
        "include_markets": ["unexpected"],
        "exclude_markets": [],
        "include_exchanges": [],
        "exclude_exchanges": [],
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    candidates_path = tmp_path / "candidates.jsonl"
    candidates_path.write_text("", encoding="utf-8")
    context = EvaluationContext(
        config=test_config,
        dataset_path=sample_dataset_dir,
        candidates_path=candidates_path,
        registry_path=tmp_path / "registry.jsonl",
        runs_dir=tmp_path / "runs",
        run_id="manifest_mismatch",
    )

    with pytest.raises(ValueError, match="universe_filter"):
        Evaluator(context).evaluate_batch()
