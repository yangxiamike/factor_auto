"""Build slice-level diagnostics outputs for evaluated candidates."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from factor_autoresearch.config import ExperimentConfig
from factor_autoresearch.data_loader import DatasetBundle

DIAGNOSTIC_COLUMNS = [
    "candidate_id",
    "slice_type",
    "slice_value",
    "horizon",
    "ic_mean",
    "rankic_mean",
    "ic_positive_ratio",
    "rankic_positive_ratio",
    "coverage_mean",
    "effective_trade_days",
]


def build_candidate_diagnostics(
    *,
    candidate_id: str,
    factor: pd.Series,
    dataset: DatasetBundle,
    config: ExperimentConfig,
) -> pd.DataFrame:
    """Build year and industry diagnostics for one candidate across all horizons."""

    merged = pd.DataFrame(
        {
            "factor": factor,
            "in_universe": dataset.panel["in_universe"],
            "industry": dataset.panel["industry"],
        }
    ).join(dataset.forward_returns, how="left")
    merged = merged[merged["in_universe"].fillna(False)].copy()
    if merged.empty:
        return pd.DataFrame(columns=DIAGNOSTIC_COLUMNS)

    merged["year"] = merged.index.get_level_values("trade_date").year.astype(str)
    merged = merged.reset_index()

    rows: list[dict[str, object]] = []
    for horizon in config.horizons:
        return_column = f"fwd_ret_{horizon}"
        rows.extend(
            _build_slice_rows(
                candidate_id=candidate_id,
                merged=merged,
                horizon=horizon,
                return_column=return_column,
                slice_type="year",
                slice_column="year",
                min_cross_section_size=config.gate.min_cross_section_size,
            )
        )
        rows.extend(
            _build_slice_rows(
                candidate_id=candidate_id,
                merged=merged,
                horizon=horizon,
                return_column=return_column,
                slice_type="industry",
                slice_column="industry",
                min_cross_section_size=config.gate.min_cross_section_size,
            )
        )

    if not rows:
        return pd.DataFrame(columns=DIAGNOSTIC_COLUMNS)
    return pd.DataFrame(rows, columns=DIAGNOSTIC_COLUMNS)


def _build_slice_rows(
    *,
    candidate_id: str,
    merged: pd.DataFrame,
    horizon: str,
    return_column: str,
    slice_type: str,
    slice_column: str,
    min_cross_section_size: int,
) -> list[dict[str, object]]:
    day_rows = _compute_slice_day_rows(
        frame=merged,
        return_column=return_column,
        slice_column=slice_column,
        min_cross_section_size=min_cross_section_size,
    )

    rows: list[dict[str, object]] = []
    for slice_value, slice_days in day_rows.groupby("slice_value", sort=True):
        rows.append(
            {
                "candidate_id": candidate_id,
                "slice_type": slice_type,
                "slice_value": slice_value,
                "horizon": horizon,
                "ic_mean": _safe_mean(slice_days["ic"]),
                "rankic_mean": _safe_mean(slice_days["rankic"]),
                "ic_positive_ratio": _positive_ratio(slice_days["ic"]),
                "rankic_positive_ratio": _positive_ratio(slice_days["rankic"]),
                "coverage_mean": _safe_mean(slice_days["coverage"]),
                "effective_trade_days": int(slice_days["ic"].notna().sum()),
            }
        )
    return rows


def _compute_slice_day_rows(
    *,
    frame: pd.DataFrame,
    return_column: str,
    slice_column: str,
    min_cross_section_size: int,
) -> pd.DataFrame:
    keys = ["slice_value", "trade_date"]
    working = frame.rename(columns={slice_column: "slice_value"}).copy()
    working["slice_value"] = working["slice_value"].astype(str)

    universe_counts = working.groupby(keys, sort=False).size().rename("universe_count")
    valid = working.dropna(subset=["factor", return_column]).copy()
    valid_counts = valid.groupby(keys, sort=False).size().rename("valid_count")

    day_rows = pd.concat([universe_counts, valid_counts], axis=1).reset_index()
    day_rows["valid_count"] = day_rows["valid_count"].fillna(0).astype(int)
    day_rows["coverage"] = day_rows["valid_count"] / day_rows["universe_count"]

    if valid.empty:
        day_rows["ic"] = math.nan
        day_rows["rankic"] = math.nan
        return day_rows

    correlations = _grouped_pearson(valid, keys, "factor", return_column).rename("ic")
    valid["factor_rank"] = valid.groupby(keys, sort=False)["factor"].rank(method="average")
    valid["return_rank"] = valid.groupby(keys, sort=False)[return_column].rank(method="average")
    rank_correlations = _grouped_pearson(valid, keys, "factor_rank", "return_rank").rename("rankic")

    day_rows = day_rows.merge(correlations.reset_index(), on=keys, how="left")
    day_rows = day_rows.merge(rank_correlations.reset_index(), on=keys, how="left")
    too_small = day_rows["valid_count"] < min_cross_section_size
    day_rows.loc[too_small, ["ic", "rankic"]] = math.nan
    return day_rows


def _grouped_pearson(
    frame: pd.DataFrame,
    keys: list[str],
    left_column: str,
    right_column: str,
) -> pd.Series:
    values = frame.loc[:, keys + [left_column, right_column]].copy()
    values["left_square"] = values[left_column] * values[left_column]
    values["right_square"] = values[right_column] * values[right_column]
    values["cross"] = values[left_column] * values[right_column]

    grouped = values.groupby(keys, sort=False)
    stats = grouped.agg(
        n=(left_column, "size"),
        sum_left=(left_column, "sum"),
        sum_right=(right_column, "sum"),
        sum_left_square=("left_square", "sum"),
        sum_right_square=("right_square", "sum"),
        sum_cross=("cross", "sum"),
    )
    numerator = stats["n"] * stats["sum_cross"] - stats["sum_left"] * stats["sum_right"]
    left_denom = stats["n"] * stats["sum_left_square"] - stats["sum_left"] * stats["sum_left"]
    right_denom = stats["n"] * stats["sum_right_square"] - stats["sum_right"] * stats["sum_right"]
    denominator = np.sqrt(left_denom * right_denom)
    return numerator / denominator.replace(0.0, np.nan)


def _safe_mean(series: pd.Series) -> float:
    if series.empty:
        return math.nan
    value = series.mean()
    return float(value) if pd.notna(value) else math.nan


def _positive_ratio(series: pd.Series) -> float:
    valid = series.dropna()
    if valid.empty:
        return math.nan
    return float((valid > 0).mean())
