"""
Block3 screening 样本视图模块
负责把 dataset 与 sample protocol 整理成 Block3 可直接消费的评价视图。
不负责指标计算，也不负责 Gate 判定。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from factor_autoresearch.config import ExperimentConfig
from factor_autoresearch.data_loader import DataLoader, DatasetBundle
from factor_autoresearch.sample_protocol import SampleProtocol, build_sample_protocol_from_dataset


# ============== 数据结构 ==============
@dataclass(frozen=True)
class ScreeningSampleView:
    """Block3 样本视图: 暴露筛选所需数据、样本切片和追溯字段。"""

    dataset: DatasetBundle
    panel_view: pd.DataFrame
    forward_returns_view: pd.DataFrame
    sample_protocol_id: str
    sample_protocol_hash: str
    evaluated_slice_roles: tuple[str, ...]
    evaluated_date_start: str
    evaluated_date_end: str
    evaluated_trade_dates: tuple[pd.Timestamp, ...]
    source_universe_key: str
    forward_return_definition: dict[str, Any]
    dataset_id: str


# ============== 基础辅助函数 ==============
def _resolve_protocol(config: ExperimentConfig, dataset_path: Path) -> SampleProtocol:
    """构造样本协议: 优先复用实验配置指定的 sample protocol。"""

    return build_sample_protocol_from_dataset(
        dataset_path,
        sample_protocol_id=config.sample_protocol_id,
    )


def _select_trade_dates(
    protocol: SampleProtocol,
    screening_sample_roles: Sequence[str],
) -> tuple[tuple[str, ...], tuple[pd.Timestamp, ...]]:
    """筛选日期: 只保留指定 slice role 覆盖到的交易日。"""

    roles = tuple(str(role) for role in screening_sample_roles)
    slices = [sample_slice for sample_slice in protocol.slices if sample_slice.role in roles]
    found_roles = {sample_slice.role for sample_slice in slices}
    missing_roles = [role for role in roles if role not in found_roles]
    if missing_roles:
        raise ValueError(
            "screening sample roles not found in sample protocol: "
            + ", ".join(missing_roles)
        )

    selected_dates: set[pd.Timestamp] = set()
    for sample_slice in slices:
        date_range = pd.date_range(sample_slice.date_start, sample_slice.date_end, freq="D")
        selected_dates.update(pd.Timestamp(value).normalize() for value in date_range)

    return roles, tuple(sorted(selected_dates))


def _filter_view(frame: pd.DataFrame, trade_dates: tuple[pd.Timestamp, ...]) -> pd.DataFrame:
    """过滤视图: 仅保留目标交易日对应的多重索引数据。"""

    selected = frame.index.get_level_values("trade_date").normalize().isin(trade_dates)
    return frame.loc[selected].copy()


def _build_forward_return_definition(
    config: ExperimentConfig,
    dataset: DatasetBundle,
) -> dict[str, Any]:
    """构造收益口径追溯字段: 保留名称和当前数据集可用 horizon。"""

    available_horizons = sorted(
        column.removeprefix("fwd_ret_")
        for column in dataset.forward_returns.columns
        if column.startswith("fwd_ret_")
    )
    return {
        "name": config.forward_return_definition,
        "available_horizons": available_horizons,
    }


# ============== 公共入口 ==============
def build_screening_sample_view(
    *,
    config: ExperimentConfig,
    dataset_path: str | Path,
    screening_sample_roles: Sequence[str],
) -> ScreeningSampleView:
    """构造 Block3 样本视图: 复用区块2加载与样本协议能力。"""

    resolved_dataset_path = Path(dataset_path).resolve()
    dataset = DataLoader(config=config, dataset_path=resolved_dataset_path).load()
    protocol = _resolve_protocol(config, resolved_dataset_path)
    roles, evaluated_trade_dates = _select_trade_dates(protocol, screening_sample_roles)
    panel_view = _filter_view(dataset.panel, evaluated_trade_dates)
    forward_returns_view = _filter_view(dataset.forward_returns, evaluated_trade_dates)

    return ScreeningSampleView(
        dataset=dataset,
        panel_view=panel_view,
        forward_returns_view=forward_returns_view,
        sample_protocol_id=protocol.sample_protocol_id,
        sample_protocol_hash=protocol.sample_protocol_hash,
        evaluated_slice_roles=roles,
        evaluated_date_start=evaluated_trade_dates[0].strftime("%Y-%m-%d"),
        evaluated_date_end=evaluated_trade_dates[-1].strftime("%Y-%m-%d"),
        evaluated_trade_dates=evaluated_trade_dates,
        source_universe_key=str(dataset.manifest["source_universe_key"]),
        forward_return_definition=_build_forward_return_definition(config, dataset),
        dataset_id=str(dataset.manifest["dataset_id"]),
    )
