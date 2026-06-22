from __future__ import annotations

import numpy as np
import pandas as pd

from factor_autoresearch.config import ExperimentConfig
from factor_autoresearch.data_loader import DatasetBundle


def winsorize_by_date(series: pd.Series, in_universe: pd.Series, mad_scale: float) -> pd.Series:
    def _winsorize(values: pd.Series) -> pd.Series:
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
    def _zscore(values: pd.Series) -> pd.Series:
        std = values.std(ddof=0)
        if pd.isna(std) or std == 0:
            return pd.Series(np.nan, index=values.index, dtype=float)
        return (values - values.mean()) / std

    result = pd.Series(np.nan, index=series.index, dtype=float)
    mask = in_universe.fillna(False)
    result.loc[mask] = series.loc[mask].groupby(level="trade_date", sort=False).transform(_zscore)
    return result


def neutralize_by_date(factor_z: pd.Series, panel: pd.DataFrame) -> pd.Series:
    result = pd.Series(np.nan, index=factor_z.index, dtype=float)
    joined = pd.DataFrame(
        {
            "factor_z": factor_z,
            "industry": panel["industry"],
            "market_cap": panel["market_cap"],
            "in_universe": panel["in_universe"],
        }
    )

    for _trade_date, day in joined.groupby(level="trade_date", sort=False):
        valid = day[
            day["in_universe"].fillna(False)
            & day["factor_z"].notna()
            & day["industry"].notna()
            & day["market_cap"].notna()
            & (day["market_cap"] > 0)
        ].copy()
        if valid.empty:
            continue

        size = np.log(valid["market_cap"].astype(float))
        design = pd.get_dummies(valid["industry"], prefix="industry", dtype=float)
        design["size"] = size
        design.insert(0, "intercept", 1.0)
        if len(valid) <= design.shape[1]:
            continue

        x = design.to_numpy(dtype=float)
        y = valid["factor_z"].to_numpy(dtype=float)
        try:
            beta, *_ = np.linalg.lstsq(x, y, rcond=None)
        except np.linalg.LinAlgError:
            continue
        fitted = x @ beta
        residual = y - fitted
        result.loc[valid.index] = residual
    return result


def preprocess_factor(raw_factor: pd.Series, dataset: DatasetBundle, config: ExperimentConfig) -> pd.Series:
    winsorized = winsorize_by_date(
        raw_factor,
        dataset.panel["in_universe"],
        config.preprocess.winsorize_mad_scale,
    )
    factor_z = zscore_by_date(winsorized, dataset.panel["in_universe"])
    return neutralize_by_date(factor_z, dataset.panel)
