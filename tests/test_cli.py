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


def test_cli_dataset_show_slices_outputs_mainboard_walkforward_protocol(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    pd.DataFrame({"trade_date": pd.bdate_range("2013-01-01", "2026-05-31")}).to_parquet(
        dataset_dir / "panel.parquet",
        index=False,
    )
    manifest = {
        "dataset_id": "mainboard_pressure_v1",
        "experiment_id": "mainboard_pressure_v1",
        "sample_protocol_id": "mining_v1_mainboard_walkforward",
        "sample_protocol_config": {
            "formation_years": 5,
            "embargo_trade_days": 20,
            "test_years": 1,
            "final_oos_start": "2026-01-01",
            "final_oos_end": "2026-05-31",
        },
        "date_start": "2014-01-01",
        "date_end": "2026-05-31",
        "warmup_start": "2013-01-01",
        "forward_return_definition": "next_open_to_open_v1",
        "universe": "mainboard",
    }
    (dataset_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(app, ["dataset", "show-slices", "--dataset", str(dataset_dir)])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["sample_protocol_id"] == "mining_v1_mainboard_walkforward"
    assert payload["slices"][-1]["role"] == "final_oos"
    assert payload["sample_protocol_hash"].startswith("sha256:")


def test_cli_exposes_factor_evaluate_screening_command() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["factor", "evaluate", "--help"])
    assert result.exit_code == 0
    assert "--config" in result.stdout
    assert "--candidates" in result.stdout
    assert "--dataset" in result.stdout
    assert "--output-dir" in result.stdout
    assert "--screening-gate-config" in result.stdout


def test_cli_exposes_factor_diagnose_legacy_command() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["factor", "diagnose", "--help"])
    assert result.exit_code == 0
    assert "--engine" in result.stdout
    assert "--jobs" in result.stdout


def test_cli_exposes_asset_command_group() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["asset", "--help"])
    assert result.exit_code == 0
    assert "ingest-block3" in result.stdout
    assert "build-test-library" in result.stdout



def test_cli_asset_list_outputs_stable_json(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["asset", "list", "--asset-store", str(tmp_path / "factor_assets")])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["command"] == "asset.list"
    assert payload["items"] == []
    assert payload["total"] == 0



def test_cli_asset_show_missing_factor_returns_json_error(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["asset", "show", "missing_factor", "--asset-store", str(tmp_path / "factor_assets")],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["command"] == "asset.show"
    assert "factor not found" in payload["error"]["message"]



def test_cli_asset_build_test_library_outputs_json_and_writes_asset_log(tmp_path: Path) -> None:
    runner = CliRunner()
    asset_store = tmp_path / "factor_assets"
    result = runner.invoke(
        app,
        [
            "asset",
            "build-test-library",
            "--asset-store",
            str(asset_store),
            "--library-size",
            "3",
            "--verbose",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["command"] == "asset.build-test-library"
    assert payload["library_size"] == 3
    assert (asset_store / "logs" / "asset.log").exists()


def test_cli_asset_build_test_library_forwards_alignment_scope_options(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    asset_store = tmp_path / "factor_assets"
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir(parents=True)
    config_path = tmp_path / "experiment.toml"
    config_path.write_text("experiment_id = \"fixture\"\n", encoding="utf-8")
    screening_path = tmp_path / "screening.toml"
    screening_path.write_text("screening_sample_roles = [\"full_sample\"]\n", encoding="utf-8")
    captured: dict[str, object] = {}

    class _Summary:
        def as_dict(self) -> dict[str, object]:
            return {
                "asset_store_dir": str(asset_store),
                "factor_ids": ["lib_factor_001"],
                "library_size": 1,
                "source_run_id": "build_test_library_fixture",
            }

    def _fake_build_test_library(asset_store_dir, **kwargs):
        captured["asset_store_dir"] = asset_store_dir
        captured.update(kwargs)
        return _Summary()

    monkeypatch.setattr("factor_autoresearch.cli.build_test_library", _fake_build_test_library)

    result = runner.invoke(
        app,
        [
            "asset",
            "build-test-library",
            "--asset-store",
            str(asset_store),
            "--library-size",
            "1",
            "--dataset",
            str(dataset_dir),
            "--config",
            str(config_path),
            "--screening-gate-config",
            str(screening_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert captured["asset_store_dir"] == asset_store
    assert captured["dataset_path"] == dataset_dir
    assert captured["config_path"] == config_path
    assert captured["screening_gate_config_path"] == screening_path
