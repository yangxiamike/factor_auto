"""
数据加载模块: 负责从数据集目录读取 panel、forward returns 和 manifest。
边界约定:
- manifest、字段完整性和主键唯一性校验保留在这里
- 下游默认接收已经整理好的索引结构
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from factor_autoresearch.config import ExperimentConfig

# ============== 字段约定 ==============
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


# ============== 数据结构 ==============
@dataclass(frozen=True)
class DatasetBundle:
    """数据集对象: 打包 panel、forward returns 与 manifest。"""

    panel: pd.DataFrame
    forward_returns: pd.DataFrame
    manifest: dict[str, Any]


# ============== 加载器 ==============
class DataLoader:
    """数据加载器: 负责读取并校验单个数据集目录。"""

    def __init__(self, *, config: ExperimentConfig, dataset_path: Path) -> None:
        self.config = config
        self.dataset_path = Path(dataset_path).resolve()

    def load(self) -> DatasetBundle:
        """加载数据集: 校验 manifest、字段和主键后返回标准结构。"""

        manifest_path = self.dataset_path / "manifest.json"
        panel_path = self.dataset_path / "panel.parquet"
        forward_path = self.dataset_path / "forward_returns.parquet"

        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        self._validate_manifest(manifest)

        panel = pd.read_parquet(panel_path)
        forward_returns = pd.read_parquet(forward_path)
        missing_panel_columns = sorted(set(PANEL_COLUMNS).difference(panel.columns))
        if missing_panel_columns:
            raise ValueError(f"panel.parquet missing columns: {', '.join(missing_panel_columns)}")
        missing_forward_columns = sorted(set(FORWARD_COLUMNS).difference(forward_returns.columns))
        if missing_forward_columns:
            raise ValueError(
                f"forward_returns.parquet missing columns: {', '.join(missing_forward_columns)}"
            )

        panel = panel.loc[:, PANEL_COLUMNS].copy()
        forward_returns = forward_returns.loc[:, FORWARD_COLUMNS].copy()
        panel["trade_date"] = pd.to_datetime(panel["trade_date"])
        forward_returns["trade_date"] = pd.to_datetime(forward_returns["trade_date"])

        if panel.duplicated(["trade_date", "ts_code"]).any():
            raise ValueError("panel.parquet contains duplicate (trade_date, ts_code)")
        if forward_returns.duplicated(["trade_date", "ts_code"]).any():
            raise ValueError("forward_returns.parquet contains duplicate (trade_date, ts_code)")

        panel = panel.sort_values(["trade_date", "ts_code"]).set_index(["trade_date", "ts_code"])
        forward_returns = forward_returns.sort_values(["trade_date", "ts_code"]).set_index(
            ["trade_date", "ts_code"]
        )
        return DatasetBundle(panel=panel, forward_returns=forward_returns, manifest=manifest)

    def _validate_manifest(self, manifest: dict[str, Any]) -> None:
        """Validate that the dataset was prepared with the active experiment contract."""

        expected_filter = {
            "include_markets": self.config.prepare.include_markets,
            "exclude_markets": self.config.prepare.exclude_markets,
            "include_exchanges": self.config.prepare.include_exchanges,
            "exclude_exchanges": self.config.prepare.exclude_exchanges,
        }
        checks = {
            "dataset_id": self.config.dataset_id,
            "experiment_id": self.config.experiment_id,
            "universe": self.config.universe,
            "source_universe_key": self.config.source_universe_key,
            "forward_return_definition": self.config.forward_return_definition,
            "universe_filter": expected_filter,
        }
        for key, expected in checks.items():
            actual = manifest.get(key)
            if key == "universe_filter" and actual is None and expected == {
                "include_markets": [],
                "exclude_markets": [],
                "include_exchanges": [],
                "exclude_exchanges": [],
            }:
                actual = expected
            if actual != expected:
                raise ValueError(f"dataset manifest {key} does not match experiment config")
