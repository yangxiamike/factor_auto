"""
因子预处理模块: 负责按日截面完成去极值、标准化和中性化。
命名约定:
- 截面级局部变量优先用 day / values 这类短名
- 串联主流程时使用更直观的阶段名
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from factor_autoresearch.config import ExperimentConfig
from factor_autoresearch.data_loader import DatasetBundle


# ============== 截面预处理函数 ==============
def winsorize_by_date(series: pd.Series, in_universe: pd.Series, mad_scale: float) -> pd.Series:
    """按日去极值: 仅对股票池内样本执行 MAD winsorize。"""

    def _winsorize(values: pd.Series) -> pd.Series:
        """单日去极值: 按中位数和 MAD 裁剪极端值。"""
        median = values.median()
        mad = (values - median).abs().median()
        if pd.isna(mad) or mad == 0:
            return values
        lower = median - mad_scale * mad
        upper = median + mad_scale * mad
        return values.clip(lower=lower, upper=upper)

    result = pd.Series(np.nan, index=series.index, dtype=float)
    mask = in_universe.fillna(False)
    result.loc[mask] = series.loc[mask].groupby(level="trade_date", sort=False).transform(_winsorize)
    return result


def zscore_by_date(series: pd.Series, in_universe: pd.Series) -> pd.Series:
    """按日标准化: 仅对股票池内样本计算 z-score。"""

    def _zscore(values: pd.Series) -> pd.Series:
        """单日标准化: 对单个交易日截面做 z-score。"""
        std = values.std(ddof=0)
        if pd.isna(std) or std == 0:
            return pd.Series(np.nan, index=values.index, dtype=float)
        return (values - values.mean()) / std

    result = pd.Series(np.nan, index=series.index, dtype=float)
    mask = in_universe.fillna(False)
    result.loc[mask] = series.loc[mask].groupby(level="trade_date", sort=False).transform(_zscore)
    return result


def neutralize_by_date(factor_z: pd.Series, panel: pd.DataFrame) -> pd.Series:
    """按日中性化: 回归剔除行业和市值暴露后的残差。"""

    result = pd.Series(np.nan, index=factor_z.index, dtype=float)
    joined = pd.DataFrame(
        {
            "factor_z": factor_z,
            "industry": panel["industry"],
            "market_cap": panel["market_cap"],
            "in_universe": panel["in_universe"],
        }
    )

    for _trade_date, day_frame in joined.groupby(level="trade_date", sort=False):
        valid_rows = day_frame[
            day_frame["in_universe"].fillna(False)
            & day_frame["factor_z"].notna()
            & day_frame["industry"].notna()
            & day_frame["market_cap"].notna()
            & (day_frame["market_cap"] > 0)
        ].copy()
        if valid_rows.empty:
            continue

        size_exposure = np.log(valid_rows["market_cap"].astype(float))
        design_matrix = pd.get_dummies(valid_rows["industry"], prefix="industry", dtype=float)
        design_matrix["size"] = size_exposure
        design_matrix.insert(0, "intercept", 1.0)
        if len(valid_rows) <= design_matrix.shape[1]:
            continue

        x = design_matrix.to_numpy(dtype=float)
        y = valid_rows["factor_z"].to_numpy(dtype=float)
        try:
            beta, *_ = np.linalg.lstsq(x, y, rcond=None)
        except np.linalg.LinAlgError:
            continue
        fitted = x @ beta
        residual = y - fitted
        result.loc[valid_rows.index] = residual
    return result


# ============== 预处理主入口 ==============
def preprocess_factor(raw_factor: pd.Series, dataset: DatasetBundle, config: ExperimentConfig) -> pd.Series:
    """预处理因子: 串联执行去极值、标准化和中性化。"""

    winsorized_factor = winsorize_by_date(
        raw_factor,
        dataset.panel["in_universe"],
        config.preprocess.winsorize_mad_scale,
    )
    standardized_factor = zscore_by_date(winsorized_factor, dataset.panel["in_universe"])
    return neutralize_by_date(standardized_factor, dataset.panel)
