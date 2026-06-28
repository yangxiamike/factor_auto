from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pytest

from factor_autoresearch.candidates import Candidate
from factor_autoresearch.compute_v1.screening import (
    MissingComputeV1MetricError,
    compute_block3_screening_metrics,
)
from factor_autoresearch.data_loader import DataLoader, DatasetBundle


@dataclass(frozen=True)
class _ScreeningConfig:
    experiment_config: object
    admission_horizon: str = "5d"
    batch_corr_threshold: float = 0.5
    library_corr_threshold: float = 0.5
    quantiles: int = 4


@dataclass(frozen=True)
class _SampleView:
    dataset: DatasetBundle
    panel_view: pd.DataFrame
    forward_returns_view: pd.DataFrame


def _candidate(expression: str = "cs_rank((close_hfq - open_hfq) / open_hfq)") -> Candidate:
    return Candidate(
        candidate_id="fa_screening_v1",
        name="screening_v1",
        expression=expression,
        expected_direction="positive",
        hypothesis="screening_v1",
        category="intraday",
        lookback_days=1,
        created_at="2026-06-28",
        notes="screening_v1",
    )


def _load_view(sample_dataset_dir, test_config, forward_columns: list[str] | None = None) -> _SampleView:
    dataset = DataLoader(config=test_config, dataset_path=sample_dataset_dir).load()
    forward_returns = dataset.forward_returns
    if forward_columns is not None:
        forward_returns = forward_returns.loc[:, forward_columns].copy()
        dataset = DatasetBundle(
            panel=dataset.panel,
            forward_returns=forward_returns,
            manifest=dataset.manifest,
        )
    return _SampleView(
        dataset=dataset,
        panel_view=dataset.panel,
        forward_returns_view=forward_returns,
    )


def test_compute_block3_screening_metrics_returns_only_gate_fields(sample_dataset_dir, test_config) -> None:
    view = _load_view(sample_dataset_dir, test_config)
    config = _ScreeningConfig(experiment_config=test_config)
    library_factor = view.dataset.panel["close_hfq"].rename("library_factor")
    batch_factor = view.dataset.panel["open_hfq"].rename("batch_factor")

    bundle = compute_block3_screening_metrics(
        candidate=_candidate(),
        sample_view=view,
        config=config,
        library_factors={"existing_factor": library_factor},
        batch_factors={"batch_peer": batch_factor},
    )

    assert set(bundle.gate0_metrics) == {
        "expression_parse_status",
        "expression_allowlist_status",
        "leakage_check_status",
        "expression_depth",
        "coverage_mean",
        "effective_trade_days",
        "median_valid_stock_count",
        "finite_ratio",
        "std",
        "unique_ratio",
    }
    assert set(bundle.gate1_metrics) == {
        "admission_horizon",
        "expected_direction",
        "directional_rankic_mean",
        "directional_rankic_ir",
    }
    assert set(bundle.gate2_metrics) == {
        "max_abs_corr_to_batch",
        "max_abs_corr_to_library",
        "correlation_overlap_count",
        "correlated_factor_count",
        "matched_factor_id",
    }
    assert set(bundle.gate3_metrics) == {
        "directional_long_short_sharpe",
        "long_short_effective_days",
        "monotonicity_score",
        "turnover_proxy",
    }
    assert bundle.factor_exposure_ref == "memory://compute_v1/screening/fa_screening_v1/factor_exposure"
    assert bundle.engine_version == "compute_v1"

    all_metric_keys = set().union(
        bundle.gate0_metrics,
        bundle.gate1_metrics,
        bundle.gate2_metrics,
        bundle.gate3_metrics,
    )
    forbidden_fields = {
        "ic_mean",
        "rankic_mean",
        "ic_positive_ratio",
        "rankic_positive_ratio",
        "directional_ic_mean",
        "directional_ic_positive_ratio",
        "directional_rankic_positive_ratio",
        "spread",
        "node_count",
        "long_short_return",
        "long_short_sharpe",
        "best_horizon",
    }
    assert all_metric_keys.isdisjoint(forbidden_fields)
    assert not any("1d" in key or "20d" in key for key in all_metric_keys)


def test_compute_block3_screening_metrics_uses_configured_admission_horizon_only(
    sample_dataset_dir,
    test_config,
) -> None:
    view = _load_view(sample_dataset_dir, test_config, forward_columns=["fwd_ret_5d"])
    config = _ScreeningConfig(experiment_config=test_config, admission_horizon="5d")

    bundle = compute_block3_screening_metrics(
        candidate=_candidate(),
        sample_view=view,
        config=config,
    )

    assert bundle.gate1_metrics["admission_horizon"] == "5d"
    assert pd.notna(bundle.gate1_metrics["directional_rankic_mean"])


def test_compute_block3_screening_metrics_raises_compute_v1_error_when_required_metric_missing(
    sample_dataset_dir,
    test_config,
) -> None:
    view = _load_view(sample_dataset_dir, test_config, forward_columns=["fwd_ret_1d"])
    config = _ScreeningConfig(experiment_config=test_config, admission_horizon="5d")

    with pytest.raises(MissingComputeV1MetricError, match="fwd_ret_5d"):
        compute_block3_screening_metrics(
            candidate=_candidate(),
            sample_view=view,
            config=config,
            requested_gates=("gate0", "gate1"),
        )


def test_compute_block3_screening_metrics_supports_staged_gate0_failure(
    sample_dataset_dir,
    test_config,
) -> None:
    view = _load_view(sample_dataset_dir, test_config)
    config = _ScreeningConfig(experiment_config=test_config)

    bundle = compute_block3_screening_metrics(
        candidate=_candidate(expression="cs_rank("),
        sample_view=view,
        config=config,
        requested_gates=("gate0", "gate1", "gate2", "gate3"),
    )

    assert bundle.gate0_metrics == {
        "expression_parse_status": "failed",
        "expression_allowlist_status": "not_checked",
        "leakage_check_status": "not_checked",
        "expression_depth": None,
    }
    assert bundle.gate1_metrics == {}
    assert bundle.gate2_metrics == {}
    assert bundle.gate3_metrics == {}
    assert bundle.factor_exposure_ref is None
