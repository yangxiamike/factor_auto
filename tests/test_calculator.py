from factor_autoresearch.calculator import ExpressionValidationError, FactorCalc
from factor_autoresearch.candidates import Candidate
from factor_autoresearch.data_loader import DataLoader


def _candidate(expression: str, lookback_days: int = 5) -> Candidate:
    return Candidate(
        candidate_id="fa_test",
        name="test",
        expression=expression,
        expected_direction="positive",
        hypothesis="test",
        category="momentum",
        lookback_days=lookback_days,
        created_at="2026-06-22",
        notes="test",
    )


def test_factor_calc_calculates_series(sample_dataset_dir, test_config) -> None:
    dataset = DataLoader(config=test_config, dataset_path=sample_dataset_dir).load()
    calc = FactorCalc(test_config)
    result = calc.calculate(_candidate("cs_rank((close_hfq - open_hfq) / open_hfq)", 1), dataset)
    assert result.notna().sum() > 0
    assert result.name == "fa_test"


def test_factor_calc_uses_bound_config_for_validation(test_config) -> None:
    calc = FactorCalc(test_config)
    candidate = _candidate("ts_mean(close_hfq, 5)", 5)
    metadata = calc.validate_candidate(candidate)
    assert metadata.inferred_lookback == 5
    assert calc.complexity_score(candidate) == 3


def test_factor_calc_rejects_python(sample_dataset_dir, test_config) -> None:
    dataset = DataLoader(config=test_config, dataset_path=sample_dataset_dir).load()
    calc = FactorCalc(test_config)
    try:
        calc.calculate(_candidate("__import__('os').system('dir')", 1), dataset)
    except ExpressionValidationError:
        return
    raise AssertionError("expected ExpressionValidationError")
