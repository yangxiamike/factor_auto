import pandas as pd

from factor_autoresearch.compute_v1.equivalence import compare_equivalence


def _frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    metrics = pd.DataFrame(
        [
            {"candidate_id": "fa_1", "horizon": 5, "rankic_mean": 0.12, "coverage_mean": 0.95},
            {"candidate_id": "fa_1", "horizon": 10, "rankic_mean": 0.08, "coverage_mean": 0.91},
        ]
    )
    ic_series = pd.DataFrame(
        [
            {"candidate_id": "fa_1", "trade_date": "2026-01-02", "horizon": 5, "rankic": 0.11},
            {"candidate_id": "fa_1", "trade_date": "2026-01-03", "horizon": 5, "rankic": 0.13},
        ]
    )
    return metrics, ic_series


def _diagnostics() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"table_name": "horizon_table", "candidate_id": "fa_1", "horizon": 5, "rankic_mean": 0.12},
            {"table_name": "aggregate_table", "candidate_id": "fa_1", "coverage_mean": 0.93},
        ]
    )


def _results() -> list[dict[str, object]]:
    return [
        {
            "id": "fa_1",
            "status": "candidate_pass",
            "failure_bucket": None,
            "best_horizon": 5,
            "best_horizon_score": 0.12,
            "signal_direction": "positive",
            "details": {"passed_rules": ["rankic"]},
            "metrics": {"coverage_mean": 0.93, "effective_trade_days": 20},
        }
    ]


def test_compare_equivalence_matches_when_all_outputs_are_identical() -> None:
    results = _results()
    metrics, ic_series = _frames()
    diagnostics = _diagnostics()

    report = compare_equivalence(
        legacy_results=results,
        v1_results=results,
        legacy_metrics=metrics,
        v1_metrics=metrics.copy(),
        legacy_ic_series=ic_series,
        v1_ic_series=ic_series.copy(),
        legacy_diagnostics=diagnostics,
        v1_diagnostics=diagnostics.copy(),
    )

    assert report.matches is True
    assert report.candidate_results.matches is True
    assert report.metrics.matches is True
    assert report.ic_series.matches is True
    assert report.diagnostics.matches is True


def test_compare_equivalence_accepts_float_differences_within_tolerance() -> None:
    legacy_results = _results()
    v1_results = _results()
    v1_results[0]["best_horizon_score"] = 0.1205
    v1_results[0]["metrics"] = {"coverage_mean": 0.9304, "effective_trade_days": 20}
    legacy_metrics, legacy_ic_series = _frames()
    legacy_diagnostics = _diagnostics()
    v1_metrics = legacy_metrics.copy()
    v1_metrics.loc[0, "rankic_mean"] = 0.1204
    v1_ic_series = legacy_ic_series.copy()
    v1_ic_series.loc[1, "rankic"] = 0.1296
    v1_diagnostics = legacy_diagnostics.copy()
    v1_diagnostics.loc[0, "rankic_mean"] = 0.1204

    report = compare_equivalence(
        legacy_results=legacy_results,
        v1_results=v1_results,
        legacy_metrics=legacy_metrics,
        v1_metrics=v1_metrics,
        legacy_ic_series=legacy_ic_series,
        v1_ic_series=v1_ic_series,
        legacy_diagnostics=legacy_diagnostics,
        v1_diagnostics=v1_diagnostics,
        float_tolerance=0.001,
    )

    assert report.matches is True


def test_compare_equivalence_fails_when_float_difference_exceeds_tolerance() -> None:
    legacy_results = _results()
    v1_results = _results()
    v1_results[0]["best_horizon_score"] = 0.14
    legacy_metrics, legacy_ic_series = _frames()
    diagnostics = _diagnostics()

    report = compare_equivalence(
        legacy_results=legacy_results,
        v1_results=v1_results,
        legacy_metrics=legacy_metrics,
        v1_metrics=legacy_metrics.copy(),
        legacy_ic_series=legacy_ic_series,
        v1_ic_series=legacy_ic_series.copy(),
        legacy_diagnostics=diagnostics,
        v1_diagnostics=diagnostics.copy(),
        float_tolerance=0.001,
    )

    assert report.matches is False
    assert report.candidate_results.matches is False
    assert report.candidate_results.diffs[0].field == "best_horizon_score"
    assert report.candidate_results.diffs[0].reason == "value_mismatch"


def test_compare_equivalence_checks_non_empty_diagnostics_values() -> None:
    results = _results()
    metrics, ic_series = _frames()
    legacy_diagnostics = pd.DataFrame(
        [
            {
                "table_name": "daily_summary_table",
                "candidate_id": "fa_1",
                "horizon": "1d",
                "coverage_mean": 0.91,
                "ic_mean": 0.031,
                "rankic_mean": 0.042,
            }
        ]
    )
    v1_diagnostics = legacy_diagnostics.copy()
    v1_diagnostics.loc[0, "rankic_mean"] = 0.0424

    report = compare_equivalence(
        legacy_results=results,
        v1_results=results,
        legacy_metrics=metrics,
        v1_metrics=metrics.copy(),
        legacy_ic_series=ic_series,
        v1_ic_series=ic_series.copy(),
        legacy_diagnostics=legacy_diagnostics,
        v1_diagnostics=v1_diagnostics,
        float_tolerance=0.001,
    )

    assert report.matches is True
    assert report.diagnostics.matches is True


def test_compare_equivalence_fails_non_empty_diagnostics_outside_tolerance() -> None:
    results = _results()
    metrics, ic_series = _frames()
    legacy_diagnostics = pd.DataFrame(
        [
            {
                "table_name": "daily_summary_table",
                "candidate_id": "fa_1",
                "horizon": "1d",
                "coverage_mean": 0.91,
                "ic_mean": 0.031,
                "rankic_mean": 0.042,
            }
        ]
    )
    v1_diagnostics = legacy_diagnostics.copy()
    v1_diagnostics.loc[0, "rankic_mean"] = 0.052

    report = compare_equivalence(
        legacy_results=results,
        v1_results=results,
        legacy_metrics=metrics,
        v1_metrics=metrics.copy(),
        legacy_ic_series=ic_series,
        v1_ic_series=ic_series.copy(),
        legacy_diagnostics=legacy_diagnostics,
        v1_diagnostics=v1_diagnostics,
        float_tolerance=0.001,
    )

    assert report.matches is False
    assert report.diagnostics.matches is False
    assert report.diagnostics.diffs[0].column == "rankic_mean"


def test_compare_equivalence_reports_schema_and_row_count_differences() -> None:
    results = _results()
    legacy_metrics, legacy_ic_series = _frames()
    legacy_diagnostics = _diagnostics()
    v1_metrics = legacy_metrics.drop(columns=["coverage_mean"])
    v1_ic_series = legacy_ic_series.iloc[:1].copy()
    v1_diagnostics = legacy_diagnostics.drop(columns=["table_name"])

    report = compare_equivalence(
        legacy_results=results,
        v1_results=results,
        legacy_metrics=legacy_metrics,
        v1_metrics=v1_metrics,
        legacy_ic_series=legacy_ic_series,
        v1_ic_series=v1_ic_series,
        legacy_diagnostics=legacy_diagnostics,
        v1_diagnostics=v1_diagnostics,
    )

    assert report.matches is False
    assert report.metrics.schema.matches is False
    assert report.metrics.schema.missing_in_v1 == ["coverage_mean"]
    assert report.ic_series.row_count_match is False
    assert report.ic_series.legacy_rows == 2
    assert report.ic_series.v1_rows == 1
    assert report.diagnostics.schema.missing_in_v1 == ["table_name"]


def test_compare_equivalence_reports_missing_candidate_field() -> None:
    legacy_results = _results()
    v1_results = [
        {
            "id": "fa_1",
            "status": "candidate_pass",
            "failure_bucket": None,
            "best_horizon": 5,
            "best_horizon_score": 0.12,
            "details": {"passed_rules": ["rankic"]},
            "metrics": {"coverage_mean": 0.93, "effective_trade_days": 20},
        }
    ]
    metrics, ic_series = _frames()
    diagnostics = _diagnostics()

    report = compare_equivalence(
        legacy_results=legacy_results,
        v1_results=v1_results,
        legacy_metrics=metrics,
        v1_metrics=metrics.copy(),
        legacy_ic_series=ic_series,
        v1_ic_series=ic_series.copy(),
        legacy_diagnostics=diagnostics,
        v1_diagnostics=diagnostics.copy(),
    )

    assert report.matches is False
    assert report.candidate_results.matches is False
    assert report.candidate_results.diffs[0].field == "signal_direction"
    assert report.candidate_results.diffs[0].reason == "missing_field"
