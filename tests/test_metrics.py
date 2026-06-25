import pytest

from factor_autoresearch.calculator import FactorCalc
from factor_autoresearch.candidates import Candidate
from factor_autoresearch.data_loader import DataLoader
from factor_autoresearch.metrics import compute_candidate_metrics
from factor_autoresearch.preprocess import preprocess_factor


def test_compute_candidate_metrics_returns_horizon_rows(sample_dataset_dir, test_config) -> None:
    dataset = DataLoader(config=test_config, dataset_path=sample_dataset_dir).load()
    candidate = Candidate(
        candidate_id="fa_metric",
        name="metric",
        expression="cs_rank((close_hfq - open_hfq) / open_hfq)",
        expected_direction="positive",
        hypothesis="metric",
        category="intraday",
        lookback_days=1,
        created_at="2026-06-22",
        notes="metric",
    )
    calc = FactorCalc(test_config)
    raw = calc.calculate(candidate, dataset)
    processed = preprocess_factor(raw, dataset, test_config)
    result = compute_candidate_metrics(
        candidate_id=candidate.candidate_id,
        factor=processed,
        dataset=dataset,
        config=test_config,
        complexity_score=calc.complexity_score(candidate),
        expected_direction=candidate.expected_direction,
    )
    assert set(result.horizon_rows["horizon"]) == {"1d", "5d", "20d"}
    assert result.aggregate["coverage_mean"] > 0
    assert {
        "ic_positive_ratio",
        "rankic_positive_ratio",
        "directional_ic_positive_ratio",
        "directional_rankic_positive_ratio",
        "directional_ic_mean",
        "directional_rankic_mean",
        "directional_monotonicity",
    }.issubset(result.horizon_rows.columns)


def test_compute_candidate_metrics_directional_fields_follow_expected_direction(
    sample_dataset_dir, test_config
) -> None:
    dataset = DataLoader(config=test_config, dataset_path=sample_dataset_dir).load()
    candidate = Candidate(
        candidate_id="fa_metric_direction",
        name="metric direction",
        expression="cs_rank((close_hfq - open_hfq) / open_hfq)",
        expected_direction="positive",
        hypothesis="metric",
        category="intraday",
        lookback_days=1,
        created_at="2026-06-22",
        notes="metric",
    )
    calc = FactorCalc(test_config)
    raw = calc.calculate(candidate, dataset)
    processed = preprocess_factor(raw, dataset, test_config)

    positive_result = compute_candidate_metrics(
        candidate_id=candidate.candidate_id,
        factor=processed,
        dataset=dataset,
        config=test_config,
        complexity_score=calc.complexity_score(candidate),
        expected_direction="positive",
    )
    negative_result = compute_candidate_metrics(
        candidate_id=candidate.candidate_id,
        factor=processed,
        dataset=dataset,
        config=test_config,
        complexity_score=calc.complexity_score(candidate),
        expected_direction="negative",
    )

    positive_row = positive_result.horizon_rows.loc[
        positive_result.horizon_rows["horizon"] == "1d"
    ].iloc[0]
    negative_row = negative_result.horizon_rows.loc[
        negative_result.horizon_rows["horizon"] == "1d"
    ].iloc[0]

    assert positive_row["ic_positive_ratio"] == 1.0
    assert positive_row["rankic_positive_ratio"] == 1.0
    assert positive_row["directional_ic_positive_ratio"] == 1.0
    assert positive_row["directional_rankic_positive_ratio"] == 1.0
    assert positive_row["directional_ic_mean"] > 0
    assert positive_row["directional_rankic_mean"] > 0
    assert positive_row["directional_monotonicity"] > 0
    assert negative_row["directional_ic_mean"] == pytest.approx(-positive_row["ic_mean"])
    assert negative_row["directional_rankic_mean"] == pytest.approx(-positive_row["rankic_mean"])
    assert negative_row["directional_ic_positive_ratio"] == pytest.approx(
        1.0 - positive_row["ic_positive_ratio"]
    )
    assert negative_row["directional_rankic_positive_ratio"] == pytest.approx(
        1.0 - positive_row["rankic_positive_ratio"]
    )
    assert negative_row["directional_monotonicity"] == pytest.approx(-positive_row["monotonicity"])
