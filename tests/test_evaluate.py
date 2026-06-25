import json

import pytest

from factor_autoresearch.context import EvaluationContext
from factor_autoresearch.evaluate import Evaluator


def test_evaluator_writes_artifacts(sample_dataset_dir, tmp_path, test_config) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    candidates_path.write_text(
        json.dumps(
            {
                "id": "fa_eval",
                "name": "eval",
                "expression": "cs_rank((close_hfq - open_hfq) / open_hfq)",
                "expected_direction": "positive",
                "hypothesis": "eval",
                "category": "intraday",
                "lookback_days": 1,
                "created_at": "2026-06-22",
                "notes": "eval",
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
        run_id="smoke_001",
        engine="v1",
        jobs="auto",
        verbose=False,
    )
    evaluator = Evaluator(context)
    artifacts = evaluator.evaluate_batch()
    assert (artifacts.run_dir / "summary.md").exists()
    assert (artifacts.run_dir / "logs" / "evaluate.log").exists()
    assert (artifacts.run_dir / "manifest.json").exists()
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
