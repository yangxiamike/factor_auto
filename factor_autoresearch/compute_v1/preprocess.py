"""Matrix-backed preprocess helpers aligned with the legacy implementation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from factor_autoresearch.compute_v1.panel import PanelStore
from factor_autoresearch.config import ExperimentConfig


@dataclass(frozen=True)
class NeutralizationDesign:
    """Cached per-date design matrices for repeated neutralization."""

    valid_masks: tuple[np.ndarray, ...]
    design_matrices: tuple[np.ndarray | None, ...]
    pseudo_inverses: tuple[np.ndarray | None, ...]


def build_industry_matrix(industry: np.ndarray | pd.Series | pd.DataFrame, panel: PanelStore) -> np.ndarray:
    """Normalize industry inputs into a dense date x asset matrix."""

    if isinstance(industry, pd.DataFrame):
        industry = industry["industry"]
    if isinstance(industry, pd.Series):
        aligned = industry.reindex(panel.long_index)
        return aligned.to_numpy(dtype=object).reshape(panel.universe_mask.shape)

    industry_matrix = np.asarray(industry, dtype=object)
    if industry_matrix.shape != panel.universe_mask.shape:
        raise ValueError("industry matrix shape must match panel.universe_mask")
    return industry_matrix


def build_neutralization_design(
    panel: PanelStore,
    industry: np.ndarray | pd.Series | pd.DataFrame,
) -> NeutralizationDesign:
    """Precompute reusable neutralization matrices for days with stable exposures."""

    industry_values = build_industry_matrix(industry, panel)
    market_cap = panel.field("market_cap")
    universe_mask = np.asarray(panel.universe_mask, dtype=bool)

    valid_masks: list[np.ndarray] = []
    design_matrices: list[np.ndarray | None] = []
    pseudo_inverses: list[np.ndarray | None] = []

    for day in range(universe_mask.shape[0]):
        valid = (
            universe_mask[day]
            & pd.notna(industry_values[day])
            & np.isfinite(market_cap[day])
            & (market_cap[day] > 0)
        )
        valid_masks.append(valid)
        if not np.any(valid):
            design_matrices.append(None)
            pseudo_inverses.append(None)
            continue

        size = np.log(market_cap[day, valid])
        industry_day = industry_values[day, valid]
        categories, inverse = np.unique(industry_day, return_inverse=True)
        x = np.zeros((int(valid.sum()), 2 + len(categories)), dtype=float)
        x[:, 0] = 1.0
        x[np.arange(x.shape[0]), inverse + 1] = 1.0
        x[:, -1] = size
        if x.shape[0] <= x.shape[1]:
            design_matrices.append(None)
            pseudo_inverses.append(None)
            continue
        design_matrices.append(x)
        pseudo_inverses.append(np.linalg.pinv(x))

    return NeutralizationDesign(
        valid_masks=tuple(valid_masks),
        design_matrices=tuple(design_matrices),
        pseudo_inverses=tuple(pseudo_inverses),
    )


def winsorize_by_date(values: np.ndarray, universe_mask: np.ndarray, mad_scale: float) -> np.ndarray:
    """Winsorize each date cross section inside the universe mask."""

    result = np.full_like(np.asarray(values, dtype=float), np.nan, dtype=float)
    mask = np.asarray(universe_mask, dtype=bool)
    source = np.asarray(values, dtype=float)

    for day in range(source.shape[0]):
        day_mask = mask[day]
        if not np.any(day_mask):
            continue
        day_values = source[day, day_mask]
        valid = np.isfinite(day_values)
        if not np.any(valid):
            continue

        clipped = day_values.copy()
        valid_values = day_values[valid]
        median = float(np.median(valid_values))
        mad = float(np.median(np.abs(valid_values - median)))
        if mad != 0.0:
            lower = median - mad_scale * mad
            upper = median + mad_scale * mad
            clipped[valid] = np.clip(valid_values, lower, upper)
        result[day, day_mask] = clipped
    return result


def zscore_by_date(values: np.ndarray, universe_mask: np.ndarray) -> np.ndarray:
    """Z-score each date cross section inside the universe mask using ddof=0."""

    result = np.full_like(np.asarray(values, dtype=float), np.nan, dtype=float)
    mask = np.asarray(universe_mask, dtype=bool)
    source = np.asarray(values, dtype=float)

    for day in range(source.shape[0]):
        day_mask = mask[day]
        if not np.any(day_mask):
            continue
        day_values = source[day, day_mask]
        valid = np.isfinite(day_values)
        if not np.any(valid):
            continue

        valid_values = day_values[valid]
        std = float(np.std(valid_values, ddof=0))
        standardized = np.full(day_values.shape, np.nan, dtype=float)
        if std != 0.0:
            mean = float(np.mean(valid_values))
            standardized[valid] = (valid_values - mean) / std
        result[day, day_mask] = standardized
    return result


def neutralize_by_date(
    factor_z: np.ndarray,
    panel: PanelStore,
    industry: np.ndarray | pd.Series | pd.DataFrame,
    design: NeutralizationDesign | None = None,
) -> np.ndarray:
    """Regress out industry dummies and log market cap by date, returning residuals."""

    result = np.full_like(np.asarray(factor_z, dtype=float), np.nan, dtype=float)
    factor_values = np.asarray(factor_z, dtype=float)
    industry_values = build_industry_matrix(industry, panel)
    market_cap = panel.field("market_cap")
    universe_mask = np.asarray(panel.universe_mask, dtype=bool)

    for day in range(factor_values.shape[0]):
        y_all = factor_values[day]
        industry_all = industry_values[day]
        market_cap_all = market_cap[day]
        if design is not None:
            base_valid = design.valid_masks[day]
            valid = base_valid & np.isfinite(y_all)
            matrix = design.design_matrices[day]
            pseudo_inverse = design.pseudo_inverses[day]
            if np.any(valid) and matrix is not None and pseudo_inverse is not None and np.array_equal(valid, base_valid):
                y = y_all[valid]
                result[day, valid] = y - (matrix @ (pseudo_inverse @ y))
                continue
        else:
            valid = (
                universe_mask[day]
                & np.isfinite(y_all)
                & pd.notna(industry_all)
                & np.isfinite(market_cap_all)
                & (market_cap_all > 0)
            )
        if not np.any(valid):
            continue

        y = y_all[valid]
        size = np.log(market_cap_all[valid])
        industry_day = industry_all[valid]
        categories, inverse = np.unique(industry_day, return_inverse=True)
        x = np.zeros((len(y), 2 + len(categories)), dtype=float)
        x[:, 0] = 1.0
        x[np.arange(len(y)), inverse + 1] = 1.0
        x[:, -1] = size
        if len(y) <= x.shape[1]:
            continue

        try:
            beta, *_ = np.linalg.lstsq(x, y, rcond=None)
        except np.linalg.LinAlgError:
            continue
        result[day, valid] = y - (x @ beta)
    return result


def preprocess_factor_matrix(
    raw_factor: np.ndarray,
    panel: PanelStore,
    config: ExperimentConfig,
    industry: np.ndarray | pd.Series | pd.DataFrame,
    neutralization_design: NeutralizationDesign | None = None,
) -> np.ndarray:
    """Apply the legacy preprocess pipeline on dense matrices."""

    winsorized = winsorize_by_date(raw_factor, panel.universe_mask, config.preprocess.winsorize_mad_scale)
    standardized = zscore_by_date(winsorized, panel.universe_mask)
    return neutralize_by_date(standardized, panel, industry, neutralization_design)
