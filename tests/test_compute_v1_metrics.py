from __future__ import annotations

import pandas as pd

from factor_autoresearch.calculator import FactorCalc
from factor_autoresearch.candidates import Candidate
from factor_autoresearch.compute_v1.diagnostics import build_metrics_diagnostics
from factor_autoresearch.compute_v1.metrics import compute_candidate_metrics as compute_v1_metrics
from factor_autoresearch.data_loader import DataLoader
from factor_autoresearch.metrics import compute_candidate_metrics as compute_legacy_metrics
from factor_autoresearch.preprocess import preprocess_factor


def _build_candidate() -> Candidate:
    return Candidate(
        candidate_id="fa_metric_v1",
        name="metric_v1",
        expression="cs_rank((close_hfq - open_hfq) / open_hfq)",
        expected_direction="positive",
        hypothesis="metric_v1",
        category="intraday",
        lookback_days=1,
        created_at="2026-06-24",
        notes="metric_v1",
    )


def _load_fixture_metrics(sample_dataset_dir, test_config):
    dataset = DataLoader(config=test_config, dataset_path=sample_dataset_dir).load()
    candidate = _build_candidate()
    calc = FactorCalc(test_config)
    raw_factor = calc.calculate(candidate, dataset)
    processed_factor = preprocess_factor(raw_factor, dataset, test_config)
    complexity_score = calc.complexity_score(candidate)

    legacy = compute_legacy_metrics(
        candidate_id=candidate.candidate_id,
        factor=processed_factor,
        dataset=dataset,
        config=test_config,
        complexity_score=complexity_score,
    )
    v1 = compute_v1_metrics(
        candidate_id=candidate.candidate_id,
        factor=processed_factor,
        dataset=dataset,
        config=test_config,
        complexity_score=complexity_score,
    )
    return legacy, v1


def test_compute_v1_metrics_horizon_rows_schema_matches_legacy(sample_dataset_dir, test_config) -> None:
    legacy, v1 = _load_fixture_metrics(sample_dataset_dir, test_config)

    assert list(v1.horizon_rows.columns) == list(legacy.horizon_rows.columns)
    assert list(v1.horizon_rows["horizon"]) == list(legacy.horizon_rows["horizon"])


def test_compute_v1_metrics_ic_series_schema_matches_legacy(sample_dataset_dir, test_config) -> None:
    legacy, v1 = _load_fixture_metrics(sample_dataset_dir, test_config)

    assert list(v1.ic_series.columns) == list(legacy.ic_series.columns)
    assert set(v1.ic_series["horizon"]) == set(test_config.horizons)


def test_compute_v1_metrics_key_values_close_to_legacy(sample_dataset_dir, test_config) -> None:
    legacy, v1 = _load_fixture_metrics(sample_dataset_dir, test_config)

    horizon_columns = [
        "horizon",
        "ic_mean",
        "rankic_mean",
        "icir",
        "coverage_mean",
        "long_short_return",
        "monotonicity",
        "effective_trade_days",
    ]
    legacy_horizon = legacy.horizon_rows.loc[:, horizon_columns].sort_values("horizon").reset_index(drop=True)
    v1_horizon = v1.horizon_rows.loc[:, horizon_columns].sort_values("horizon").reset_index(drop=True)
    pd.testing.assert_frame_equal(legacy_horizon, v1_horizon, check_exact=False, atol=1e-12, rtol=1e-9)

    daily_columns = [
        "trade_date",
        "horizon",
        "coverage",
        "valid_count",
        "ic",
        "rankic",
        "long_short_return",
        "monotonicity",
        "bucket_count",
    ]
    legacy_daily = legacy.ic_series.loc[:, daily_columns].sort_values(["horizon", "trade_date"]).reset_index(drop=True)
    v1_daily = v1.ic_series.loc[:, daily_columns].sort_values(["horizon", "trade_date"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(legacy_daily, v1_daily, check_exact=False, atol=1e-12, rtol=1e-9)

    assert v1.aggregate["effective_trade_days"] == legacy.aggregate["effective_trade_days"]
    assert v1.aggregate["complexity_score"] == legacy.aggregate["complexity_score"]
    assert abs(v1.aggregate["coverage_mean"] - legacy.aggregate["coverage_mean"]) <= 1e-12


def test_compute_v1_diagnostics_builds_stable_tables(sample_dataset_dir, test_config) -> None:
    _, v1 = _load_fixture_metrics(sample_dataset_dir, test_config)
    diagnostics = build_metrics_diagnostics(v1)

    assert list(diagnostics.horizon_table["horizon"]) == list(test_config.horizons)
    assert list(diagnostics.daily_summary_table.columns) == [
        "candidate_id",
        "horizon",
        "trade_days",
        "effective_trade_days",
        "coverage_mean",
        "ic_mean",
        "rankic_mean",
        "long_short_return",
        "monotonicity",
    ]
    assert list(diagnostics.quantile_table.columns) == [
        "candidate_id",
        "horizon",
        "quantile",
        "mean_return",
    ]
    assert diagnostics.aggregate_table.loc[0, "candidate_id"] == _build_candidate().candidate_id
