import json
from pathlib import Path

import pandas as pd
from conftest import write_test_config_files
from typer.testing import CliRunner

from factor_autoresearch.cli import app


def _assert_run_outputs(run_dir: Path) -> None:
    assert (run_dir / "summary.md").exists()
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "logs" / "evaluate.log").exists()
    assert {
        path.name for path in (run_dir / "results").iterdir() if path.is_file()
    } == {
        "candidate_results.jsonl",
        "metrics.parquet",
        "ic_series.parquet",
        "diagnostics.parquet",
    }


def test_smoke_validate_evaluate_clean(sample_dataset_dir, tmp_path) -> None:
    config_path = write_test_config_files(tmp_path)
    candidates_path = tmp_path / "candidates.jsonl"
    candidates_path.write_text(
        json.dumps(
            {
                "id": "fa_smoke",
                "name": "smoke",
                "expression": "cs_rank((close_hfq - open_hfq) / open_hfq)",
                "expected_direction": "positive",
                "hypothesis": "smoke",
                "category": "intraday",
                "lookback_days": 1,
                "created_at": "2026-06-22",
                "notes": "smoke",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    validate = runner.invoke(
        app,
        [
            "factor",
            "validate",
            "--dataset",
            str(sample_dataset_dir),
            "--candidates",
            str(candidates_path),
            "--config",
            str(config_path),
        ],
    )
    assert validate.exit_code == 0

    evaluate = runner.invoke(
        app,
        [
            "factor",
            "evaluate",
            "--dataset",
            str(sample_dataset_dir),
            "--candidates",
            str(candidates_path),
            "--config",
            str(config_path),
            "--run-id",
            "smoke_001",
            "--runs-dir",
            str(tmp_path / "runs"),
            "--registry",
            str(tmp_path / "registry.jsonl"),
        ],
    )
    assert evaluate.exit_code == 0
    run_dir = tmp_path / "runs" / "smoke_001"
    _assert_run_outputs(run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["gate_config_hash"].startswith("sha256:")

    results_path = run_dir / "results" / "candidate_results.jsonl"
    results = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines()]
    assert results[0]["failed_rules"] == []
    assert {
        "best_horizon_directional_ic_positive_ratio",
        "best_horizon_directional_rankic_positive_ratio",
    }.issubset(results[0]["details"])

    diagnostics_path = run_dir / "results" / "diagnostics.parquet"
    assert diagnostics_path.exists()
    diagnostics = pd.read_parquet(diagnostics_path)
    assert set(diagnostics["slice_type"]) == {"year", "industry"}

    summary = (run_dir / "summary.md").read_text(encoding="utf-8")
    assert "## Failed Rules Summary" in summary
    assert "## Diagnostics" in summary
    assert "diagnostics.parquet" in summary

    registry_lines = (tmp_path / "registry.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(registry_lines) == 1
    assert json.loads(registry_lines[0])["factor_id"] == "fa_smoke"

    clean = runner.invoke(
        app,
        [
            "experiment",
            "clean",
            "--experiment-id",
            "csi500_ohlcv_sandbox_v1",
            "--runs-dir",
            str(tmp_path / "runs"),
            "--registry",
            str(tmp_path / "registry.jsonl"),
        ],
    )
    assert clean.exit_code == 0


def test_smoke_evaluate_v1_engine(sample_dataset_dir, tmp_path) -> None:
    config_path = write_test_config_files(tmp_path)
    candidates_path = tmp_path / "candidates.jsonl"
    candidates_path.write_text(
        json.dumps(
            {
                "id": "fa_smoke_v1",
                "name": "smoke v1",
                "expression": "cs_rank(ts_return(close_hfq, 3))",
                "expected_direction": "positive",
                "hypothesis": "smoke v1",
                "category": "momentum",
                "lookback_days": 3,
                "created_at": "2026-06-22",
                "notes": "smoke v1",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    evaluate = runner.invoke(
        app,
        [
            "factor",
            "evaluate",
            "--dataset",
            str(sample_dataset_dir),
            "--candidates",
            str(candidates_path),
            "--config",
            str(config_path),
            "--run-id",
            "smoke_v1",
            "--runs-dir",
            str(tmp_path / "runs"),
            "--registry",
            str(tmp_path / "registry.jsonl"),
            "--engine",
            "v1",
            "--jobs",
            "2",
        ],
    )
    assert evaluate.exit_code == 0
    _assert_run_outputs(tmp_path / "runs" / "smoke_v1")
