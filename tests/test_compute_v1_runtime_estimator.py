from factor_autoresearch.compute_v1.runtime_estimator import (
    RuntimeEstimate,
    estimate_mining_runtime,
)


def test_estimate_mining_runtime_scales_candidate_and_year_count() -> None:
    estimate = estimate_mining_runtime(
        baseline_seconds=54.654126,
        baseline_trade_days=485,
        baseline_candidates=30,
        target_years=10,
        target_candidates=30,
    )

    assert isinstance(estimate, RuntimeEstimate)
    assert estimate.projected_seconds == 283.976077
    assert estimate.projected_minutes == 4.733
    assert estimate.classification == "strong_green"
    assert estimate.should_trigger_optimization_loop is False


def test_estimate_mining_runtime_accounts_for_oos_and_walk_forward() -> None:
    estimate = estimate_mining_runtime(
        baseline_seconds=54.654126,
        baseline_trade_days=485,
        baseline_candidates=30,
        target_years=10,
        target_candidates=30,
        oos_multiplier=1.3,
        walk_forward_windows=3,
    )

    assert estimate.projected_seconds == 1107.506702
    assert estimate.projected_minutes == 18.458
    assert estimate.classification == "yellow"
    assert estimate.should_trigger_optimization_loop is True


def test_estimate_mining_runtime_rejects_invalid_inputs() -> None:
    for kwargs in (
        {"baseline_seconds": 0},
        {"baseline_trade_days": 0},
        {"baseline_candidates": 0},
        {"target_years": 0},
        {"target_candidates": 0},
        {"oos_multiplier": 0},
        {"walk_forward_windows": 0},
    ):
        base = {
            "baseline_seconds": 54.654126,
            "baseline_trade_days": 485,
            "baseline_candidates": 30,
            "target_years": 10,
            "target_candidates": 30,
        }
        base.update(kwargs)
        try:
            estimate_mining_runtime(**base)
        except ValueError as exc:
            assert "must be positive" in str(exc)
        else:
            raise AssertionError("expected ValueError")

