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
        if manifest["dataset_id"] != self.config.dataset_id:
            raise ValueError("dataset_id mismatch between manifest and config")
        if manifest["experiment_id"] != self.config.experiment_id:
            raise ValueError("experiment_id mismatch between manifest and config")

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
