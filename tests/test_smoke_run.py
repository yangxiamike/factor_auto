import json

from conftest import write_test_config_files
from typer.testing import CliRunner

from factor_autoresearch.cli import app


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
