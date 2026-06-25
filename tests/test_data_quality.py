from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pandas as pd

from factor_autoresearch.config import load_experiment_config
from factor_autoresearch.data_quality import FAIL, PASS, WARNING, build_data_quality_report


def _build_sample_dataset_dir(base_dir: Path) -> Path:
    dataset_dir = base_dir / "dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)

    trade_dates = pd.date_range("2024-01-02", periods=8, freq="B")
    stocks = ["000001.SZ", "000002.SZ", "000003.SZ", "000004.SZ"]
    rows: list[dict[str, object]] = []
    for date_idx, trade_date in enumerate(trade_dates):
        for stock_idx, ts_code in enumerate(stocks):
            open_price = 10.0 + stock_idx
            intraday = 0.01 * (stock_idx - 1.5) + 0.001 * date_idx
            close_price = open_price * (1.0 + intraday)
            rows.append(
                {
                    "trade_date": trade_date,
                    "ts_code": ts_code,
                    "in_universe": True,
                    "industry": "IND_A",
                    "market_cap": 1000.0,
                    "open_hfq": open_price,
                    "high_hfq": close_price * 1.01,
                    "low_hfq": open_price * 0.99,
                    "close_hfq": close_price,
                    "volume": 10000.0 + 100.0 * stock_idx + date_idx,
                }
            )
    pd.DataFrame(rows).to_parquet(dataset_dir / "panel.parquet", index=False)

    forward_rows: list[dict[str, object]] = []
    for date_idx, trade_date in enumerate(trade_dates):
        for stock_idx, ts_code in enumerate(stocks):
            signal = 0.02 * (stock_idx - 1.5) + 0.001 * date_idx
            forward_rows.append(
                {
                    "trade_date": trade_date,
                    "ts_code": ts_code,
                    "fwd_ret_1d": signal,
                    "fwd_ret_5d": signal * 1.2,
                    "fwd_ret_20d": signal * 1.5,
                }
            )
    pd.DataFrame(forward_rows).to_parquet(dataset_dir / "forward_returns.parquet", index=False)

    manifest = {
        "dataset_id": "sandbox_v1",
        "experiment_id": "csi500_ohlcv_sandbox_v1",
        "created_at": "2026-06-22",
        "source": "fixture",
        "source_path": str(base_dir),
        "universe": "csi500",
        "source_universe_key": "fixture",
        "date_start": "2024-01-01",
        "date_end": "2025-12-31",
        "adjustment": "hfq",
        "features": ["open_hfq", "high_hfq", "low_hfq", "close_hfq", "volume"],
        "preprocess_exposures": ["industry", "market_cap"],
        "base_filters_inherited": [],
        "forward_returns": ["1d", "5d", "20d"],
        "forward_return_definition": "next_open_to_open_v1",
    }
    (dataset_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return dataset_dir


def _write_test_config_files(base_dir: Path) -> Path:
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
    experiment_path = config_dir / "experiment.toml"
    experiment_path.write_text(
        "\n".join(
            [
                'experiment_id = "csi500_ohlcv_sandbox_v1"',
                'dataset_id = "sandbox_v1"',
                'universe = "csi500"',
                'date_start = "2024-01-01"',
                'date_end = "2025-12-31"',
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
    return experiment_path


def _build_aligned_dataset_and_config(tmp_path: Path) -> tuple[Path, object]:
    dataset_dir = _build_sample_dataset_dir(tmp_path)
    panel = pd.read_parquet(dataset_dir / "panel.parquet")
    manifest_path = dataset_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["date_start"] = panel["trade_date"].min().strftime("%Y-%m-%d")
    manifest["date_end"] = panel["trade_date"].max().strftime("%Y-%m-%d")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    config_path = _write_test_config_files(tmp_path)
    config = load_experiment_config(config_path)
    aligned_config = replace(
        config,
        date_start=manifest["date_start"],
        date_end=manifest["date_end"],
    )
    return dataset_dir, aligned_config


def _check_map(report) -> dict[str, object]:
    return {check.check_id: check for check in report.checks}


def test_build_data_quality_report_passes_for_aligned_fixture(tmp_path: Path) -> None:
    dataset_dir, config = _build_aligned_dataset_and_config(tmp_path)

    forward = pd.read_parquet(dataset_dir / "forward_returns.parquet")
    observed_dates = sorted(forward["trade_date"].drop_duplicates())
    tail_1d_dates = observed_dates[-2:]
    tail_5d_dates = observed_dates[-6:]
    forward.loc[forward["trade_date"].isin(tail_1d_dates), "fwd_ret_1d"] = pd.NA
    forward.loc[forward["trade_date"].isin(tail_5d_dates), "fwd_ret_5d"] = pd.NA
    forward.to_parquet(dataset_dir / "forward_returns.parquet", index=False)

    report = build_data_quality_report(dataset_dir, config=config)
    checks = _check_map(report)

    assert report.overall_outcome == PASS
    assert report.summary["fail_count"] == 0
    assert report.summary["warning_count"] == 0
    assert checks["required_files"].outcome == PASS
    assert checks["manifest_required_fields"].outcome == PASS
    assert checks["manifest_config_consistency"].outcome == PASS
    assert checks["date_range_consistency"].outcome == PASS
    assert checks["forward_return_coverage"].outcome == PASS
    assert report.metrics["daily_universe"]["min"] == 4
    assert report.metrics["missing_rates"]["ohlcv"]["open_hfq"] == 0.0
    assert (
        report.metrics["forward_return_coverage"]["by_horizon"]["fwd_ret_1d"][
            "expected_tail_missing_rate"
        ]
        == 1.0
    )
    assert "Data Quality Report" in report.to_markdown()
    assert "forward_return_coverage" in report.to_markdown()


def test_build_data_quality_report_accepts_small_calendar_boundary_gap(tmp_path: Path) -> None:
    dataset_dir = _build_sample_dataset_dir(tmp_path)
    config_path = _write_test_config_files(tmp_path)
    config = load_experiment_config(config_path)

    manifest_path = dataset_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["date_end"] = "2024-01-11"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    config = replace(config, date_end="2024-01-11")

    report = build_data_quality_report(dataset_dir, config=config)

    assert report.overall_outcome == PASS
    assert _check_map(report)["date_range_consistency"].outcome == PASS


def test_build_data_quality_report_accepts_warmup_rows_before_formal_start(tmp_path: Path) -> None:
    dataset_dir = _build_sample_dataset_dir(tmp_path)
    config_path = _write_test_config_files(tmp_path)
    config = load_experiment_config(config_path)

    manifest_path = dataset_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["warmup_start"] = "2024-01-02"
    manifest["date_start"] = "2024-01-08"
    manifest["date_end"] = "2024-01-11"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    config = replace(
        config,
        warmup_start="2024-01-02",
        date_start="2024-01-08",
        date_end="2024-01-11",
    )

    report = build_data_quality_report(dataset_dir, config=config)

    assert report.overall_outcome == PASS
    assert _check_map(report)["date_range_consistency"].outcome == PASS


def test_build_data_quality_report_fails_when_required_file_missing(tmp_path: Path) -> None:
    dataset_dir, config = _build_aligned_dataset_and_config(tmp_path)
    (dataset_dir / "forward_returns.parquet").unlink()

    report = build_data_quality_report(dataset_dir, config=config)
    checks = _check_map(report)

    assert report.overall_outcome == FAIL
    assert checks["required_files"].outcome == FAIL
    assert "forward_returns.parquet" in checks["required_files"].details["missing_files"]


def test_build_data_quality_report_fails_on_duplicate_keys_and_date_mismatch(
    tmp_path: Path,
) -> None:
    dataset_dir, config = _build_aligned_dataset_and_config(tmp_path)

    panel = pd.read_parquet(dataset_dir / "panel.parquet")
    panel = pd.concat([panel, panel.iloc[[0]]], ignore_index=True)
    panel.to_parquet(dataset_dir / "panel.parquet", index=False)

    manifest_path = dataset_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["date_end"] = "2024-01-31"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = build_data_quality_report(dataset_dir, config=config)
    checks = _check_map(report)

    assert report.overall_outcome == FAIL
    assert checks["panel.parquet_primary_key_unique"].outcome == FAIL
    assert checks["manifest_config_consistency"].outcome == PASS
    assert checks["date_range_consistency"].outcome == FAIL
    assert checks["date_range_consistency"].details["panel_range"]["date_end"] == "2024-01-11"


def test_build_data_quality_report_warns_on_statistical_anomalies(tmp_path: Path) -> None:
    dataset_dir, config = _build_aligned_dataset_and_config(tmp_path)

    panel = pd.read_parquet(dataset_dir / "panel.parquet")
    forward = pd.read_parquet(dataset_dir / "forward_returns.parquet")

    anomaly_date = pd.Timestamp("2024-01-04")
    low_count_codes = ["000002.SZ", "000003.SZ", "000004.SZ"]
    panel.loc[
        (panel["trade_date"] == anomaly_date) & (panel["ts_code"].isin(low_count_codes)),
        "in_universe",
    ] = False
    panel.loc[panel["trade_date"] <= pd.Timestamp("2024-01-02"), "open_hfq"] = pd.NA
    panel.loc[panel["trade_date"] <= pd.Timestamp("2024-01-03"), "industry"] = pd.NA
    panel.loc[
        (panel["trade_date"] == pd.Timestamp("2024-01-02"))
        & (panel["ts_code"] == "000001.SZ"),
        "market_cap",
    ] = -1.0
    panel.to_parquet(dataset_dir / "panel.parquet", index=False)

    forward.loc[
        (forward["trade_date"] == pd.Timestamp("2024-01-02"))
        & (forward["ts_code"] == "000001.SZ"),
        "fwd_ret_5d",
    ] = pd.NA
    forward.to_parquet(dataset_dir / "forward_returns.parquet", index=False)

    report = build_data_quality_report(dataset_dir, config=config)
    checks = _check_map(report)

    assert report.overall_outcome == WARNING
    assert checks["daily_universe_counts"].outcome == WARNING
    assert checks["ohlcv_missing_rates"].outcome == WARNING
    assert checks["exposure_missing_rates"].outcome == WARNING
    assert checks["forward_return_coverage"].outcome == WARNING
    assert checks["market_cap_nonpositive_rate"].outcome == WARNING
    assert report.metrics["daily_universe"]["dates_below_threshold"] == ["2024-01-04"]
    assert report.metrics["missing_rates"]["ohlcv"]["open_hfq"] > 0.05
    assert (
        report.metrics["forward_return_coverage"]["by_horizon"]["fwd_ret_5d"][
            "non_tail_missing_rate"
        ]
        > 0.02
    )
    assert report.metrics["market_cap_nonpositive"]["nonpositive_count"] == 1


def test_build_data_quality_report_warns_when_a_trade_date_has_zero_universe_rows(tmp_path: Path) -> None:
    dataset_dir, config = _build_aligned_dataset_and_config(tmp_path)
    panel = pd.read_parquet(dataset_dir / "panel.parquet")

    zero_universe_date = pd.Timestamp("2024-01-04")
    panel.loc[panel["trade_date"] == zero_universe_date, "in_universe"] = False
    panel.to_parquet(dataset_dir / "panel.parquet", index=False)

    report = build_data_quality_report(dataset_dir, config=config)
    daily_universe_check = _check_map(report)["daily_universe_counts"]

    assert daily_universe_check.outcome == WARNING
    assert report.metrics["daily_universe"]["dates_below_threshold"] == ["2024-01-04"]
    assert report.metrics["daily_universe"]["min"] == 0
