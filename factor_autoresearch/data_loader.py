from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from factor_autoresearch.config import ExperimentConfig

PANEL_COLUMNS = [
    "trade_date",
    "ts_code",
    "in_universe",
    "industry",
    "market_cap",
    "open_hfq",
    "high_hfq",
    "low_hfq",
    "close_hfq",
    "volume",
]
FORWARD_COLUMNS = ["trade_date", "ts_code", "fwd_ret_1d", "fwd_ret_5d", "fwd_ret_20d"]


@dataclass(frozen=True)
class DatasetBundle:
    panel: pd.DataFrame
    forward_returns: pd.DataFrame
    manifest: dict[str, Any]


class DataLoader:
    def load(self, dataset_path: Path, config: ExperimentConfig) -> DatasetBundle:
        dataset_path = dataset_path.resolve()
        manifest_path = dataset_path / "manifest.json"
        panel_path = dataset_path / "panel.parquet"
        forward_path = dataset_path / "forward_returns.parquet"

        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        if manifest["dataset_id"] != config.dataset_id:
            raise ValueError("dataset_id mismatch between manifest and config")
        if manifest["experiment_id"] != config.experiment_id:
            raise ValueError("experiment_id mismatch between manifest and config")

        panel = pd.read_parquet(panel_path)
        forward_returns = pd.read_parquet(forward_path)
        missing_panel = sorted(set(PANEL_COLUMNS).difference(panel.columns))
        if missing_panel:
            raise ValueError(f"panel.parquet missing columns: {', '.join(missing_panel)}")
        missing_forward = sorted(set(FORWARD_COLUMNS).difference(forward_returns.columns))
        if missing_forward:
            raise ValueError(f"forward_returns.parquet missing columns: {', '.join(missing_forward)}")

        panel = panel.loc[:, PANEL_COLUMNS].copy()
        forward_returns = forward_returns.loc[:, FORWARD_COLUMNS].copy()
        panel["trade_date"] = pd.to_datetime(panel["trade_date"])
        forward_returns["trade_date"] = pd.to_datetime(forward_returns["trade_date"])

        if panel.duplicated(["trade_date", "ts_code"]).any():
            raise ValueError("panel.parquet contains duplicate (trade_date, ts_code)")
        if forward_returns.duplicated(["trade_date", "ts_code"]).any():
            raise ValueError("forward_returns.parquet contains duplicate (trade_date, ts_code)")

        panel = panel.sort_values(["trade_date", "ts_code"]).set_index(["trade_date", "ts_code"])
        forward_returns = forward_returns.sort_values(["trade_date", "ts_code"]).set_index(["trade_date", "ts_code"])
        return DatasetBundle(panel=panel, forward_returns=forward_returns, manifest=manifest)
