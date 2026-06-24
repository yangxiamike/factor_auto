"""Matrix-backed candidate metrics aligned with the legacy metrics schema."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from factor_autoresearch.compute_v1.panel import PanelStore
from factor_autoresearch.config import ExperimentConfig
from factor_autoresearch.data_loader import DatasetBundle
from factor_autoresearch.metrics import MetricsResult


@dataclass(frozen=True)
class _QuantileDayStats:
    long_short_return: float
    monotonicity: float
    bucket_count: int
    quantile_returns: dict[int, float]


def _series_to_matrix(series: pd.Series, store: PanelStore) -> np.ndarray:
    aligned = series.reindex(store.long_index)
    return aligned.to_numpy(dtype=float).reshape(len(store.date_index), len(store.asset_index))


def _frame_to_cube(
    frame: pd.DataFrame,
    columns: list[str],
    store: PanelStore,
) -> np.ndarray:
    aligned = frame.reindex(store.long_index)
    arrays = [
        aligned[column].to_numpy(dtype=float).reshape(len(store.date_index), len(store.asset_index))
        for column in columns
    ]
    return np.stack(arrays, axis=0)


def _rowwise_corr(x: np.ndarray, y: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    out = np.full(x.shape[0], np.nan, dtype=float)
    for row in range(x.shape[0]):
        mask = valid_mask[row]
        if int(mask.sum()) < 2:
            continue
        corr = np.corrcoef(x[row, mask], y[row, mask])[0, 1]
        if np.isfinite(corr):
            out[row] = float(corr)
    return out


def _rowwise_spearman(x: np.ndarray, y: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    x_rank = (
        pd.DataFrame(np.where(valid_mask, x, np.nan))
        .rank(axis=1, method="average", na_option="keep")
        .to_numpy(dtype=float)
    )
    y_rank = (
        pd.DataFrame(np.where(valid_mask, y, np.nan))
        .rank(axis=1, method="average", na_option="keep")
        .to_numpy(dtype=float)
    )
    return _rowwise_corr(x_rank, y_rank, valid_mask)


def _stable_quantile_stats(
    factor_values: np.ndarray,
    return_values: np.ndarray,
    valid_mask: np.ndarray,
    quantiles: int,
) -> _QuantileDayStats:
    valid_indices = np.flatnonzero(valid_mask)
    if valid_indices.size < quantiles:
        return _QuantileDayStats(
            long_short_return=np.nan,
            monotonicity=np.nan,
            bucket_count=0,
            quantile_returns={},
        )

    ordered = valid_indices[np.argsort(factor_values[valid_indices], kind="mergesort")]
    ranks = np.arange(1, ordered.size + 1, dtype=float)
    edges = 1.0 + (ordered.size - 1.0) * np.arange(1, quantiles, dtype=float) / quantiles
    labels = np.searchsorted(edges, ranks, side="left") + 1

    bucket_returns: dict[int, float] = {}
    for bucket in range(1, quantiles + 1):
        bucket_assets = ordered[labels == bucket]
        if bucket_assets.size == 0:
            continue
        bucket_returns[bucket] = float(np.nanmean(return_values[bucket_assets]))

    bucket_count = len(bucket_returns)
    if bucket_count < 2:
        long_short_return = np.nan
        monotonicity = np.nan
    else:
        ordered_returns = pd.Series([bucket_returns[bucket] for bucket in sorted(bucket_returns)], dtype=float)
        long_short_return = float(ordered_returns.iloc[-1] - ordered_returns.iloc[0])
        monotonicity = float(
            pd.Series(range(1, bucket_count + 1), dtype=float).corr(
                ordered_returns,
                method="spearman",
            )
        )

    return _QuantileDayStats(
        long_short_return=long_short_return,
        monotonicity=monotonicity,
        bucket_count=bucket_count,
        quantile_returns=bucket_returns,
    )


def _nanmean_or_nan(values: np.ndarray | pd.Series) -> float:
    array = np.asarray(values, dtype=float)
    if array.size == 0 or np.isnan(array).all():
        return np.nan
    return float(np.nanmean(array))


def build_returns_cube(
    dataset: DatasetBundle,
    config: ExperimentConfig,
    store: PanelStore | None = None,
) -> tuple[PanelStore, np.ndarray]:
    """Build the shared returns cube used by compute_v1 metrics."""

    panel_store = store or PanelStore.from_dataset(dataset)
    horizon_columns = [f"fwd_ret_{horizon}" for horizon in config.horizons]
    return panel_store, _frame_to_cube(dataset.forward_returns, horizon_columns, panel_store)


def compute_candidate_metrics_from_matrix(
    *,
    candidate_id: str,
    factor_matrix: np.ndarray,
    panel_store: PanelStore,
    returns_cube: np.ndarray,
    config: ExperimentConfig,
    complexity_score: int,
) -> MetricsResult:
    """Compute metrics using already-prepared dense matrices."""

    universe_mask = panel_store.universe_mask
    universe_count = universe_mask.sum(axis=1).astype(int)
    factor_valid = np.isfinite(factor_matrix)

    horizon_summary_rows: list[dict[str, object]] = []
    ic_series_rows: list[dict[str, object]] = []

    for horizon_index, horizon in enumerate(config.horizons):
        return_matrix = returns_cube[horizon_index]
        valid_mask = universe_mask & factor_valid & np.isfinite(return_matrix)
        valid_count = valid_mask.sum(axis=1).astype(int)

        coverage = np.divide(
            valid_count,
            universe_count,
            out=np.full(valid_count.shape, np.nan, dtype=float),
            where=universe_count > 0,
        )
        ic = _rowwise_corr(factor_matrix, return_matrix, valid_mask)
        rankic = _rowwise_spearman(factor_matrix, return_matrix, valid_mask)
        ic[valid_count < config.gate.min_cross_section_size] = np.nan
        rankic[valid_count < config.gate.min_cross_section_size] = np.nan

        long_short = np.full(len(panel_store.date_index), np.nan, dtype=float)
        monotonicity = np.full(len(panel_store.date_index), np.nan, dtype=float)
        bucket_count = np.zeros(len(panel_store.date_index), dtype=int)
        quantile_returns_by_bucket: dict[int, list[float]] = {
            bucket: [] for bucket in range(1, config.gate.quantiles + 1)
        }

        for day_index, trade_date in enumerate(panel_store.date_index):
            day_quantiles = _stable_quantile_stats(
                factor_matrix[day_index],
                return_matrix[day_index],
                valid_mask[day_index],
                config.gate.quantiles,
            )
            long_short[day_index] = day_quantiles.long_short_return
            monotonicity[day_index] = day_quantiles.monotonicity
            bucket_count[day_index] = day_quantiles.bucket_count
            for bucket, bucket_return in day_quantiles.quantile_returns.items():
                quantile_returns_by_bucket[bucket].append(bucket_return)

            ic_series_rows.append(
                {
                    "candidate_id": candidate_id,
                    "trade_date": trade_date,
                    "horizon": horizon,
                    "coverage": float(coverage[day_index]),
                    "valid_count": int(valid_count[day_index]),
                    "ic": float(ic[day_index]) if np.isfinite(ic[day_index]) else np.nan,
                    "rankic": float(rankic[day_index]) if np.isfinite(rankic[day_index]) else np.nan,
                    "long_short_return": float(long_short[day_index])
                    if np.isfinite(long_short[day_index])
                    else np.nan,
                    "monotonicity": float(monotonicity[day_index])
                    if np.isfinite(monotonicity[day_index])
                    else np.nan,
                    "bucket_count": int(bucket_count[day_index]),
                }
            )

        ic_mean = _nanmean_or_nan(ic)
        rankic_mean = _nanmean_or_nan(rankic)
        ic_std = float(np.nanstd(ic)) if np.isfinite(ic).any() else np.nan
        icir = (
            float(ic_mean / ic_std)
            if np.isfinite(ic_mean)
            and np.isfinite(ic_std)
            and not np.isclose(ic_std, 0.0, atol=1e-12)
            else np.nan
        )
        coverage_mean = _nanmean_or_nan(coverage)
        long_short_mean = _nanmean_or_nan(long_short)
        monotonicity_mean = _nanmean_or_nan(monotonicity)
        effective_trade_days = int(np.isfinite(ic).sum())

        quantile_summary = {
            f"quantile_return_q{bucket}_{horizon}": _nanmean_or_nan(bucket_returns)
            for bucket, bucket_returns in quantile_returns_by_bucket.items()
            if bucket_returns
        }

        horizon_summary_rows.append(
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
                "complexity_score": int(complexity_score),
                **quantile_summary,
            }
        )

    horizon_rows = pd.DataFrame(horizon_summary_rows)
    aggregate = {
        "candidate_id": candidate_id,
        "coverage_mean": _nanmean_or_nan(horizon_rows["coverage_mean"])
        if not horizon_rows.empty
        else np.nan,
        "effective_trade_days": int(horizon_rows["effective_trade_days"].max())
        if not horizon_rows.empty
        else 0,
        "complexity_score": int(complexity_score),
    }
    return MetricsResult(
        horizon_rows=horizon_rows,
        ic_series=pd.DataFrame(ic_series_rows),
        aggregate=aggregate,
    )


def compute_candidate_metrics(
    *,
    candidate_id: str,
    factor: pd.Series,
    dataset: DatasetBundle,
    config: ExperimentConfig,
    complexity_score: int,
) -> MetricsResult:
    """Compute daily and aggregate metrics for all configured horizons in one pass."""

    store, returns_cube = build_returns_cube(dataset, config)
    factor_matrix = _series_to_matrix(factor, store)
    return compute_candidate_metrics_from_matrix(
        candidate_id=candidate_id,
        factor_matrix=factor_matrix,
        panel_store=store,
        returns_cube=returns_cube,
        config=config,
        complexity_score=complexity_score,
    )
