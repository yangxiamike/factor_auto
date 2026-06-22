from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from factor_autoresearch.config import ExperimentConfig
from factor_autoresearch.data_loader import DatasetBundle


@dataclass(frozen=True)
class MetricsResult:
    horizon_rows: pd.DataFrame
    ic_series: pd.DataFrame
    aggregate: dict[str, float | int | str]


def _safe_spearman(x: pd.Series, y: pd.Series) -> float:
    if len(x) < 2:
        return math.nan
    return float(x.corr(y, method="spearman"))


def _assign_quantiles(values: pd.Series, quantiles: int) -> pd.Series:
    ranked = values.rank(method="first")
    return pd.qcut(ranked, q=quantiles, labels=False, duplicates="drop")


def compute_candidate_metrics(
    *,
    candidate_id: str,
    factor: pd.Series,
    dataset: DatasetBundle,
    config: ExperimentConfig,
    complexity_score: int,
) -> MetricsResult:
    merged = pd.DataFrame({"factor": factor, "in_universe": dataset.panel["in_universe"]}).join(
        dataset.forward_returns, how="left"
    )
    universe_counts = (
        dataset.panel["in_universe"].fillna(False).groupby(level="trade_date").sum().astype(int)
    )
    gate = config.gate

    horizon_rows: list[dict[str, object]] = []
    ic_rows: list[dict[str, object]] = []

    for horizon in config.horizons:
        return_column = f"fwd_ret_{horizon}"
        day_rows: list[dict[str, object]] = []
        quantile_means_all: list[pd.Series] = []

        for trade_date, day in merged.groupby(level="trade_date", sort=False):
            day = day[day["in_universe"].fillna(False)]
            universe_count = int(universe_counts.get(trade_date, 0))
            valid = day[["factor", return_column]].dropna()
            coverage = (len(valid) / universe_count) if universe_count else math.nan
            ic = math.nan
            rankic = math.nan
            long_short_return = math.nan
            monotonicity = math.nan
            bucket_count = 0

            if len(valid) >= gate.quantiles:
                buckets = _assign_quantiles(valid["factor"], gate.quantiles)
                quantile_means = valid.groupby(buckets, observed=True)[return_column].mean()
                quantile_means.index = quantile_means.index.astype(int) + 1
                quantile_means_all.append(quantile_means)
                bucket_count = len(quantile_means)
                if len(quantile_means) >= 2:
                    long_short_return = float(quantile_means.iloc[-1] - quantile_means.iloc[0])
                    monotonicity = _safe_spearman(
                        pd.Series(range(1, len(quantile_means) + 1), dtype=float),
                        quantile_means.reset_index(drop=True),
                    )

            if len(valid) >= gate.min_cross_section_size:
                ic = float(valid["factor"].corr(valid[return_column], method="pearson"))
                rankic = _safe_spearman(valid["factor"], valid[return_column])

            day_rows.append(
                {
                    "candidate_id": candidate_id,
                    "trade_date": trade_date,
                    "horizon": horizon,
                    "coverage": coverage,
                    "valid_count": int(len(valid)),
                    "ic": ic,
                    "rankic": rankic,
                    "long_short_return": long_short_return,
                    "monotonicity": monotonicity,
                    "bucket_count": bucket_count,
                }
            )

        day_frame = pd.DataFrame(day_rows)
        ic_rows.extend(day_rows)
        effective_trade_days = int(day_frame["ic"].notna().sum())
        ic_mean = float(day_frame["ic"].mean()) if not day_frame.empty else math.nan
        rankic_mean = float(day_frame["rankic"].mean()) if not day_frame.empty else math.nan
        ic_std = float(day_frame["ic"].std(ddof=0)) if not day_frame.empty else math.nan
        icir = float(ic_mean / ic_std) if pd.notna(ic_std) and ic_std != 0 else math.nan
        coverage_mean = float(day_frame["coverage"].mean()) if not day_frame.empty else math.nan
        long_short_mean = (
            float(day_frame["long_short_return"].mean()) if not day_frame.empty else math.nan
        )
        monotonicity_mean = (
            float(day_frame["monotonicity"].mean()) if not day_frame.empty else math.nan
        )

        quantile_summary: dict[str, float] = {}
        if quantile_means_all:
            quantile_frame = pd.DataFrame(quantile_means_all).sort_index(axis=1)
            for bucket in quantile_frame.columns:
                quantile_summary[f"quantile_return_q{int(bucket)}_{horizon}"] = float(
                    quantile_frame[bucket].mean()
                )

        horizon_rows.append(
            {
                "candidate_id": candidate_id,
                "horizon": horizon,
                "ic_mean": ic_mean,
                "rankic_mean": rankic_mean,
                "icir": icir,
                "coverage_mean": coverage_mean,
                "long_short_return": long_short_mean,
                "monotonicity": monotonicity_mean,
                "effective_trade_days": effective_trade_days,
                "complexity_score": complexity_score,
                **quantile_summary,
            }
        )

    horizon_frame = pd.DataFrame(horizon_rows)
    coverage_values = horizon_frame["coverage_mean"].dropna()
    aggregate = {
        "candidate_id": candidate_id,
        "coverage_mean": float(coverage_values.mean()) if not coverage_values.empty else math.nan,
        "effective_trade_days": int(horizon_frame["effective_trade_days"].max())
        if not horizon_frame.empty
        else 0,
        "complexity_score": int(complexity_score),
    }
    return MetricsResult(
        horizon_rows=horizon_frame,
        ic_series=pd.DataFrame(ic_rows),
        aggregate=aggregate,
    )
