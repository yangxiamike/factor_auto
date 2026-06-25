from __future__ import annotations

from dataclasses import replace

import pandas as pd
from conftest import write_test_config_files

from factor_autoresearch.config import load_experiment_config
from factor_autoresearch.prepare import _filter_universe_members, prepare_fixed_dataset


def test_prepare_fixed_dataset_from_fake_zer0share(tmp_path) -> None:
    source_dir = tmp_path / "source"
    data_dir = source_dir / "data"

    basic_dir = data_dir / "stock" / "basic"
    basic_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "ts_code": ["000001.SZ", "000002.SZ"],
            "exchange": ["SZSE", "SZSE"],
            "market": ["MAIN", "MAIN"],
        }
    ).to_parquet(basic_dir / "data.parquet", index=False)

    trade_cal_dir = data_dir / "stock" / "trade_cal" / "exchange=SSE"
    trade_cal_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "exchange": ["SSE", "SSE", "SSE", "SSE"],
            "cal_date": ["20231229", "20240102", "20240103", "20240104"],
            "is_open": [True, True, True, True],
            "pretrade_date": ["20231228", "20231229", "20240102", "20240103"],
        }
    ).to_parquet(trade_cal_dir / "data.parquet", index=False)

    for trade_date in ["20231229", "20240102", "20240103", "20240104"]:
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
    config_text = config_path.read_text(encoding="utf-8")
    config_text = config_text.replace(
        'gate_config = "configs/candidate_gate_baseline_v0.toml"',
        '\n'.join(
            [
                'gate_config = "configs/candidate_gate_baseline_v0.toml"',
                'warmup_start = "2023-12-29"',
                'sample_protocol_id = "sandbox_v1"',
                '',
                '[sample_protocol_config]',
                'note = "fixture"',
            ]
        ),
    )
    config_path.write_text(config_text, encoding="utf-8")
    config = load_experiment_config(config_path)
    assert config.warmup_start == "2023-12-29"
    assert config.sample_protocol_id == "sandbox_v1"
    assert config.sample_protocol_config == {"note": "fixture"}
    output_dir = tmp_path / "prepared"
    prepared = prepare_fixed_dataset(config=config, output_path=output_dir)

    assert (output_dir / "panel.parquet").exists()
    assert (output_dir / "forward_returns.parquet").exists()
    assert prepared.panel["trade_date"].min().strftime("%Y-%m-%d") == "2023-12-29"
    assert prepared.manifest["dataset_id"] == "sandbox_v1"
    assert prepared.manifest["date_start"] == "2024-01-01"
    assert prepared.manifest["warmup_start"] == "2023-12-29"
    assert prepared.manifest["sample_protocol_id"] == "sandbox_v1"
    assert prepared.manifest["sample_protocol_config"] == {"note": "fixture"}
    assert prepared.manifest["sample_protocol_hash"].startswith("sha256:")
    assert prepared.manifest["data_quality_report"] == {
        "status": "not_generated",
        "json_path": "data_quality_report.json",
        "markdown_path": "data_quality_report.md",
    }
    assert prepared.manifest["universe_filter"] == {
        "include_markets": [],
        "exclude_markets": [],
        "include_exchanges": [],
        "exclude_exchanges": [],
    }
    assert {"open_hfq", "close_hfq", "industry", "market_cap"}.issubset(prepared.panel.columns)
    readme = (output_dir / "README.md").read_text(encoding="utf-8")
    assert "- warmup_start: 2023-12-29" in readme
    assert "- sample_protocol_id: sandbox_v1" in readme
    assert "- sample_protocol_hash: sha256:" in readme

def test_filter_universe_members_by_market_and_exchange(test_config) -> None:
    universe_members = pd.DataFrame(
        {
            "trade_date": ["20240102", "20240102", "20240102", "20240102"],
            "ts_code": ["000001.SZ", "000002.SZ", "688001.SH", "830001.BJ"],
        }
    )
    stock_basic = pd.DataFrame(
        {
            "ts_code": ["000001.SZ", "000002.SZ", "688001.SH", "830001.BJ"],
            "exchange": ["SZSE", "SSE", "SSE", "BSE"],
            "market": ["MAIN", "MAIN", "STAR", "BSE"],
        }
    )
    config = replace(
        test_config,
        prepare=replace(
            test_config.prepare,
            include_markets=["MAIN"],
            exclude_exchanges=["BSE"],
        ),
    )

    filtered = _filter_universe_members(universe_members, stock_basic, config)

    assert filtered["ts_code"].tolist() == ["000001.SZ", "000002.SZ"]
