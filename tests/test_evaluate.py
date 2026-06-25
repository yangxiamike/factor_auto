import json

import pandas as pd

from factor_autoresearch.context import EvaluationContext
from factor_autoresearch.evaluate import Evaluator


def test_evaluator_writes_artifacts(sample_dataset_dir, tmp_path, test_config) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    candidates_path.write_text(
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
