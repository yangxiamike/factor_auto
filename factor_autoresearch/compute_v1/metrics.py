"""Matrix-backed candidate metrics aligned with the legacy metrics schema."""

from __future__ import annotations

import numpy as np
import pandas as pd

from factor_autoresearch.compute_v1.metrics_kernels import resolve_metrics_backend
from factor_autoresearch.compute_v1.panel import PanelStore
from factor_autoresearch.config import ExperimentConfig
from factor_autoresearch.data_loader import DatasetBundle
from factor_autoresearch.metrics import MetricsResult


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
    backend: str = "auto",
) -> MetricsResult:
    """Compute metrics using already-prepared dense matrices."""

    backend_impl = resolve_metrics_backend(backend)
    universe_mask = panel_store.universe_mask
    universe_count = universe_mask.sum(axis=1).astype(int)
    factor_valid = np.isfinite(factor_matrix)

    horizon_summary_rows: list[dict[str, object]] = []
    ic_frames: list[pd.DataFrame] = []

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
        ic = backend_impl.rowwise_corr(factor_matrix, return_matrix, valid_mask)
        rankic = backend_impl.rowwise_spearman(factor_matrix, return_matrix, valid_mask)
        ic[valid_count < config.gate.min_cross_section_size] = np.nan
        rankic[valid_count < config.gate.min_cross_section_size] = np.nan

        long_short, monotonicity, bucket_count, quantile_returns = backend_impl.quantile_stats(
            factor_matrix,
            return_matrix,
            valid_mask,
            config.gate.quantiles,
        )

        ic_frames.append(
            pd.DataFrame(
                {
                    "candidate_id": candidate_id,
                    "trade_date": panel_store.date_index,
                    "horizon": horizon,
                    "coverage": coverage.astype(float),
                    "valid_count": valid_count.astype(int),
                    "ic": ic.astype(float),
                    "rankic": rankic.astype(float),
                    "long_short_return": long_short.astype(float),
                    "monotonicity": monotonicity.astype(float),
                    "bucket_count": bucket_count.astype(int),
                }
            )
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
            f"quantile_return_q{bucket + 1}_{horizon}": _nanmean_or_nan(quantile_returns[:, bucket])
            for bucket in range(config.gate.quantiles)
            if np.isfinite(quantile_returns[:, bucket]).any()
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
        ic_series=pd.concat(ic_frames, ignore_index=True) if ic_frames else pd.DataFrame(),
        aggregate=aggregate,
    )


def compute_candidate_metrics(
    *,
    candidate_id: str,
    factor: pd.Series,
    dataset: DatasetBundle,
    config: ExperimentConfig,
    complexity_score: int,
    backend: str = "auto",
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
        backend=backend,
    )
