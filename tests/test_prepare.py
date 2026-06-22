from __future__ import annotations

import pandas as pd

from conftest import write_test_config_files
from factor_autoresearch.config import load_experiment_config
from factor_autoresearch.prepare import prepare_fixed_dataset


def test_prepare_fixed_dataset_from_fake_zer0share(tmp_path) -> None:
    source_dir = tmp_path / "source"
    data_dir = source_dir / "data"

    trade_cal_dir = data_dir / "stock" / "trade_cal" / "exchange=SSE"
    trade_cal_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "exchange": ["SSE", "SSE", "SSE"],
            "cal_date": ["20240102", "20240103", "20240104"],
            "is_open": [True, True, True],
            "pretrade_date": ["20240101", "20240102", "20240103"],
        }
    ).to_parquet(trade_cal_dir / "data.parquet", index=False)

    for trade_date in ["20240102", "20240103", "20240104"]:
        universe_dir = data_dir / "stock" / "universe" / "name=univ_trade_zz500" / f"date={trade_date}"
        universe_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            {
                "trade_date": [trade_date, trade_date],
                "universe": ["univ_trade_zz500", "univ_trade_zz500"],
                "ts_code": ["000001.SZ", "000002.SZ"],
            }
        ).to_parquet(universe_dir / "data.parquet", index=False)

        for table_name, rows in {
            "daily_kline": {
                "ts_code": ["000001.SZ", "000002.SZ"],
                "trade_date": [trade_date, trade_date],
                "open": [10.0, 20.0],
                "high": [10.5, 20.5],
                "low": [9.5, 19.5],
                "close": [10.2, 20.3],
                "vol": [1000.0, 2000.0],
            },
            "daily_basic": {
                "ts_code": ["000001.SZ", "000002.SZ"],
                "trade_date": [trade_date, trade_date],
                "total_mv": [10000.0, 20000.0],
            },
            "adj_factor": {
                "ts_code": ["000001.SZ", "000002.SZ"],
                "trade_date": [trade_date, trade_date],
                "adj_factor": [1.0, 1.0],
            },
        }.items():
            table_dir = data_dir / "stock" / table_name / f"date={trade_date}"
            table_dir.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(rows).to_parquet(table_dir / "data.parquet", index=False)

    industry_dir = data_dir / "stock" / "industry" / "ci_member"
    industry_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "l1_code": ["CI01", "CI02"],
            "l1_name": ["Finance", "Industry"],
            "l2_code": ["", ""],
            "l2_name": ["", ""],
            "l3_code": ["", ""],
            "l3_name": ["", ""],
            "ts_code": ["000001.SZ", "000002.SZ"],
            "name": ["A", "B"],
            "in_date": ["20200101", "20200101"],
            "out_date": ["", ""],
            "is_new": ["Y", "Y"],
        }
    ).to_parquet(industry_dir / "data.parquet", index=False)

    config_path = write_test_config_files(source_dir)
    config = load_experiment_config(config_path)
    output_dir = tmp_path / "prepared"
    prepared = prepare_fixed_dataset(config=config, output_path=output_dir)

    assert (output_dir / "panel.parquet").exists()
    assert (output_dir / "forward_returns.parquet").exists()
    assert prepared.manifest["dataset_id"] == "sandbox_v1"
    assert {"open_hfq", "close_hfq", "industry", "market_cap"}.issubset(prepared.panel.columns)
