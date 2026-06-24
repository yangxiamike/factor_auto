import json

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
        verbose=False,
    )
    evaluator = Evaluator(context)
    artifacts = evaluator.evaluate_batch()
    assert (artifacts.run_dir / "summary.md").exists()
    assert (artifacts.run_dir / "logs" / "evaluate.log").exists()
    assert (artifacts.run_dir / "manifest.json").exists()
    assert {
        path.name for path in (artifacts.run_dir / "results").iterdir() if path.is_file()
    } == {
        "candidate_results.jsonl",
        "metrics.parquet",
        "ic_series.parquet",
        "diagnostics.parquet",
    }
