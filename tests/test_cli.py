import json
from pathlib import Path

import pandas as pd
from typer.testing import CliRunner

from factor_autoresearch.cli import app


def _write_cli_config(base_dir: Path, *, date_start: str, date_end: str) -> Path:
    config_dir = base_dir / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    gate_path = config_dir / "candidate_gate_v1.toml"
    gate_path.write_text(
        "\n".join(
            [
                "[gate]",
                'version = "candidate_gate_v1"',
                "coverage_mean_min = 0.5",
                "effective_trade_days_min = 3",
                "complexity_score_max = 20",
                "best_horizon_score_min = 0.1",
                "min_cross_section_size = 2",
                "quantiles = 4",
                "",
                "[gate.weights]",
                "ic = 0.30",
                "rankic = 0.40",
                "monotonicity = 0.30",
                "",
                "[gate.components]",
                "ic_scale = 0.01",
                "rankic_scale = 0.01",
                "monotonicity_min = 0.0",
                "monotonicity_max = 1.0",
                "component_max = 2.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    config_path = config_dir / "experiment.toml"
    config_path.write_text(
        "\n".join(
            [
                'experiment_id = "csi500_ohlcv_sandbox_v1"',
                'dataset_id = "sandbox_v1"',
                'universe = "csi500"',
                f'date_start = "{date_start}"',
                f'date_end = "{date_end}"',
                'adjustment = "hfq"',
                'forward_return_definition = "next_open_to_open_v1"',
                'allowed_fields = ["open_hfq", "high_hfq", "low_hfq", "close_hfq", "volume"]',
                (
                    'allowed_functions = ["abs", "log", "delay", "ts_mean", "ts_std", '
                    '"ts_delta", "ts_return", "ts_rank", "cs_rank", "cs_zscore"]'
                ),
                "allowed_windows = [1, 3, 5, 10, 20]",
                ('categories = ["momentum", "reversal", "volatility", "liquidity", "volume", "intraday", "gap"]'),
                'horizons = ["1d", "5d", "20d"]',
                'features = ["open_hfq", "high_hfq", "low_hfq", "close_hfq", "volume"]',
                'preprocess_exposures = ["industry", "market_cap"]',
                'source = "fixture"',
                f'source_path = "{base_dir.as_posix()}"',
                'source_universe_key = "fixture"',
                'industry_source = "ci_l1_name"',
                "base_filters_inherited = []",
                'gate_config = "configs/candidate_gate_v1.toml"',
                "",
                "[prepare]",
                "price_start_buffer_days = 30",
                "use_incremental_universe = true",
                "",
                "[preprocess]",
                "winsorize_mad_scale = 5.0",
                'size_exposure = "log_market_cap"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return config_path


def _build_aligned_cli_fixture(dataset_dir: Path) -> tuple[Path, Path]:
    manifest_path = dataset_dir / "manifest.json"
    panel_frame = pd.read_parquet(dataset_dir / "panel.parquet")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["date_start"] = panel_frame["trade_date"].min().strftime("%Y-%m-%d")
    manifest["date_end"] = panel_frame["trade_date"].max().strftime("%Y-%m-%d")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    config_path = _write_cli_config(
        dataset_dir.parent,
        date_start=manifest["date_start"],
        date_end=manifest["date_end"],
    )
    return dataset_dir, config_path


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "dataset" in result.stdout


def test_cli_dataset_check_quality_writes_reports(sample_dataset_dir) -> None:
    runner = CliRunner()
    dataset_dir, config_path = _build_aligned_cli_fixture(sample_dataset_dir)
    result = runner.invoke(
        app,
        [
            "dataset",
            "check-quality",
            "--dataset",
            str(dataset_dir),
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["overall_outcome"] == "pass"
    assert (dataset_dir / "data_quality_report.json").exists()
    assert (dataset_dir / "data_quality_report.md").exists()


def test_cli_dataset_show_slices_outputs_protocol(sample_dataset_dir) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "dataset",
            "show-slices",
            "--dataset",
            str(sample_dataset_dir),
            "--sample-protocol",
            "mining_v1",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["sample_protocol_id"] == "mining_v1"
    assert payload["sample_protocol_hash"].startswith("sha256:")
    assert payload["slices"][0]["slice_id"] == "formation"


def test_cli_evaluate_exposes_engine_and_jobs_options() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["factor", "evaluate", "--help"])
    assert result.exit_code == 0
    assert "--engine" in result.stdout
    assert "--jobs" in result.stdout
