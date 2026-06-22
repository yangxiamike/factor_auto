from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from factor_autoresearch.config import load_experiment_config


def build_sample_dataset_dir(base_dir: Path) -> Path:
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
    panel = pd.DataFrame(rows)
    panel.to_parquet(dataset_dir / "panel.parquet", index=False)

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
    (dataset_dir / "README.md").write_text("# Fixture dataset\n", encoding="utf-8")
    return dataset_dir


def build_test_config() -> object:
    config = load_experiment_config(Path("configs/csi500_ohlcv_sandbox_v1.toml"))
    gate = replace(
        config.gate,
        coverage_mean_min=0.5,
        effective_trade_days_min=3,
        complexity_score_max=20,
        best_horizon_score_min=0.1,
        min_cross_section_size=2,
    )
    return replace(config, gate=gate)


def write_test_config_files(base_dir: Path) -> Path:
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


@pytest.fixture
def sample_dataset_dir(tmp_path: Path) -> Path:
    return build_sample_dataset_dir(tmp_path)


@pytest.fixture
def test_config():
    return build_test_config()
